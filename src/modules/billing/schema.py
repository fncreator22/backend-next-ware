from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import List, Optional
from datetime import datetime


class TaxDetailCreate(BaseModel):
    name: str
    tax_type: str = Field("percentage", alias="taxType")
    rate: Decimal
    amount: Decimal

    model_config = ConfigDict(
        populate_by_name=True
    )


class InvoiceItemCreate(BaseModel):
    item_id: str = Field(..., alias="id")
    name: str
    price: Decimal = Field(..., ge=0)
    tax_category: str = Field(..., alias="taxCategory")
    tax_rate: Decimal = Field(..., alias="taxRate")
    qty: int = Field(..., gt=0)
    taxes: Optional[List[TaxDetailCreate]] = None

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
    tax_details: Optional[List[TaxDetailCreate]] = Field(None, alias="taxDetails")
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = Field(None, alias="exchangeRate")
    
    # New billing & corporate fields
    seller_address: Optional[str] = Field(None, alias="sellerAddress")
    seller_contact: Optional[str] = Field(None, alias="sellerContact")
    seller_tax_number: Optional[str] = Field(None, alias="sellerTaxNumber")
    buyer_billing_address: Optional[str] = Field(None, alias="buyerBillingAddress")
    buyer_shipping_address: Optional[str] = Field(None, alias="buyerShippingAddress")
    customer_phone: Optional[str] = Field(None, alias="customerPhone")
    customer_email: Optional[str] = Field(None, alias="customerEmail")
    employee_id: Optional[str] = Field(None, alias="employeeId")
    employee_name: Optional[str] = Field(None, alias="employeeName")
    employee_role: Optional[str] = Field(None, alias="employeeRole")

    model_config = ConfigDict(
        populate_by_name=True
    )


class TaxDetailResponse(BaseModel):
    name: str
    tax_type: str = Field(..., alias="taxType")
    rate: float
    amount: float

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class InvoiceItemResponse(BaseModel):
    item_id: str = Field(..., alias="id")
    name: str
    qty: int
    price: float
    tax_category: str = Field(..., alias="taxCategory")
    tax_rate_snapshot: float = Field(..., alias="taxRate")
    taxes: Optional[List[TaxDetailResponse]] = None

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
    tax_config_snapshot: Optional[TaxConfigSnapshotResponse] = Field(None, alias="taxConfigSnapshot")
    tax_details: Optional[List[TaxDetailResponse]] = Field(None, alias="taxDetails")
    created_by: str = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    currency: Optional[str] = None
    exchange_rate: Optional[float] = Field(None, alias="exchangeRate")

    # New corporate and metadata fields
    seller_address: Optional[str] = Field(None, alias="sellerAddress")
    seller_contact: Optional[str] = Field(None, alias="sellerContact")
    seller_tax_number: Optional[str] = Field(None, alias="sellerTaxNumber")
    buyer_billing_address: Optional[str] = Field(None, alias="buyerBillingAddress")
    buyer_shipping_address: Optional[str] = Field(None, alias="buyerShippingAddress")
    customer_phone: Optional[str] = Field(None, alias="customerPhone")
    customer_email: Optional[str] = Field(None, alias="customerEmail")
    employee_id: Optional[str] = Field(None, alias="employeeId")
    employee_name: Optional[str] = Field(None, alias="employeeName")
    employee_role: Optional[str] = Field(None, alias="employeeRole")

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
            if "exchangeRate" not in data and "exchange_rate" in data:
                data["exchangeRate"] = data["exchange_rate"]
            if "taxDetails" not in data and "tax_details" in data:
                data["taxDetails"] = data["tax_details"]
                if isinstance(data["taxDetails"], list):
                    for t in data["taxDetails"]:
                        if isinstance(t, dict):
                            if "taxType" not in t and "tax_type" in t:
                                t["taxType"] = t["tax_type"]
            # Map new corporate and metadata fields
            for camel, snake in [
                ("sellerAddress", "seller_address"),
                ("sellerContact", "seller_contact"),
                ("sellerTaxNumber", "seller_tax_number"),
                ("buyerBillingAddress", "buyer_billing_address"),
                ("buyerShippingAddress", "buyer_shipping_address"),
                ("customerPhone", "customer_phone"),
                ("customerEmail", "customer_email"),
                ("employeeId", "employee_id"),
                ("employeeName", "employee_name"),
                ("employeeRole", "employee_role"),
            ]:
                if camel not in data and snake in data:
                    data[camel] = data[snake]
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
                        if "taxes" in item and isinstance(item["taxes"], list):
                            for t in item["taxes"]:
                                if isinstance(t, dict):
                                    if "taxType" not in t and "tax_type" in t:
                                        t["taxType"] = t["tax_type"]
        return data

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )
