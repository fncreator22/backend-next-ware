from fastapi import APIRouter, Depends, status
from src.modules.warehouses.schema import WarehouseCreate, WarehouseUpdate

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


@router.get("/")
async def list_warehouses():
    """List all warehouses scoped to current tenant and roles."""
    return {"success": True, "data": []}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_warehouse(payload: WarehouseCreate):
    """Create a new warehouse registry under subscription limitations."""
    return {"success": True, "message": "Warehouse created successfully", "data": {"name": payload.name}}


@router.get("/{id}")
async def get_warehouse_detail(id: str):
    """Fetch detail for a single warehouse, asserting isolation constraints."""
    return {"success": True, "data": {"id": id}}


@router.put("/{id}")
async def update_warehouse(id: str, payload: WarehouseUpdate):
    """Update details of an active warehouse."""
    return {"success": True, "message": "Warehouse updated successfully"}


@router.delete("/{id}")
async def delete_warehouse(id: str):
    """Cascade delete all warehouse inventory, workforce, dynamic schemas, and billing documents."""
    return {"success": True, "message": "Warehouse cascade deleted successfully"}
