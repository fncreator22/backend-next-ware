import logging
from datetime import datetime
from bson import ObjectId
from fastapi import Depends
from src.database import get_db

logger = logging.getLogger("wareops_erp.modules.trash.service")


class TrashService:
    def __init__(self, db=Depends(get_db)):
        self.db = db
        self.collection = db.trash

    async def soft_delete(self, doc_id: str, original_collection: str, tenant_id: str, deleted_by: str, data: dict) -> dict:
        """
        Move a document to the trash collection to act as a soft delete.
        """
        trash_doc = {
            "original_id": doc_id,
            "original_collection": original_collection,
            "tenant_id": tenant_id,
            "deleted_at": datetime.utcnow(),
            "deleted_by": deleted_by,
            "data": data
        }
        res = await self.collection.insert_one(trash_doc)
        trash_doc["_id"] = str(res.inserted_id)
        logger.info(f"Soft deleted document: id={doc_id} from collection={original_collection} by user={deleted_by}")
        return trash_doc

    async def restore(self, trash_id: str, tenant_id: str, current_user: dict = None, audit_service = None) -> dict:
        """
        Restore a soft-deleted document back to its original collection.
        """
        try:
            query = {"_id": ObjectId(trash_id), "tenant_id": tenant_id}
        except Exception:
            query = {"_id": trash_id, "tenant_id": tenant_id}

        trash_doc = await self.collection.find_one(query)
        if not trash_doc:
            return None

        # Re-insert into original collection
        orig_collection = trash_doc["original_collection"]
        doc_data = trash_doc["data"]
        
        # Ensure correct MongoDB ObjectId conversion if original had ObjectId
        orig_id = trash_doc["original_id"]
        try:
            doc_data["_id"] = ObjectId(orig_id)
        except Exception:
            doc_data["_id"] = orig_id

        await self.db[orig_collection].insert_one(doc_data)
        
        # Remove from trash
        await self.collection.delete_one({"_id": trash_doc["_id"]})
        logger.info(f"Restored document: original_id={orig_id} to collection={orig_collection}")
        
        # Audit Log Integration if user and service are provided
        if current_user and audit_service:
            await audit_service.log_event(
                user_id=str(current_user["_id"]),
                user_name=current_user["name"],
                action="restore",
                description=f"Restored document {orig_id} back to collection '{orig_collection}'",
                tenant_id=tenant_id
            )

        doc_data["id"] = str(doc_data["_id"])
        return doc_data

    async def permanent_delete(self, trash_id: str, tenant_id: str) -> bool:
        """
        Permanently delete a soft-deleted document from recovery storage.
        """
        try:
            query = {"_id": ObjectId(trash_id), "tenant_id": tenant_id}
        except Exception:
            query = {"_id": trash_id, "tenant_id": tenant_id}

        res = await self.collection.delete_one(query)
        if res.deleted_count > 0:
            logger.info(f"Permanently purged document {trash_id} from trash.")
            return True
        return False

    async def list_trash(self, tenant_id: str) -> list[dict]:
        """
        List all soft-deleted records under user's tenant space.
        """
        cursor = self.collection.find({"tenant_id": tenant_id}).sort("deleted_at", -1)
        items = await cursor.to_list(length=100)
        for it in items:
            it["id"] = str(it["_id"])
            del it["_id"]
            if "deleted_at" in it and isinstance(it["deleted_at"], datetime):
                it["deleted_at"] = it["deleted_at"].isoformat()
        return items
