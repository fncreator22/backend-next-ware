import asyncio
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_signup")

async def main():
    url = "http://127.0.0.1:8000/api/v1/auth/signup"
    payload = {
        "name": "Test Super Admin",
        "email": "test-admin@nexware-erp.com",
        "password": "SecurePassword123!"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info("Sending signup request to backend...")
            res = await client.post(url, json=payload)
            logger.info(f"Status Code: {res.status_code}")
            logger.info(f"Response: {res.json()}")
        except Exception as e:
            logger.error(f"Error connecting to backend: {e}")

if __name__ == "__main__":
    asyncio.run(main())
