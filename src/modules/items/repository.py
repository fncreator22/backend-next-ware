import logging
from bson import ObjectId
from bson.decimal128 import Decimal128
from decimal import Decimal
from fastapi import Depends
from src.database import get_db

logger = logging.getLogger("wareops_erp.modules.items.repository")


class ItemRepository:
    def __init__(self, db=Depends(get_db)):
        self.db = db
        self.collection = db.inventory_items

    def _convert_decimal128_to_decimal(self, doc: dict) -> dict:
        """Utility to convert BSON Decimal128 fields back to Python Decimal."""
        if not doc:
            return doc
        doc = dict(doc)
        if "price" in doc and isinstance(doc["price"], Decimal128):
            doc["price"] = doc["price"].to_decimal()
        return doc

    def _convert_decimal_to_decimal128(self, data: dict) -> dict:
        """Utility to convert Python Decimal fields to BSON Decimal128 for database insert."""
        data = dict(data)
        if "price" in data and isinstance(data["price"], Decimal):
            data["price"] = Decimal128(data["price"])
        return data

    async def find_by_id(self, item_id: str, tenant_id: str) -> dict:
        """Query an item by primary key and tenant boundaries."""
        try:
            query = {"_id": ObjectId(item_id), "tenant_id": tenant_id}
        except Exception:
            query = {"_id": item_id, "tenant_id": tenant_id}
        doc = await self.collection.find_one(query)
        if doc:
            doc["_id"] = str(doc["_id"])
            return self._convert_decimal128_to_decimal(doc)
        return None

    async def find_by_sku_and_warehouse(self, sku: str, warehouse_id: str, tenant_id: str) -> dict:
        """Query item by compound natural key scoped to tenant space."""
        doc = await self.collection.find_one({
            "sku": sku,
            "warehouse_id": warehouse_id,
            "tenant_id": tenant_id
        })
        if doc:
            doc["_id"] = str(doc["_id"])
            return self._convert_decimal128_to_decimal(doc)
        return None

    async def create_item(self, doc: dict) -> dict:
        """Insert new inventory document into the collection."""
        insert_data = self._convert_decimal_to_decimal128(doc)
        res = await self.collection.insert_one(insert_data)
        doc["_id"] = str(res.inserted_id)
        if "price" in doc and isinstance(doc["price"], Decimal128):
            doc["price"] = doc["price"].to_decimal()
        return doc

    async def update_item(self, item_id: str, tenant_id: str, data: dict) -> dict:
        """Update inventory document parameters."""
        update_data = self._convert_decimal_to_decimal128(data)
        try:
            query = {"_id": ObjectId(item_id), "tenant_id": tenant_id}
        except Exception:
            query = {"_id": item_id, "tenant_id": tenant_id}

        await self.collection.update_one(query, {"$set": update_data})
        return await self.find_by_id(item_id, tenant_id)

    async def delete_item(self, item_id: str, tenant_id: str) -> bool:
        """Remove item from active inventory mapping."""
        try:
            query = {"_id": ObjectId(item_id), "tenant_id": tenant_id}
        except Exception:
            query = {"_id": item_id, "tenant_id": tenant_id}

        res = await self.collection.delete_one(query)
        return res.deleted_count > 0

    async def list_items(self, query: dict, skip: int = 0, limit: int = 100) -> list[dict]:
        """Fetch items matching query search filters with pagination boundaries."""
        cursor = self.collection.find(query).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)
        res_items = []
        for doc in items:
            doc["_id"] = str(doc["_id"])
            res_items.append(self._convert_decimal128_to_decimal(doc))
        return res_items

    async def count_items(self, query: dict) -> int:
        """Count total items matching active query filters."""
        return await self.collection.count_documents(query)
