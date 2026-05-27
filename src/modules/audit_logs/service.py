import logging
import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import Depends
from src.modules.audit_logs.repository import AuditLogRepository

logger = logging.getLogger("wareops_erp.modules.audit_logs.service")


class AuditLogService:
    def __init__(self, repository: AuditLogRepository = Depends()):
        self.repo = repository

    async def log_event(
        self,
        user_id: str,
        user_name: str,
        action: str,
        description: str,
        tenant_id: str,
        warehouse_id: Optional[str] = None
    ) -> dict:
        """Create and write a new immutable audit log document."""
        doc = {
            "user_id": user_id,
            "user_name": user_name,
            "action": action,
            "description": description,
            "warehouse_id": warehouse_id,
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow()
        }
        log = await self.repo.create_log(doc)
        
        # Trigger real-time broadcast fallback for standalone server configurations
        try:
            from src.modules.realtime import ws_manager, normalize_doc
            asyncio.create_task(ws_manager.broadcast_event(
                tenant_id=tenant_id,
                event_type="audit_event",
                data=normalize_doc(log),
                warehouse_id=warehouse_id
            ))
        except Exception as e:
            logger.debug(f"Manual WebSocket broadcast failed for audit log: {e}")
            
        return log

    async def list_logs(self, current_user: dict, warehouse_filter: Optional[str] = None) -> List[dict]:
        """Fetch audit log history matching tenant scoping and strict hierarchical role permissions."""
        tenant_id = current_user["tenant_id"]
        role = current_user.get("role")
        user_id = str(current_user.get("_id") or current_user.get("id", ""))

        # Base query scopes per tenant
        query = {"tenant_id": tenant_id}

        if role == "super_admin":
            # Super Admin can see all logs under tenant
            if warehouse_filter:
                query["warehouse_id"] = warehouse_filter
        else:
            # Other roles are locked into their assigned warehouse location
            warehouse_id = current_user.get("warehouse_id")
            query["warehouse_id"] = warehouse_id

            # Enforce dynamic upward role scoping reflection (Manager sees Staff, Employee sees only Employee/Self)
            levels = {"employee": 1, "staff": 2, "manager": 3, "admin": 4, "super_admin": 5}
            caller_level = levels.get(role, 1)

            # Query all active users in the same warehouse
            users_cursor = self.repo.db.users.find({
                "warehouse_id": warehouse_id,
                "tenant_id": tenant_id
            })
            users = await users_cursor.to_list(length=1000)

            # Filter visible user IDs
            visible_user_ids = []
            for u in users:
                u_role = u.get("role", "employee")
                if levels.get(u_role, 1) <= caller_level:
                    visible_user_ids.append(str(u["_id"]))

            # Always include caller's own logs
            if user_id not in visible_user_ids:
                visible_user_ids.append(user_id)

            # Scope query by these visible user IDs
            query["user_id"] = {"$in": visible_user_ids}

        logs = await self.repo.list_logs(query)
        return logs
