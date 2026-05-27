import asyncio
import httpx
import time
import logging
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from src.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("wareops_erp.stress_test")

API_BASE = "http://127.0.0.1:8000/api/v1"
TEST_EMAIL = "stress_admin_qa@nexware.com"
TEST_PASS = "securePassStress999!"
TEST_COMPANY = "Stress Test Corporation"

async def run_stress_test():
    logger.info("🚀 STARTING PHASE 3 SCALE & STRESS TESTING SIMULATION...")
    
    # 1. Initialize DB Connection to seed historical data directly and check query speeds
    db_client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = db_client[settings.DB_NAME]
    
    # 2. Register/Login via HTTP Client to measure auth overhead
    async with httpx.AsyncClient(timeout=60.0) as client:
        signup_payload = {
            "name": "Stress Admin QA",
            "email": TEST_EMAIL,
            "password": TEST_PASS
        }
        
        logger.info(f"Authenticating stress test administrator: {TEST_EMAIL}...")
        # Signup
        signup_res = await client.post(f"{API_BASE}/auth/signup", json=signup_payload)
        if signup_res.status_code == 201:
            logger.info("✅ Fresh stress test tenant registered successfully.")
        else:
            logger.info("Using existing stress test tenant profile.")
            
        # Login to capture token
        login_res = await client.post(f"{API_BASE}/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASS
        })
        if login_res.status_code != 200:
            logger.error(f"❌ Authentication failed: {login_res.text}")
            return
            
        auth_data = login_res.json()["data"]
        token = auth_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        tenant_id = auth_data["user"]["tenant_id"]
        user_id = auth_data["user"]["id"]
        
        logger.info(f"✅ JWT Token verified. Tenant ID: {tenant_id}")
        
        # 3. Create Warehouse
        logger.info("Registering scale test warehouse hub...")
        wh_create_data = {
            "name": "Mega Scale Hub",
            "businessName": TEST_COMPANY,
            "address": "404 Scalability Way, Cloud City",
            "contact": "+1 (555) 777-8888",
            "email": "scalehub@stresscorp.com",
            "taxPreference": "standard",
            "logo": "🏢"
        }
        wh_res = await client.post(f"{API_BASE}/warehouses/", json=wh_create_data, headers=headers)
        if wh_res.status_code != 201:
            logger.error(f"❌ Warehouse creation failed: {wh_res.text}")
            return
            
        wh_id = wh_res.json()["data"]["_id"]
        logger.info(f"✅ Scale Hub initialized successfully. ID: {wh_id}")
        
        # 4. Generate CSV payload with 1,000 unique inventory items to stress the batch importer
        logger.info("Generating CSV string with 1,000 unique products...")
        csv_headers = "name,sku,category,price,stock,warehouseId\n"
        csv_rows = []
        for i in range(1, 1001):
            category = "Electronics" if i % 3 == 0 else "Furniture" if i % 3 == 1 else "Apparel"
            csv_rows.append(f"Product Number {i},SKU-STRESS-{i:04d},{category},{19.99 + i},{10 + (i % 90)},{wh_id}")
        csv_content = csv_headers + "\n".join(csv_rows)
        
        # Post files
        logger.info("Invoking high-performance CSV batch importer via REST API...")
        files = {"file": ("stress_import.csv", csv_content.encode("utf-8"), "text/csv")}
        start_time = time.time()
        import_res = await client.post(f"{API_BASE}/items/import", files=files, headers=headers)
        duration = time.time() - start_time
        
        if import_res.status_code != 200:
            logger.error(f"❌ CSV Batch Importer failed: {import_res.text}")
            return
            
        logger.info(f"✅ CSV Batch Importer finished successfully! Duration: {duration:.2f}s (Speed: {1000/duration:.1f} items/sec)")
        
        # 5. Direct Database Seeding of 500 Bills and 500 Audit Logs to avoid HTTP network bottleneck
        logger.info("Bypassing REST layer to seed 500 historical bills and 500 audit logs directly inside MongoDB...")
        
        bills_to_insert = []
        logs_to_insert = []
        now = datetime.utcnow()
        
        from bson.decimal128 import Decimal128
        from decimal import Decimal
        
        for i in range(1, 501):
            # Seed over last 12 months dynamically
            bill_date = now - timedelta(days=i % 365)
            bills_to_insert.append({
                "tenant_id": tenant_id,
                "warehouse_id": wh_id,
                "bill_no": f"INV-STRESS-{i:04d}",
                "customer": f"Enterprise Client {i}",
                "subtotal": Decimal128(Decimal(f"{100.0 * i}")),
                "tax": Decimal128(Decimal(f"{10.0 * i}")),
                "total": Decimal128(Decimal(f"{110.0 * i}")),
                "status": "paid",
                "items": [
                    {"item_id": f"dummy_{i}", "qty": i % 5 + 1, "price": Decimal128(Decimal("100.0"))}
                ],
                "created_at": bill_date
            })
            
            logs_to_insert.append({
                "tenant_id": tenant_id,
                "warehouse_id": wh_id,
                "action": "stress_simulate",
                "description": f"Scale profiling simulation event log number {i}",
                "user_id": user_id,
                "user_name": "Stress Agent",
                "timestamp": bill_date
            })
            
        # Perform Bulk writes
        await db.bills.insert_many(bills_to_insert)
        await db.audit_logs.insert_many(logs_to_insert)
        logger.info(f"✅ Seeding finished successfully. Seeding details:")
        logger.info(f"  - Inventory Items: 1,000 registered")
        logger.info(f"  - Bills/Invoices: 500 created")
        logger.info(f"  - Audit Logs: 500 registered")
        
        # 6. BENCHMARK AND PROFILING ACTIVE LOOPS
        logger.info("-------------------------------------------------------------------")
        logger.info("🎯 EXECUTING ENTERPRISE PERFORMANCE BENCHMARK SUITE...")
        logger.info("-------------------------------------------------------------------")
        
        # A. Inventory retrieval page profiling
        logger.info("1. Benchmarking paginated inventory query (SKU filter)...")
        start_time = time.time()
        res_items = await client.get(f"{API_BASE}/items/?page=1&limit=50&search=SKU-STRESS", headers=headers)
        q_time = (time.time() - start_time) * 1000
        logger.info(f"   [RESULT] Paginated Items Query: Status: {res_items.status_code} | Duration: {q_time:.2f}ms")
        
        # B. Analytics summary queries profiling (Aggregation Pipelines)
        logger.info("2. Benchmarking Analytics Dashboard Summary (Heavy aggregations, inventory suggestions)...")
        start_time = time.time()
        res_dash = await client.get(f"{API_BASE}/analytics/dashboard", headers=headers)
        q_time = (time.time() - start_time) * 1000
        logger.info(f"   [RESULT] Analytics Summary Query: Status: {res_dash.status_code} | Duration: {q_time:.2f}ms")
        
        # C. Audit logs listing index lookup profiling (Sorting by timestamp descending)
        logger.info("3. Benchmarking Audit Logs list query (Compound index search)...")
        start_time = time.time()
        res_logs = await client.get(f"{API_BASE}/audit-logs/", headers=headers)
        q_time = (time.time() - start_time) * 1000
        logger.info(f"   [RESULT] Audit Logs Query: Status: {res_logs.status_code} | Duration: {q_time:.2f}ms")
        
        # D. Concurrent load spikes
        logger.info("4. Benchmarking simultaneous concurrent load bursts (20 parallel requests)...")
        
        async def fetch_dashboard():
            t0 = time.time()
            r = await client.get(f"{API_BASE}/analytics/dashboard", headers=headers)
            return r.status_code, (time.time() - t0) * 1000
            
        tasks = [fetch_dashboard() for _ in range(20)]
        t_start = time.time()
        results = await asyncio.gather(*tasks)
        burst_duration = (time.time() - t_start) * 1000
        
        durations = [r[1] for r in results]
        avg_dur = sum(durations) / len(durations)
        logger.info(f"   [RESULT] 20 Concurrent Bursts: Total Duration: {burst_duration:.2f}ms | Avg Request: {avg_dur:.2f}ms")
        
        # 7. CLEANUP PHASE (IMMUTABLE ISOLATION CHECK: delete only stress records)
        logger.info("-------------------------------------------------------------------")
        logger.info("🧹 CLEANING UP SIMULATED STRESS TEST DATASETS...")
        logger.info("-------------------------------------------------------------------")
        
        del_items = await db.inventory_items.delete_many({"tenant_id": tenant_id})
        del_bills = await db.bills.delete_many({"tenant_id": tenant_id})
        del_logs = await db.audit_logs.delete_many({"tenant_id": tenant_id})
        # Delete warehouse by string user_id or by ObjectId
        try:
            del_wh = await db.warehouses.delete_many({"ownerId": user_id})
        except Exception:
            try:
                clean_uid = user_id[1:] if user_id.startswith('u') else user_id
                del_wh = await db.warehouses.delete_many({"ownerId": ObjectId(clean_uid)})
            except Exception:
                del_wh = type('obj', (object,), {'deleted_count': 0})()
        
        logger.info(f"✅ Cleanup finished successfully:")
        logger.info(f"  - Removed Items: {del_items.deleted_count}")
        logger.info(f"  - Removed Bills: {del_bills.deleted_count}")
        logger.info(f"  - Removed Logs: {del_logs.deleted_count}")
        logger.info(f"  - Removed Warehouses: {del_wh.deleted_count}")
        
    db_client.close()
    logger.info("🎉 PERFORMANCE BENCHMARK COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_stress_test())
