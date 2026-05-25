import time
import json
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from src.modules.auth.utils import decode_token

logger = logging.getLogger("wareops_erp.middleware.logging")
request_logger = logging.getLogger("wareops_erp.json_requests")

# Make sure request_logger only outputs raw message to keep it clean JSON
request_logger.propagate = False
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(message)s"))
request_logger.addHandler(sh)
request_logger.setLevel(logging.INFO)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Production-grade Centralized Logging Middleware.
    Intercepts all HTTP transactions and outputs structured JSON records.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()

        client_ip = request.client.host if request.client else "unknown-ip"
        method = request.method
        path = request.url.path

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            status_code = 500
            raise e
        finally:
            end_time = time.perf_counter()
            duration_ms = round((end_time - start_time) * 1000, 2)

            tenant_id = "anonymous"
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                try:
                    payload = decode_token(token)
                    tenant_id = payload.get("tenant_id", "anonymous")
                except Exception:
                    pass

            log_entry = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "client_ip": client_ip,
                "method": method,
                "path": path,
                "status_code": status_code,
                "latency_ms": duration_ms,
                "tenant_id": tenant_id
            }

            request_logger.info(json.dumps(log_entry))
