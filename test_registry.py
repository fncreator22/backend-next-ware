import asyncio
import logging
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_registry")

from src.config import settings
from src.modules.registry.service import CentralRegistryService, CustomerService, generate_code39_svg
from src.modules.warehouses.service import WarehouseService
from src.modules.warehouses.repository import WarehouseRepository
from src.modules.warehouses.schema import WarehouseCreate
from src.modules.workforce.service import WorkforceService
from src.modules.workforce.repository import WorkforceRepository
from src.modules.workforce.schema import UserCreate
from src.modules.items.service import ItemService
from src.modules.items.repository import ItemRepository
from src.modules.items.schema import ItemCreate
from src.modules.dynamic_tables.service import DynamicTableService
from src.modules.dynamic_tables.repository import DynamicTableRepository
from src.modules.dynamic_tables.schema import TableSchemaCreate, TableColumnCreate
from src.modules.billing.service import BillingService
from src.modules.billing.repository import InvoiceRepository
from src.modules.billing.schema import InvoiceCreate, InvoiceItemCreate, TaxDetailCreate

async def run_tests():
    logger.info("Initializing Registry & CRM Test Suite...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DB_NAME]

    # Setup standard fake tenant IDs
    tenant_a = "TENANT-ALPHA-999"
    tenant_b = "TENANT-BETA-777"

    # Purge any test counters and registry logs for deterministic results
    await db.enterprise_counters.delete_many({"tenant_id": {"$in": [tenant_a, tenant_b]}})
    await db.enterprise_registry.delete_many({"tenant_id": {"$in": [tenant_a, tenant_b]}})
    await db.customers.delete_many({"tenant_id": {"$in": [tenant_a, tenant_b]}})
    await db.warehouses.delete_many({"tenant_id": {"$in": [tenant_a, tenant_b]}})
    await db.users.delete_many({"tenant_id": {"$in": [tenant_a, tenant_b]}})
    await db.inventory_items.delete_many({"tenant_id": {"$in": [tenant_a, tenant_b]}})
    await db.table_schemas.delete_many({"tenant_id": {"$in": [tenant_a, tenant_b]}})
    await db.bills.delete_many({"tenant_id": {"$in": [tenant_a, tenant_b]}})

    # Setup services
    from src.modules.audit_logs.repository import AuditLogRepository
    from src.modules.audit_logs.service import AuditLogService
    from src.modules.trash.service import TrashService

    audit_repo = AuditLogRepository(db=db)
    audit_service = AuditLogService(repository=audit_repo)
    trash_service = TrashService(db=db)

    registry_service = CentralRegistryService(db=db, audit=audit_service)
    customer_service = CustomerService(db=db, registry=registry_service, audit=audit_service)
    
    wh_repo = WarehouseRepository(db=db)
    wh_service = WarehouseService(
        repository=wh_repo,
        db=db,
        audit=audit_service,
        trash=trash_service,
        registry=registry_service
    )
    
    wf_repo = WorkforceRepository(db=db)
    wf_service = WorkforceService(
        repository=wf_repo,
        db=db,
        audit=audit_service,
        trash=trash_service,
        registry=registry_service
    )
    
    item_repo = ItemRepository(db=db)
    item_service = ItemService(
        repository=item_repo,
        db=db,
        audit=audit_service,
        trash=trash_service,
        registry=registry_service
    )
    
    tbl_repo = DynamicTableRepository(db=db)
    tbl_service = DynamicTableService(
        repository=tbl_repo,
        audit_service=audit_service,
        trash_service=trash_service,
        registry=registry_service
    )
    
    inv_repo = InvoiceRepository(db=db)
    billing_service = BillingService(
        repository=inv_repo,
        warehouse_repo=wh_repo,
        item_repo=item_repo,
        db=db,
        audit=audit_service,
        trash=trash_service,
        registry=registry_service,
        customer_service=customer_service
    )

    # 1. TEST UNIQUE ENTERPRISE ID SEQUENCING & TENANT ISOLATION
    logger.info("TEST 1: Testing atomic sequential ID generation & multi-tenant isolation...")
    
    # Generate for Tenant A
    id_a1 = await registry_service.get_next_enterprise_id(tenant_a, "WH")
    id_a2 = await registry_service.get_next_enterprise_id(tenant_a, "WH")
    
    # Generate for Tenant B
    id_b1 = await registry_service.get_next_enterprise_id(tenant_b, "WH")
    
    current_year = datetime.utcnow().year
    
    assert id_a1 == f"WH-{current_year}-0001", f"Expected WH-{current_year}-0001, got {id_a1}"
    assert id_a2 == f"WH-{current_year}-0002", f"Expected WH-{current_year}-0002, got {id_a2}"
    assert id_b1 == f"WH-{current_year}-0001", f"Expected isolated counter WH-{current_year}-0001 for Tenant B, got {id_b1}"
    
    logger.info("✅ TEST 1 PASSED: Multi-tenant counters isolated and sequential.")

    # 2. TEST BARCODE SVG GENERATOR
    logger.info("TEST 2: Testing Code 39 SVG barcode renderer...")
    svg = generate_code39_svg("INV-2026-0001")
    assert "<svg" in svg, "Expected SVG markup element wrapper"
    assert "</svg>" in svg, "Expected SVG closing markup element"
    assert 'text-anchor="middle"' in svg, "Expected SVG styling features"
    assert "INV-2026-0001" in svg, "Expected label text inside barcode SVG"
    logger.info("✅ TEST 2 PASSED: Code 39 vector SVG barcode rendered successfully.")

    # 3. TEST WAREHOUSE CREATION AUTOMATED REGISTRY HOOKS
    logger.info("TEST 3: Testing Warehouse creation registry hooks...")
    super_user = {
        "_id": ObjectId(),
        "name": "Super Administrator A",
        "email": "super@tenant-a.com",
        "role": "super_admin",
        "tenant_id": tenant_a
    }
    
    wh_payload = WarehouseCreate(
        name="Primary Logistics Hub",
        businessName="NexWare Logistics Alpha",
        address="100 Tech Park Drive, California",
        contact="+1555123456",
        email="hub-alpha@tenant-a.com",
        taxPreference="custom",
        logo="logo_alpha.png",
        currency="USD"
    )
    
    created_wh = await wh_service.create_warehouse(wh_payload, super_user)
    wh_ent_id = created_wh.get("enterprise_id")
    wh_id = str(created_wh["_id"])
    
    assert wh_ent_id == f"WH-{current_year}-0003", f"Expected WH-{current_year}-0003, got {wh_ent_id}"
    assert created_wh.get("barcode") == wh_ent_id, "Expected matching barcode field"
    
    # Verify logged inside centralized enterprise registry
    registry_log = await db.enterprise_registry.find_one({"tenant_id": tenant_a, "entity_id": wh_ent_id})
    assert registry_log is not None, "Expected tracking registry log entry"
    assert registry_log["entity_type"] == "warehouse", "Expected type warehouse"
    assert registry_log["warehouse_id"] == wh_id, "Expected matching warehouse id scope"
    assert registry_log["metadata_snapshot"]["name"] == "Primary Logistics Hub", "Expected correct snapshot"
    
    logger.info("✅ TEST 3 PASSED: Warehouse created, ID assigned, registered atomically.")

    # 4. TEST WORKFORCE REGISTRATION REGISTRY HOOKS
    logger.info("TEST 4: Testing Workforce employee registration hooks...")
    wf_payload = UserCreate(
        name="Staff Member A",
        email="staff-a@tenant-a.com",
        password="SuperSecretPassword123!",
        role="staff",
        warehouse_id=wh_id
    )
    
    created_emp = await wf_service.create_workforce_member(wf_payload, super_user)
    emp_ent_id = created_emp.get("enterprise_id")
    
    assert emp_ent_id == f"EMP-{current_year}-0001", f"Expected EMP-{current_year}-0001, got {emp_ent_id}"
    assert created_emp.get("barcode") == emp_ent_id
    
    emp_log = await db.enterprise_registry.find_one({"tenant_id": tenant_a, "entity_id": emp_ent_id})
    assert emp_log is not None
    assert emp_log["entity_type"] == "employee"
    assert emp_log["warehouse_id"] == wh_id
    
    logger.info("✅ TEST 4 PASSED: Workforce employee created, ID assigned, registered atomically.")

    # 5. TEST INVENTORY ITEM REGISTRATION REGISTRY HOOKS
    logger.info("TEST 5: Testing Inventory item registration hooks...")
    admin_user = {
        "_id": created_emp["_id"],
        "name": "Staff Member A",
        "email": "staff-a@tenant-a.com",
        "role": "admin",
        "tenant_id": tenant_a,
        "warehouse_id": wh_id
    }
    
    item_payload = ItemCreate(
        warehouse_id=wh_id,
        sku="SKU-TEST-TRACK-001",
        name="Premium Microchips",
        category="Electronics",
        price=450.0,
        stock=500,
        unit="pcs",
        tax_category="normal"
    )
    
    created_item = await item_service.create_item(item_payload, admin_user)
    item_ent_id = created_item.get("enterprise_id")
    item_id = str(created_item["_id"])
    
    assert item_ent_id == f"ITEM-{current_year}-0001", f"Expected ITEM-{current_year}-0001, got {item_ent_id}"
    assert created_item.get("barcode") == item_ent_id
    
    item_log = await db.enterprise_registry.find_one({"tenant_id": tenant_a, "entity_id": item_ent_id})
    assert item_log is not None
    assert item_log["entity_type"] == "inventory"
    assert item_log["warehouse_id"] == wh_id
    
    logger.info("✅ TEST 5 PASSED: Inventory item created, ID assigned, registered atomically.")

    # 6. TEST CUSTOM TABLE SCHEMA REGISTRATION HOOKS
    logger.info("TEST 6: Testing Custom operational table registration hooks...")
    tbl_payload = TableSchemaCreate(
        name="Maintenance Log Table",
        category="Maintenance",
        description="Daily operational maintenance checklist",
        warehouse_id=wh_id,
        columns=[
            TableColumnCreate(id="c1", name="Machine Code", type="text", required=True),
            TableColumnCreate(id="c2", name="Status Check", type="status", required=True)
        ],
        roles=["staff", "manager"],
        header_color="#10b981"
    )
    
    created_tbl = await tbl_service.create_schema(tbl_payload, admin_user)
    tbl_ent_id = created_tbl.get("enterprise_id")
    
    assert tbl_ent_id == f"TBL-{current_year}-0001", f"Expected TBL-{current_year}-0001, got {tbl_ent_id}"
    assert created_tbl.get("barcode") == tbl_ent_id
    
    tbl_log = await db.enterprise_registry.find_one({"tenant_id": tenant_a, "entity_id": tbl_ent_id})
    assert tbl_log is not None
    assert tbl_log["entity_type"] == "table_registry"
    assert tbl_log["warehouse_id"] == wh_id
    
    logger.info("✅ TEST 6 PASSED: Custom table schema registered and logged atomically.")

    # 7. TEST BILLING INVOICE AND AUTOMATED CRM CHECKOUT LINKING
    logger.info("TEST 7: Testing Billing checkout invoice unique ID and automated CRM Repeat Shopper profiles...")
    
    # Verify checkout for a first-time CRM customer
    billing_payload1 = InvoiceCreate(
        warehouse_id=wh_id,
        customer="Enterprise Client Corp",
        customer_phone="+1555999888",
        customer_email="procurement@enterprise-client.com",
        buyer_billing_address="99 corporate court, silicon valley",
        buyer_shipping_address="99 corporate court, silicon valley",
        items=[
            InvoiceItemCreate(
                item_id=item_id,
                name="Premium Microchips",
                qty=10,
                price=450.0,
                tax_category="normal",
                tax_rate=0.05,
                taxes=[]
            )
        ],
        subtotal=4500.0,
        tax=225.0,
        total=4725.0,
        seller_address="100 Tech Park Drive, California",
        seller_contact="+1555123456",
        seller_tax_number="27HUBALPHAC1234F1Z5"
    )
    
    inv_created1 = await billing_service.create_invoice(billing_payload1, admin_user)
    inv_ent_id1 = inv_created1.get("bill_no")
    
    assert inv_ent_id1 == f"INV-{current_year}-0001", f"Expected INV-{current_year}-0001, got {inv_ent_id1}"
    assert inv_created1.get("barcode") == inv_ent_id1
    
    # 7.1 Verify CRM customer creation
    customer_profile = await db.customers.find_one({"tenant_id": tenant_a, "email": "procurement@enterprise-client.com"})
    assert customer_profile is not None, "Expected CRM customer profile to be automatically registered!"
    cust_ent_id = customer_profile["customer_id"]
    assert cust_ent_id == f"CUST-{current_year}-0001", f"Expected customer unique ID CUST-{current_year}-0001, got {cust_ent_id}"
    assert customer_profile["barcode"] == cust_ent_id
    assert len(customer_profile["invoices"]) == 1, "Expected 1 recorded invoice in customer CRM history"
    assert customer_profile["invoices"][0]["bill_no"] == inv_ent_id1
    
    # 7.2 Verify logged inside centralized enterprise registry
    inv_log = await db.enterprise_registry.find_one({"tenant_id": tenant_a, "entity_id": inv_ent_id1})
    assert inv_log is not None
    assert inv_log["entity_type"] == "invoice"
    
    cust_log = await db.enterprise_registry.find_one({"tenant_id": tenant_a, "entity_id": cust_ent_id})
    assert cust_log is not None
    assert cust_log["entity_type"] == "customer"
    
    # 7.3 Repeat Checkout: Test CRM Repeat Customer Loyalty Tracking
    billing_payload2 = InvoiceCreate(
        warehouse_id=wh_id,
        customer="Enterprise Client Corp",
        customer_phone="+1555999888",
        customer_email="procurement@enterprise-client.com",
        buyer_billing_address="99 corporate court, silicon valley",
        buyer_shipping_address="99 corporate court, silicon valley",
        items=[
            InvoiceItemCreate(
                item_id=item_id,
                name="Premium Microchips",
                qty=5,
                price=450.0,
                tax_category="normal",
                tax_rate=0.05,
                taxes=[]
            )
        ],
        subtotal=2250.0,
        tax=112.5,
        total=2362.5,
        seller_address="100 Tech Park Drive, California",
        seller_contact="+1555123456",
        seller_tax_number="27HUBALPHAC1234F1Z5"
    )
    
    inv_created2 = await billing_service.create_invoice(billing_payload2, admin_user)
    inv_ent_id2 = inv_created2.get("bill_no")
    
    assert inv_ent_id2 == f"INV-{current_year}-0002", f"Expected INV-{current_year}-0002, got {inv_ent_id2}"
    
    # Verify CRM updated rather than duplicated
    customer_profile_repeat = await db.customers.find_one({"tenant_id": tenant_a, "email": "procurement@enterprise-client.com"})
    assert customer_profile_repeat["customer_id"] == cust_ent_id, "Expected same customer ID, no duplicate profiles!"
    assert len(customer_profile_repeat["invoices"]) == 2, f"Expected 2 invoices for repeat loyalty tracker, got {len(customer_profile_repeat['invoices'])}"
    assert customer_profile_repeat["invoices"][1]["bill_no"] == inv_ent_id2
    
    logger.info("✅ TEST 7 PASSED: Invoices sequential, auto CRM repeat shopping tracking completely operational.")
    
    logger.info("🎉 ALL TESTS PASSED SUCCESSFULLY! NexWare ERP enterprise tracking architecture is robust and 100% correct.")

if __name__ == "__main__":
    asyncio.run(run_tests())
