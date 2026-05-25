from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import List, Optional


class InvoiceItemSnapshot(BaseModel):
    item_id: str
    name: str
    qty: int
    price: Decimal
    tax_category: str
    tax_rate_snapshot: Decimal


class TaxConfigSnapshot(BaseModel):
    normal: Decimal
    luxury: Decimal


class InvoiceDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    bill_no: str
    customer: str
    warehouse_id: str
    tenant_id: str
    items: List[InvoiceItemSnapshot]
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    tax_config_snapshot: TaxConfigSnapshot
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
