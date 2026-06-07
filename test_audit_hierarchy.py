import asyncio
import sys
import logging
from src.database import connect_to_mongo, close_mongo_connection, get_db
from src.modules.audit_logs.service import AuditLogService
from src.modules.audit_logs.repository import AuditLogRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_audit_hierarchy")

async def test_hierarchy():
    logger.info("Initializing Audit Hierarchy Test...")
    await connect_to_mongo()
    db = await get_db()
    
    # 1. Setup mock tenant, warehouse, and users
    tenant_id = "test_tenant_h1"
    wh_id = "test_warehouse_h1"
    wh_id_other = "test_warehouse_other"
    
    # Delete previous test data
    await db.users.delete_many({"tenant_id": tenant_id})
    await db.audit_logs.delete_many({"tenant_id": tenant_id})
    
    # Create test users with different roles
    super_admin = {
        "_id": "user_super_admin",
        "name": "Super Admin User",
        "email": "super@test.com",
        "role": "super_admin",
        "tenant_id": tenant_id,
        "warehouse_id": None
    }
    
    admin_user = {
        "_id": "user_admin",
        "name": "Admin User",
        "email": "admin@test.com",
        "role": "admin",
        "tenant_id": tenant_id,
        "warehouse_id": wh_id
    }
    
    manager_user = {
        "_id": "user_manager",
        "name": "Manager User",
        "email": "manager@test.com",
        "role": "manager",
        "tenant_id": tenant_id,
        "warehouse_id": wh_id,
        "permission_overrides": {
            "audit": {"view": True}
        }
    }
    
    staff_user = {
        "_id": "user_staff",
        "name": "Staff User",
        "email": "staff@test.com",
        "role": "staff",
        "tenant_id": tenant_id,
        "warehouse_id": wh_id,
        "permission_overrides": {
            "audit": {"view": True}
        }
    }
    
    other_staff_user = {
        "_id": "user_other_staff",
        "name": "Other Staff User",
        "email": "other@test.com",
        "role": "staff",
        "tenant_id": tenant_id,
        "warehouse_id": wh_id_other
    }
    
    await db.users.insert_many([super_admin, admin_user, manager_user, staff_user, other_staff_user])
    
    # Instantiate repository and service
    repo = AuditLogRepository(db=db)
    service = AuditLogService(repository=repo)
    
    # Log events from each user
    await service.log_event("user_super_admin", "Super Admin User", "login", "Super admin logged in", tenant_id)
    await service.log_event("user_admin", "Admin User", "item_create", "Admin created item", tenant_id, wh_id)
    await service.log_event("user_manager", "Manager User", "item_edit", "Manager edited item", tenant_id, wh_id)
    await service.log_event("user_staff", "Staff User", "table_row_create", "Staff appended row", tenant_id, wh_id)
    await service.log_event("user_other_staff", "Other Staff User", "table_row_create", "Other Staff appended row", tenant_id, wh_id_other)
    
    # Perform queries and test visibility
    
    # Test 1: Super Admin views everything under tenant_id
    res = await service.list_logs(super_admin)
    logs = res["logs"]
    logger.info(f"Super Admin sees {len(logs)} logs.")
    assert len(logs) == 5, f"Super Admin should see 5 logs, saw {len(logs)}"
    
    # Test 2: Admin views all admin, manager, staff logs under wh_id
    res = await service.list_logs(admin_user)
    logs = res["logs"]
    logger.info(f"Admin sees {len(logs)} logs.")
    # Admin sees: Admin log, Manager log, Staff log.
    assert len(logs) == 3, f"Admin should see 3 logs, saw {len(logs)}"
    user_ids = [l["user_id"] for l in logs]
    assert "user_admin" in user_ids
    assert "user_manager" in user_ids
    assert "user_staff" in user_ids
    assert "user_other_staff" not in user_ids
    
    # Test 3: Manager views manager, staff logs under wh_id
    res = await service.list_logs(manager_user)
    logs = res["logs"]
    logger.info(f"Manager sees {len(logs)} logs.")
    # Manager sees: Manager log, Staff log.
    assert len(logs) == 2, f"Manager should see 2 logs, saw {len(logs)}"
    user_ids = [l["user_id"] for l in logs]
    assert "user_manager" in user_ids
    assert "user_staff" in user_ids
    assert "user_admin" not in user_ids
    
    # Test 4: Staff views only own logs
    res = await service.list_logs(staff_user)
    logs = res["logs"]
    logger.info(f"Staff sees {len(logs)} logs.")
    # Staff sees only staff_user log.
    assert len(logs) == 1, f"Staff should see 1 log, saw {len(logs)}"
    assert logs[0]["user_id"] == "user_staff"
    
    # Clean up test data
    await db.users.delete_many({"tenant_id": tenant_id})
    await db.audit_logs.delete_many({"tenant_id": tenant_id})
    await close_mongo_connection()
    
    print("\n=============================================")
    print("SUCCESS: Audit Trail hierarchical visibility passes all constraints programmatically!")
    print("1. Super Admin -> saw all logs (5/5)")
    print("2. Admin       -> saw only admin/manager/staff logs in same warehouse (3/5)")
    print("3. Manager     -> saw only manager/staff logs in same warehouse (2/5)")
    print("4. Staff       -> saw only own logs (1/5)")
    print("=============================================")

if __name__ == "__main__":
    asyncio.run(test_hierarchy())
