import logging
from motor.motor_asyncio import AsyncIOMotorClient
from src.config import settings

logger = logging.getLogger("wareops_erp.database")


class Database:
    client: AsyncIOMotorClient = None
    db = None


db_conn = Database()


async def initialize_indexes():
    """Create unique indexes for collections to enforce relational constraints."""
    db = db_conn.db
    if db is None:
        return
    try:
        logger.info("Initializing database unique indexes...")
        # Unique index on users.email
        await db.users.create_index("email", unique=True)
        # Compound unique index on items.sku scoped per warehouse
        await db.inventory_items.create_index([("warehouse_id", 1), ("sku", 1)], unique=True)
        # Compound unique index on table_schemas table_name scoped per warehouse
        await db.table_schemas.create_index([("warehouse_id", 1), ("table_name", 1)], unique=True)
        logger.info("Database unique indexes successfully verified and initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize database indexes: {e}")


async def connect_to_mongo():
    """Establish connection to MongoDB."""
    logger.info("Connecting to MongoDB cluster...")
    db_conn.client = AsyncIOMotorClient(settings.MONGODB_URL)
    db_conn.db = db_conn.client[settings.DB_NAME]
    logger.info("Successfully connected to MongoDB.")
    # Initialize index constraints on startup
    await initialize_indexes()


async def close_mongo_connection():
    """Disconnect from MongoDB."""
    logger.info("Closing MongoDB connection...")
    if db_conn.client:
        db_conn.client.close()
    logger.info("MongoDB connection closed.")


async def get_db():
    """Dependency helper to get dynamic reference to MongoDB database instance."""
    return db_conn.db
