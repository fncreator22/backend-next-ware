import logging
from typing import Optional
from bson import ObjectId
from fastapi import Depends
from src.database import get_db

logger = logging.getLogger("wareops_erp.modules.dynamic_tables.repository")


class DynamicTableRepository:
    def __init__(self, db=Depends(get_db)):
        self.db = db
        self.schema_collection = db.table_schemas
        self.rows_collection = db.table_rows

    # --- TABLE SCHEMAS COLLECTION DRIVERS ---

    async def find_schema_by_id(self, table_id: str, tenant_id: str) -> dict:
        """Fetch custom table schema metadata from db matching tenant isolation limits."""
        try:
            query = {"_id": ObjectId(table_id), "tenant_id": tenant_id}
        except Exception:
            query = {"_id": table_id, "tenant_id": tenant_id}
        doc = await self.schema_collection.find_one(query)
        return doc

    async def find_schema_by_name_and_warehouse(self, name: str, warehouse_id: Optional[str], tenant_id: str) -> dict:
        """Query schema by warehouse boundaries and table name to assert uniqueness constraints."""
        query = {
            "name": name,
            "warehouse_id": warehouse_id,
            "tenant_id": tenant_id
        }
        doc = await self.schema_collection.find_one(query)
        return doc

    async def create_schema(self, doc: dict) -> dict:
        """Register a new custom operational table schema validation registry."""
        res = await self.schema_collection.insert_one(doc)
        doc["_id"] = str(res.inserted_id)
        return doc

    async def update_schema(self, table_id: str, tenant_id: str, data: dict) -> dict:
        """Update schema metadata configurations."""
        try:
            query = {"_id": ObjectId(table_id), "tenant_id": tenant_id}
        except Exception:
            query = {"_id": table_id, "tenant_id": tenant_id}
        await self.schema_collection.update_one(query, {"$set": data})
        return await self.find_schema_by_id(table_id, tenant_id)

    async def delete_schema(self, table_id: str, tenant_id: str) -> bool:
        """Remove a custom table registry."""
        try:
            query = {"_id": ObjectId(table_id), "tenant_id": tenant_id}
        except Exception:
            query = {"_id": table_id, "tenant_id": tenant_id}
        res = await self.schema_collection.delete_one(query)
        return res.deleted_count > 0

    async def list_schemas(self, query: dict) -> list[dict]:
        """Fetch custom table schemas matching active queries."""
        cursor = self.schema_collection.find(query)
        return await cursor.to_list(length=1000)

    # --- TABLE ROWS COLLECTION DRIVERS ---

    async def find_row_by_id(self, row_id: str, tenant_id: str) -> dict:
        """Query specific dynamic table row document."""
        try:
            query = {"_id": ObjectId(row_id), "tenant_id": tenant_id}
        except Exception:
            query = {"_id": row_id, "tenant_id": tenant_id}
        doc = await self.rows_collection.find_one(query)
        return doc

    async def create_row(self, doc: dict) -> dict:
        """Append validated custom row documents into database."""
        res = await self.rows_collection.insert_one(doc)
        doc["_id"] = str(res.inserted_id)
        return doc

    async def update_row(self, row_id: str, tenant_id: str, data: dict) -> dict:
        """Update validated custom row fields."""
        try:
            query = {"_id": ObjectId(row_id), "tenant_id": tenant_id}
        except Exception:
            query = {"_id": row_id, "tenant_id": tenant_id}
        await self.rows_collection.update_one(query, {"$set": {"data": data}})
        return await self.find_row_by_id(row_id, tenant_id)

    async def delete_row(self, row_id: str, tenant_id: str) -> bool:
        """Delete custom row document from the collection."""
        try:
            query = {"_id": ObjectId(row_id), "tenant_id": tenant_id}
        except Exception:
            query = {"_id": row_id, "tenant_id": tenant_id}
        res = await self.rows_collection.delete_one(query)
        return res.deleted_count > 0

    async def list_rows_by_table(self, table_id: str, tenant_id: str) -> list[dict]:
        """Retrieve dynamic table rows matching table id."""
        cursor = self.rows_collection.find({"table_id": table_id, "tenant_id": tenant_id}).sort("created_at", 1)
        return await cursor.to_list(length=1000)

    async def list_rows_by_table_and_page(self, table_id: str, page_number: int, tenant_id: str) -> list[dict]:
        """Retrieve dynamic table rows matching table id and page number."""
        query = {
            "table_id": table_id,
            "tenant_id": tenant_id,
            "page_number": {"$in": [page_number, None]} if page_number == 1 else page_number
        }
        cursor = self.rows_collection.find(query).sort("created_at", 1)
        return await cursor.to_list(length=1000)

    async def delete_all_rows_for_table(self, table_id: str, tenant_id: str) -> int:
        """Cascade deletes all row documents belonging to a schema."""
        res = await self.rows_collection.delete_many({"table_id": table_id, "tenant_id": tenant_id})
        return res.deleted_count
