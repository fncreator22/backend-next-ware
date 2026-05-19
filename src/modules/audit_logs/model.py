from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class AuditLogDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    action: str
    target_resource: str
    warehouse_id: Optional[str] = None
    tenant_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
