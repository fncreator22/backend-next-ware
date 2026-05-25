import time
import logging
import asyncio
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from src.utils.cache import cache_manager

logger = logging.getLogger("wareops_erp.middleware.rate_limiter")


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Production-grade Rate Limiting Middleware.
    Pipes limits to Redis if active, with thread-safe in-memory sliding window fallback.
    """
    def __init__(self, app, requests_limit: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self._in_memory_db = {}
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next) -> Response:
        # Bypass rate limiter for WebSockets and Health Checks
        path = request.url.path
        if request.scope.get("type") == "websocket" or path.startswith("/api/v1/realtime/ws"):
            return await call_next(request)

        if path in ["/health", "/health/db", "/health/cache", "/health/system", "/"]:
            return await call_next(request)

        # Identify client IP
        client_ip = request.client.host if request.client else "unknown-ip"

        # Check rate limit
        allowed = await self._is_allowed(client_ip)
        if not allowed:
            logger.warning(f"Rate limit exceeded for IP: {client_ip} on path: {path}")
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "Too many requests. Please check your request rate and try again later."
                }
            )

        return await call_next(request)

    async def _is_allowed(self, ip: str) -> bool:
        now = time.time()
        
        # Redis implementation
        if cache_manager.use_redis and cache_manager.redis_client:
            redis_key = f"rate:{ip}:{int(now / self.window_seconds)}"
            try:
                pipe = cache_manager.redis_client.pipeline()
                pipe.incr(redis_key)
                pipe.expire(redis_key, self.window_seconds)
                results = await pipe.execute()
                count = results[0]
                return count <= self.requests_limit
            except Exception as e:
                logger.error(f"Redis rate limiter exception: {e}. Degrading to In-Memory rate limiter.")

        # In-Memory thread-safe sliding window implementation
        async with self._lock:
            if ip not in self._in_memory_db:
                self._in_memory_db[ip] = []

            # Filter out timestamps outside the sliding window
            cutoff = now - self.window_seconds
            timestamps = [ts for ts in self._in_memory_db[ip] if ts > cutoff]
            
            # Check limit
            if len(timestamps) >= self.requests_limit:
                self._in_memory_db[ip] = timestamps
                return False

            # Add current request timestamp
            timestamps.append(now)
            self._in_memory_db[ip] = timestamps
            
            # Periodic cleanup of other stale IPs to prevent memory leaks
            if len(self._in_memory_db) > 1000:
                self._cleanup_in_memory_db(now)
                
            return True

    def _cleanup_in_memory_db(self, now: float):
        cutoff = now - self.window_seconds
        stale_keys = []
        for key, ts_list in self._in_memory_db.items():
            filtered = [ts for ts in ts_list if ts > cutoff]
            if not filtered:
                stale_keys.append(key)
            else:
                self._in_memory_db[key] = filtered
        for key in stale_keys:
            del self._in_memory_db[key]
