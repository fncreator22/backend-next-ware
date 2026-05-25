import logging
from datetime import datetime
from bson import ObjectId
from fastapi import Depends
from src.database import get_db

logger = logging.getLogger("wareops_erp.modules.warehouses.repository")


class WarehouseRepository:
    def __init__(self, db=Depends(get_db)):
        self.db = db
        self.collection = db.warehouses

    async def find_by_id(self, warehouse_id: str) -> dict:
        """Find a warehouse by its unique ID."""
        return await self.collection.find_one({"_id": warehouse_id})

    async def find_by_id_and_tenant(self, warehouse_id: str, tenant_id: str) -> dict:
        """Find a warehouse by ID and ensure it belongs to the target tenant."""
        return await self.collection.find_one({"_id": warehouse_id, "tenant_id": tenant_id})

    async def find_all_by_tenant(self, tenant_id: str) -> list[dict]:
        """Fetch all warehouses associated with the tenant."""
        cursor = self.collection.find({"tenant_id": tenant_id})
        return await cursor.to_list(length=1000)

    async def create_warehouse(self, doc: dict) -> dict:
        """Create a new warehouse registry. Assigns 'wh' prefixed unique ID string."""
        if "_id" not in doc:
            doc["_id"] = "wh" + str(ObjectId())
        
        logger.info(f"Creating new warehouse: {doc['_id']} under tenant: {doc['tenant_id']}")
        await self.collection.insert_one(doc)
        return doc

    async def update_warehouse(self, warehouse_id: str, update_fields: dict) -> dict:
        """Update warehouse profile details and save updated_at timestamp."""
        update_fields["updated_at"] = datetime.utcnow()
        logger.info(f"Updating warehouse: {warehouse_id}")
        await self.collection.update_one({"_id": warehouse_id}, {"$set": update_fields})
        return await self.find_by_id(warehouse_id)

    async def delete_warehouse(self, warehouse_id: str) -> None:
        """Directly remove the warehouse record from warehouses collection."""
        logger.info(f"Deleting warehouse: {warehouse_id} from registries")
        await self.collection.delete_one({"_id": warehouse_id})
