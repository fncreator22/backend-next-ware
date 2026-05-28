from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional


class UserSignup(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    warehouse_id: Optional[str] = Field(None, alias="warehouseId")
    tenant_id: str = Field(..., alias="tenantId")
    avatar: str
    status: str

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )
