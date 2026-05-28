import logging
from fastapi import Depends
from src.database import get_db

logger = logging.getLogger("wareops_erp.modules.audit_logs.repository")


class AuditLogRepository:
    def __init__(self, db=Depends(get_db)):
        self.db = db
        self.collection = db.audit_logs

    async def create_log(self, doc: dict, session = None) -> dict:
        """Insert new immutable audit log document."""
        res = await self.collection.insert_one(doc, session=session)
        doc["_id"] = str(res.inserted_id)
        return doc

    async def list_logs(self, query: dict, limit: int = 5000) -> list[dict]:
        """Query audit log history sorted chronologically by timestamp (descending)."""
        cursor = self.collection.find(query).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)
