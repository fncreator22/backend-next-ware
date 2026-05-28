from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = "employee"  # employee, staff, manager, admin, super_admin
    warehouse_id: str = Field(..., alias="warehouseId")

    class Config:
        populate_by_name = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    warehouse_id: Optional[str] = Field(None, alias="warehouseId")
    status: Optional[str] = None

    class Config:
        populate_by_name = True


class UserResponse(BaseModel):
    id: str = Field(..., alias="_id")
    name: str
    email: EmailStr
    role: str
    warehouse_id: Optional[str] = Field(None, alias="warehouseId")
    tenant_id: str = Field(..., alias="tenantId")
    avatar: str
    status: str

    class Config:
        populate_by_name = True
        from_attributes = True
