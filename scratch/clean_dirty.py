from pymongo import MongoClient

def clean():
    client = MongoClient("mongodb://localhost:27017")
    db = client["wareops_erp_db"]
    # Clean stress test tenant database collections first
    stress_user = db.users.find_one({"email": "stress_admin_qa@nexware.com"})
    if stress_user:
        tenant_id = stress_user.get("tenant_id")
        db.inventory_items.delete_many({"tenant_id": tenant_id})
        db.bills.delete_many({"tenant_id": tenant_id})
        db.audit_logs.delete_many({"tenant_id": tenant_id})
        db.warehouses.delete_many({"ownerId": stress_user["_id"]})
        print("Cleaned up stress test tenant data.")
        
    db.users.delete_many({"email": {"$in": ["p2admin@nexware.com", "p2manager@nexware.com", "stress_admin_qa@nexware.com"]}})
    query = {"$or": [{"unit": {"$exists": False}}, {"tax_category": {"$exists": False}}]}
    count = db.inventory_items.count_documents(query)
    print(f"Found {count} malformed documents.")
    if count > 0:
        res = db.inventory_items.delete_many(query)
        print(f"Successfully deleted {res.deleted_count} malformed items.")
    client.close()

if __name__ == "__main__":
    clean()
