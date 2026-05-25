from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


CATEGORIES = [
    "Electronics",
    "Furniture",
    "Apparel",
    "Food & Beverage",
    "Tools",
    "Medical",
    "Automotive",
    "Books",
    "Sports",
    "Other"
]

UNITS = ["pcs", "kg", "lbs", "box", "pallet", "set", "m", "ft"]


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    sku: Optional[str] = Field(None, min_length=3, max_length=50)
    category: str = Field(..., description="Item category segment")
    price: Decimal = Field(..., ge=0)
    stock: int = Field(..., ge=0)
    unit: str = Field("pcs")
    tax_category: str = Field("normal", alias="taxCategory")
    warehouse_id: str = Field(..., alias="warehouseId")

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True
    )


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    sku: Optional[str] = Field(None, min_length=3, max_length=50)
    category: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    stock: Optional[int] = Field(None, ge=0)
    unit: Optional[str] = None
    tax_category: Optional[str] = Field(None, alias="taxCategory")
    warehouse_id: Optional[str] = Field(None, alias="warehouseId")

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True
    )


class ItemResponse(BaseModel):
    id: str = Field(..., alias="id")
    sku: str
    name: str
    category: str
    price: float
    stock: int
    unit: str
    tax_category: str = Field(..., alias="taxCategory")
    warehouse_id: str = Field(..., alias="warehouseId")
    created_by: str = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")

    @model_validator(mode="before")
    @classmethod
    def map_id_fields(cls, data: any) -> any:
        if isinstance(data, dict):
            if "id" not in data and "_id" in data:
                data["id"] = str(data["_id"])
            # Ensure safe fallback mapping for camelCase fields in dictionaries
            if "taxCategory" not in data and "tax_category" in data:
                data["taxCategory"] = data["tax_category"]
            if "warehouseId" not in data and "warehouse_id" in data:
                data["warehouseId"] = data["warehouse_id"]
            if "createdBy" not in data and "created_by" in data:
                data["createdBy"] = data["created_by"]
            if "createdAt" not in data and "created_at" in data:
                data["createdAt"] = data["created_at"]
            if "updatedAt" not in data and "updated_at" in data:
                data["updatedAt"] = data["updated_at"]
        return data

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )
