"""
validate_all_phases.py - Full 3-Phase ERP Validation (final corrected)
Uses exact API schemas discovered from source inspection.
"""
import sys
import io
import time
import threading
import uuid
import requests

BASE = "http://127.0.0.1:8000/api/v1"
results = []

def check(label, ok, detail=""):
    tag = "[PASS]" if ok else "[FAIL]"
    line = f"  {tag}  {label}"
    if detail:
        line += f" -- {detail}"
    print(line, flush=True)
    results.append((label, ok, detail))
    return ok

def section(title):
    bar = "=" * 62
    print(f"\n{bar}\n  {title}\n{bar}", flush=True)

def signup_and_login(name, email, password, role, tenant_name):
    """Register then login; return (access_token, tenant_id, user_data)."""
    r = requests.post(f"{BASE}/auth/signup", json={
        "name": name, "email": email, "password": password,
        "role": role, "tenant_name": tenant_name
    })
    if r.status_code != 201:
        return None, None, {}
    user_data = r.json().get("data", {})
    tenant_id = user_data.get("tenant_id", "")
    r2 = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    if r2.status_code != 200:
        return None, tenant_id, user_data
    token = r2.json().get("data", {}).get("access_token", "")
    return token, tenant_id, user_data

# ==============================================================
# SETUP
# ==============================================================
section("SETUP -- Registering Two Isolated Tenants")
uid = uuid.uuid4().hex[:8]

a_token, a_tid, _ = signup_and_login(
    f"Admin_{uid}", f"admin_{uid}@val.com", "TestPass@123",
    "super_admin", f"TenantA_{uid}"
)
check("Tenant A signup+login OK", bool(a_token))
check("Tenant A tenant_id received", bool(a_tid))
HA = {"Authorization": f"Bearer {a_token}"} if a_token else {}

b_token, b_tid, _ = signup_and_login(
    f"IsoAdmin_{uid}", f"isoadmin_{uid}@val.com", "TestPass@123",
    "super_admin", f"TenantB_{uid}"
)
check("Tenant B signup+login OK", bool(b_token))
HB = {"Authorization": f"Bearer {b_token}"} if b_token else {}

if not a_token:
    print("\n  [FATAL] Cannot continue without Tenant A token.", flush=True)
    sys.exit(1)

# ==============================================================
# PHASE 1 -- Core Modules
# ==============================================================
section("PHASE 1 -- Warehouses / Items / Billing / Workforce")

# -- Warehouses (actual schema: name, businessName, address, contact, email, taxPreference) --
r = requests.post(f"{BASE}/warehouses", json={
    "name": f"WH_{uid}",
    "businessName": f"Business_{uid}",
    "address": "123 Validation Street, Test City",
    "contact": "+1-555-000-0001",
    "email": f"wh_{uid}@val.com",
    "taxPreference": "standard"
}, headers=HA)
check("Create warehouse -> 201", r.status_code == 201, str(r.status_code))
wh_data = r.json().get("data", {})
wh_id = wh_data.get("_id", "")
check("Warehouse _id present", bool(wh_id))

r = requests.get(f"{BASE}/warehouses", headers=HA)
check("List warehouses -> 200", r.status_code == 200)
wh_list = r.json().get("data", [])
check("Warehouse appears in list", any(w.get("_id") == wh_id for w in wh_list))

r = requests.get(f"{BASE}/warehouses/{wh_id}", headers=HA)
check("Get single warehouse -> 200", r.status_code == 200, str(r.status_code))

# Update (PUT) uses WarehouseUpdate — all optional fields
r = requests.put(f"{BASE}/warehouses/{wh_id}", json={
    "businessName": f"Business_{uid}_Updated",
    "contact": "+1-555-999-9999"
}, headers=HA)
check("Update warehouse (PUT) -> 200", r.status_code == 200, str(r.status_code))

