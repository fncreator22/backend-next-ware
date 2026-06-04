import logging
from datetime import datetime, timedelta
import jwt
from bson import ObjectId
from fastapi import Depends
from src.modules.auth.repository import UserRepository
from src.modules.auth.schema import UserSignup, UserLogin
from src.modules.auth.utils import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from src.middleware.exceptions import AuthException, ValidationException
from src.modules.audit_logs.service import AuditLogService
from src.utils.email import send_registration_email

logger = logging.getLogger("wareops_erp.modules.auth.service")


class AuthService:
    def __init__(self, repository: UserRepository = Depends(), audit: AuditLogService = Depends()):
        self.repository = repository
        self.audit = audit

    async def register_tenant(self, payload: UserSignup) -> dict:
        """Register a new Super Admin tenant and set up initial profile."""
        existing = await self.repository.find_by_email(payload.email)
        if existing:
            raise ValidationException("Email already registered.")

        # Hash password securely using Argon2id
        hashed_pw = hash_password(payload.password)
        
        # Generate tenant ID & initials avatar
        tenant_id = "t" + str(ObjectId())
        name_parts = payload.name.split()
        avatar = "".join([n[0] for n in name_parts]).upper()[:2] if name_parts else "US"

        user_doc = {
            "name": payload.name,
            "email": payload.email.lower(),
            "hashed_password": hashed_pw,
            "role": "super_admin",
            "warehouse_id": None,
            "tenant_id": tenant_id,
            "avatar": avatar,
            "status": "active",
            "created_at": datetime.utcnow()
        }

        created_user = await self.repository.create_user(user_doc)
        logger.info(f"Successfully registered Super Admin user: {created_user['_id']} with tenant ID: {tenant_id}")
        
        # Log signup audit trail
        await self.audit.log_event(
            user_id=str(created_user["_id"]),
            user_name=created_user["name"],
            action="signup",
            description=f"Signed up new user account: {created_user['email']} (Super Admin)",
            tenant_id=tenant_id
        )

        # Trigger Super Admin registration email in the background
        try:
            import asyncio
            asyncio.create_task(send_registration_email(
                recipient_email=created_user["email"],
                recipient_name=created_user["name"]
            ))
        except Exception as e:
            logger.error(f"Failed to queue registration welcome email: {e}")

        return {
            "id": created_user["_id"],
            "name": created_user["name"],
            "email": created_user["email"],
            "role": created_user["role"],
            "warehouse_id": created_user["warehouse_id"],
            "tenant_id": created_user["tenant_id"],
            "avatar": created_user["avatar"],
            "status": created_user["status"]
        }

    async def authenticate_user(self, payload: UserLogin) -> dict:
        """Verify credentials and return access and stateful refresh tokens."""
        user = await self.repository.find_by_email(payload.email)
        if not user:
            raise AuthException("Invalid email or password.")

        if not verify_password(user["hashed_password"], payload.password):
            raise AuthException("Invalid email or password.")

        if user.get("status", "active") != "active":
            raise AuthException("User account is inactive. Please contact your system administrator.")

        logger.info(f"User authenticated successfully: {user['_id']}")
        return user

    async def create_session_tokens(self, user: dict) -> dict:
        """Generate and register a new access/refresh token pair for active session."""
        token_id = str(ObjectId())
        
        # Claims payloads
        claims = {
            "user_id": user["_id"],
            "role": user["role"],
            "warehouse_id": user.get("warehouse_id"),
            "tenant_id": user["tenant_id"],
            "jti": token_id
        }

        access_token = create_access_token(claims)
        refresh_token = create_refresh_token(claims)

        # Record session expiry in DB for stateful tracking
        # Refresh token is 7 days, Access token is 15 minutes
        expires_at = datetime.utcnow() + timedelta(days=7)
        await self.repository.add_session(user["_id"], token_id, expires_at)

        # Log login audit trail
        await self.audit.log_event(
            user_id=str(user["_id"]),
            user_name=user["name"],
            action="login",
            description=f"User logged in successfully: {user['email']}",
            tenant_id=user["tenant_id"],
            warehouse_id=user.get("warehouse_id")
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user["_id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "warehouse_id": user.get("warehouse_id"),
                "tenant_id": user["tenant_id"],
                "avatar": user["avatar"],
                "status": user["status"],
                "permissionOverrides": user.get("permission_overrides"),
                "tableOverrides": user.get("table_overrides"),
                "warehouseOverrides": user.get("warehouse_overrides"),
                "moduleOverrides": user.get("module_overrides"),
                "employeeId": user.get("employee_id") or user.get("enterprise_id")
            }
        }

    async def rotate_session_tokens(self, refresh_token: str) -> dict:
        """Validate long-lived refresh token and return new rotated token pair."""
        try:
            payload = decode_token(refresh_token)
        except jwt.ExpiredSignatureError:
            raise AuthException("Session has expired. Please sign in again.")
        except jwt.InvalidTokenError:
            raise AuthException("Invalid session credentials.")

        if payload.get("type") != "refresh":
            raise AuthException("Invalid credentials token type.")

        jti = payload.get("jti")
        user_id = payload.get("user_id")
        
        if not jti or not user_id:
            raise AuthException("Invalid credentials structure.")

        # Stateful verification inside MongoDB sessions blacklist
        session = await self.repository.get_session(jti)
        if not session or session.get("is_revoked", False):
            # Invalidate all active sessions for this user (potential compromise replay defense)
            await self.repository.revoke_all_user_sessions(user_id)
            raise AuthException("Session has been terminated or replayed.")

        # Invalidate old refresh token session
        await self.repository.revoke_session(jti)

        user = await self.repository.find_by_id(user_id)
        if not user or user.get("status") != "active":
            raise AuthException("Associated user account is inactive or not found.")

        # Generate new rotated token pair
        logger.info(f"Rotating active session tokens for user: {user_id}")
        return await self.create_session_tokens(user)

    async def terminate_session(self, refresh_token: str) -> None:
        """Revoke the current active session in the database."""
        try:
            payload = decode_token(refresh_token)
            jti = payload.get("jti")
            if jti:
                await self.repository.revoke_session(jti)
                
                # Log logout audit trail
                user_id = payload.get("user_id")
                if user_id:
                    user = await self.repository.find_by_id(user_id)
                    if user:
                        await self.audit.log_event(
                            user_id=str(user["_id"]),
                            user_name=user["name"],
                            action="logout",
                            description=f"User logged out successfully: {user['email']}",
                            tenant_id=user["tenant_id"],
                            warehouse_id=user.get("warehouse_id")
                        )
        except Exception as e:
            # Silent fallback since logout should not crash the frontend
            logger.warning(f"Failed to log logout event: {e}")
            pass
