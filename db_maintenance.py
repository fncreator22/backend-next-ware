import os
import sys
import json
import logging
import argparse
from typing import Any
from datetime import datetime
from bson import ObjectId, Decimal128
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("wareops_erp.db_maintenance")


# Helper to convert MongoDB documents to JSON-serializable structures
def mongo_to_json_helper(doc: Any) -> Any:
    if isinstance(doc, dict):
        return {k: mongo_to_json_helper(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [mongo_to_json_helper(v) for v in doc]
    elif isinstance(doc, ObjectId):
        return {"$oid": str(doc)}
    elif isinstance(doc, datetime):
        return {"$date": doc.isoformat()}
    elif isinstance(doc, Decimal128):
        return {"$decimal": str(doc)}
    return doc


# Helper to restore BSON structures from JSON-serializable dictionaries
def json_to_mongo_helper(data: Any) -> Any:
    if isinstance(data, dict):
        if "$oid" in data:
            return ObjectId(data["$oid"])
        if "$date" in data:
            return datetime.fromisoformat(data["$date"])
        if "$decimal" in data:
            return Decimal128(data["$decimal"])
        return {k: json_to_mongo_helper(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [json_to_mongo_helper(v) for v in data]
    return data


class DatabaseMaintenance:
    def __init__(self, mongodb_url="mongodb://localhost:27017", db_name="wareops_erp_db"):
        self.client = MongoClient(mongodb_url)
        self.db = self.client[db_name]
        self.collections = [
            "users",
            "warehouses",
            "sessions",
            "audit_logs",
            "inventory_items",
            "bills",
            "table_schemas",
            "table_rows"
        ]

    def backup(self, output_file: str) -> bool:
        """Backup all ERP database collections into a structured JSON file."""
        logger.info(f"Starting database backup to: {output_file}...")
        backup_data = {}

        try:
            for col_name in self.collections:
                col = self.db[col_name]
                docs = list(col.find({}))
                backup_data[col_name] = mongo_to_json_helper(docs)
                logger.info(f"Collection '{col_name}': Backed up {len(docs)} documents.")

            # Ensure parent directories exist
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)

            logger.info("Database backup completed successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return False

    def restore(self, input_file: str) -> bool:
        """Safely restore all ERP database collections from a JSON backup file."""
        logger.info(f"Starting database restoration from: {input_file}...")

        if not os.path.exists(input_file):
            logger.error(f"Input backup file does not exist: {input_file}")
            return False

        try:
            with open(input_file, "r", encoding="utf-8") as f:
                backup_data = json.load(f)

            # Clear and restore collection data
            for col_name in self.collections:
                if col_name not in backup_data:
                    logger.warning(f"Collection '{col_name}' missing from backup file. Skipping.")
                    continue

                col = self.db[col_name]
                
                # Delete existing documents
                del_res = col.delete_many({})
                logger.info(f"Collection '{col_name}': Cleared {del_res.deleted_count} existing records.")

                # Insert backup documents
                raw_docs = backup_data[col_name]
                if raw_docs:
                    mongo_docs = json_to_mongo_helper(raw_docs)
                    ins_res = col.insert_many(mongo_docs)
                    logger.info(f"Collection '{col_name}': Restored {len(ins_res.inserted_ids)} records.")
                else:
                    logger.info(f"Collection '{col_name}': No records to restore.")

            logger.info("Database restoration completed successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return False

    def reset(self) -> bool:
        """Safely reset all ERP database collections after generating an automatic backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.getcwd(), "backups")
        auto_backup_file = os.path.join(backup_dir, f"auto_backup_{timestamp}.json")

        logger.info("Initiating database safe reset sequence...")
        
        # 1. Generate backup first to satisfy safety constraints
        backup_success = self.backup(auto_backup_file)
        if not backup_success:
            logger.error("Database backup failed. Safe reset aborted to prevent accidental data loss.")
            return False

        logger.info(f"Safe auto-backup successfully stored at: {auto_backup_file}")

        # 2. Reset collections
        try:
            for col_name in self.collections:
                col = self.db[col_name]
                res = col.delete_many({})
                logger.info(f"Collection '{col_name}': Safely cleared {res.deleted_count} records.")
            
            logger.info("Database successfully reset to a clean slate.")
            return True
        except Exception as e:
            logger.error(f"Failed to reset database: {e}")
            return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NexWare ERP Database Maintenance & Backup Utility")
    parser.add_argument("action", choices=["backup", "restore", "reset"], help="Maintenance action to execute")
    parser.add_argument("--file", "-f", help="Path to backup JSON file (required for backup/restore)")
    parser.add_argument("--url", default="mongodb://localhost:27017", help="MongoDB connection URL")
    parser.add_argument("--db", default="wareops_erp_db", help="Database name")

    args = parser.parse_args()
    maintenance = DatabaseMaintenance(mongodb_url=args.url, db_name=args.db)

    if args.action == "backup":
        if not args.file:
            logger.error("Error: --file argument is required for backup action.")
            sys.exit(1)
        success = maintenance.backup(args.file)
        sys.exit(0 if success else 1)

    elif args.action == "restore":
        if not args.file:
            logger.error("Error: --file argument is required for restore action.")
            sys.exit(1)
        success = maintenance.restore(args.file)
        sys.exit(0 if success else 1)

    elif args.action == "reset":
        # Double check confirmation
        print("WARNING: This will delete all records across all collections!")
        print("An automatic backup will be generated first.")
        confirm = input("Are you sure you want to proceed? (yes/no): ").strip().lower()
        if confirm == "yes":
            success = maintenance.reset()
            sys.exit(0 if success else 1)
        else:
            logger.info("Database reset cancelled by user.")
            sys.exit(0)
