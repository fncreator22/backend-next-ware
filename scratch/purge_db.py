import os
from pymongo import MongoClient

def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client["wareops_erp_db"]
    collections = [
        "users",
        "warehouses",
        "sessions",
        "audit_logs",
        "inventory_items",
        "bills",
        "table_schemas",
        "table_rows"
    ]
    print("Pre-Purge Collection Audit:")
    for col_name in collections:
        col = db[col_name]
        print(f" - {col_name}: {col.count_documents({})} docs")
        
    print("\nPurging all collections...")
    for col_name in collections:
        col = db[col_name]
        res = col.delete_many({})
        print(f" - Safely purged {res.deleted_count} records from '{col_name}'")

    print("\nVerifying index preservation:")
    for col_name in collections:
        col = db[col_name]
        indices = list(col.list_indexes())
        print(f" - '{col_name}' has {len(indices)} indexes: {[idx['name'] for idx in indices]}")

if __name__ == "__main__":
    main()
