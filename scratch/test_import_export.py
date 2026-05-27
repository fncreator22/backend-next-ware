import os
import json
import subprocess
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
    
    print("Pre-test database checks...")
    for col_name in collections:
        col = db[col_name]
        count = col.count_documents({})
        assert count == 0, f"Collection '{col_name}' has docs, must be empty for reset test."
        
    backup_file = "scratch/empty_backup_test.json"
    if os.path.exists(backup_file):
        os.remove(backup_file)
        
    print("\nRunning automated command-line backup on clean database...")
    # Execute python db_maintenance.py backup -f scratch/empty_backup_test.json
    res_backup = subprocess.run(
        ["python", "db_maintenance.py", "backup", "-f", backup_file],
        capture_output=True,
        text=True
    )
    
    print(res_backup.stdout)
    print(res_backup.stderr)
    assert res_backup.returncode == 0, "Backup script failed to execute!"
    assert os.path.exists(backup_file), "Backup file was not created!"
    
    print("Verifying empty backup structure...")
    with open(backup_file, "r") as f:
        data = json.load(f)
        
    for col_name in collections:
        assert col_name in data, f"Missing '{col_name}' key in backup JSON."
        assert isinstance(data[col_name], list), f"'{col_name}' key must map to a list."
        assert len(data[col_name]) == 0, f"'{col_name}' list must be empty."
    print("SUCCESS: Backup file has correct clean-slate JSON structure!")
    
    print("\nRunning automated command-line restore from empty backup...")
    # Execute python db_maintenance.py restore -f scratch/empty_backup_test.json
    res_restore = subprocess.run(
        ["python", "db_maintenance.py", "restore", "-f", backup_file],
        capture_output=True,
        text=True
    )
    
    print(res_restore.stdout)
    print(res_restore.stderr)
    assert res_restore.returncode == 0, "Restore script failed to execute!"
    
    print("Verifying database remains clean and indexes are preserved...")
    for col_name in collections:
        col = db[col_name]
        assert col.count_documents({}) == 0, f"Collection '{col_name}' got docs, must remain empty."
        indices = list(col.list_indexes())
        assert len(indices) >= 1, f"Missing indexes on collection '{col_name}'!"
        print(f" - '{col_name}': 0 docs, indexes: {[idx['name'] for idx in indices]}")
        
    print("\nSUCCESS: Database backup & restore empty-state integrity fully validated!")

if __name__ == "__main__":
    main()
