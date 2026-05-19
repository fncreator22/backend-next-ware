class WorkforceService:
    def __init__(self):
        pass

    def can_assign_role(self, caller_role: str, target_role: str) -> bool:
        """Dynamic permission hierarchy assignments check."""
        role_levels = {
            "employee": 1,
            "staff": 2,
            "manager": 3,
            "admin": 4,
            "super_admin": 5
        }
        return role_levels.get(caller_role, 0) > role_levels.get(target_role, 0)
