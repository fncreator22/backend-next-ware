import asyncio
import sys
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from src.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("wareops_erp.db_test")


async def test_mongodb_connection():
    logger.info("Initializing MongoDB Connectivity Test...")
    logger.info(f"Target connection URL: '{settings.MONGODB_URL}'")
    logger.info(f"Target database name:  '{settings.DB_NAME}'")

    try:
        # Initialize AsyncIOMotorClient
        client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=3000)
        db = client[settings.DB_NAME]

        # Execute ping command to verify roundtrip connection
        logger.info("Sending database ping command...")
        await db.command("ping")
        
        logger.info("Connection status: SUCCESSFUL!")
        logger.info("Motor async database connection is fully active and healthy.")
        
        # Display server details
        server_info = await client.server_info()
        logger.info(f"MongoDB Version: {server_info.get('version', 'Unknown')}")
        sys_info = server_info.get('sysInfo', {})
        os_type = sys_info.get('osType', 'Unknown') if isinstance(sys_info, dict) else 'Unknown'
        logger.info(f"Server OS:      {os_type}")
        client.close()
        
        print("\nSUCCESS: Backend to MongoDB connectivity verified!")
        sys.exit(0)
        
    except Exception as e:
        logger.error("Connection status: FAILED!")
        logger.error(f"Error details: {e}")
        logger.info("\nTROUBLESHOOTING GUIDE:")
        logger.info("1. Ensure your MongoDB server is active and running:")
        logger.info("   - Local installation: Verify mongod service is running on port 27017.")
        logger.info("   - MongoDB Atlas: Ensure your IP address is whitelisted in the Atlas Network Access panel.")
        logger.info("2. Validate your credentials in the local '.env' file:")
        logger.info("   - Check MONGODB_URL and verify username, password, and database parameters.")
        logger.info("3. Confirm that no firewall or security rules block port 27017.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_mongodb_connection())
