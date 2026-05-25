from fastapi import APIRouter, Depends, Query
from typing import Optional
from src.modules.auth.dependencies import get_current_user
from src.modules.analytics.service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Enterprise Analytics"])


@router.get("/dashboard", response_model=dict)
async def get_dashboard_summary(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    """Fetch high-performance, real-time dashboard data metrics summary scoped by tenant boundaries."""
    data = await service.get_dashboard_summary(current_user, warehouse_id=warehouse_id)
    return {
        "success": True,
        "data": data,
        "message": "Dashboard summary generated successfully."
    }


@router.get("/revenue", response_model=dict)
async def get_revenue_analytics(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    """Compute gross revenues, tax collections, averages and net margins metrics."""
    data = await service.get_revenue_analytics(current_user, warehouse_id=warehouse_id)
    return {
        "success": True,
        "data": data,
        "message": "Revenue analytics computed successfully."
    }


@router.get("/inventory", response_model=dict)
async def get_inventory_analytics(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    """Fetch total stocks and financial valuations breakdown grouped per category."""
    data = await service.get_inventory_analytics(current_user, warehouse_id=warehouse_id)
    return {
        "success": True,
        "data": data,
        "message": "Inventory analytics compiled successfully."
    }


@router.get("/workforce", response_model=dict)
async def get_workforce_analytics(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    """Aggregate total active user allocations grouped per role distributions."""
    data = await service.get_workforce_analytics(current_user, warehouse_id=warehouse_id)
    return {
        "success": True,
        "data": data,
        "message": "Workforce analytics compiled successfully."
    }


@router.get("/trends", response_model=dict)
async def get_trends_analytics(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: AnalyticsService = Depends()
):
    """Retrieve 12-month billing trend analytics and taxation aggregates."""
    data = await service.get_trends_analytics(current_user, warehouse_id=warehouse_id)
    return {
        "success": True,
        "data": data,
        "message": "Monthly revenue trends compiled successfully."
    }
