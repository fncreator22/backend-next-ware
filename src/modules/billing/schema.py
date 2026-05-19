from decimal import Decimal
from pydantic import BaseModel, Field
from typing import List


class InvoiceItem(BaseModel):
    item_id: str
    quantity: int = Field(..., gt=0)
    price: Decimal = Field(..., gt=0)
    tax_category: str = "normal"  # normal, luxury


class InvoiceCreate(BaseModel):
    warehouse_id: str
    items: List[InvoiceItem]
