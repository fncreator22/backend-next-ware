import logging
import jwt
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.modules.auth.utils import decode_token
from src.modules.auth.repository import UserRepository
from src.middleware.exceptions import AuthException, PermissionException

logger = logging.getLogger("wareops_erp.modules.auth.dependencies")

# Instantiate HTTPBearer security scheme to leverage standard Authorization Bearer header
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    repository: UserRepository = Depends()
) -> dict:
    """Verify standard access token JWT and return user profile details."""
    if not credentials:
        raise AuthException("Authentication header token is missing or malformed.")
        
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthException("Session access token has expired. Please refresh your session.")
    except jwt.InvalidTokenError:
        raise AuthException("Invalid authentication credentials.")

    if payload.get("type") != "access":
        raise AuthException("Invalid credentials token type context.")

    user_id = payload.get("user_id")
    if not user_id:
        raise AuthException("Credentials payload is malformed.")

    user = await repository.find_by_id(user_id)
    if not user:
        raise AuthException("Associated user profile not found.")

    if user.get("status", "active") != "active":
        raise AuthException("User profile has been deactivated.")

    return user


class RequireRole:
    """Class-based dependency guard to restrict endpoints by role membership."""
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role")
        if user_role not in self.allowed_roles:
            logger.warning(f"Role constraint violation: user '{current_user['_id']}' with role '{user_role}' tried to access role boundary: {self.allowed_roles}")
            raise PermissionException("You are not authorized to access this resource.")
        return current_user
