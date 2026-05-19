from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class AuditLogResponse(BaseModel):
    id: str
    user_id: str
    action: str
    target_resource: str
    timestamp: datetime
    warehouse_id: Optional[str]
    tenant_id: str
