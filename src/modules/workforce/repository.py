import logging
from datetime import datetime
from bson import ObjectId
from fastapi import Depends
from src.database import get_db

logger = logging.getLogger("wareops_erp.modules.workforce.repository")


class WorkforceRepository:
    def __init__(self, db=Depends(get_db)):
        self.db = db
        self.collection = db.users

    async def find_by_id(self, member_id: str) -> dict:
        """Fetch a specific workforce member by their unique ID."""
        return await self.collection.find_one({"_id": member_id})

    async def find_by_email(self, email: str) -> dict:
        """Query user document matching email address."""
        return await self.collection.find_one({"email": email.lower()})

    async def list_members_in_warehouses(
        self,
        tenant_id: str,
        warehouse_ids: list[str],
        role_limit: str = None
    ) -> list[dict]:
        """
        Query workforce members belonging to the target tenant, scoped to specific warehouses,
        and optionally filtered by role privilege bounds.
        """
        query = {
            "tenant_id": tenant_id,
            "warehouse_id": {"$in": warehouse_ids},
            "role": {"$ne": "super_admin"}  # Workforce excludes the platform Super Admin
        }

        # If a role limit is specified, we filter roles dynamically
        if role_limit:
            # We will handle role levels filtering inside the service layer
            pass

        cursor = self.collection.find(query)
        return await cursor.to_list(length=1000)

    async def list_all_tenant_members(self, tenant_id: str, exclude_user_id: str) -> list[dict]:
        """Fetch all workforce users inside a tenant space, excluding the caller."""
        cursor = self.collection.find({
            "tenant_id": tenant_id,
            "_id": {"$ne": exclude_user_id}
        })
        return await cursor.to_list(length=1000)

    async def create_member(self, doc: dict) -> dict:
        """Register a new workforce member. Assigns unique string ID."""
        if "_id" not in doc:
            doc["_id"] = "u" + str(ObjectId())
        doc["email"] = doc["email"].lower()
        
        logger.info(f"Registering new workforce user: {doc['_id']} ({doc['role']})")
        await self.collection.insert_one(doc)
        return doc

    async def update_member(self, member_id: str, update_fields: dict) -> dict:
        """Modify user status, role, or active warehouse assignments."""
        update_fields["updated_at"] = datetime.utcnow()
        logger.info(f"Modifying workforce user profile: {member_id}")
        await self.collection.update_one({"_id": member_id}, {"$set": update_fields})
        return await self.find_by_id(member_id)

    async def delete_member(self, member_id: str) -> None:
        """Remove user profile from database."""
        logger.info(f"Deleting workforce user: {member_id}")
        await self.collection.delete_one({"_id": member_id})
