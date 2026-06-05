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
    images: Optional[List[str]] = Field(default_factory=list)
    barcode: Optional[str] = None
    barcodes: Optional[List[str]] = Field(default_factory=list)
    low_stock_threshold: int = Field(20, alias="lowStockThreshold")

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
    images: Optional[List[str]] = None
    barcode: Optional[str] = None
    barcodes: Optional[List[str]] = None
    low_stock_threshold: Optional[int] = Field(None, alias="lowStockThreshold")

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
    images: Optional[List[str]] = Field(default_factory=list)
    barcode: Optional[str] = None
    barcodes: Optional[List[str]] = Field(default_factory=list)
    low_stock_threshold: int = Field(20, alias="lowStockThreshold")
    health_status: str = Field(..., alias="healthStatus")

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
            if "lowStockThreshold" not in data and "low_stock_threshold" in data:
                data["lowStockThreshold"] = data["low_stock_threshold"]
            elif "low_stock_threshold" not in data and "lowStockThreshold" in data:
                data["low_stock_threshold"] = data["lowStockThreshold"]
            
            threshold = data.get("low_stock_threshold") or data.get("lowStockThreshold") or 20
            stock = data.get("stock", 0)
            if stock == 0:
                data["healthStatus"] = "Critical"
            elif stock < threshold:
                data["healthStatus"] = "Low Stock"
            else:
                data["healthStatus"] = "Healthy"
            data["health_status"] = data["healthStatus"]
        else:
            threshold = getattr(data, "low_stock_threshold", 20) or getattr(data, "lowStockThreshold", 20)
            stock = getattr(data, "stock", 0)
            if stock == 0:
                setattr(data, "healthStatus", "Critical")
                setattr(data, "health_status", "Critical")
            elif stock < threshold:
                setattr(data, "healthStatus", "Low Stock")
                setattr(data, "health_status", "Low Stock")
            else:
                setattr(data, "healthStatus", "Healthy")
                setattr(data, "health_status", "Healthy")
        return data

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class BarcodeGenerateRequest(BaseModel):
    itemId: Optional[str] = Field(None, alias="itemId")
    quantity: int = Field(..., ge=1, le=50)
    newItem: Optional[ItemCreate] = Field(None, alias="newItem")

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True
    )

