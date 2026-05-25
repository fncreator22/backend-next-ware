from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class RevenueAnalyticsResponse(BaseModel):
    totalRevenue: float
    totalTax: float
    netRevenue: float
    avgInvoiceValue: float
    invoicesCount: int


class CategoryItemBreakdown(BaseModel):
    category: str
    totalStock: int
    totalValuation: float


class RoleWorkforceBreakdown(BaseModel):
    role: str
    count: int


class MonthlyTrendRecord(BaseModel):
    year: int
    month: int
    monthName: str
    totalRevenue: float
    totalTax: float


class WarehousePerformanceRecord(BaseModel):
    warehouseId: str
    warehouseName: str
    revenue: float
    invoiceCount: int
    staffCount: int
