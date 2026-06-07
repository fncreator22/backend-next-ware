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
    permission_overrides: Optional[dict] = None
    table_overrides: Optional[list[str]] = None
    warehouse_overrides: Optional[list[str]] = None
    module_overrides: Optional[list[str]] = None
    employee_id: Optional[str] = None
    failed_login_attempts: int = 0
    lockout_until: Optional[datetime] = None
    profile: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RoleDocument(BaseModel):
    id: str = Field(..., alias="_id")
    tenant_id: str
    name: str
    description: Optional[str] = ""
    color: Optional[str] = "#71717a"
    disabled: Optional[bool] = False
    permissions: dict
    page_order: Optional[list[str]] = None
    module_visibility: Optional[dict] = None
    feature_access: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
