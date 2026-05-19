from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class WorkforceMemberDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    email: str
    hashed_password: str
    role: str
    warehouse_id: Optional[str] = None
    tenant_id: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
