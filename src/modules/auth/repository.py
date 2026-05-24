import logging
from datetime import datetime
from bson import ObjectId
from fastapi import Depends
from src.database import get_db

logger = logging.getLogger("wareops_erp.modules.auth.repository")


class UserRepository:
    def __init__(self, db=Depends(get_db)):
        self.db = db
        # Collection mappings
        self.users = db.users
        self.sessions = db.sessions

    async def find_by_email(self, email: str) -> dict:
        """Retrieve user document matching email address."""
        logger.info(f"Querying users collection for email: '{email}'")
        return await self.users.find_one({"email": email.lower()})

    async def find_by_id(self, user_id: str) -> dict:
        """Retrieve user document matching unique ID string."""
        logger.info(f"Querying users collection for ID: '{user_id}'")
        return await self.users.find_one({"_id": user_id})

    async def create_user(self, user_doc: dict) -> dict:
        """Insert a new user document. Automatically assigns 'u' prefixed string ID if missing."""
        if "_id" not in user_doc:
            user_doc["_id"] = "u" + str(ObjectId())
        
        user_doc["email"] = user_doc["email"].lower()
        logger.info(f"Inserting new user document: '{user_doc['_id']}' for email: '{user_doc['email']}'")
        await self.users.insert_one(user_doc)
        return user_doc

    async def add_session(self, user_id: str, token_id: str, expires_at: datetime) -> dict:
        """Register active refresh token session in the sessions blacklist/whitelist registry."""
        session_doc = {
            "_id": token_id,
            "user_id": user_id,
            "expires_at": expires_at,
            "is_revoked": False,
            "created_at": datetime.utcnow()
        }
        logger.info(f"Registering session: '{token_id}' for user ID: '{user_id}'")
        await self.sessions.insert_one(session_doc)
        return session_doc

    async def get_session(self, token_id: str) -> dict:
        """Fetch session registry by token ID identifier."""
        return await self.sessions.find_one({"_id": token_id})

    async def revoke_session(self, token_id: str) -> None:
        """Revoke a specific active refresh token session."""
        logger.info(f"Revoking session ID: '{token_id}'")
        await self.sessions.update_one({"_id": token_id}, {"$set": {"is_revoked": True}})

    async def revoke_all_user_sessions(self, user_id: str) -> None:
        """Invalidate all session keys active for a specific user profile (e.g. password resets)."""
        logger.info(f"Revoking all active sessions for user ID: '{user_id}'")
        await self.sessions.update_many({"user_id": user_id}, {"$set": {"is_revoked": True}})
