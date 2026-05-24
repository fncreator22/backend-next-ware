import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.database import connect_to_mongo, close_mongo_connection

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("wareops_erp.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection events across the application life cycle."""
    await connect_to_mongo()
    yield
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

# Modular prefix registration under namespace /api/v1
app.include_router(auth_router, prefix="/api/v1")
app.include_router(warehouses_router, prefix="/api/v1")
app.include_router(items_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(dynamic_tables_router, prefix="/api/v1")
app.include_router(workforce_router, prefix="/api/v1")
app.include_router(audit_logs_router, prefix="/api/v1")


@app.get("/", tags=["Health Check"])
async def root_health_check():
    """Verify that the API server is active and responding."""
    return {
        "success": True,
        "message": "WareOps ERP API is active and online."
    }
