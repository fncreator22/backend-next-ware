from fastapi import APIRouter, Depends, Query
from typing import Optional
from src.modules.auth.dependencies import get_current_user
from src.modules.audit_logs.schema import AuditLogResponse
from src.modules.audit_logs.service import AuditLogService

router = APIRouter(prefix="/audit-logs", tags=["Audit Trails"])


@router.get("/", response_model=dict)
async def list_audit_logs(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: AuditLogService = Depends()
):
    """Retrieve historical, read-only audit log trails scoped by multi-tenant and role hierarchies."""
    logs = await service.list_logs(current_user, warehouse_filter=warehouse_id)
    serialized = [AuditLogResponse.from_doc(l).model_dump(by_alias=True) for l in logs]
    return {
        "success": True,
        "data": serialized,
        "message": "Audit logs fetched successfully."
    }
