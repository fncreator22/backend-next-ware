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
    permission_overrides: Optional[dict] = Field(None, alias="permissionOverrides")
    table_overrides: Optional[list[str]] = Field(None, alias="tableOverrides")
    warehouse_overrides: Optional[list[str]] = Field(None, alias="warehouseOverrides")
    module_overrides: Optional[list[str]] = Field(None, alias="moduleOverrides")
    employee_id: Optional[str] = Field(None, alias="employeeId")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    color: Optional[str] = "#71717a"
    disabled: Optional[bool] = False
    permissions: dict
    page_order: Optional[list[str]] = Field(None, alias="pageOrder")
    module_visibility: Optional[dict] = Field(None, alias="moduleVisibility")
    feature_access: Optional[dict] = Field(None, alias="featureAccess")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    disabled: Optional[bool] = None
    permissions: Optional[dict] = None
    page_order: Optional[list[str]] = Field(None, alias="pageOrder")
    module_visibility: Optional[dict] = Field(None, alias="moduleVisibility")
    feature_access: Optional[dict] = Field(None, alias="featureAccess")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class RoleResponse(BaseModel):
    id: str = Field(..., alias="id")
    tenant_id: str = Field(..., alias="tenantId")
    name: str
    description: str
    color: str
    disabled: bool
    permissions: dict
    page_order: Optional[list[str]] = Field(None, alias="pageOrder")
    module_visibility: Optional[dict] = Field(None, alias="moduleVisibility")
    feature_access: Optional[dict] = Field(None, alias="featureAccess")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )
