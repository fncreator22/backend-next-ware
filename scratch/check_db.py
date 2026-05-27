import os
import sys
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
    print("Database Collection Counts:")
    for col_name in collections:
        col = db[col_name]
        print(f" - {col_name}: {col.count_documents({})}")
        
if __name__ == "__main__":
    main()
