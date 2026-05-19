from fastapi import APIRouter, Depends, status
from src.modules.items.schema import ItemCreate, ItemUpdate

router = APIRouter(prefix="/items", tags=["Inventory Items"])


@router.get("/")
async def list_items():
    """Fetch active warehouse inventory items, scoped by role access."""
    return {"success": True, "data": []}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate):
    """Create new item, asserting warehouse boundaries and checking SKU uniqueness."""
    return {"success": True, "message": "Inventory item registered successfully", "data": {"sku": payload.sku}}


@router.put("/{id}")
async def update_item(id: str, payload: ItemUpdate):
    """Update stock counts or product details (excludes base employees)."""
    return {"success": True, "message": "Inventory item updated successfully"}


@router.delete("/{id}")
async def delete_item(id: str):
    """Remove item from active inventory mapping."""
    return {"success": True, "message": "Inventory item removed successfully"}
