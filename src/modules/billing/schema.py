from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
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

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )
