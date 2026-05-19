from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = "employee"  # employee, staff, manager, admin, super_admin
    warehouse_id: str


class UserUpdate(BaseModel):
    role: Optional[str] = None
    warehouse_id: Optional[str] = None
    is_active: Optional[bool] = None
class UserResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
    warehouse_id: Optional[str]
    tenant_id: str
