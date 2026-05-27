from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import List, Optional
from datetime import datetime


class InvoiceItemCreate(BaseModel):
    item_id: str = Field(..., alias="id")
    name: str
    price: Decimal = Field(..., ge=0)
    tax_category: str = Field(..., alias="taxCategory")
    tax_rate: Decimal = Field(..., alias="taxRate")
    qty: int = Field(..., gt=0)

    model_config = ConfigDict(
        populate_by_name=True
    )


class InvoiceCreate(BaseModel):
    customer: str = Field(..., min_length=2, max_length=100)
    warehouse_id: str = Field(..., alias="warehouseId")
    items: List[InvoiceItemCreate]
    subtotal: Decimal = Field(..., ge=0)
    tax: Decimal = Field(..., ge=0)
    total: Decimal = Field(..., ge=0)

    model_config = ConfigDict(
        populate_by_name=True
    )


class InvoiceItemResponse(BaseModel):
    item_id: str = Field(..., alias="id")
    name: str
    qty: int
    price: float
    tax_category: str = Field(..., alias="taxCategory")
    tax_rate_snapshot: float = Field(..., alias="taxRate")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class TaxConfigSnapshotResponse(BaseModel):
    normal: float
    luxury: float

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class InvoiceResponse(BaseModel):
    id: str = Field(..., alias="id")
    bill_no: str = Field(..., alias="billNo")
    customer: str
    warehouse_id: str = Field(..., alias="warehouseId")
    items: List[InvoiceItemResponse]
    subtotal: float
    tax: float
    total: float
    tax_config_snapshot: TaxConfigSnapshotResponse = Field(..., alias="taxConfigSnapshot")
    created_by: str = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")

    @model_validator(mode="before")
    @classmethod
    def map_mongo_fields(cls, data: any) -> any:
        """Map MongoDB snake_case and _id fields to their camelCase/alias equivalents."""
        if isinstance(data, dict):
            # Map _id -> id
            if "id" not in data and "_id" in data:
                data["id"] = str(data["_id"])
            # Map snake_case -> camelCase aliases
            if "billNo" not in data and "bill_no" in data:
                data["billNo"] = data["bill_no"]
            if "warehouseId" not in data and "warehouse_id" in data:
                data["warehouseId"] = data["warehouse_id"]
            if "createdBy" not in data and "created_by" in data:
                data["createdBy"] = data["created_by"]
            if "createdAt" not in data and "created_at" in data:
                data["createdAt"] = data["created_at"]
            if "taxConfigSnapshot" not in data and "tax_config_snapshot" in data:
                data["taxConfigSnapshot"] = data["tax_config_snapshot"]
            # Map items: tax_category -> taxCategory, tax_rate_snapshot -> taxRate
            if "items" in data and isinstance(data["items"], list):
                for item in data["items"]:
                    if isinstance(item, dict):
                        if "id" not in item and "item_id" in item:
                            item["id"] = item["item_id"]
                        if "taxCategory" not in item and "tax_category" in item:
                            item["taxCategory"] = item["tax_category"]
                        if "taxRate" not in item and "tax_rate_snapshot" in item:
                            item["taxRate"] = item["tax_rate_snapshot"]
        return data

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )
