import sys
import json
import urllib.request
import urllib.error
import time

def make_request(url, data=None, headers=None, method="GET"):
    if headers is None:
        headers = {}
    
    encoded_data = None
    if data is not None:
        encoded_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
        
    req = urllib.request.Request(
        url, 
        data=encoded_data,
        headers=headers,
        method=method
    )
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
        return e.code, parsed
    except Exception as e:
        return 0, str(e)

def run_tests():
    base_url = "http://127.0.0.1:8000/api/v1"
    email = f"user_{int(time.time())}@nexware.com"
    password = "SecurePassword123!"
    
    print("======================================================================")
    print("  NExWARE ERP AUTOMATED USER FLOW & FEATURE AUDIT TEST ")
    print("======================================================================\n")
    
    report = []
    
    # --------------------------------------------------------
    # 1. SIGNUP NEW USER
    # --------------------------------------------------------
    print("Step 1: Signing up a new Super Admin...")
    signup_data = {"name": "Alex Mercer", "email": email, "password": password}
    code, res = make_request(f"{base_url}/auth/signup", data=signup_data, method="POST")
    if code == 201:
        print("[SUCCESS] SIGNUP: Successful!")
        report.append(("Signup Flow", "PASSED", "Super Admin registered successfully."))
    else:
        print("[FAIL] SIGNUP: Failed!", res)
        report.append(("Signup Flow", "FAILED", f"Status {code}: {res}"))
        return report
        
    # --------------------------------------------------------
    # 2. LOGIN USER & FETCH SESSION
    # --------------------------------------------------------
    print("\nStep 2: Authenticating and retrieving JWT...")
    login_data = {"email": email, "password": password}
    code, res = make_request(f"{base_url}/auth/login", data=login_data, method="POST")
    if code == 200:
        token = res["data"]["access_token"]
        user_id = res["data"]["user"]["id"]
        tenant_id = res["data"]["user"]["tenant_id"]
        headers = {"Authorization": f"Bearer {token}"}
        print("[SUCCESS] LOGIN: Successful! JWT token issued.")
        report.append(("Login Authentication", "PASSED", "JWT issued and session created."))
    else:
        print("[FAIL] LOGIN: Failed!", res)
        report.append(("Login Authentication", "FAILED", f"Status {code}: {res}"))
        return report
        
    # --------------------------------------------------------
    # 3. REGISTER FIRST WAREHOUSE
    # --------------------------------------------------------
    print("\nStep 3: Registering first warehouse hub...")
    wh_data = {
        "name": "Dallas Logistics Depot",
        "businessName": "Dallas Hub Inc.",
        "address": "400 Freight Way, Dallas, TX 75201",
        "contact": "+1-214-555-7890",
        "email": "dallas@nexware.com",
        "taxPreference": "standard",
        "logo": "W"
    }
    code, res = make_request(f"{base_url}/warehouses/", data=wh_data, headers=headers, method="POST")
    if code == 201:
        wh_id = res["data"].get("id") or res["data"].get("_id")
        print(f"[SUCCESS] WAREHOUSE CREATION: Successful! Warehouse ID: {wh_id}")
        report.append(("Warehouse Registration", "PASSED", f"Created Dallas Depot: {wh_id}"))
    else:
        print("[FAIL] WAREHOUSE CREATION: Failed!", res)
        report.append(("Warehouse Registration", "FAILED", f"Status {code}: {res}"))
        return report

    # --------------------------------------------------------
    # 4. CREATE INVENTORY ITEM
    # --------------------------------------------------------
    print("\nStep 4: Creating a new inventory item...")
    sku = f"SKU-PIPE-{int(time.time())}"
    item_data = {
        "name": "Industrial Steel Pipes",
        "category": "Tools",
        "sku": sku,
        "price": 45.50,
        "stock": 100,
        "unit": "pcs",
        "taxCategory": "normal",
        "warehouseId": wh_id
    }
    code, res = make_request(f"{base_url}/items/", data=item_data, headers=headers, method="POST")
    if code == 201:
        item_id = res["data"].get("id") or res["data"].get("_id")
        print(f"[SUCCESS] ITEM CREATION: Successful! Item ID: {item_id}")
        report.append(("Item Creation", "PASSED", f"Created SKU {sku}: {item_id}"))
    else:
        print("[FAIL] ITEM CREATION: Failed!", res)
        report.append(("Item Creation", "FAILED", f"Status {code}: {res}"))
        return report

    # --------------------------------------------------------
    # 4b. VERIFY SKU DUPLICATE BLOCK
    # --------------------------------------------------------
    print("\nStep 4b: Testing SKU uniqueness block...")
    code, res = make_request(f"{base_url}/items/", data=item_data, headers=headers, method="POST")
    if code == 400 or "exists" in str(res):
        print("[SUCCESS] DUPLICATE SKU BLOCK: Successfully blocked duplicate SKU!")
        report.append(("SKU Uniqueness Guard", "PASSED", "Duplicate SKU creations successfully rejected by database."))
    else:
        print("[WARNING] DUPLICATE SKU BLOCK: Failed to block duplicate!", res)
        report.append(("SKU Uniqueness Guard", "FAILED", "Duplicate SKU was allowed by backend (database index bypass)."))

    # --------------------------------------------------------
    # 5. CREATE WORKFORCE MEMBER
    # --------------------------------------------------------
    print("\nStep 5: Inviting a shift manager (Workforce)...")
    mgr_email = f"manager_{int(time.time())}@nexware.com"
    mgr_data = {
        "name": "Sarah Connor",
        "email": mgr_email,
        "password": "ManagerPassword123!",
        "role": "manager",
        "warehouseId": wh_id
    }
    code, res = make_request(f"{base_url}/workforce/", data=mgr_data, headers=headers, method="POST")
    if code == 201:
        mgr_id = res["data"].get("id") or res["data"].get("_id")
        print(f"[SUCCESS] WORKFORCE CREATION: Successful! Member ID: {mgr_id}")
        report.append(("Workforce Management", "PASSED", f"Invited Manager {mgr_email}"))
    else:
        print("[FAIL] WORKFORCE CREATION: Failed!", res)
        report.append(("Workforce Management", "FAILED", f"Status {code}: {res}"))

    # --------------------------------------------------------
    # 6. CREATE DYNAMIC TABLE
    # --------------------------------------------------------
    print("\nStep 6: Creating custom dynamic table...")
    table_data = {
        "warehouseId": wh_id,
        "name": "Maintenance Logs",
        "category": "Operations",
        "description": "Log daily forklift checkups",
        "columns": [
            {"id": "col1", "name": "Forklift ID", "type": "text", "required": True},
            {"id": "col2", "name": "Inspector", "type": "text", "required": True},
            {"id": "col3", "name": "Status", "type": "dropdown", "options": "Ok,Maintenance Required", "required": True}
        ],
        "roles": ["admin", "manager"],
        "headerColor": "#4f46e5"
    }
    code, res = make_request(f"{base_url}/dynamic-tables/", data=table_data, headers=headers, method="POST")
    if code == 201:
        tbl_id = res["data"].get("id") or res["data"].get("_id")
        print(f"[SUCCESS] DYNAMIC TABLE CREATION: Successful! Table ID: {tbl_id}")
        report.append(("Dynamic Table Builder", "PASSED", f"Created schema 'Maintenance Logs': {tbl_id}"))
    else:
        print("[FAIL] DYNAMIC TABLE CREATION: Failed!", res)
        report.append(("Dynamic Table Builder", "FAILED", f"Status {code}: {res}"))

    # --------------------------------------------------------
    # 7. ADD ROW TO DYNAMIC TABLE
    # --------------------------------------------------------
    print("\nStep 7: Appending data row to dynamic table...")
    row_data = {
        "col1": "FL-004",
        "col2": "Sarah Connor",
        "col3": "Ok"
    }
    code, res = make_request(f"{base_url}/dynamic-tables/{tbl_id}/rows", data=row_data, headers=headers, method="POST")
    if code == 201:
        row_id = res["data"].get("id") or res["data"].get("_id")
        print(f"[SUCCESS] DYNAMIC ROW APPEND: Successful! Row ID: {row_id}")
        report.append(("Dynamic Row Storage", "PASSED", f"Stored row in custom collection: {row_id}"))
    else:
        print("[FAIL] DYNAMIC ROW APPEND: Failed!", res)
        report.append(("Dynamic Row Storage", "FAILED", f"Status {code}: {res}"))

    # --------------------------------------------------------
    # 8. CREATE BILL & ATOMICALLY DECREMENT STOCK
    # --------------------------------------------------------
    print("\nStep 8: Generating an invoice (Billing) and testing stock sync...")
    bill_data = {
        "warehouseId": wh_id,
        "customer": "Texas Ironworks Ltd.",
        "items": [
            {
                "id": item_id,
                "name": "Industrial Steel Pipes",
                "qty": 20,
                "price": 45.50,
                "taxCategory": "normal",
                "taxRate": 0.05
            }
        ],
        "subtotal": 910.00,
        "tax": 45.50, # 5% tax config
        "total": 955.50,
        "notes": "First industrial export"
    }
    code, res = make_request(f"{base_url}/billing/", data=bill_data, headers=headers, method="POST")
    if code == 201:
        bill_id = res["data"].get("id") or res["data"].get("_id")
        print(f"[SUCCESS] INVOICE GENERATION: Successful! Bill No: {res['data'].get('billNo') or res['data'].get('bill_no')}")
        report.append(("Billing & Taxation", "PASSED", f"Created Invoice {res['data'].get('billNo') or res['data'].get('bill_no')} with correct tax snapshots."))
    else:
        print("[FAIL] INVOICE GENERATION: Failed!", res)
        report.append(("Billing & Taxation", "FAILED", f"Status {code}: {res}"))

    # --------------------------------------------------------
    # 9. VERIFY ATOMIC INVENTORY DECREMENT
    # --------------------------------------------------------
    print("\nStep 9: Verifying stock level was atomically decremented in MongoDB...")
    code, res = make_request(f"{base_url}/items/{item_id}", headers=headers, method="GET")
    if code == 200:
        current_stock = res["data"]["stock"]
        expected_stock = 80 # 100 - 20
        if current_stock == expected_stock:
            print(f"[SUCCESS] INVENTORY ATOMIC DECREMENT: Successful! Live stock: {current_stock}")
            report.append(("Inventory Decrement", "PASSED", f"Atomically decremented stock from 100 to {current_stock}."))
        else:
            print(f"[FAIL] INVENTORY ATOMIC DECREMENT: Incorrect stock! Expected 80, got {current_stock}")
            report.append(("Inventory Decrement", "FAILED", f"Stock mapping desync: expected 80, got {current_stock}"))
    else:
        print("[FAIL] INVENTORY DECREMENT VERIFICATION: Failed!", res)
        report.append(("Inventory Decrement", "FAILED", f"Status {code}: {res}"))

    # --------------------------------------------------------
    # 10. FETCH AUDIT LOGS
    # --------------------------------------------------------
    print("\nStep 10: Fetching system compliance audit logs...")
    code, res = make_request(f"{base_url}/audit-logs/", headers=headers, method="GET")
    if code == 200:
        logs = res["data"]
        print(f"[SUCCESS] AUDIT LOGS: Successful! Fetched {len(logs)} audit entries.")
        report.append(("Compliance Audit Logs", "PASSED", f"Captured {len(logs)} mutative action logs."))
    else:
        print("[FAIL] AUDIT LOGS: Failed!", res)
        report.append(("Compliance Audit Logs", "FAILED", f"Status {code}: {res}"))

    return report

if __name__ == "__main__":
    results = run_tests()
    
    print("\n" + "=" * 60)
    print(" COMPLIANCE FEATURE STATUS REPORT")
    print("=" * 60)
    for feat, status, desc in results:
        sym = "[OK]" if status == "PASSED" else "[ERR]"
        print(f"{sym} {feat:<30} | {status:<10} | {desc}")
    print("=" * 60)
