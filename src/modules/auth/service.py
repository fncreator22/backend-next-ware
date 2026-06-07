import logging
from datetime import datetime, timedelta
import jwt
from bson import ObjectId
from fastapi import Depends
from src.modules.auth.repository import UserRepository
from src.modules.auth.schema import UserSignup, UserLogin, ChangePassword, ForgotPassword, ResetPassword
from src.modules.auth.utils import hash_password, verify_password, create_access_token, create_refresh_token, decode_token, create_access_token as create_reset_token
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
        import math
        user = await self.repository.find_by_email(payload.email)
        if not user:
            raise AuthException("Invalid email or password.")

        # Check account lockout status
        lockout_until = user.get("lockout_until")
        if lockout_until:
            if isinstance(lockout_until, str):
                try:
                    lockout_until = datetime.fromisoformat(lockout_until)
                except ValueError:
                    pass
            if lockout_until > datetime.utcnow():
                diff_sec = int((lockout_until - datetime.utcnow()).total_seconds())
                diff_min = math.ceil(diff_sec / 60)
                raise AuthException(f"Account is temporarily locked. Please try again in {diff_min} minutes.")

        if not verify_password(user["hashed_password"], payload.password):
            # Increment failed attempts count
            attempts = user.get("failed_login_attempts", 0) + 1
            update_fields = {"failed_login_attempts": attempts}
            if attempts >= 5:
                update_fields["lockout_until"] = datetime.utcnow() + timedelta(minutes=15)
                await self.repository.update_user(user["_id"], update_fields)
                raise AuthException("Too many failed login attempts. Account locked for 15 minutes.")
            else:
                await self.repository.update_user(user["_id"], update_fields)
                raise AuthException("Invalid email or password.")

        if user.get("status", "active") != "active":
            raise AuthException("User account is inactive. Please contact your system administrator.")

        # Reset failed attempts and lockout upon successful authentication
        if user.get("failed_login_attempts", 0) > 0 or user.get("lockout_until") is not None:
            await self.repository.update_user(user["_id"], {
                "failed_login_attempts": 0,
                "lockout_until": None
            })

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

    async def change_password(self, current_user: dict, payload: ChangePassword) -> None:
        """Modify logged-in user's password securely, revoking existing sessions."""
        if not verify_password(current_user["hashed_password"], payload.old_password):
            raise AuthException("Incorrect old password.")

        hashed_pw = hash_password(payload.new_password)
        user_id = current_user["_id"]
        
        await self.repository.update_user(user_id, {"hashed_password": hashed_pw})
        await self.repository.revoke_all_user_sessions(user_id)

        # Log password change event
        await self.audit.log_event(
            user_id=str(user_id),
            user_name=current_user["name"],
            action="password_change",
            description="User changed account password successfully.",
            tenant_id=current_user["tenant_id"],
            warehouse_id=current_user.get("warehouse_id")
        )

    async def forgot_password(self, payload: ForgotPassword) -> str:
        """Generate a short-lived password reset token for valid email addresses."""
        user = await self.repository.find_by_email(payload.email)
        if not user:
            # Return a dummy string/mock success to prevent email enumeration
            logger.warning(f"Forgot password requested for non-existent email: '{payload.email}'")
            return "mock-token"

        # Generate a 15-minute reset token containing user ID
        token_id = str(ObjectId())
        claims = {
            "user_id": user["_id"],
            "type": "reset",
            "jti": token_id,
            "exp": datetime.utcnow() + timedelta(minutes=15)
        }
        reset_token = create_reset_token(claims)
        
        logger.info(f"Password reset token generated for user: '{user['_id']}'")
        
        # Log forgot password request
        await self.audit.log_event(
            user_id=str(user["_id"]),
            user_name=user["name"],
            action="forgot_password_request",
            description="Password reset token requested.",
            tenant_id=user["tenant_id"],
            warehouse_id=user.get("warehouse_id")
        )
        return reset_token

    async def reset_password(self, payload: ResetPassword) -> None:
        """Decode reset token and update user's password securely."""
        try:
            claims = decode_token(payload.token)
        except jwt.ExpiredSignatureError:
            raise AuthException("Password reset link has expired.")
        except jwt.InvalidTokenError:
            raise AuthException("Invalid password reset link.")

        if claims.get("type") != "reset":
            raise AuthException("Invalid password reset token type.")

        user_id = claims.get("user_id")
        if not user_id:
            raise AuthException("Invalid token payload structure.")

        user = await self.repository.find_by_id(user_id)
        if not user or user.get("status") != "active":
            raise AuthException("User profile is inactive or not found.")

        hashed_pw = hash_password(payload.new_password)
        await self.repository.update_user(user_id, {
            "hashed_password": hashed_pw,
            "failed_login_attempts": 0,
            "lockout_until": None
        })
        await self.repository.revoke_all_user_sessions(user_id)

        # Log password reset
        await self.audit.log_event(
            user_id=str(user_id),
            user_name=user["name"],
            action="password_reset",
            description="User password reset completed successfully.",
            tenant_id=user["tenant_id"],
            warehouse_id=user.get("warehouse_id")
        )
