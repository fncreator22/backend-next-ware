import logging
from bson import ObjectId
from bson.decimal128 import Decimal128
from decimal import Decimal
from fastapi import Depends
from src.database import get_db

logger = logging.getLogger("wareops_erp.modules.billing.repository")


class InvoiceRepository:
    def __init__(self, db=Depends(get_db)):
        self.db = db
        self.collection = db.bills

    def _convert_decimal128_to_decimal(self, doc: dict) -> dict:
        """Utility to convert BSON Decimal128 fields back to Python Decimal."""
        if not doc:
            return doc
        doc = dict(doc)
        for key in ["subtotal", "tax", "total"]:
            if key in doc and isinstance(doc[key], Decimal128):
                doc[key] = doc[key].to_decimal()

        if "items" in doc and isinstance(doc["items"], list):
            converted_items = []
            for item in doc["items"]:
                item_copy = dict(item)
                if "price" in item_copy and isinstance(item_copy["price"], Decimal128):
                    item_copy["price"] = item_copy["price"].to_decimal()
                if "tax_rate_snapshot" in item_copy and isinstance(item_copy["tax_rate_snapshot"], Decimal128):
                    item_copy["tax_rate_snapshot"] = item_copy["tax_rate_snapshot"].to_decimal()
                converted_items.append(item_copy)
            doc["items"] = converted_items

        if "tax_config_snapshot" in doc and isinstance(doc["tax_config_snapshot"], dict):
            tc = dict(doc["tax_config_snapshot"])
            for key in ["normal", "luxury"]:
                if key in tc and isinstance(tc[key], Decimal128):
                    tc[key] = tc[key].to_decimal()
            doc["tax_config_snapshot"] = tc

        return doc

    def _convert_decimal_to_decimal128(self, data: dict) -> dict:
        """Utility to convert Python Decimal fields to BSON Decimal128 for inserts."""
        data = dict(data)
        for key in ["subtotal", "tax", "total"]:
            if key in data and isinstance(data[key], Decimal):
                data[key] = Decimal128(data[key])

        if "items" in data and isinstance(data["items"], list):
            converted_items = []
            for item in data["items"]:
                item_copy = dict(item)
                if "price" in item_copy and isinstance(item_copy["price"], Decimal):
                    item_copy["price"] = Decimal128(item_copy["price"])
                if "tax_rate_snapshot" in item_copy and isinstance(item_copy["tax_rate_snapshot"], Decimal):
                    item_copy["tax_rate_snapshot"] = Decimal128(item_copy["tax_rate_snapshot"])
                converted_items.append(item_copy)
            data["items"] = converted_items

        if "tax_config_snapshot" in data and isinstance(data["tax_config_snapshot"], dict):
            tc = dict(data["tax_config_snapshot"])
            for key in ["normal", "luxury"]:
                if key in tc and isinstance(tc[key], Decimal):
                    tc[key] = Decimal128(tc[key])
            data["tax_config_snapshot"] = tc

        return data

    async def get_next_bill_no(self, tenant_id: str) -> str:
        """Compute the next sequential Bill number scoped under active tenant partition."""
        count = await self.collection.count_documents({"tenant_id": tenant_id})
        next_num = count + 1
        return f"INV-{next_num:04d}"

    async def find_by_id(self, bill_id: str, tenant_id: str) -> dict:
        """Query an invoice by primary key and tenant boundaries."""
        try:
            query = {"_id": ObjectId(bill_id), "tenant_id": tenant_id}
        except Exception:
            query = {"_id": bill_id, "tenant_id": tenant_id}
        doc = await self.collection.find_one(query)
        if doc:
            doc["_id"] = str(doc["_id"])
            return self._convert_decimal128_to_decimal(doc)
        return None

    async def create_invoice(self, doc: dict, session=None) -> dict:
        """Insert new invoice document into collection."""
        insert_data = self._convert_decimal_to_decimal128(doc)
        res = await self.collection.insert_one(insert_data, session=session)
        doc["_id"] = str(res.inserted_id)
        # Convert any Decimal128 types back to python decimal
        return self._convert_decimal128_to_decimal(doc)

    async def list_invoices(self, query: dict, skip: int = 0, limit: int = 100) -> list[dict]:
        """Fetch invoices matching query filters with sorting by created_at descending."""
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        bills = await cursor.to_list(length=limit)
        res_bills = []
        for doc in bills:
            doc["_id"] = str(doc["_id"])
            res_bills.append(self._convert_decimal128_to_decimal(doc))
        return res_bills

    async def count_invoices(self, query: dict) -> int:
        """Count total invoices matching active filters."""
        return await self.collection.count_documents(query)
