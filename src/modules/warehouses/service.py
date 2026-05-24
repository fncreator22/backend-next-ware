import logging
from datetime import datetime
from bson import ObjectId
from fastapi import Depends
from src.modules.warehouses.repository import WarehouseRepository
from src.modules.warehouses.schema import WarehouseCreate, WarehouseUpdate
from src.middleware.exceptions import PermissionException, NotFoundException, ValidationException
from src.database import get_db

logger = logging.getLogger("wareops_erp.modules.warehouses.service")


class WarehouseService:
    def __init__(self, repository: WarehouseRepository = Depends(), db=Depends(get_db)):
        self.repository = repository
        self.db = db

    async def list_warehouses(self, current_user: dict) -> list[dict]:
        """List warehouses scoped dynamically based on active user privileges."""
        tenant_id = current_user["tenant_id"]
        role = current_user["role"]

        if role == "super_admin":
            # Super Admin views all warehouses in their tenant
            return await self.repository.find_all_by_tenant(tenant_id)
        else:
            # Other roles are strictly restricted to their assigned warehouse ID
            wh_id = current_user.get("warehouse_id")
            if not wh_id:
                return []
            wh = await self.repository.find_by_id_and_tenant(wh_id, tenant_id)
            return [wh] if wh else []

    async def get_warehouse_detail(self, warehouse_id: str, current_user: dict) -> dict:
        """Fetch individual warehouse details asserting tenant boundaries."""
        tenant_id = current_user["tenant_id"]
        role = current_user["role"]

        # Scope verification: Non-Super-Admins can only view their assigned warehouse
        if role != "super_admin" and current_user.get("warehouse_id") != warehouse_id:
            raise PermissionException("Unauthorized: You do not have access to this warehouse registry.")

        wh = await self.repository.find_by_id_and_tenant(warehouse_id, tenant_id)
        if not wh:
            raise NotFoundException("Warehouse registry not found.")
        return wh

    async def create_warehouse(self, payload: WarehouseCreate, current_user: dict) -> dict:
        """Create a new warehouse registry under the tenant's space."""
        if current_user["role"] != "super_admin":
            raise PermissionException("Unauthorized: Only Super Admins can register new warehouses.")

        # Determine tax config overrides based on preference
        tax_config = {"luxury": 15.0, "normal": 5.0}
        if payload.taxPreference == "none":
            tax_config = {"luxury": 0.0, "normal": 0.0}

        user_id = current_user.get("_id") or current_user.get("id")

        wh_doc = {
            "tenant_id": current_user["tenant_id"],
            "ownerId": user_id,
            "name": payload.name,
            "businessName": payload.businessName,
            "address": payload.address,
            "contact": payload.contact,
            "email": payload.email,
            "taxPreference": payload.taxPreference,
            "logo": payload.logo,
            "status": "active",
            "taxConfig": tax_config,
            "created_at": datetime.utcnow()
        }

        created = await self.repository.create_warehouse(wh_doc)
        
        # Append to audit logs dynamically
        await self.db.audit_logs.insert_one({
            "action": "warehouse_create",
            "description": f"Warehouse created: '{payload.name}'",
            "userId": user_id,
            "userName": current_user["name"],
            "warehouseId": created["_id"],
            "timestamp": datetime.utcnow()
        })

        return created

    async def update_warehouse(self, warehouse_id: str, payload: WarehouseUpdate, current_user: dict) -> dict:
        """Update warehouse profile details according to role boundaries."""
        role = current_user["role"]
        tenant_id = current_user["tenant_id"]
        user_id = current_user.get("_id") or current_user.get("id")

        # Super Admin can update any warehouse in their tenant. Admin can only update their own.
        if role != "super_admin" and (role != "admin" or current_user.get("warehouse_id") != warehouse_id):
            raise PermissionException("Unauthorized: You do not have permissions to modify this warehouse profile.")

        wh = await self.repository.find_by_id_and_tenant(warehouse_id, tenant_id)
        if not wh:
            raise NotFoundException("Warehouse registry not found.")

        # Collect fields to update
        update_data = payload.dict(exclude_unset=True)
        if not update_data:
            return wh

        updated = await self.repository.update_warehouse(warehouse_id, update_data)

        # Log audit operation
        await self.db.audit_logs.insert_one({
            "action": "warehouse_update",
            "description": f"Warehouse updated: '{wh['name']}' details modified.",
            "userId": user_id,
            "userName": current_user["name"],
            "warehouseId": warehouse_id,
            "timestamp": datetime.utcnow()
        })

        return updated

    async def _execute_cascade_deletes(self, warehouse_id: str, user_id: str, warehouse_name: str, session=None):
        """Execute all core deletions across collections sequentially."""
        # 1. Remove the warehouse itself
        await self.db.warehouses.delete_one({"_id": warehouse_id}, session=session)
        
        # 2. Cascade delete associated users (workforce)
        # Keep Super Admins (ownerId) un-deleted since they own the tenant space itself!
        await self.db.users.delete_many(
            {"warehouse_id": warehouse_id, "role": {"$ne": "super_admin"}}, 
            session=session
        )
        
        # 3. Cascade delete associated items (inventory)
        await self.db.inventory_items.delete_many({"warehouse_id": warehouse_id}, session=session)
        
        # 4. Cascade delete invoices (billing)
        await self.db.bills.delete_many({"warehouse_id": warehouse_id}, session=session)
        
        # 5. Cascade delete dynamic tables and rows
        cursor = self.db.table_schemas.find({"warehouse_id": warehouse_id}, session=session)
        tables = await cursor.to_list(length=1000)
        for tbl in tables:
            tbl_id = tbl["_id"]
            await self.db.table_rows.delete_many({"table_id": tbl_id}, session=session)
        await self.db.table_schemas.delete_many({"warehouse_id": warehouse_id}, session=session)

        # 6. Log audit event
        await self.db.audit_logs.insert_one({
            "action": "warehouse_delete",
            "description": f"Warehouse deleted (cascade): '{warehouse_name}'",
            "userId": user_id,
            "userName": "Super Admin",
            "warehouseId": None,
            "timestamp": datetime.utcnow()
        }, session=session)

    async def retire_warehouse_cascade(self, warehouse_id: str, current_user: dict) -> None:
        """Cascade retire warehouse and atomically delete all associated records inside an ACID transaction session."""
        if current_user["role"] != "super_admin":
            raise PermissionException("Unauthorized: Only Super Admins can remove warehouse registries.")

        tenant_id = current_user["tenant_id"]
        user_id = current_user.get("_id") or current_user.get("id")
        
        wh = await self.repository.find_by_id_and_tenant(warehouse_id, tenant_id)
        if not wh:
            raise NotFoundException("Warehouse registry not found.")

        # Check if database is configured as a replica set supporting transactions
        try:
            hello_res = await self.db.command("hello")
            is_replica_set = "setName" in hello_res
        except Exception:
            is_replica_set = False

        if is_replica_set:
            # Execute cascade operations inside an ACID transaction session
            client = self.db.client
            async with await client.start_session() as session:
                async with session.start_transaction():
                    try:
                        await self._execute_cascade_deletes(warehouse_id, user_id, wh["name"], session=session)
                        logger.info(f"Successfully completed transactional cascade deletion for warehouse: {warehouse_id}")
                    except Exception as e:
                        logger.error(f"Failed transactional cascade delete for {warehouse_id}: {e}")
                        raise ValidationException(f"Failed to delete warehouse: {e}")
        else:
            # Standalone fallback: execute sequential deletions without a transaction session
            logger.warning(f"MongoDB is running in Standalone mode. Executing sequential warehouse cascade deletion without ACID guarantees...")
            try:
                await self._execute_cascade_deletes(warehouse_id, user_id, wh["name"], session=None)
                logger.info(f"Successfully completed standalone cascade deletion for warehouse: {warehouse_id}")
            except Exception as e:
                logger.error(f"Failed standalone cascade delete for {warehouse_id}: {e}")
                raise ValidationException(f"Failed to delete warehouse sequentially: {e}")