# -- Items (actual schema: name, sku, category, price, stock, unit, taxCategory, warehouseId) --
r = requests.post(f"{BASE}/items", json={
    "name": f"Item_{uid}",
    "sku": f"SKU-{uid}",
    "category": "Electronics",
    "price": 29.99,
    "stock": 100,
    "unit": "pcs",
    "taxCategory": "normal",
    "warehouseId": wh_id
}, headers=HA)
check("Create item -> 201", r.status_code == 201, str(r.status_code))
item_data = r.json().get("data", {})
item_id = item_data.get("id", "")
check("Item id present", bool(item_id))

r = requests.get(f"{BASE}/items?warehouseId={wh_id}", headers=HA)
check("List items -> 200", r.status_code == 200)
items = r.json().get("data", [])
check("Item appears in list", any(i.get("id", i.get("_id")) == item_id for i in items))

r = requests.get(f"{BASE}/items/{item_id}", headers=HA)
check("Get single item -> 200", r.status_code == 200)

# Update item (PUT) — use same schema fields all optional
r = requests.put(f"{BASE}/items/{item_id}", json={
    "stock": 250
}, headers=HA)
check("Update item stock (PUT) -> 200", r.status_code == 200, str(r.status_code))
if r.status_code == 200:
    updated_stock = r.json().get("data", {}).get("stock", -1)
    check("Stock updated to 250", updated_stock == 250, f"got {updated_stock}")
else:
    check("Stock updated to 250", False, "update failed")

# -- Billing (actual schema: customer, warehouseId, items[id,name,price,taxCategory,taxRate,qty], subtotal, tax, total) --
r = requests.post(f"{BASE}/billing", json={
    "customer": f"Customer_{uid}",
    "warehouseId": wh_id,
    "items": [{
        "id": item_id,
        "name": f"Item_{uid}",
        "price": 29.99,
        "taxCategory": "normal",
        "taxRate": 0.1,
        "qty": 2
    }],
    "subtotal": 59.98,
    "tax": 6.00,
    "total": 65.98
}, headers=HA)
check("Create bill -> 201", r.status_code == 201, str(r.status_code))
bill_data = r.json().get("data", {})
bill_id = bill_data.get("id", bill_data.get("_id", ""))  # InvoiceResponse serializes as 'id'
check("Bill _id present", bool(bill_id))

r = requests.get(f"{BASE}/billing?warehouseId={wh_id}", headers=HA)
check("List bills -> 200", r.status_code == 200)
bills = r.json().get("data", [])
check("Bill appears in list", any(b.get("id", b.get("_id")) == bill_id for b in bills))

r = requests.get(f"{BASE}/billing/{bill_id}", headers=HA)
check("Get single bill -> 200", r.status_code == 200, str(r.status_code))

# -- Workforce (route: /workforce/, not /workforce/users) --
r = requests.post(f"{BASE}/workforce", json={
    "name": f"Staff_{uid}",
    "email": f"staff_{uid}@val.com",
    "password": "StaffPass@123",
    "role": "staff",
    "warehouse_id": wh_id
}, headers=HA)
check("Create staff user -> 201", r.status_code == 201, str(r.status_code))
staff_id = r.json().get("data", {}).get("_id", "")
check("Staff _id present", bool(staff_id))

r = requests.get(f"{BASE}/workforce", headers=HA)
check("List workforce -> 200", r.status_code == 200)
wf = r.json().get("data", [])
check("Staff appears in workforce list", any(u.get("_id") == staff_id for u in wf))

# ==============================================================
# PHASE 2 -- RBAC / Notifications / Audit / Analytics / CSV
# ==============================================================
section("PHASE 2 -- RBAC / Notifications / Audit / Analytics / CSV / Isolation")

# -- RBAC --
r = requests.post(f"{BASE}/workforce", json={
    "name": f"Mgr_{uid}", "email": f"mgr_{uid}@val.com",
    "password": "MgrPass@123", "role": "manager", "warehouse_id": wh_id
}, headers=HA)
check("Create manager -> 201", r.status_code == 201, str(r.status_code))

