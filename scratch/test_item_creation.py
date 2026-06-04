import asyncio
import logging
from decimal import Decimal
from datetime import datetime
from src.database import get_db, connect_to_mongo
from src.modules.items.service import ItemService
from src.modules.items.repository import ItemRepository
from src.modules.items.schema import ItemCreate
from src.modules.audit_logs.service import AuditLogService
from src.modules.trash.service import TrashService
from src.modules.audit_logs.repository import AuditLogRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_item")

async def main():
    await connect_to_mongo()
    db = await get_db()
    item_repo = ItemRepository(db)
    audit_repo = AuditLogRepository(db)
    audit_service = AuditLogService(audit_repo)
    trash_service = TrashService(db)
    
    service = ItemService(
        repository=item_repo,
        db=db,
        audit=audit_service,
        trash=trash_service
    )
    
    # Mock user
    current_user = {
        "_id": "u6a19adb7b821dc61744f4918",
        "name": "Integration Admin",
        "email": "test_sa_1780067767@wareops.io",
        "role": "super_admin",
        "warehouse_id": "wh6a19adb7b821dc61744f491c",
        "tenant_id": "t6a19adb7b821dc61744f4917"
    }
    
    payload = ItemCreate(
        name="Premium Mechanical Keyboard",
        sku="SKU-TEST-12345",
        category="Electronics",
        price=Decimal("129.99"),
        stock=150,
        unit="pcs",
        taxCategory="normal",
        warehouseId="wh6a19adb7b821dc61744f491c"
    )
    
    try:
        res = await service.create_item(payload, current_user)
        logger.info(f"✅ Successfully created item: {res}")
    except Exception as e:
        logger.error(f"❌ Failed to create item: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
