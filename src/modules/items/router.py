from fastapi import APIRouter, Depends, status, Query
from typing import Optional, List
from src.modules.auth.dependencies import get_current_user
from src.modules.items.schema import ItemCreate, ItemUpdate, ItemResponse
from src.modules.items.service import ItemService

router = APIRouter(prefix="/items", tags=["Inventory Items"])


@router.get("/analytics/summary")
async def get_analytics_summary(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Compute top-level inventory KPI stats for dashboard widgets."""
    data = await service.get_analytics_summary(current_user, warehouse_id=warehouse_id)
    return {"success": True, "data": data}


@router.get("/analytics/categories")
async def get_analytics_categories(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Aggregate product counts and monetary valuation per category segment."""
    data = await service.get_analytics_categories(current_user, warehouse_id=warehouse_id)
    return {"success": True, "data": data}


@router.get("/analytics/stock-status")
async def get_analytics_stock_status(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Categorize and count stock records into active health buckets."""
    data = await service.get_analytics_stock_status(current_user, warehouse_id=warehouse_id)
    return {"success": True, "data": data}


@router.get("/analytics/trends")
async def get_analytics_trends(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Aggregate monthly inventory registrations trend."""
    data = await service.get_analytics_trends(current_user, warehouse_id=warehouse_id)
    return {"success": True, "data": data}


@router.get("/", response_model=dict)
async def list_items(
    search: str = Query("", description="Search term matching item SKU or name"),
    category: str = Query("", description="Item category filter"),
    warehouse_id: Optional[str] = Query(None, alias="warehouseId", description="Warehouse filter"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Fetch active warehouse inventory items, scoped by role access."""
    res = await service.list_items(
        current_user,
        search_q=search,
        category_filter=category,
        warehouse_filter=warehouse_id,
        page=page,
        limit=limit
    )
    # Serialize items to schema models
    serialized = [ItemResponse.model_validate(item).model_dump(by_alias=True) for item in res["items"]]
    return {
        "success": True,
        "data": serialized,
        "total": res["total"],
        "pages": res["pages"],
        "message": "Inventory items fetched successfully."
    }


@router.get("/{id}")
async def get_item_detail(
    id: str,
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Fetch individual item details asserting isolation boundaries."""
    item = await service.get_item_detail(id, current_user)
    serialized = ItemResponse.model_validate(item).model_dump(by_alias=True)
    return {"success": True, "data": serialized}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate,
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Create new item, asserting warehouse boundaries and checking SKU uniqueness."""
    item = await service.create_item(payload, current_user)
    serialized = ItemResponse.model_validate(item).model_dump(by_alias=True)
    return {
        "success": True,
        "message": "Inventory item registered successfully.",
        "data": serialized
    }


@router.put("/{id}")
async def update_item(
    id: str,
    payload: ItemUpdate,
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Update stock counts or product details (excludes base employees/staff)."""
    item = await service.update_item(id, payload, current_user)
    serialized = ItemResponse.model_validate(item).model_dump(by_alias=True)
    return {
        "success": True,
        "message": "Inventory item updated successfully.",
        "data": serialized
    }


@router.delete("/{id}")
async def delete_item(
    id: str,
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Remove item from active inventory mapping."""
    await service.delete_item(id, current_user)
    return {
        "success": True,
        "message": "Inventory item removed successfully."
    }
