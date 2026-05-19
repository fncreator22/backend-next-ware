from fastapi import APIRouter

router = APIRouter(prefix="/audit-logs", tags=["Audit Trails"])


@router.get("/")
async def list_audit_logs():
    """Retrieve historical, read-only audit log trails (visible to peers/managers based on role hierarchy)."""
    return {"success": True, "data": []}
