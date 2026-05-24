import logging
from fastapi import APIRouter, Depends, status
from src.modules.warehouses.schema import WarehouseCreate, WarehouseUpdate
from src.modules.warehouses.service import WarehouseService
from src.modules.auth.dependencies import get_current_user

logger = logging.getLogger("wareops_erp.modules.warehouses.router")

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


@router.get("/")
async def list_warehouses(
    current_user: dict = Depends(get_current_user),
    service: WarehouseService = Depends()
):
    """List all warehouses scoped dynamically to the caller's role and tenant boundaries."""
    whs = await service.list_warehouses(current_user)
    return {
        "success": True,
        "data": whs,
        "message": "Warehouses fetched successfully."
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    payload: WarehouseCreate,
    current_user: dict = Depends(get_current_user),
    service: WarehouseService = Depends()
):
    """Create a new warehouse registry under caller's tenant (Super Admin only)."""
    wh = await service.create_warehouse(payload, current_user)
    return {
        "success": True,
        "data": wh,
        "message": "Warehouse registered successfully."
    }


@router.get("/{id}")
async def get_warehouse_detail(
    id: str,
    current_user: dict = Depends(get_current_user),
    service: WarehouseService = Depends()
):
    """Fetch individual warehouse details asserting tenant boundaries."""
    wh = await service.get_warehouse_detail(id, current_user)
    return {
        "success": True,
        "data": wh,
        "message": "Warehouse detail fetched successfully."
    }


@router.put("/{id}")
async def update_warehouse(
    id: str,
    payload: WarehouseUpdate,
    current_user: dict = Depends(get_current_user),
    service: WarehouseService = Depends()
):
    """Update warehouse profile details according to role boundaries (Super Admin / Admin)."""
    wh = await service.update_warehouse(id, payload, current_user)
    return {
        "success": True,
        "data": wh,
        "message": "Warehouse profile updated successfully."
    }


@router.delete("/{id}")
async def delete_warehouse(
    id: str,
    current_user: dict = Depends(get_current_user),
    service: WarehouseService = Depends()
):
    """Cascade delete warehouse registry and all associated users, stock items, and billing documents."""
    await service.retire_warehouse_cascade(id, current_user)
    return {
        "success": True,
        "message": "Warehouse and all associated data cascade deleted successfully."
    }
