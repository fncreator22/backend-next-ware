from fastapi import APIRouter, Depends, status, Query, Response
from typing import Optional
from src.modules.auth.dependencies import get_current_user
from src.modules.registry.service import CentralRegistryService, CustomerService, generate_code39_svg

router = APIRouter(prefix="/registry", tags=["Enterprise Tracking & CRM Registry"])


@router.get("/")
async def list_registry_entries(
    search: str = Query("", description="Search registry by ID, barcode, or creator"),
    entity_type: str = Query("", alias="entityType", description="Filter by entity type (invoice, warehouse, employee, etc.)"),
    warehouse_id: Optional[str] = Query(None, alias="warehouseId", description="Filter by warehouse"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    current_user: dict = Depends(get_current_user),
    service: CentralRegistryService = Depends()
):
    """Retrieve multi-tenant tracking log registry ledger entries."""
    data = await service.list_registry_entries(
        current_user=current_user,
        search_q=search,
        type_filter=entity_type,
        warehouse_filter=warehouse_id,
        page=page,
        limit=limit
    )
    return {"success": True, "data": data}


@router.get("/barcode")
async def get_barcode_svg(
    code: str = Query(..., description="String code to encode in Code 39 format")
):
    """Renders scan-ready vector SVG barcodes dynamically."""
    svg_content = generate_code39_svg(code)
    return Response(content=svg_content, media_type="image/svg+xml")


@router.get("/customers")
async def list_customers(
    search: str = Query("", description="Search customers by name, phone, email, or ID"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    current_user: dict = Depends(get_current_user),
    service: CustomerService = Depends()
):
    """List CRM customer repeat portfolios."""
    data = await service.list_customers(
        current_user=current_user,
        search_q=search,
        page=page,
        limit=limit
    )
    return {"success": True, "data": data}


@router.get("/customers/{customer_id}")
async def get_customer_detail(
    customer_id: str,
    current_user: dict = Depends(get_current_user),
    service: CustomerService = Depends()
):
    """Fetch detailed profile workspace for a CRM customer."""
    data = await service.get_customer_detail(customer_id, current_user)
    return {"success": True, "data": data}
