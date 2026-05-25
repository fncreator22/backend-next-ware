from fastapi import APIRouter, Depends, status, Query
from typing import List, Optional
from src.modules.auth.dependencies import get_current_user, RequireRole
from src.modules.dynamic_tables.schema import TableSchemaCreate, TableSchemaResponse
from src.modules.dynamic_tables.service import DynamicTableService

router = APIRouter(prefix="/dynamic-tables", tags=["Dynamic Tables Builder"])


@router.get("/", response_model=dict)
async def list_schemas(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: DynamicTableService = Depends()
):
    """Retrieve all custom table schemas registered within warehouse bounds."""
    schemas = await service.list_schemas(current_user, warehouse_id=warehouse_id)
    serialized = [TableSchemaResponse.from_doc(s).model_dump(by_alias=True) for s in schemas]
    return {
        "success": True,
        "data": serialized,
        "message": "Custom table schemas fetched successfully."
    }


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_schema(
    payload: TableSchemaCreate,
    current_user: dict = Depends(RequireRole(["super_admin", "admin"])),
    service: DynamicTableService = Depends()
):
    """Create a new custom table metadata schema validation registry (Super Admins/Admins)."""
    schema = await service.create_schema(payload, current_user)
    serialized = TableSchemaResponse.from_doc(schema).model_dump(by_alias=True)
    return {
        "success": True,
        "message": "Custom table schema registered successfully.",
        "data": serialized
    }


@router.put("/{tableId}", response_model=dict)
async def update_schema(
    tableId: str,
    payload: TableSchemaCreate,
    current_user: dict = Depends(RequireRole(["super_admin", "admin"])),
    service: DynamicTableService = Depends()
):
    """Update custom table schema definitions configuration (Super Admins/Admins)."""
    schema = await service.update_schema(tableId, payload, current_user)
    serialized = TableSchemaResponse.from_doc(schema).model_dump(by_alias=True)
    return {
        "success": True,
        "message": "Custom table schema updated successfully.",
        "data": serialized
    }


@router.delete("/{tableId}", response_model=dict)
async def delete_schema(
    tableId: str,
    current_user: dict = Depends(RequireRole(["super_admin", "admin"])),
    service: DynamicTableService = Depends()
):
    """Delete a custom table schema and cascade purge all dynamic rows documents."""
    await service.delete_schema(tableId, current_user)
    return {
        "success": True,
        "message": "Custom table and all associated row documents deleted successfully."
    }


@router.get("/{tableId}/rows", response_model=dict)
async def list_rows(
    tableId: str,
    current_user: dict = Depends(get_current_user),
    service: DynamicTableService = Depends()
):
    """Fetch custom row documents from MongoDB collections matching isolation scopes."""
    rows = await service.list_rows(tableId, current_user)
    return {
        "success": True,
        "data": rows,
        "message": "Custom table rows fetched successfully."
    }


@router.post("/{tableId}/rows", status_code=status.HTTP_201_CREATED, response_model=dict)
async def append_row(
    tableId: str,
    payload: dict,
    current_user: dict = Depends(RequireRole(["super_admin", "admin", "manager", "staff"])),
    service: DynamicTableService = Depends()
):
    """Append validated custom row documents into database (Admins, Managers, and Staff)."""
    row = await service.append_row(tableId, payload, current_user)
    return {
        "success": True,
        "message": "Row successfully appended into custom table.",
        "data": row
    }


@router.put("/{tableId}/rows/{rowId}", response_model=dict)
async def update_row(
    tableId: str,
    rowId: str,
    payload: dict,
    current_user: dict = Depends(RequireRole(["super_admin", "admin", "manager", "staff"])),
    service: DynamicTableService = Depends()
):
    """Update custom table row validated fields (Admins, Managers, and Staff)."""
    row = await service.update_row(tableId, rowId, payload, current_user)
    return {
        "success": True,
        "message": "Row successfully updated in custom table.",
        "data": row
    }


@router.delete("/{tableId}/rows/{rowId}", response_model=dict)
async def delete_row(
    tableId: str,
    rowId: str,
    current_user: dict = Depends(RequireRole(["super_admin", "admin", "manager", "staff"])),
    service: DynamicTableService = Depends()
):
    """Delete custom row document (Admins, Managers, and Staff)."""
    await service.delete_row(tableId, rowId, current_user)
    return {
        "success": True,
        "message": "Row successfully deleted from custom table."
    }
