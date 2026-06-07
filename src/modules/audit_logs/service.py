import logging
import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import Depends
from src.modules.audit_logs.repository import AuditLogRepository
from src.modules.auth.dependencies import check_user_permission
from src.middleware.exceptions import PermissionException

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
        warehouse_id: Optional[str] = None,
        session = None
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
        log = await self.repo.create_log(doc, session=session)
        
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

    async def list_logs(
        self,
        current_user: dict,
        warehouse_filter: Optional[str] = None,
        page: int = 1,
        limit: int = 100,
        search: Optional[str] = None,
        action: Optional[str] = None,
        scope: str = "enterprise"
    ) -> dict:
        """Fetch audit log history matching tenant scoping, pagination, and strict hierarchical role permissions."""
        import math
        tenant_id = current_user["tenant_id"]
        role = current_user.get("role")
        user_id = str(current_user.get("_id") or current_user.get("id", ""))
        warehouse_id = current_user.get("warehouse_id")

        # Base query scopes per tenant
        query = {"tenant_id": tenant_id}

        if scope == "personal":
            # Personal scope is available to all authenticated users and returns only their own logs
            query["user_id"] = user_id
        else:
            # Enterprise scope requires view permissions and is role-filtered
            if not await check_user_permission(current_user, "audit", "view", self.repo.db):
                raise PermissionException("Unauthorized: You do not have permission to view audit logs.")

            if role == "super_admin":
                # Super Admin can see all logs under tenant
                if warehouse_filter:
                    query["warehouse_id"] = warehouse_filter
            elif role == "admin":
                # Admin -> admin/manager/staff under the same warehouse
                if warehouse_id:
                    query["warehouse_id"] = warehouse_id
                visible_roles = ["admin", "manager", "staff"]
                users_cursor = self.repo.db.users.find({
                    "tenant_id": tenant_id,
                    "warehouse_id": warehouse_id,
                    "role": {"$in": visible_roles}
                })
                users = await users_cursor.to_list(length=1000)
                visible_user_ids = [str(u["_id"]) for u in users]
                if user_id not in visible_user_ids:
                    visible_user_ids.append(user_id)
                query["user_id"] = {"$in": visible_user_ids}
            elif role == "manager":
                # Manager -> manager/staff under the same warehouse
                if warehouse_id:
                    query["warehouse_id"] = warehouse_id
                visible_roles = ["manager", "staff"]
                users_cursor = self.repo.db.users.find({
                    "tenant_id": tenant_id,
                    "warehouse_id": warehouse_id,
                    "role": {"$in": visible_roles}
                })
                users = await users_cursor.to_list(length=1000)
                visible_user_ids = [str(u["_id"]) for u in users]
                if user_id not in visible_user_ids:
                    visible_user_ids.append(user_id)
                query["user_id"] = {"$in": visible_user_ids}
            else:
                # Staff & other roles -> own logs only
                if warehouse_id:
                    query["warehouse_id"] = warehouse_id
                query["user_id"] = user_id

        # Apply action filter
        if action:
            query["action"] = action

        # Apply search filter (description, user_name, or action)
        if search:
            query["$or"] = [
                {"description": {"$regex": search, "$options": "i"}},
                {"user_name": {"$regex": search, "$options": "i"}},
                {"action": {"$regex": search, "$options": "i"}}
            ]

        # Count total matching documents for pagination
        total = await self.repo.collection.count_documents(query)

        # Pagination offsets
        skip = (page - 1) * limit
        logs = await self.repo.list_logs(query, skip=skip, limit=limit)

        return {
            "logs": logs,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": math.ceil(total / limit) if limit > 0 else 1
        }
