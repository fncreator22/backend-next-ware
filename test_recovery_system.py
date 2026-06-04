import asyncio
import sys
import logging
from datetime import datetime
from decimal import Decimal
from bson.decimal128 import Decimal128
from src.database import connect_to_mongo, close_mongo_connection, get_db

# Import services
from src.modules.trash.service import TrashService
from src.modules.audit_logs.service import AuditLogService
from src.modules.items.service import ItemService
from src.modules.items.repository import ItemRepository
from src.modules.billing.service import BillingService
from src.modules.billing.repository import InvoiceRepository
from src.modules.dynamic_tables.service import DynamicTableService
from src.modules.dynamic_tables.repository import DynamicTableRepository
from src.modules.warehouses.service import WarehouseService
from src.modules.warehouses.repository import WarehouseRepository
from src.modules.workforce.service import WorkforceService
from src.modules.workforce.repository import WorkforceRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_recovery_system")

class MockRepo:
    def __init__(self, db):
        self.db = db
        self.collection = db.audit_logs
    async def create_log(self, doc, session=None):
        await self.db.audit_logs.insert_one(doc, session=session)
        return doc

async def test_recovery():
    logger.info("Initializing Recovery System (Trash/Bin) Integration Test...")
    await connect_to_mongo()
    db = await get_db()

    tenant_id = "tenant_rec_v1"
    wh_id = "wh_rec_v1"
    actor_id = "user_rec_actor"

    # Clean up any existing test data under this tenant space
    await db.users.delete_many({"tenant_id": tenant_id})
    await db.warehouses.delete_many({"tenant_id": tenant_id})
    await db.inventory_items.delete_many({"tenant_id": tenant_id})
    await db.bills.delete_many({"tenant_id": tenant_id})
    await db.table_schemas.delete_many({"tenant_id": tenant_id})
    await db.table_rows.delete_many({"tenant_id": tenant_id})
    await db.trash.delete_many({"tenant_id": tenant_id})
    await db.audit_logs.delete_many({"tenant_id": tenant_id})

    # 1. Setup mock actor and dependencies
    actor_user = {
        "_id": actor_id,
        "name": "Recovery Super Admin",
        "email": "rec_admin@test.com",
        "role": "super_admin",
        "tenant_id": tenant_id,
        "warehouse_id": wh_id
    }
    
    # Save actor as workforce member so we can query/delete users
    await db.users.insert_one(actor_user)

    # Initialize Services
    trash_service = TrashService(db=db)
    audit_service = AuditLogService(repository=None)
    audit_service.repo = MockRepo(db=db)
    
    item_service = ItemService(repository=ItemRepository(db=db), db=db, audit=audit_service, trash=trash_service)
    billing_service = BillingService(repository=InvoiceRepository(db=db), warehouse_repo=WarehouseRepository(db=db), item_repo=ItemRepository(db=db), db=db, audit=audit_service, trash=trash_service)
    table_service = DynamicTableService(repository=DynamicTableRepository(db=db), audit_service=audit_service, trash_service=trash_service)
    warehouse_service = WarehouseService(repository=WarehouseRepository(db=db), db=db, audit=audit_service, trash=trash_service)
    workforce_service = WorkforceService(repository=WorkforceRepository(db=db), db=db, audit=audit_service, trash=trash_service)

    logger.info("Services successfully initialized. Creating test records for all 5 modules...")

    # --- SEED DATA ---
    # A. Create Warehouse
    wh_doc = {
        "_id": wh_id,
        "name": "Recovery Warehouse Hub",
        "businessName": "Recovery LLC",
        "tenant_id": tenant_id,
        "created_at": datetime.utcnow()
    }
    await db.warehouses.insert_one(wh_doc)

    # B. Create User (Workforce member)
    staff_id = "user_rec_staff"
    staff_user = {
        "_id": staff_id,
        "name": "Staff Rec",
        "role": "staff",
        "tenant_id": tenant_id,
        "warehouse_id": wh_id
    }
    await db.users.insert_one(staff_user)

    # C. Create Item (Inventory)
    item_id = "item_rec_v1"
    item_doc = {
        "_id": item_id,
        "name": "Recovery Item",
        "sku": "SKU-REC-1",
        "price": Decimal128("25.99"),
        "stock": 100,
        "warehouse_id": wh_id,
        "tenant_id": tenant_id,
        "created_at": datetime.utcnow()
    }
    await db.inventory_items.insert_one(item_doc)

    # D. Create Invoices (Billing)
    invoice_id = "inv_rec_v1"
    invoice_doc = {
        "_id": invoice_id,
        "bill_no": "BILL-REC-1",
        "customer": "Customer Rec",
        "subtotal": Decimal128("100.00"),
        "tax": Decimal128("5.00"),
        "total": Decimal128("105.00"),
        "items": [],
        "warehouse_id": wh_id,
        "tenant_id": tenant_id,
        "created_at": datetime.utcnow()
    }
    await db.bills.insert_one(invoice_doc)

    # E. Create Tables and Rows
    tbl_schema_doc = {
        "_id": "tbl_rec_v1",
        "name": "Recovery Table",
        "table_name": "Recovery Table",
        "columns": [{"id": "col1", "name": "Column 1", "type": "text"}],
        "warehouse_id": wh_id,
        "tenant_id": tenant_id,
        "created_at": datetime.utcnow()
    }
    await db.table_schemas.insert_one(tbl_schema_doc)

    tbl_row_doc = {
        "_id": "row_rec_v1",
        "table_id": "tbl_rec_v1",
        "warehouse_id": wh_id,
        "tenant_id": tenant_id,
        "data": {"col1": "Row Value Snapshot"},
        "created_at": datetime.utcnow()
    }
    await db.table_rows.insert_one(tbl_row_doc)

    logger.info("Test records successfully seeded. Beginning soft-deletion E2E flow...")

    # --- SOFT DELETION TESTS ---

    # 1. Soft-delete Item
    logger.info("1. Deleting Item...")
    await item_service.delete_item(item_id, actor_user)
    assert await db.inventory_items.find_one({"_id": item_id}) is None
    item_trash = await db.trash.find_one({"original_id": item_id, "original_collection": "inventory_items", "tenant_id": tenant_id})
    assert item_trash is not None
    assert item_trash["deleted_by"] == actor_id
    assert item_trash["data"]["sku"] == "SKU-REC-1"

    # 2. Soft-delete Invoices
    logger.info("2. Deleting Invoice...")
    await billing_service.delete_invoice(invoice_id, actor_user)
    assert await db.bills.find_one({"_id": invoice_id}) is None
    inv_trash = await db.trash.find_one({"original_id": invoice_id, "original_collection": "bills", "tenant_id": tenant_id})
    assert inv_trash is not None
    assert inv_trash["deleted_by"] == actor_id
    assert inv_trash["data"]["bill_no"] == "BILL-REC-1"

    # 3. Soft-delete Table Rows & Schemas
    logger.info("3. Deleting Table Rows & Schemas...")
    # Row Soft-delete
    await table_service.delete_row("tbl_rec_v1", "row_rec_v1", actor_user)
    assert await db.table_rows.find_one({"_id": "row_rec_v1"}) is None
    row_trash = await db.trash.find_one({"original_id": "row_rec_v1", "original_collection": "table_rows", "tenant_id": tenant_id})
    assert row_trash is not None
    
    # Schema Soft-delete
    await table_service.delete_schema("tbl_rec_v1", actor_user)
    assert await db.table_schemas.find_one({"_id": "tbl_rec_v1"}) is None
    schema_trash = await db.trash.find_one({"original_id": "tbl_rec_v1", "original_collection": "table_schemas", "tenant_id": tenant_id})
    assert schema_trash is not None

    # 4. Soft-delete Workforce Member
    logger.info("4. Deleting Workforce Member...")
    await workforce_service.delete_workforce_member(staff_id, actor_user)
    assert await db.users.find_one({"_id": staff_id}) is None
    user_trash = await db.trash.find_one({"original_id": staff_id, "original_collection": "users", "tenant_id": tenant_id})
    assert user_trash is not None

    # 5. Soft-delete Warehouse (Cascade check)
    logger.info("5. Deleting Warehouse (Soft-deletes warehouse snapshot)...")
    await warehouse_service.retire_warehouse_cascade(wh_id, actor_user)
    assert await db.warehouses.find_one({"_id": wh_id}) is None
    wh_trash = await db.trash.find_one({"original_id": wh_id, "original_collection": "warehouses", "tenant_id": tenant_id})
    assert wh_trash is not None

    logger.info("All 5 modules successfully integrated with centralized soft-deletion!")

    # --- LIST RECOVERY ITEMS ---
    logger.info("6. Verifying List Trash API...")
    trash_list = await trash_service.list_trash(tenant_id)
    # Total soft-deleted items should be 6 (item, invoice, row, schema, user, warehouse)
    assert len(trash_list) == 6, f"Expected 6 trash items, saw {len(trash_list)}"
    logger.info(f"Verified list_trash successfully returned {len(trash_list)} items.")

    # --- RESTORATION TESTS ---
    logger.info("7. Testing Restoration...")
    trash_item_to_restore = next(t for t in trash_list if t["original_collection"] == "inventory_items")
    restored_item = await trash_service.restore(trash_item_to_restore["id"], tenant_id, actor_user, audit_service)
    
    # Assert item is back in collection
    assert restored_item is not None
    db_item = await db.inventory_items.find_one({"_id": item_id})
    assert db_item is not None
    assert db_item["sku"] == "SKU-REC-1"
    
    # Assert item is removed from trash
    assert await db.trash.find_one({"original_id": item_id}) is None
    
    # Assert restore audit log exists
    restore_audit = await db.audit_logs.find_one({"tenant_id": tenant_id, "action": "restore"})
    assert restore_audit is not None
    assert "inventory_items" in restore_audit["description"]
    logger.info("Restoration and restore audit logs successfully verified!")

    # --- PERMANENT PURGE TESTS ---
    logger.info("8. Testing Permanent Purging...")
    trash_item_to_purge = next(t for t in trash_list if t["original_collection"] == "bills")
    purged = await trash_service.permanent_delete(trash_item_to_purge["id"], tenant_id)
    assert purged is True
    assert await db.trash.find_one({"original_id": invoice_id}) is None
    logger.info("Permanent deletion successfully verified!")

    # Clean up test data
    await db.users.delete_many({"tenant_id": tenant_id})
    await db.warehouses.delete_many({"tenant_id": tenant_id})
    await db.inventory_items.delete_many({"tenant_id": tenant_id})
    await db.bills.delete_many({"tenant_id": tenant_id})
    await db.table_schemas.delete_many({"tenant_id": tenant_id})
    await db.table_rows.delete_many({"tenant_id": tenant_id})
    await db.trash.delete_many({"tenant_id": tenant_id})
    await db.audit_logs.delete_many({"tenant_id": tenant_id})
    await close_mongo_connection()

    print("\n=============================================")
    print("SUCCESS: Recovery (Trash/Bin) system verified!")
    print("1. Soft-delete snaps original data snapshots successfully")
    print("2. Centralized collection ('trash') records original schema bounds")
    print("3. Integrity-preserving RESTORE successfully restores records")
    print("4. Super Admin PERMANENT PURGE permanently erases data safely")
    print("5. Comprehensive recovery actions logged successfully in audit trail")
    print("=============================================")

if __name__ == "__main__":
    asyncio.run(test_recovery())
