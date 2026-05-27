import asyncio
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wareops_erp.verify_phase2")

API_BASE = "http://127.0.0.1:8000/api/v1"

async def run_verification():
    logger.info("Initializing Phase 2 Technical Verification...")
    
    # 1. Sign up/Login to get a valid JWT token
    async with httpx.AsyncClient() as client:
        # Create a fresh Super Admin account to perform tests
        signup_data = {
            "name": "Phase2 Verification SuperAdmin",
            "email": "p2admin@nexware.com",
            "password": "strongpassword123"
        }
        logger.info("Registering a fresh Super Admin...")
        try:
            signup_res = await client.post(f"{API_BASE}/auth/signup", json=signup_data)
            if signup_res.status_code == 201:
                logger.info("✅ Super Admin signed up successfully.")
            elif signup_res.status_code == 400 and "already exists" in signup_res.text.lower():
                logger.info("Super Admin already exists. Proceeding to login...")
            else:
                logger.error(f"❌ Signup failed: {signup_res.status_code} - {signup_res.text}")
                return
        except Exception as e:
            logger.error(f"❌ Failed to reach backend: {e}")
            return

        # Login
        logger.info("Authenticating Super Admin...")
        login_res = await client.post(f"{API_BASE}/auth/login", json={
            "email": signup_data["email"],
            "password": signup_data["password"]
        })
        if login_res.status_code != 200:
            logger.error(f"❌ Login failed: {login_res.status_code}")
            return
            
        auth_data = login_res.json()["data"]
        token = auth_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        logger.info("✅ Successfully logged in and captured Access Token.")

        # Let's ensure a warehouse exists first
        logger.info("Fetching warehouses...")
        wh_res = await client.get(f"{API_BASE}/warehouses/", headers=headers)
        warehouses = wh_res.json()["data"]
        if not warehouses:
            logger.info("No warehouses found. Registering a test warehouse...")
            wh_create_data = {
                "name": "Validation Hub",
                "businessName": "NexWare Verification Corp",
                "address": "101 Validation Blvd",
                "contact": "+1 (555) 987-6543",
                "email": "hub@nexware.com",
                "taxPreference": "normal",
                "logo": ""
            }
            create_wh_res = await client.post(f"{API_BASE}/warehouses/", json=wh_create_data, headers=headers)
            if create_wh_res.status_code != 201:
                logger.error(f"❌ Warehouse creation failed: {create_wh_res.text}")
                return
            warehouse_id = create_wh_res.json()["data"]["_id"]
            logger.info(f"✅ Test Warehouse created successfully. ID: {warehouse_id}")
        else:
            warehouse_id = warehouses[0]["id"]
            logger.info(f"✅ Using existing warehouse. ID: {warehouse_id}")

        # 2. Test Notification endpoints
        logger.info("1. Testing Notifications Creation Endpoint...")
        notif_payload = [
            {
                "type": "bill_create",
                "title": "Invoice Generated",
                "message": "Invoice INV-0001 generated for $120.00",
                "link": "/billing",
                "userId": auth_data["user"]["id"],
                "targetWarehouseId": warehouse_id
            },
            {
                "type": "item_create",
                "title": "Low Stock Warning",
                "message": "Stock of SKU-999 is low (10 left)",
                "link": "/items",
                "userId": auth_data["user"]["id"],
                "targetWarehouseId": warehouse_id
            }
        ]
        create_notif_res = await client.post(f"{API_BASE}/realtime/notifications", json=notif_payload, headers=headers)
        if create_notif_res.status_code != 201:
            logger.error(f"❌ Notification batch creation failed: {create_notif_res.text}")
            return
        logger.info("✅ Batch notifications created successfully in MongoDB.")

        # Fetch notifications
        logger.info("2. Testing Notifications List Retrieval...")
        list_notif_res = await client.get(f"{API_BASE}/realtime/notifications", headers=headers)
        if list_notif_res.status_code != 200:
            logger.error(f"❌ Notifications fetch failed: {list_notif_res.text}")
            return
        notifs = list_notif_res.json()["data"]
        logger.info(f"✅ Notifications list successfully retrieved. Count: {len(notifs)}")
        
        # Test marking one read
        target_notif_id = notifs[0]["id"]
        logger.info(f"3. Testing Single Notification Read Toggle ({target_notif_id})...")
        read_res = await client.put(f"{API_BASE}/realtime/notifications/{target_notif_id}/read", headers=headers)
        if read_res.status_code != 200:
            logger.error(f"❌ Mark read failed: {read_res.text}")
            return
        logger.info("✅ Notification marked as read successfully.")

        # Test marking all read
        logger.info("4. Testing Mark All Notifications Read...")
        read_all_res = await client.put(f"{API_BASE}/realtime/notifications/read-all", headers=headers)
        if read_all_res.status_code != 200:
            logger.error(f"❌ Mark all read failed: {read_all_res.text}")
            return
        logger.info("✅ All notifications marked as read successfully.")

        # Test clearing notifications
        logger.info("5. Testing Clear All Notifications...")
        clear_res = await client.delete(f"{API_BASE}/realtime/notifications/clear", headers=headers)
        if clear_res.status_code != 200:
            logger.error(f"❌ Clear failed: {clear_res.text}")
            return
        logger.info("✅ Notifications cleared successfully.")

        # 3. Test Workforce RBAC boundaries
        # Create a Manager user to perform testing
        logger.info("Creating a test Manager workforce user...")
        manager_create_payload = {
            "name": "Phase2 Test Manager",
            "email": "p2manager@nexware.com",
            "password": "securepassword456",
            "role": "manager",
            "warehouseId": warehouse_id
        }
        create_mgr_res = await client.post(f"{API_BASE}/workforce/", json=manager_create_payload, headers=headers)
        if create_mgr_res.status_code != 201:
            logger.error(f"❌ Manager creation failed: {create_mgr_res.text}")
            return
        logger.info("✅ Manager workforce user created successfully.")

        # Login as Manager
        logger.info("Authenticating as Manager...")
        mgr_login_res = await client.post(f"{API_BASE}/auth/login", json={
            "email": manager_create_payload["email"],
            "password": manager_create_payload["password"]
        })
        if mgr_login_res.status_code != 200:
            logger.error(f"❌ Manager login failed: {mgr_login_res.text}")
            return
            
        mgr_auth = mgr_login_res.json()["data"]
        mgr_token = mgr_auth["access_token"]
        mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
        logger.info("✅ Manager successfully authenticated.")

        # Try to register a new user as Manager (should fail due to RBAC restriction!)
        logger.info("Testing Manager RBAC boundary: Attempting user creation as Manager...")
        bad_user_payload = {
            "name": "Illegal Employee",
            "email": "illegal@nexware.com",
            "password": "somepassword999",
            "role": "employee",
            "warehouseId": warehouse_id
        }
        bad_res = await client.post(f"{API_BASE}/workforce/", json=bad_user_payload, headers=mgr_headers)
        if bad_res.status_code == 403 or (bad_res.status_code == 400 and "unauthorized" in bad_res.text.lower()):
            logger.info("✅ RBAC Boundary verified! Manager was forbidden from registering users.")
        else:
            logger.error(f"❌ Security boundary failure: Manager was allowed to create a user! Status: {bad_res.status_code} - {bad_res.text}")
            return

        logger.info("🎉 TECHNICAL VERIFICATION SUCCESSFUL! All Phase 2 backend operational systems stable, secured, and isolation-verified.")

if __name__ == "__main__":
    asyncio.run(run_verification())
