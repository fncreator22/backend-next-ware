import asyncio
import logging
from pymongo.errors import OperationFailure
from src.database import db_conn
from src.modules.realtime.websocket_manager import manager

logger = logging.getLogger("wareops_erp.modules.realtime.change_streams")

# Global status tracking if Change Streams are active
change_streams_active = False


async def watch_collection(collection_name: str, event_type: str):
    """Asynchronously monitor change stream for a specific MongoDB collection."""
    global change_streams_active
    db = db_conn.db
    if db is None:
        return

    collection = db[collection_name]
    logger.info(f"Setting up Change Stream listener for: {collection_name}")
    try:
        async with collection.watch() as stream:
            change_streams_active = True
            async for change in stream:
                op_type = change.get("operationType")
                if op_type not in ["insert", "update", "replace", "delete"]:
                    continue

                full_doc = change.get("fullDocument")
                if not full_doc:
                    doc_id = change.get("documentKey", {}).get("_id")
                    if doc_id:
                        full_doc = await collection.find_one({"_id": doc_id})

                if full_doc:
                    full_doc = normalize_doc(full_doc)
                    tenant_id = full_doc.get("tenant_id")
                    warehouse_id = full_doc.get("warehouse_id")

                    if tenant_id:
                        await manager.broadcast_event(
                            tenant_id=tenant_id,
                            event_type=event_type,
                            data=full_doc,
                            warehouse_id=warehouse_id
                        )
    except OperationFailure as e:
        logger.warning(
            f"MongoDB Change Streams not supported on {collection_name}: {e.details.get('errmsg', str(e))}. "
            "Falling back to explicit Manual Pub-Sub event dispatch broker."
        )
        change_streams_active = False
    except Exception as e:
        logger.error(f"Error in Change Stream listener for {collection_name}: {e}")
        change_streams_active = False


def normalize_doc(doc: dict) -> dict:
    """Normalize BSON document objects into standard JSON-serializable types."""
    from bson import ObjectId
    from bson.decimal128 import Decimal128
    from decimal import Decimal
    
    if not doc:
        return doc
        
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if "id" not in doc and "_id" in doc:
        doc["id"] = doc["_id"]

    for k, v in doc.items():
        if isinstance(v, Decimal128):
            doc[k] = float(v.to_decimal())
        elif isinstance(v, Decimal):
            doc[k] = float(v)
        elif isinstance(v, ObjectId):
            doc[k] = str(v)
        elif isinstance(v, list):
            doc[k] = [normalize_doc(item) if isinstance(item, dict) else item for item in v]
        elif isinstance(v, dict):
            doc[k] = normalize_doc(v)
            
    return doc


async def start_realtime_change_listeners():
    """Startup change stream watch loops for core collections in background."""
    asyncio.create_task(watch_collection("inventory_items", "inventory_change"))
    asyncio.create_task(watch_collection("bills", "billing_completion"))
    asyncio.create_task(watch_collection("audit_logs", "audit_event"))
    asyncio.create_task(watch_collection("users", "workforce_activity"))
    logger.info("Realtime background change streams initialized.")
