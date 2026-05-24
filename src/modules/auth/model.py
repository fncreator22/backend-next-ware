# model.py
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class UserDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    email: str
    hashed_password: str
    role: str = "super_admin"
    warehouse_id: Optional[str] = None
    tenant_id: str
    avatar: str
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
