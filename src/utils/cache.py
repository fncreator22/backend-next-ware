import time
import logging
import asyncio
from typing import Optional

logger = logging.getLogger("wareops_erp.utils.cache")

# Try to import redis safely
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None
    REDIS_AVAILABLE = False


class InMemoryCache:
    """Thread-safe In-Memory TTL Cache Fallback."""
    def __init__(self):
        self._store = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[str]:
        async with self._lock:
            if key not in self._store:
                return None
            val, expires_at = self._store[key]
            if expires_at is not None and time.time() > expires_at:
                del self._store[key]
                return None
            return val

    async def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        async with self._lock:
            expires_at = time.time() + expire if expire is not None else None
            self._store[key] = (value, expires_at)
            return True

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()


class CacheManager:
    """Enterprise Cache Abstraction Layer with transparent Redis to In-Memory fallback."""
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis_client = None
        self.in_memory = InMemoryCache()
        self.use_redis = False

    async def connect(self):
        if not REDIS_AVAILABLE:
            logger.info("Redis package is not installed. Using safe In-Memory cache fallback.")
            self.use_redis = False
            return

        try:
            self.redis_client = aioredis.from_url(
                self.redis_url, 
                decode_responses=True, 
                socket_connect_timeout=1.0,
                socket_timeout=1.0
            )
            await self.redis_client.ping()
            self.use_redis = True
            logger.info(f"Successfully connected to Redis cache at {self.redis_url}")
        except Exception as e:
            logger.warning(f"Redis cache connection failed: {e}. Falling back to safe In-Memory TTL cache.")
            self.use_redis = False
            if self.redis_client:
                try:
                    await self.redis_client.close()
                except Exception:
                    pass
                self.redis_client = None

    async def get(self, key: str) -> Optional[str]:
        if self.use_redis and self.redis_client:
            try:
                return await self.redis_client.get(key)
            except Exception as e:
                logger.error(f"Redis cache GET error: {e}. Falling back to In-Memory cache.")
                return await self.in_memory.get(key)
        return await self.in_memory.get(key)

    async def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        if self.use_redis and self.redis_client:
            try:
                if expire:
                    await self.redis_client.setex(key, expire, value)
                else:
                    await self.redis_client.set(key, value)
                return True
            except Exception as e:
                logger.error(f"Redis cache SET error: {e}. Falling back to In-Memory cache.")
                return await self.in_memory.set(key, value, expire)
        return await self.in_memory.set(key, value, expire)

    async def delete(self, key: str) -> bool:
        if self.use_redis and self.redis_client:
            try:
                await self.redis_client.delete(key)
                return True
            except Exception as e:
                logger.error(f"Redis cache DELETE error: {e}. Falling back to In-Memory cache.")
                return await self.in_memory.delete(key)
        return await self.in_memory.delete(key)

    async def close(self):
        if self.redis_client:
            try:
                await self.redis_client.close()
                logger.info("Redis cache connection closed.")
            except Exception:
                pass


# Global cache manager instance using settings
from src.config import settings
cache_manager = CacheManager(settings.REDIS_URL)
