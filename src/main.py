import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.database import connect_to_mongo, close_mongo_connection
from src.utils.cache import cache_manager
from src.modules.realtime import start_realtime_change_listeners

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("wareops_erp.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection events and optional cache lifecycles."""
    await connect_to_mongo()
    await cache_manager.connect()
    
    # Non-blocking startup of Change Stream watchers
    try:
        await start_realtime_change_listeners()
    except Exception as e:
        logger.warning(f"Failed to start change stream watchers: {e}")
        
    yield
    
    await cache_manager.close()
    await close_mongo_connection()

app = FastAPI(
    title="WareOps ERP Enterprise API",
    description="Scalable, Multi-Tenant ERP Modular Monolith Backend API",
    version="1.0.0",
    lifespan=lifespan
)

# Apply global CORS configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Apply production-grade logging and rate limiting middlewares
from src.middleware.logging import LoggingMiddleware
from src.middleware.rate_limiter import RateLimiterMiddleware

app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimiterMiddleware, requests_limit=100, window_seconds=60)

# Register global exception handlers
from src.middleware.exceptions import register_exception_handlers
register_exception_handlers(app)

# Import and attach modular routers
from src.modules.auth import auth_router
from src.modules.warehouses import warehouses_router
from src.modules.items import items_router
from src.modules.billing import billing_router
from src.modules.dynamic_tables import dynamic_tables_router
from src.modules.workforce import workforce_router
from src.modules.audit_logs import audit_logs_router
from src.modules.analytics import analytics_router
from src.modules.realtime.router import router as realtime_router
from src.modules.health.router import router as health_router

# Direct registration of health check routes under root namespace
app.include_router(health_router)

# Modular prefix registration under namespace /api/v1
app.include_router(auth_router, prefix="/api/v1")
app.include_router(warehouses_router, prefix="/api/v1")
app.include_router(items_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(dynamic_tables_router, prefix="/api/v1")
app.include_router(workforce_router, prefix="/api/v1")
app.include_router(audit_logs_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(realtime_router, prefix="/api/v1")


@app.get("/", tags=["Health Check"])
async def root_health_check():
    """Verify that the API server is active and responding."""
    return {
        "success": True,
        "message": "WareOps ERP API is active and online."
    }

