from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from bson.decimal128 import Decimal128


class ItemDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    sku: str
    name: str
    category: str
    price: Decimal
    stock: int
    unit: str = "pcs"
    tax_category: str = "normal"  # "normal" or "luxury"
    warehouse_id: str
    tenant_id: str
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    images: List[str] = Field(default_factory=list)
    barcode: Optional[str] = None
    barcodes: List[str] = Field(default_factory=list)
    low_stock_threshold: int = 20

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
