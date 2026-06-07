from fastapi import APIRouter, Depends, status, Query, Body
from typing import List, Optional
from src.modules.auth.dependencies import get_current_user, RequirePermission
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
    current_user: dict = Depends(RequirePermission("tables", "create")),
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


@router.get("/{tableId}", response_model=dict)
async def get_schema(
    tableId: str,
    current_user: dict = Depends(get_current_user),
    service: DynamicTableService = Depends()
):
    """Retrieve detailed metadata schema configuration for a custom table."""
    schema = await service.get_schema_detail(tableId, current_user)
    serialized = TableSchemaResponse.from_doc(schema).model_dump(by_alias=True)
    return {
        "success": True,
        "message": "Custom table schema fetched successfully.",
        "data": serialized
    }


@router.put("/{tableId}", response_model=dict)
async def update_schema(
    tableId: str,
    payload: TableSchemaCreate,
    current_user: dict = Depends(RequirePermission("tables", "edit")),
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
    current_user: dict = Depends(RequirePermission("tables", "delete")),
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
    page: int = Query(1, alias="page"),
    search: str = Query("", description="Search registry"),
    entity_type: str = Query("", alias="entityType"),
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: DynamicTableService = Depends()
):
    """Fetch custom row documents from MongoDB collections matching isolation scopes and page number."""
    rows = await service.list_rows(
        tableId,
        current_user,
        page=page,
        search=search,
        entity_type=entity_type,
        warehouse_id=warehouse_id
    )
    return {
        "success": True,
        "data": rows,
        "message": "Custom table rows fetched successfully."
    }


@router.post("/{tableId}/rows", status_code=status.HTTP_201_CREATED, response_model=dict)
async def append_row(
    tableId: str,
    payload: dict,
    page: int = Query(1, alias="page"),
    current_user: dict = Depends(RequirePermission("tables", "create")),
    service: DynamicTableService = Depends()
):
    """Append validated custom row documents into database (Admins, Managers, and Staff)."""
    row = await service.append_row(tableId, payload, current_user, page=page)
    return {
        "success": True,
        "message": "Row successfully appended into custom table.",
        "data": row
    }


@router.post("/{tableId}/pages", response_model=dict)
async def add_table_page(
    tableId: str,
    current_user: dict = Depends(get_current_user),
    service: DynamicTableService = Depends()
):
    """Add a new page to the custom table under subscription bounds."""
    schema = await service.add_page(tableId, current_user)
    serialized = TableSchemaResponse.from_doc(schema).model_dump(by_alias=True)
    return {
        "success": True,
        "data": serialized,
        "message": "New table page created successfully."
    }


@router.delete("/{tableId}/pages/{pageNumber}", response_model=dict)
async def delete_table_page(
    tableId: str,
    pageNumber: int,
    current_user: dict = Depends(get_current_user),
    service: DynamicTableService = Depends()
):
    """Delete a page from the custom table and cascade purge its rows."""
    schema = await service.delete_page(tableId, pageNumber, current_user)
    serialized = TableSchemaResponse.from_doc(schema).model_dump(by_alias=True)
    return {
        "success": True,
        "data": serialized,
        "message": f"Table page {pageNumber} and its rows deleted successfully."
    }


@router.put("/{tableId}/rows/{rowId}", response_model=dict)
async def update_row(
    tableId: str,
    rowId: str,
    payload: dict,
    current_user: dict = Depends(RequirePermission("tables", "edit")),
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
    current_user: dict = Depends(RequirePermission("tables", "delete")),
    service: DynamicTableService = Depends()
):
    """Delete custom row document (Admins, Managers, and Staff)."""
    await service.delete_row(tableId, rowId, current_user)
    return {
        "success": True,
        "message": "Row successfully deleted from custom table."
    }


@router.post("/{tableId}/rows/import", status_code=status.HTTP_200_OK, response_model=dict)
async def import_rows(
    tableId: str,
    payload: list = Body(...),
    page: int = Query(1, alias="page"),
    current_user: dict = Depends(RequirePermission("tables", "import")),
    service: DynamicTableService = Depends()
):
    """
    Bulk import multiple row documents from CSV/JSON payload (Admin/Manager only).
    Accepts a list of row dicts keyed by column id.
    """
    result = await service.import_rows(tableId, payload, current_user, page=page)
    return {
        "success": True,
        "message": f"Import complete: {result['inserted']} rows inserted, {len(result['errors'])} errors.",
        "data": result
    }
