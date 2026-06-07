import sys
import json
import urllib.request
import urllib.error
import time

BASE_URL = "http://127.0.0.1:8000/api/v1"

def make_request(url, data=None, headers=None, method="GET"):
    if headers is None:
        headers = {}
    encoded_data = None
    if data is not None:
        encoded_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
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

async def test_permissions():
    print("==================================================")
    print(" NexWare ERP Modular Permission Verification Test ")
    print("==================================================")

    # 1. Sign up a Super Admin
    timestamp = int(time.time())
    sa_email = f"sa_{timestamp}@nexware.com"
    sa_password = "SuperPassword123!"
    
    print("\n[INIT] Registering Super Admin...")
    code, res = make_request(f"{BASE_URL}/auth/signup", data={"name": "Super Admin", "email": sa_email, "password": sa_password}, method="POST")
    if code != 201:
        print(f"FAILED to sign up Super Admin: {code} - {res}")
        return
    
    print("[INIT] Logging in as Super Admin...")
    code, res = make_request(f"{BASE_URL}/auth/login", data={"email": sa_email, "password": sa_password}, method="POST")
    sa_token = res["data"]["access_token"]
    sa_headers = {"Authorization": f"Bearer {sa_token}"}

    print("[INIT] Registering Warehouse...")
    wh_data = {
        "name": "Dallas Logistics Depot",
        "businessName": "Dallas Hub Inc.",
        "address": "400 Freight Way, Dallas, TX 75201",
        "contact": "+1-214-555-7890",
        "email": "dallas@nexware.com",
        "taxPreference": "standard",
        "logo": "W"
    }
    code, res = make_request(f"{BASE_URL}/warehouses/", data=wh_data, headers=sa_headers, method="POST")
    wh_id = res["data"]["_id"]
    
    print("[INIT] Creating items for billing/inventory tests...")
    item_data = {
        "name": "Industrial Steel Pipes",
        "category": "Tools",
        "sku": f"SKU-PIPE-{timestamp}",
        "price": 50.0,
        "stock": 100,
        "unit": "pcs",
        "taxCategory": "normal",
        "warehouseId": wh_id
    }
    code, res = make_request(f"{BASE_URL}/items/", data=item_data, headers=sa_headers, method="POST")
    item_id = res["data"].get("id") or res["data"].get("_id")

    # Create users with different roles
    roles_list = ["admin", "manager", "staff", "employee"]
    users = {}
    
    for r in roles_list:
        print(f"[INIT] Creating workforce user for role '{r}'...")
        u_email = f"user_{r}_{timestamp}@nexware.com"
        u_password = "UserPassword123!"
        u_data = {
            "name": f"User {r.capitalize()}",
            "email": u_email,
            "password": u_password,
            "role": r,
            "warehouseId": wh_id
        }
        code, res = make_request(f"{BASE_URL}/workforce/", data=u_data, headers=sa_headers, method="POST")
        if code != 201:
            print(f"Failed to create workforce user for {r}: {code} - {res}")
            continue
            
        # Log in as this user to get token
        code, login_res = make_request(f"{BASE_URL}/auth/login", data={"email": u_email, "password": u_password}, method="POST")
        users[r] = {
            "headers": {"Authorization": f"Bearer {login_res['data']['access_token']}"},
            "id": login_res["data"]["user"]["id"]
        }

    # Add Super Admin to users mapping
    users["super_admin"] = {"headers": sa_headers, "id": "sa"}

    # We will test specific endpoints for permission checking
    test_cases = [
        # (Role, Endpoint, Method, Payload, Expected Code)
        
        # 1. Billing List/Detail permissions
        ("super_admin", "/billing/", "GET", None, 200),
        ("admin", "/billing/", "GET", None, 200),
        ("manager", "/billing/", "GET", None, 200),
        ("staff", "/billing/", "GET", None, 200),
        ("employee", "/billing/", "GET", None, 403), # Employee has no billing view permission
        
        # 2. Billing Create permissions
        ("staff", "/billing/", "POST", {
            "warehouseId": wh_id,
            "customer": "Texas Ironworks Ltd.",
            "items": [{"id": item_id, "name": "Industrial Steel Pipes", "qty": 1, "price": 50.0, "taxCategory": "normal", "taxRate": 0.05}],
            "subtotal": 50.0, "tax": 2.50, "total": 52.50, "notes": "Staff billing"
        }, 201),
        ("employee", "/billing/", "POST", {
            "warehouseId": wh_id,
            "customer": "Texas Ironworks Ltd.",
            "items": [{"id": item_id, "name": "Industrial Steel Pipes", "qty": 1, "price": 50.0, "taxCategory": "normal", "taxRate": 0.05}],
            "subtotal": 50.0, "tax": 2.50, "total": 52.50, "notes": "Employee billing"
        }, 403), # Employee has no billing:create

        # 3. Analytics & Reports view permissions
        ("super_admin", "/analytics/dashboard", "GET", None, 200),
        ("admin", "/analytics/dashboard", "GET", None, 200),
        ("employee", "/analytics/dashboard", "GET", None, 200), # Employee has dashboard:view

        ("super_admin", "/analytics/revenue", "GET", None, 200),
        ("admin", "/analytics/revenue", "GET", None, 200),
        ("manager", "/analytics/revenue", "GET", None, 200),
        ("staff", "/analytics/revenue", "GET", None, 403), # Staff has reports:view = False
        ("employee", "/analytics/revenue", "GET", None, 403), # Employee has reports:view = False

        # 4. Audit Log access
        ("super_admin", "/audit-logs/", "GET", None, 200),
        ("admin", "/audit-logs/", "GET", None, 200),
        ("manager", "/audit-logs/", "GET", None, 403), # Manager has audit:view = False
        ("staff", "/audit-logs/", "GET", None, 403), # Staff has audit:view = False
        ("employee", "/audit-logs/", "GET", None, 403), # Employee has audit:view = False
    ]

    print("\n--------------------------------------------------")
    print(" Running Permission Enforcement Test Cases...")
    print("--------------------------------------------------")
    
    passed_count = 0
    failed_count = 0
    
    for role, endpoint, method, payload, expected in test_cases:
        headers = users[role]["headers"]
        url = f"{BASE_URL}{endpoint}"
        code, res = make_request(url, data=payload, headers=headers, method=method)
        
        status = "PASSED" if code == expected else "FAILED"
        if status == "PASSED":
            passed_count += 1
            print(f"[OK] [{status}] Role: {role:<12} | {method} {endpoint:<30} -> Status: {code} (Expected: {expected})")
        else:
            failed_count += 1
            print(f"[ERR] [{status}] Role: {role:<12} | {method} {endpoint:<30} -> Status: {code} (Expected: {expected})")
            print(f"    Response: {res}")

    print("\n--------------------------------------------------")
    print(f" Results: {passed_count} Passed, {failed_count} Failed.")
    print("--------------------------------------------------")
    
    if failed_count == 0:
        print("[SUCCESS] ALL API PERMISSION TESTS PASSED SUCCESSFULLY!")
    else:
        print("[WARN] SOME TESTS FAILED. PLEASE AUDIT PATHS.")

if __name__ == "__main__":
    # Wait for server to start if needed
    time.sleep(1)
    import asyncio
    asyncio.run(test_permissions())
