# repository.py
import logging
from src.database import get_db

logger = logging.getLogger("wareops_erp.modules.auth.repository")


class UserRepository:
    def __init__(self):
        pass

    async def find_by_email(self, email: str):
        logger.info(f"Finding user by email: {email} placeholder...")
        return None
