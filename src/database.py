import logging
from motor.motor_asyncio import AsyncIOMotorClient
from src.config import settings

logger = logging.getLogger("wareops_erp.database")


class Database:
    client: AsyncIOMotorClient = None
    db = None


db_conn = Database()


async def connect_to_mongo():
    """Establish connection to MongoDB."""
    logger.info("Connecting to MongoDB cluster...")
    db_conn.client = AsyncIOMotorClient(settings.MONGODB_URL)
    db_conn.db = db_conn.client[settings.DB_NAME]
    logger.info("Successfully connected to MongoDB.")


async def close_mongo_connection():
    """Disconnect from MongoDB."""
    logger.info("Closing MongoDB connection...")
    if db_conn.client:
        db_conn.client.close()
    logger.info("MongoDB connection closed.")


async def get_db():
    """Dependency helper to get dynamic reference to MongoDB database instance."""
    return db_conn.db
