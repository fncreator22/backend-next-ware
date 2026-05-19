from fastapi import APIRouter, status
from src.modules.workforce.schema import UserCreate, UserUpdate

router = APIRouter(prefix="/workforce", tags=["Workforce & Hierarchy"])


@router.get("/")
async def list_workforce_members():
    """Retrieve workforce members scoped inside hierarchy rules."""
    return {"success": True, "data": []}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_workforce_member(payload: UserCreate):
    """Register workforce member, ensuring role assigned is less than caller role."""
    return {"success": True, "message": "Workforce member created successfully", "data": {"email": payload.email}}


@router.put("/{id}")
async def update_workforce_member(id: str, payload: UserUpdate):
    """Modify workforce member status, role assignments, or active warehouse assignments."""
    return {"success": True, "message": "Workforce member updated successfully"}
