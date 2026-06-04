from fastapi import APIRouter, Depends, status, HTTPException
from typing import Optional
from src.modules.auth.dependencies import get_current_user
from src.modules.trash.service import TrashService
from src.modules.audit_logs.service import AuditLogService

router = APIRouter(prefix="/trash", tags=["System Recovery"])


@router.get("/", response_model=dict)
async def list_trash(
    current_user: dict = Depends(get_current_user),
    service: TrashService = Depends()
):
    """Retrieve list of all soft-deleted records under user's tenant space (super_admin or admin only)."""
    if current_user["role"] not in ["super_admin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Only Super Admins and Admins can access recovery storage."
        )
    
    trash_items = await service.list_trash(current_user["tenant_id"])
    return {
        "success": True,
        "data": trash_items,
        "message": "Trash items retrieved successfully."
    }


@router.post("/{trash_id}/restore", response_model=dict)
async def restore_trash(
    trash_id: str,
    current_user: dict = Depends(get_current_user),
    service: TrashService = Depends(),
    audit: AuditLogService = Depends()
):
    """Restore a soft-deleted document back to its original collection (super_admin or admin only)."""
    if current_user["role"] not in ["super_admin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Only Super Admins and Admins can restore documents."
        )
        
    restored = await service.restore(trash_id, current_user["tenant_id"], current_user, audit)
    if not restored:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Soft-deleted document not found or belongs to another tenant."
        )
        
    return {
        "success": True,
        "data": restored,
        "message": "Document successfully restored back to its original catalog."
    }


@router.delete("/{trash_id}", response_model=dict)
async def permanent_delete(
    trash_id: str,
    current_user: dict = Depends(get_current_user),
    service: TrashService = Depends(),
    audit: AuditLogService = Depends()
):
    """Permanently delete a soft-deleted document from recovery storage (super_admin only)."""
    if current_user["role"] != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Only Super Admins can permanently purge documents from recovery storage."
        )
        
    # Retrieve trash document snapshot to log its details
    try:
        from bson import ObjectId
        query = {"_id": ObjectId(trash_id), "tenant_id": current_user["tenant_id"]}
    except Exception:
        query = {"_id": trash_id, "tenant_id": current_user["tenant_id"]}
        
    trash_doc = await service.collection.find_one(query)
    if not trash_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Soft-deleted document not found."
        )
        
    purged = await service.permanent_delete(trash_id, current_user["tenant_id"])
    if not purged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to permanently delete document."
        )
        
    # Log permanent delete audit trail
    await audit.log_event(
        user_id=str(current_user["_id"]),
        user_name=current_user["name"],
        action="permanent_delete",
        description=f"Permanently purged document {trash_doc['original_id']} from original collection '{trash_doc['original_collection']}'",
        tenant_id=current_user["tenant_id"]
    )
    
    return {
        "success": True,
        "message": "Document successfully and permanently purged from database."
    }
