from fastapi import APIRouter, Depends, Query, status
from typing import Optional
from src.modules.auth.dependencies import get_current_user
from src.modules.audit_logs.schema import AuditLogResponse, AuditLogCreate
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


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_audit_log(
    payload: AuditLogCreate,
    current_user: dict = Depends(get_current_user),
    service: AuditLogService = Depends()
):
    """Log a custom administrative or settings change event from the frontend securely."""
    log = await service.log_event(
        user_id=str(current_user["_id"]),
        user_name=current_user["name"],
        action=payload.action,
        description=payload.description,
        tenant_id=current_user["tenant_id"],
        warehouse_id=payload.warehouse_id
    )
    return {
        "success": True,
        "data": AuditLogResponse.from_doc(log).model_dump(by_alias=True),
        "message": "Custom audit log created successfully."
    }
