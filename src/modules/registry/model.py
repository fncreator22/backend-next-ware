from datetime import datetime
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any


class RegistryDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    tenant_id: str
    entity_id: str  # Unique enterprise ID, e.g. WH-2026-0001
    barcode: str  # Barcode representation (matches entity_id)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str  # User ID of creator
    creator_name: str  # Name of creator
    warehouse_id: Optional[str] = None  # Scoped per warehouse (None means Global scope)
    entity_type: str  # invoice, warehouse, employee, inventory, table_registry
    metadata_snapshot: Dict[str, Any]  # Snapshot of current state for audit/history


class CustomerInvoiceSnapshot(BaseModel):
    invoice_id: str  # DB ID
    bill_no: str  # Enterprise INV ID
    subtotal: float
    tax: float
    total: float
    checkout_at: datetime


class CustomerDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    tenant_id: str
    customer_id: str  # Unique customer ID, e.g. CUST-2026-0001
    barcode: str  # Barcode representation (matches customer_id)
    name: str
    address: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    tax_number: Optional[str] = ""  # GSTIN or corporate registration
    invoices: List[CustomerInvoiceSnapshot] = []  # Transaction history snapshots
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str
    last_active_at: datetime = Field(default_factory=datetime.utcnow)
