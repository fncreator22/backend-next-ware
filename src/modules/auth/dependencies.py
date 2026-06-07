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


from src.database import get_db

DEFAULT_ROLE_PERMISSIONS = {
  "super_admin": {
    "dashboard":      {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":True,  "manage":True  },
    "inventory":      {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":True,  "manage":True  },
    "warehouses":     {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":True,  "manage":True  },
    "workforce":      {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":True,  "manage":True  },
    "billing":        {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":True,  "manage":True  },
    "crm":            {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":True,  "manage":True  },
    "tables":         {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":True,  "manage":True  },
    "reports":        {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":True,  "manage":True  },
    "notifications":  {"view":True,  "create":False, "edit":False, "delete":True,  "export":False, "import":False, "manage":True  },
    "audit":          {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":True,  "manage":True  },
    "settings":       {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":True,  "manage":True  },
    "registration":   {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":True,  "manage":True  },
  },
  "admin": {
    "dashboard":      {"view":True,  "create":False, "edit":False, "delete":False, "export":True,  "import":False, "manage":False },
    "inventory":      {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":True,  "manage":True  },
    "warehouses":     {"view":True,  "create":False, "edit":True,  "delete":False, "export":True,  "import":False, "manage":False },
    "workforce":      {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":False, "manage":True  },
    "billing":        {"view":True,  "create":True,  "edit":True,  "delete":False, "export":True,  "import":False, "manage":False },
    "crm":            {"view":True,  "create":True,  "edit":True,  "delete":False, "export":True,  "import":False, "manage":False },
    "tables":         {"view":True,  "create":True,  "edit":True,  "delete":True,  "export":True,  "import":True,  "manage":True  },
    "reports":        {"view":True,  "create":False, "edit":False, "delete":False, "export":True,  "import":False, "manage":False },
    "notifications":  {"view":True,  "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "audit":          {"view":True,  "create":False, "edit":False, "delete":False, "export":True,  "import":False, "manage":False },
    "settings":       {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "registration":   {"view":True,  "create":True,  "edit":True,  "delete":False, "export":True,  "import":False, "manage":True  },
  },
  "manager": {
    "dashboard":      {"view":True,  "create":False, "edit":False, "delete":False, "export":True,  "import":False, "manage":False },
    "inventory":      {"view":True,  "create":True,  "edit":True,  "delete":False, "export":True,  "import":True,  "manage":False },
    "warehouses":     {"view":True,  "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "workforce":      {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "billing":        {"view":True,  "create":True,  "edit":True,  "delete":False, "export":True,  "import":False, "manage":False },
    "crm":            {"view":True,  "create":False, "edit":True,  "delete":False, "export":True,  "import":False, "manage":False },
    "tables":         {"view":True,  "create":True,  "edit":True,  "delete":False, "export":True,  "import":True,  "manage":False },
    "reports":        {"view":True,  "create":False, "edit":False, "delete":False, "export":True,  "import":False, "manage":False },
    "notifications":  {"view":True,  "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "audit":          {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "settings":       {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "registration":   {"view":True,  "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
  },
  "staff": {
    "dashboard":      {"view":True,  "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "inventory":      {"view":True,  "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "warehouses":     {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "workforce":      {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "billing":        {"view":True,  "create":True,  "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "crm":            {"view":True,  "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "tables":         {"view":True,  "create":False, "edit":True,  "delete":False, "export":False, "import":False, "manage":False },
    "reports":        {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "notifications":  {"view":True,  "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "audit":          {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "settings":       {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "registration":   {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
  },
  "employee": {
    "dashboard":      {"view":True,  "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "inventory":      {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "warehouses":     {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "workforce":      {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "billing":        {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "crm":            {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "tables":         {"view":True,  "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "reports":        {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "notifications":  {"view":True,  "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "audit":          {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "settings":       {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
    "registration":   {"view":False, "create":False, "edit":False, "delete":False, "export":False, "import":False, "manage":False },
  }
}

async def check_user_permission(user: dict, module: str, action: str, db) -> bool:
    role_key = user.get("role", "employee")
    if role_key == "super_admin":
        return True
    
    permissions = {}
    if role_key in DEFAULT_ROLE_PERMISSIONS:
        import copy
        permissions = copy.deepcopy(DEFAULT_ROLE_PERMISSIONS[role_key])
    else:
        # Custom role lookup in roles collection
        custom_role = await db.roles.find_one({"_id": role_key, "tenant_id": user.get("tenant_id")})
        if custom_role and "permissions" in custom_role:
            permissions = custom_role["permissions"]
            
    # Apply user overrides
    user_overrides = user.get("permission_overrides") or user.get("permissionOverrides") or {}
    if user_overrides:
        for m_key, actions in user_overrides.items():
            if m_key not in permissions:
                permissions[m_key] = {}
            for a_key, val in actions.items():
                permissions[m_key][a_key] = val
                
    val = permissions.get(module, {}).get(action, False)
    return bool(val)

class RequirePermission:
    """Class-based dependency guard to restrict endpoints by modular permissions."""
    def __init__(self, module: str, action: str):
        self.module = module
        self.action = action

    async def __call__(
        self, 
        current_user: dict = Depends(get_current_user),
        db = Depends(get_db)
    ) -> dict:
        has_perm = await check_user_permission(current_user, self.module, self.action, db)
        if not has_perm:
            raise PermissionException(f"You do not have permission to {self.action} in {self.module}.")
        return current_user
