import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from src.config import settings

async def main():
    print(f"Connecting to: {settings.MONGODB_URL}")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DB_NAME]
    
    users = await db.users.find().to_list(length=100)
    print("\n--- Users in MongoDB ---")
    for u in users:
        print(f"ID: {u['_id']}, Name: {u['name']}, Email: {u['email']}, Role: {u['role']}, TenantID: {u['tenant_id']}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(main())
