from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional


class UserSignup(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class EmployeeProfile(BaseModel):
    job_title: Optional[str] = Field(None, alias="jobTitle")
    department: Optional[str] = Field(None, alias="department")
    joining_date: Optional[str] = Field(None, alias="joiningDate")
    manager_id: Optional[str] = Field(None, alias="managerId")
    work_type: Optional[str] = Field(None, alias="workType")
    phone: Optional[str] = None
    slack_username: Optional[str] = Field(None, alias="slackUsername")
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = Field(None, alias="emergencyContactName")
    emergency_contact_phone: Optional[str] = Field(None, alias="emergencyContactPhone")
    emergency_contact_relation: Optional[str] = Field(None, alias="emergencyContactRelation")
    shift: Optional[str] = None
    location: Optional[str] = None
    assigned_warehouse_id: Optional[str] = Field(None, alias="assignedWarehouseId")
    documents: Optional[list[dict]] = None
    activity: Optional[list[dict]] = None
    privacy: Optional[dict] = None
    communication_identity: Optional[dict] = Field(None, alias="communicationIdentity")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


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
    profile: Optional[EmployeeProfile] = None

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


class ChangePassword(BaseModel):
    old_password: str = Field(..., alias="oldPassword")
    new_password: str = Field(..., min_length=8, alias="newPassword")

    class Config:
        populate_by_name = True


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, alias="newPassword")

    class Config:
        populate_by_name = True