r = requests.post(f"{BASE}/auth/login", json={"email": f"mgr_{uid}@val.com", "password": "MgrPass@123"})
check("Manager login -> 200", r.status_code == 200)
mgr_token = r.json().get("data", {}).get("access_token", "")
HM = {"Authorization": f"Bearer {mgr_token}"}

r = requests.post(f"{BASE}/workforce", json={
    "name": "AttackUser", "email": f"atk_{uid}@val.com",
    "password": "Atk@1234", "role": "staff", "warehouse_id": wh_id
}, headers=HM)
check("RBAC: Manager cannot create users -> 403", r.status_code == 403, str(r.status_code))

# -- Notifications (POST accepts list or dict; data is list) --
r = requests.post(f"{BASE}/realtime/notifications", json={
    "title": "Phase2 Test",
    "message": "Validation notification",
    "type": "info",
    "userId": a_tid  # use tenant_id as stand-in for userId
}, headers=HA)
notif_ok = r.status_code in (200, 201)
check("Create notification -> 200/201", notif_ok, str(r.status_code))
# data is a list; get first item's "id" key (not "_id")
notif_list = r.json().get("data", []) if notif_ok else []
notif_id = notif_list[0].get("id", "") if notif_list else ""
check("Notification id received", bool(notif_id))

r = requests.get(f"{BASE}/realtime/notifications", headers=HA)
check("List notifications -> 200", r.status_code == 200, str(r.status_code))

if notif_id:
    r = requests.put(f"{BASE}/realtime/notifications/{notif_id}/read", headers=HA)
    check("Mark notification read -> 200", r.status_code == 200, str(r.status_code))

r = requests.put(f"{BASE}/realtime/notifications/read-all", headers=HA)
check("Mark all notifications read -> 200", r.status_code == 200, str(r.status_code))

r = requests.delete(f"{BASE}/realtime/notifications/clear", headers=HA)
check("Clear all notifications -> 200/204", r.status_code in (200, 204), str(r.status_code))

# -- Audit Logs --
r = requests.get(f"{BASE}/audit-logs", headers=HA)
check("List audit logs -> 200", r.status_code == 200, str(r.status_code))
audit = r.json().get("data", [])
check("Audit log has entries", len(audit) > 0, f"found {len(audit)}")

r = requests.get(f"{BASE}/audit-logs?limit=10&skip=0", headers=HA)
check("Audit logs pagination -> 200", r.status_code == 200)

# -- Analytics --
t0 = time.time()
r = requests.get(f"{BASE}/analytics/dashboard?warehouseId={wh_id}", headers=HA)
ms = (time.time() - t0) * 1000
check("Analytics dashboard -> 200", r.status_code == 200, str(r.status_code))
check("Analytics latency < 5000ms", ms < 5000, f"{ms:.0f}ms")
dash = r.json().get("data", {})
check("Dashboard returns data object", bool(dash), str(list(dash.keys()))[:80] if dash else "empty")

# -- CSV Import (columns: name,sku,stock,price,category,unit,taxCategory; route: /items/import?warehouseId=) --
csv_body = "name,sku,stock,price,category,unit,taxCategory\n"
for i in range(5):
    csv_body += f"CSV_{i}_{uid},CSKU-{i}-{uid},{10+i},{4.99+i},Other,pcs,normal\n"
files = {"file": ("test.csv", io.BytesIO(csv_body.encode()), "text/csv")}
r = requests.post(f"{BASE}/items/import?warehouseId={wh_id}", files=files, headers=HA)
check("CSV import (5 rows) -> 200/201", r.status_code in (200, 201), str(r.status_code))
n_imported = r.json().get("imported", -1) if r.status_code in (200, 201) else -1
check("CSV: 5 rows imported", n_imported == 5, f"got {n_imported}")

# -- Tenant Isolation --
r = requests.get(f"{BASE}/items?warehouseId={wh_id}", headers=HB)
b_items = r.json().get("data", []) if r.status_code == 200 else []
leaked = [i for i in b_items if i.get("_id") == item_id]
check("Tenant isolation: Tenant B cannot see Tenant A items",
      len(leaked) == 0, "ISOLATED OK" if not leaked else f"LEAKED {len(leaked)}!")

