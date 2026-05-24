import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wareops_erp.sanity")

logger.info("Initializing WareOps ERP Environment Sanity Check...")

# 1. Test Package Imports
required_packages = [
    ("fastapi", "FastAPI Framework"),
    ("uvicorn", "Uvicorn ASGI Server"),
    ("motor", "Motor Async MongoDB Client"),
    ("pydantic", "Pydantic Validation Layer"),
    ("jwt", "PyJWT Core Security"),
    ("argon2", "Argon2 Hashing Algorithm"),
    ("cryptography", "Cryptographic Signings Library")
]

failed = False
for pkg_name, description in required_packages:
    try:
        __import__(pkg_name)
        logger.info(f"✅ Package '{pkg_name}' ({description}) imported successfully.")
    except ImportError as e:
        logger.error(f"❌ Failed to import '{pkg_name}' ({description}): {e}")
        failed = True

if failed:
    logger.error("Sanity check failed: some dependencies are missing.")
    sys.exit(1)

# 2. Test Local Config & Modularity Resolution
try:
    from src.config import settings
    logger.info(f"✅ Local Configurations loaded successfully. DB Target: '{settings.DB_NAME}'")
    
    from src.main import app
    logger.info("✅ Core FastAPI Monolith app initialized and loaded successfully.")
    
    # Show available routes in OpenAPI docs
    logger.info("Registered API Routes:")
    for route in app.routes:
        logger.info(f"   -> {route.methods} {route.path}")
        
    logger.info("🚀 Environment Sanity Check PASSED! All modules resolved cleanly.")
except Exception as e:
    logger.error(f"❌ Failed to resolve local packages/configurations: {e}")
    sys.exit(1)
