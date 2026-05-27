import logging
from datetime import datetime
from bson import ObjectId
from fastapi import Depends
from src.modules.workforce.repository import WorkforceRepository
from src.modules.workforce.schema import UserCreate, UserUpdate
from src.modules.auth.utils import hash_password
from src.middleware.exceptions import PermissionException, NotFoundException, ValidationException
from src.database import get_db
from src.utils.email import send_invitation_email

logger = logging.getLogger("wareops_erp.modules.workforce.service")

# Privilege representation mapping
ROLE_LEVELS = {
    "employee": 1,
    "staff": 2,
    "manager": 3,
    "admin": 4,
    "super_admin": 5
}


class WorkforceService:
    def __init__(self, repository: WorkforceRepository = Depends(), db=Depends(get_db)):
        self.repository = repository
        self.db = db

    async def list_workforce(self, current_user: dict) -> list[dict]:
        """Fetch workforce members scoped to tenant, warehouse access, and role hierarchy bounds."""
        tenant_id = current_user["tenant_id"]
        role = current_user["role"]
        my_id = current_user.get("_id") or current_user.get("id")

        if role == "super_admin":
            # Super Admin sees all workforce members in their tenant space (excludes self)
            return await self.repository.list_all_tenant_members(tenant_id, exclude_user_id=my_id)
        
        # Other roles are strictly restricted to their assigned warehouse
        wh_id = current_user.get("warehouse_id")
        if not wh_id:
            return []

        raw_members = await self.repository.list_members_in_warehouses(tenant_id, [wh_id])
        my_level = ROLE_LEVELS.get(role, 1)

        # Scoping filter: Can view users with a role level LESS than or EQUAL to caller's level
        filtered = [
            m for m in raw_members
            if m["_id"] != my_id and m.get("id") != my_id and ROLE_LEVELS.get(m.get("role", "employee"), 1) <= my_level
        ]
        return filtered

    async def create_workforce_member(self, payload: UserCreate, current_user: dict) -> dict:
        """Register a new workforce member, validating role hierarchy limits and warehouse bounds."""
        role = current_user["role"]
        my_level = ROLE_LEVELS.get(role, 1)
        target_level = ROLE_LEVELS.get(payload.role, 1)
        user_id = current_user.get("_id") or current_user.get("id")

        # 1. Scoping Privilege Checks
        if role not in ["super_admin", "admin"]:
            raise PermissionException("Unauthorized: Only Super Admins and Admins can register new workforce members.")

        if role != "super_admin":
            # Cannot create users with higher or peer roles
            if target_level >= my_level:
                raise PermissionException("Unauthorized: Cannot assign a role level higher than or equal to your own.")
            
            # Must assign to the same warehouse
            if payload.warehouse_id != current_user["warehouse_id"]:
                raise PermissionException("Unauthorized: Cannot assign workforce member to another warehouse.")

        # 2. Email Uniqueness Check
        existing = await self.repository.find_by_email(payload.email)
        if existing:
            raise ValidationException("Email already exists.")

        # 3. Create document fields
        hashed_pw = hash_password(payload.password)
        name_parts = payload.name.split()
        avatar = "".join([n[0] for n in name_parts]).upper()[:2] if name_parts else "US"

        member_doc = {
            "tenant_id": current_user["tenant_id"],
            "name": payload.name,
            "email": payload.email.lower(),
            "hashed_password": hashed_pw,
            "role": payload.role,
            "warehouse_id": payload.warehouse_id,
            "avatar": avatar,
            "status": "active",
            "assignedBy": user_id,
            "assignedAt": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }

        created = await self.repository.create_member(member_doc)

        # Retrieve warehouse details for rich email invitation text
        try:
            wh = await self.db.warehouses.find_one({"_id": payload.warehouse_id})
            company_name = wh.get("businessName") if wh else "NexWare ERP Enterprise"
            wh_name = wh.get("name") if wh else "North Hub"
        except Exception:
            company_name = "NexWare ERP Enterprise"
            wh_name = "North Hub"

        # Trigger workforce registration invitation email in the background
        try:
            import asyncio
            asyncio.create_task(send_invitation_email(
                recipient_email=payload.email,
                recipient_name=payload.name,
                company_name=company_name,
                role=payload.role,
                temp_password=payload.password,
                warehouse_name=wh_name
            ))
        except Exception as e:
            logger.error(f"Failed to queue workforce invitation email: {e}")

        # 4. Log audit trail
        await self.db.audit_logs.insert_one({
            "action": "user_create",
            "description": f"User created: '{payload.name}' ({payload.role})",
            "userId": user_id,
            "userName": current_user["name"],
            "warehouseId": payload.warehouse_id,
            "timestamp": datetime.utcnow()
        })

        # Trigger real-time broadcast fallback for standalone server configurations
        try:
            from src.modules.realtime import ws_manager, normalize_doc
            import asyncio
            asyncio.create_task(ws_manager.broadcast_event(
                tenant_id=current_user["tenant_id"],
                event_type="workforce_activity",
                data=normalize_doc(created),
                warehouse_id=payload.warehouse_id
            ))
        except Exception as e:
            logger.debug(f"Manual WebSocket broadcast failed for workforce creation: {e}")

        return created

    async def update_workforce_member(self, member_id: str, payload: UserUpdate, current_user: dict) -> dict:
        """Modify user credentials, status, or role levels checking hierarchy rules."""
        role = current_user["role"]
        my_level = ROLE_LEVELS.get(role, 1)
        tenant_id = current_user["tenant_id"]
        user_id = current_user.get("_id") or current_user.get("id")

        target = await self.repository.find_by_id(member_id)
        if not target:
            raise NotFoundException("Workforce member not found.")

        target_level = ROLE_LEVELS.get(target["role"], 1)
        target_id = target.get("_id") or target.get("id")

        # 1. Scoping updates by privilege levels
        if role != "super_admin":
            if user_id == target_id:
                # Can edit self, but cannot escalate own privileges or change own warehouse
                if payload.role and ROLE_LEVELS.get(payload.role, 1) > my_level:
                    raise PermissionException("Unauthorized: Cannot escalate your own role level.")
                if payload.warehouse_id and payload.warehouse_id != current_user["warehouse_id"]:
                    raise PermissionException("Unauthorized: Cannot reassign your own warehouse.")
            else:
                # Cannot modify superiors or peers
                if target_level >= my_level:
                    raise PermissionException("Unauthorized: Cannot update superiors or peers.")
                
                # Cannot escalate target's role to own or superior levels
                if payload.role and ROLE_LEVELS.get(payload.role, 1) >= my_level:
                    raise PermissionException("Unauthorized: Cannot assign a role level higher than or equal to your own.")
                
                # Targets must belong to the caller's warehouse
                if target.get("warehouse_id") != current_user["warehouse_id"]:
                    raise PermissionException("Unauthorized: Target member belongs to another warehouse.")
                
                # Cannot move workforce members to another warehouse
                if payload.warehouse_id and payload.warehouse_id != current_user["warehouse_id"]:
                    raise PermissionException("Unauthorized: Cannot reassign workforce member to another warehouse.")

        # 2. Compile updates
        update_data = payload.dict(exclude_unset=True)
        if not update_data:
            return target

        updated = await self.repository.update_member(member_id, update_data)

        # 3. Log audit trail
        await self.db.audit_logs.insert_one({
            "action": "user_update",
            "description": f"User profile updated: '{target['name']}' details modified.",
            "userId": user_id,
            "userName": current_user["name"],
            "warehouseId": target.get("warehouse_id"),
            "timestamp": datetime.utcnow()
        })

        # Trigger real-time broadcast fallback for standalone server configurations
        try:
            from src.modules.realtime import ws_manager, normalize_doc
            import asyncio
            asyncio.create_task(ws_manager.broadcast_event(
                tenant_id=tenant_id,
                event_type="workforce_activity",
                data=normalize_doc(updated),
                warehouse_id=target.get("warehouse_id")
            ))
        except Exception as e:
            logger.debug(f"Manual WebSocket broadcast failed for workforce update: {e}")

        return updated

    async def delete_workforce_member(self, member_id: str, current_user: dict) -> None:
        """De-register and remove a workforce member asserting hierarchy bounds."""
        role = current_user["role"]
        my_level = ROLE_LEVELS.get(role, 1)
        tenant_id = current_user["tenant_id"]
        user_id = current_user.get("_id") or current_user.get("id")

        target = await self.repository.find_by_id(member_id)
        if not target:
            raise NotFoundException("Workforce member not found.")

        target_level = ROLE_LEVELS.get(target["role"], 1)

        # 1. Scoping deletions checks
        if role != "super_admin":
            # Cannot delete superiors or peers
            if target_level >= my_level:
                raise PermissionException("Unauthorized: Cannot remove superiors or peers.")
            
            # Must be in same warehouse
            if target.get("warehouse_id") != current_user["warehouse_id"]:
                raise PermissionException("Unauthorized: Target belongs to another warehouse.")

        # 2. Execute deletion
        await self.repository.delete_member(member_id)

        # 3. Log audit trail
        await self.db.audit_logs.insert_one({
            "action": "user_delete",
            "description": f"User deleted: '{target['name']}' removed from platform.",
            "userId": user_id,
            "userName": current_user["name"],
            "warehouseId": target.get("warehouse_id"),
            "timestamp": datetime.utcnow()
        })

        # Trigger real-time broadcast fallback for standalone server configurations
        try:
            from src.modules.realtime import ws_manager
            import asyncio
            asyncio.create_task(ws_manager.broadcast_event(
                tenant_id=tenant_id,
                event_type="workforce_activity",
                data={"id": member_id, "_id": member_id, "action": "delete"},
                warehouse_id=target.get("warehouse_id")
            ))
        except Exception as e:
            logger.debug(f"Manual WebSocket broadcast failed for workforce deletion: {e}")
