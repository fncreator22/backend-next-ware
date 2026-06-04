from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import List, Optional


class TaxDetail(BaseModel):
    name: str
    tax_type: str = "percentage"  # "percentage" or "fixed"
    rate: Decimal
    amount: Decimal


class InvoiceItemSnapshot(BaseModel):
    item_id: str
    name: str
    qty: int
    price: Decimal
    tax_category: Optional[str] = "normal"
    tax_rate_snapshot: Optional[Decimal] = Decimal("0.05")
    taxes: Optional[List[TaxDetail]] = None


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
    tax_config_snapshot: Optional[TaxConfigSnapshot] = None
    tax_details: Optional[List[TaxDetail]] = None  # Grouped multi-tax snapshot
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # New corporate and metadata fields
    seller_address: Optional[str] = None
    seller_contact: Optional[str] = None
    seller_tax_number: Optional[str] = None
    buyer_billing_address: Optional[str] = None
    buyer_shipping_address: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    employee_id: Optional[str] = None
    employee_name: Optional[str] = None
    employee_role: Optional[str] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
