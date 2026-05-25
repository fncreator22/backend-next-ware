from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class WorkforceMemberDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    tenant_id: str
    name: str
    email: str
    hashed_password: str
    role: str = "employee"
    warehouse_id: str
    avatar: str
    status: str = "active"
    assignedBy: Optional[str] = None
    assignedAt: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
