from fastapi import APIRouter, Depends, status, Query, UploadFile, File
from typing import Optional, List
import csv
import io
from datetime import datetime
from src.modules.auth.dependencies import get_current_user
from src.modules.items.schema import ItemCreate, ItemUpdate, ItemResponse
from src.modules.items.service import ItemService

router = APIRouter(prefix="/items", tags=["Inventory Items"])


@router.get("/analytics/summary")
async def get_analytics_summary(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Compute top-level inventory KPI stats for dashboard widgets."""
    data = await service.get_analytics_summary(current_user, warehouse_id=warehouse_id)
    return {"success": True, "data": data}


@router.get("/analytics/categories")
async def get_analytics_categories(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Aggregate product counts and monetary valuation per category segment."""
    data = await service.get_analytics_categories(current_user, warehouse_id=warehouse_id)
    return {"success": True, "data": data}


@router.get("/analytics/stock-status")
async def get_analytics_stock_status(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Categorize and count stock records into active health buckets."""
    data = await service.get_analytics_stock_status(current_user, warehouse_id=warehouse_id)
    return {"success": True, "data": data}


@router.get("/analytics/trends")
async def get_analytics_trends(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Aggregate monthly inventory registrations trend."""
    data = await service.get_analytics_trends(current_user, warehouse_id=warehouse_id)
    return {"success": True, "data": data}


@router.get("/", response_model=dict)
async def list_items(
    search: str = Query("", description="Search term matching item SKU or name"),
    category: str = Query("", description="Item category filter"),
    warehouse_id: Optional[str] = Query(None, alias="warehouseId", description="Warehouse filter"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Fetch active warehouse inventory items, scoped by role access."""
    res = await service.list_items(
        current_user,
        search_q=search,
        category_filter=category,
        warehouse_filter=warehouse_id,
        page=page,
        limit=limit
    )
    # Serialize items to schema models
    serialized = [ItemResponse.model_validate(item).model_dump(by_alias=True) for item in res["items"]]
    return {
        "success": True,
        "data": serialized,
        "total": res["total"],
        "pages": res["pages"],
        "message": "Inventory items fetched successfully."
    }


@router.get("/{id}")
async def get_item_detail(
    id: str,
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Fetch individual item details asserting isolation boundaries."""
    item = await service.get_item_detail(id, current_user)
    serialized = ItemResponse.model_validate(item).model_dump(by_alias=True)
    return {"success": True, "data": serialized}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate,
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Create new item, asserting warehouse boundaries and checking SKU uniqueness."""
    item = await service.create_item(payload, current_user)
    serialized = ItemResponse.model_validate(item).model_dump(by_alias=True)
    return {
        "success": True,
        "message": "Inventory item registered successfully.",
        "data": serialized
    }


@router.put("/{id}")
async def update_item(
    id: str,
    payload: ItemUpdate,
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Update stock counts or product details (excludes base employees/staff)."""
    item = await service.update_item(id, payload, current_user)
    serialized = ItemResponse.model_validate(item).model_dump(by_alias=True)
    return {
        "success": True,
        "message": "Inventory item updated successfully.",
        "data": serialized
    }


@router.delete("/{id}")
async def delete_item(
    id: str,
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """Remove item from active inventory mapping."""
    await service.delete_item(id, current_user)
    return {
        "success": True,
        "message": "Inventory item removed successfully."
    }


@router.post("/import")
async def import_items(
    file: UploadFile = File(...),
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: ItemService = Depends()
):
    """
    High-performance CSV inventory importer.
    Parses uploads, validates schemas, maps warehouse fields, prevents SKU collisions,
    and inserts records under the caller's tenant space.
    """
    contents = await file.read()
    decoded = contents.decode("utf-8")
    csv_file = io.StringIO(decoded)
    reader = csv.DictReader(csv_file)
    
    # Verify expected headers
    expected = {"name", "sku", "category", "price", "stock"}
    headers = set(reader.fieldnames or [])
    
    # Normalize headers (lowercase and strip spaces)
    normalized_headers = {h.lower().strip().replace("_", "") for h in headers}
    
    # We want to support both camelCase and snakeCase and lowercase variations
    # Let's map normalized header values to original field names
    header_mapping = {}
    for h in headers:
        norm = h.lower().strip().replace("_", "")
        header_mapping[norm] = h
        
    missing = []
    for exp in expected:
        if exp not in normalized_headers:
            missing.append(exp)
            
    if missing:
        return {
            "success": False,
            "message": f"Malformed CSV structure. Missing columns: {', '.join(missing)}"
        }
        
    success_count = 0
    errors = []
    
    tenant_id = current_user["tenant_id"]
    role = current_user["role"]
    user_id = current_user.get("_id") or current_user.get("id")
    my_wh = current_user.get("warehouse_id") or warehouse_id
    
    import_docs = []
    
    # Read rows
    for row_idx, row in enumerate(reader, start=1):
        try:
            # Map fields using normalized names
            name_val = row.get(header_mapping.get("name", "name"), "").strip()
            sku_val = row.get(header_mapping.get("sku", "sku"), "").strip()
            category_val = row.get(header_mapping.get("category", "category"), "").strip()
            price_str = row.get(header_mapping.get("price", "price"), "0").strip()
            stock_str = row.get(header_mapping.get("stock", "stock"), "0").strip()
            
            # optional unit and taxCategory
            unit_val = row.get(header_mapping.get("unit", "unit") or "", "").strip() or "pcs"
            tax_val = row.get(header_mapping.get("taxcategory", "taxCategory") or header_mapping.get("tax_category", "taxCategory") or "", "").strip() or "normal"
            
            # optional warehouseId
            wh_val = row.get(header_mapping.get("warehouseid", "warehouseId") or header_mapping.get("warehouse_id", "warehouseId") or "", "").strip()
            
            if not name_val or not sku_val or not category_val:
                errors.append(f"Row {row_idx}: Name, SKU, and Category are required.")
                continue
                
            try:
                price_val = float(price_str)
                stock_val = int(stock_str)
            except ValueError:
                errors.append(f"Row {row_idx}: Invalid price or stock values.")
                continue
                
            # Enforce warehouse boundary
            target_wh = wh_val or my_wh
            if role != "super_admin":
                target_wh = my_wh
                
            if not target_wh:
                errors.append(f"Row {row_idx}: Warehouse assignment is required.")
                continue
                
            # Check SKU uniqueness
            unique = await service.verify_sku_uniqueness(sku_val, target_wh, tenant_id)
            if not unique:
                errors.append(f"Row {row_idx}: SKU '{sku_val}' already exists in warehouse '{target_wh}'.")
                continue
                
            # Check if this SKU was already processed in the current upload batch to prevent internal batch collisions
            if any(doc["sku"] == sku_val and doc["warehouse_id"] == target_wh for doc in import_docs):
                errors.append(f"Row {row_idx}: Duplicate SKU '{sku_val}' detected in the upload file.")
                continue
                
            # Build item document
            doc = {
                "tenant_id": tenant_id,
                "name": name_val,
                "sku": sku_val,
                "category": category_val,
                "price": price_val,
                "stock": stock_val,
                "unit": unit_val,
                "tax_category": tax_val,
                "warehouse_id": target_wh,
                "status": "in_stock" if stock_val > 0 else "out_of_stock",
                "createdBy": user_id,
                "created_at": datetime.utcnow()
            }
            import_docs.append(doc)
            
        except Exception as e:
            errors.append(f"Row {row_idx}: Unexpected parsing error: {str(e)}")
            
    # Batch insert to maximize database performance
    if import_docs:
        from bson import ObjectId
        for doc in import_docs:
            doc["_id"] = "item" + str(ObjectId())
            await service.repository.create_item(doc)
            success_count += 1
            
        # Log batch audit trail
        await service.db.audit_logs.insert_one({
            "action": "item_import",
            "description": f"Imported {success_count} inventory items via CSV upload.",
            "userId": user_id,
            "userName": current_user["name"],
            "warehouseId": my_wh,
            "timestamp": datetime.utcnow()
        })
        
    return {
        "success": len(errors) == 0 or success_count > 0,
        "message": f"Successfully imported {success_count} items." + (f" Encountered {len(errors)} errors." if errors else ""),
        "imported": success_count,
        "errors": errors
    }