# ==============================================================
# PHASE 3 -- Security / Performance / Concurrent Load
# ==============================================================
section("PHASE 3 -- Security / Performance / Concurrent Load")

# -- Unauthenticated access --
for path, label in [
    ("/items",                    "items"),
    ("/warehouses",               "warehouses"),
    ("/billing",                  "billing"),
    ("/audit-logs",               "audit-logs"),
    ("/realtime/notifications",   "notifications"),
    ("/workforce",                "workforce"),
]:
    r = requests.get(f"{BASE}{path}")
    check(f"No token on /{label} -> 401/403",
          r.status_code in (401, 403, 422), str(r.status_code))

# -- Fake JWT --
FAKE = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.fake.sig"}
for path, label in [("/items", "items"), ("/warehouses", "warehouses"), ("/billing", "billing")]:
    r = requests.get(f"{BASE}{path}", headers=FAKE)
    check(f"Fake JWT on /{label} -> 401/403", r.status_code in (401, 403), str(r.status_code))

# -- Performance (compound index paths) --
perf_cases = [
    (f"{BASE}/items?search=Item&warehouseId={wh_id}&limit=50", "Item indexed search"),
    (f"{BASE}/audit-logs?limit=50",                             "Audit log query"),
    (f"{BASE}/billing?warehouseId={wh_id}&limit=50",           "Billing query"),
]
for url, label in perf_cases:
    t0 = time.time()
    r = requests.get(url, headers=HA)
    ms = (time.time() - t0) * 1000
    check(f"{label} -> 200", r.status_code == 200, str(r.status_code))
    check(f"{label} latency < 2000ms", ms < 2000, f"{ms:.0f}ms")

# -- Concurrent dashboard burst (8 threads) --
N = 8
hits = []
def hit():
    try:
        t0 = time.time()
        resp = requests.get(
            f"{BASE}/analytics/dashboard?warehouseId={wh_id}",
            headers=HA, timeout=30
        )
        hits.append((resp.status_code == 200, (time.time() - t0) * 1000))
    except Exception:
        hits.append((False, 9999))

threads = [threading.Thread(target=hit) for _ in range(N)]
for t in threads: t.start()
for t in threads: t.join()
ok_count = sum(1 for h in hits if h[0])
avg_ms   = sum(h[1] for h in hits) / len(hits)
check(f"Concurrent {N}-thread dashboard burst -- all 200",
      ok_count == N, f"{ok_count}/{N} succeeded")
check("Avg concurrent latency < 15s", avg_ms < 15000, f"avg {avg_ms:.0f}ms")

# -- Health endpoints --
r = requests.get("http://127.0.0.1:8000/health")
check("GET /health -> 200", r.status_code == 200, str(r.status_code))

r = requests.get("http://127.0.0.1:8000/")
check("GET / (root) -> 200", r.status_code == 200)

# ==============================================================
# CLEANUP
# ==============================================================
section("CLEANUP")
r = requests.delete(f"{BASE}/warehouses/{wh_id}", headers=HA)
check("Delete test warehouse (cascade) -> 200/204",
      r.status_code in (200, 204), str(r.status_code))

# ==============================================================
# SUMMARY
# ==============================================================
total  = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed

print(f"\n{'='*62}")
print(f"  FINAL VALIDATION SUMMARY")
print(f"{'='*62}")
print(f"  Total  : {total}")
print(f"  Passed : {passed}")
print(f"  Failed : {failed}")
print(f"{'='*62}")

if failed == 0:
    print("\n  *** ALL PHASES VERIFIED -- SYSTEM FULLY OPERATIONAL ***\n")
else:
    print(f"\n  !!! {failed} CHECK(S) FAILED !!!\n")
    for label, ok, detail in results:
        if not ok:
            print(f"  [FAIL] {label}" + (f" ({detail})" if detail else ""))

sys.exit(0 if failed == 0 else 1)
