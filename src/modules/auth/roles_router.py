import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, status, Body
from src.modules.auth.dependencies import get_current_user, RequireRole
from src.modules.auth.schema import RoleCreate, RoleUpdate
from src.database import get_db
from src.middleware.exceptions import PermissionException, NotFoundException

logger = logging.getLogger("wareops_erp.modules.auth.roles")

router = APIRouter(prefix="/roles", tags=["Role Management"])


@router.get("/", response_model=dict)
async def list_roles(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """List custom roles for the active tenant space."""
    tenant_id = current_user["tenant_id"]
    cursor = db.roles.find({"tenant_id": tenant_id})
    roles = await cursor.to_list(length=100)
    
    # Normalize ID for frontend compatibility
    for r in roles:
        if "_id" in r and "id" not in r:
            r["id"] = r["_id"]
    return {"success": True, "data": roles}


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_custom_role(
    payload: RoleCreate,
    current_user: dict = Depends(RequireRole(["super_admin"])),
    db = Depends(get_db)
):
    """Create a new custom role template."""
    tenant_id = current_user["tenant_id"]
    
    # Generate unique ID key
    import uuid
    role_id = "role_" + str(uuid.uuid4().hex[:12])
    
    doc = {
        "_id": role_id,
        "id": role_id,
        "tenant_id": tenant_id,
        "name": payload.name,
        "description": payload.description,
        "color": payload.color,
        "disabled": payload.disabled,
        "permissions": payload.permissions,
        "page_order": payload.page_order,
        "module_visibility": payload.module_visibility,
        "feature_access": payload.feature_access,
        "created_at": datetime.utcnow()
    }
    
    await db.roles.insert_one(doc)
    doc["id"] = doc["_id"]
    return {"success": True, "data": doc}


@router.put("/{role_id}", response_model=dict)
async def update_custom_role(
    role_id: str,
    payload: RoleUpdate,
    current_user: dict = Depends(RequireRole(["super_admin"])),
    db = Depends(get_db)
):
    """Update custom role configuration details and permission matrices."""
    tenant_id = current_user["tenant_id"]
    
    existing = await db.roles.find_one({"_id": role_id, "tenant_id": tenant_id})
    if not existing:
        raise NotFoundException("Custom role not found.")
        
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        existing["id"] = existing["_id"]
        return {"success": True, "data": existing}
        
    update_data["updated_at"] = datetime.utcnow()
    await db.roles.update_one({"_id": role_id}, {"$set": update_data})
    
    updated = await db.roles.find_one({"_id": role_id})
    if updated:
        updated["id"] = updated["_id"]
    return {"success": True, "data": updated}


@router.delete("/{role_id}", response_model=dict)
async def delete_custom_role(
    role_id: str,
    current_user: dict = Depends(RequireRole(["super_admin"])),
    db = Depends(get_db)
):
    """Delete a custom role configuration from database."""
    tenant_id = current_user["tenant_id"]
    
    existing = await db.roles.find_one({"_id": role_id, "tenant_id": tenant_id})
    if not existing:
        raise NotFoundException("Custom role not found.")
        
    await db.roles.delete_one({"_id": role_id})
    return {"success": True, "message": "Role successfully deleted."}
