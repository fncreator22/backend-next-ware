from pydantic import BaseModel, EmailStr, Field
from typing import Optional


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

    class Config:
        populate_by_name = True
        from_attributes = True


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = "employee"  # employee, staff, manager, admin, super_admin
    warehouse_id: str = Field(..., alias="warehouseId")
    avatar: Optional[str] = None
    permission_overrides: Optional[dict] = Field(None, alias="permissionOverrides")
    table_overrides: Optional[list[str]] = Field(None, alias="tableOverrides")
    warehouse_overrides: Optional[list[str]] = Field(None, alias="warehouseOverrides")
    module_overrides: Optional[list[str]] = Field(None, alias="moduleOverrides")
    employee_id: Optional[str] = Field(None, alias="employeeId")
    profile: Optional[EmployeeProfile] = None

    class Config:
        populate_by_name = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    warehouse_id: Optional[str] = Field(None, alias="warehouseId")
    status: Optional[str] = None
    avatar: Optional[str] = None
    permission_overrides: Optional[dict] = Field(None, alias="permissionOverrides")
    table_overrides: Optional[list[str]] = Field(None, alias="tableOverrides")
    warehouse_overrides: Optional[list[str]] = Field(None, alias="warehouseOverrides")
    module_overrides: Optional[list[str]] = Field(None, alias="moduleOverrides")
    employee_id: Optional[str] = Field(None, alias="employeeId")
    profile: Optional[EmployeeProfile] = None

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
    permission_overrides: Optional[dict] = Field(None, alias="permissionOverrides")
    table_overrides: Optional[list[str]] = Field(None, alias="tableOverrides")
    warehouse_overrides: Optional[list[str]] = Field(None, alias="warehouseOverrides")
    module_overrides: Optional[list[str]] = Field(None, alias="moduleOverrides")
    employee_id: Optional[str] = Field(None, alias="employeeId")
    profile: Optional[EmployeeProfile] = None

    class Config:
        populate_by_name = True
        from_attributes = True


class DocumentReview(BaseModel):
    status: str
    remarks: Optional[str] = None
