import logging
from fastapi import APIRouter, Depends, status
from src.modules.workforce.schema import UserCreate, UserUpdate, DocumentReview
from src.modules.workforce.service import WorkforceService
from src.modules.auth.dependencies import get_current_user

logger = logging.getLogger("wareops_erp.modules.workforce.router")

router = APIRouter(prefix="/workforce", tags=["Workforce & Hierarchy"])


@router.get("/")
async def list_workforce_members(
    current_user: dict = Depends(get_current_user),
    service: WorkforceService = Depends()
):
    """Retrieve workforce members scoped according to caller's role and hierarchy rules."""
    members = await service.list_workforce(current_user)
    return {
        "success": True,
        "data": members,
        "message": "Workforce members list retrieved successfully."
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_workforce_member(
    payload: UserCreate,
    current_user: dict = Depends(get_current_user),
    service: WorkforceService = Depends()
):
    """Register workforce member, ensuring target role and warehouse matches caller restrictions."""
    created = await service.create_workforce_member(payload, current_user)
    return {
        "success": True,
        "data": created,
        "message": "Workforce member created successfully."
    }


@router.put("/{id}")
async def update_workforce_member(
    id: str,
    payload: UserUpdate,
    current_user: dict = Depends(get_current_user),
    service: WorkforceService = Depends()
):
    """Modify workforce member status, role levels, or active warehouse assignments."""
    updated = await service.update_workforce_member(id, payload, current_user)
    return {
        "success": True,
        "data": updated,
        "message": "Workforce member profile updated successfully."
    }


@router.delete("/{id}")
async def delete_workforce_member(
    id: str,
    current_user: dict = Depends(get_current_user),
    service: WorkforceService = Depends()
):
    """De-register and remove a workforce member asserting privilege hierarchy rules."""
    await service.delete_workforce_member(id, current_user)
    return {
        "success": True,
        "message": "Workforce member successfully removed from platform."
    }


@router.get("/documents/pending")
async def get_pending_documents(
    current_user: dict = Depends(get_current_user),
    service: WorkforceService = Depends()
):
    """Fetch pending compliance documents across the tenant."""
    pending = await service.get_pending_documents(current_user)
    return {
        "success": True,
        "data": pending,
        "message": "Pending documents list retrieved successfully."
    }


@router.post("/documents/{doc_id}/review")
async def review_document(
    doc_id: str,
    payload: DocumentReview,
    current_user: dict = Depends(get_current_user),
    service: WorkforceService = Depends()
):
    """Approve or reject a pending compliance document."""
    reviewed = await service.review_document(doc_id, payload.dict(), current_user)
    return {
        "success": True,
        "data": reviewed,
        "message": f"Document status updated successfully to {payload.status}."
    }
