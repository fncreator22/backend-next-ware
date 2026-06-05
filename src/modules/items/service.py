import logging
import asyncio
from datetime import datetime
from decimal import Decimal
from fastapi import Depends
from bson.decimal128 import Decimal128
from src.modules.items.repository import ItemRepository
from src.modules.items.schema import ItemCreate, ItemUpdate
from src.middleware.exceptions import PermissionException, NotFoundException, ValidationException
from src.database import get_db
from src.modules.audit_logs.service import AuditLogService
from src.modules.trash.service import TrashService
from src.modules.registry.service import CentralRegistryService

logger = logging.getLogger("wareops_erp.modules.items.service")


class ItemService:
    def __init__(
        self,
        repository: ItemRepository = Depends(),
        db=Depends(get_db),
        audit: AuditLogService = Depends(),
        trash: TrashService = Depends(),
        registry: CentralRegistryService = Depends()
    ):
        self.repository = repository
        self.db = db
        self.audit = audit
        self.trash = trash
        self.registry = registry

    def _convert_decimal128_value(self, val) -> float:
        """Helper to convert potential Decimal128 from database aggregates into float."""
        if isinstance(val, Decimal128):
            return float(val.to_decimal())
        elif isinstance(val, Decimal):
            return float(val)
        return float(val or 0.0)

    async def verify_sku_uniqueness(self, sku: str, warehouse_id: str, tenant_id: str) -> bool:
        """Verify SKU uniqueness across a single warehouse space."""
        item = await self.repository.find_by_sku_and_warehouse(sku, warehouse_id, tenant_id)
        return item is None

    async def list_items(
        self,
        current_user: dict,
        search_q: str = "",
        category_filter: str = "",
        warehouse_filter: str = "",
        page: int = 1,
        limit: int = 10
    ) -> dict:
        """Fetch items scoped dynamically to caller's tenant and warehouse scopes."""
        tenant_id = current_user["tenant_id"]
        role = current_user["role"]

        query = {"tenant_id": tenant_id}

        # Enforce warehouse boundary scoping
        if role != "super_admin":
            my_wh = current_user.get("warehouse_id")
            if not my_wh:
                return {"items": [], "total": 0, "pages": 0}
            query["warehouse_id"] = my_wh
        else:
            # Super Admin can filter by warehouse
            if warehouse_filter:
                query["warehouse_id"] = warehouse_filter

        # Apply search filter
        if search_q:
            query["$or"] = [
                {"name": {"$regex": search_q, "$options": "i"}},
                {"sku": {"$regex": search_q, "$options": "i"}},
                {"category": {"$regex": search_q, "$options": "i"}}
            ]

        # Apply category filter
        if category_filter:
            query["category"] = category_filter

        skip = (page - 1) * limit
        total = await self.repository.count_items(query)
        items = await self.repository.list_items(query, skip=skip, limit=limit)
        pages = (total + limit - 1) // limit

        return {"items": items, "total": total, "pages": pages}

    async def get_item_detail(self, item_id: str, current_user: dict) -> dict:
        """Fetch individual item details asserting isolation boundaries."""
        tenant_id = current_user["tenant_id"]
        role = current_user["role"]

        item = await self.repository.find_by_id(item_id, tenant_id)
        if not item:
            raise NotFoundException("Inventory item not found.")

        # Non-Super-Admins can only query items in their own warehouse
        if role != "super_admin" and item["warehouse_id"] != current_user.get("warehouse_id"):
            raise PermissionException("Unauthorized: You do not have access to this warehouse catalog.")

        return item

    async def create_item(self, payload: ItemCreate, current_user: dict) -> dict:
        """Register a new item, validating SKU uniqueness and scoping rules."""
        role = current_user["role"]
        tenant_id = current_user["tenant_id"]
        user_id = current_user.get("_id") or current_user.get("id")

        # Privilege Check: Only super_admin, admin, manager can create items
        if role not in ["super_admin", "admin", "manager"]:
            raise PermissionException("Unauthorized: You do not have permissions to register new catalog items.")

        # Non-super_admins can only register items to their assigned warehouse
        wh_id = payload.warehouse_id
        if role != "super_admin" and wh_id != current_user.get("warehouse_id"):
            raise PermissionException("Unauthorized: You can only register items inside your assigned warehouse.")

        # Auto-compute SKU if missing
        sku = payload.sku.strip() if payload.sku else f"SKU-WS-{wh_id}-{int(datetime.utcnow().timestamp())}"

        # Verify SKU uniqueness per warehouse
        if not await self.verify_sku_uniqueness(sku, wh_id, tenant_id):
            raise ValidationException(f"Catalog SKU '{sku}' already exists in this warehouse partition.")

        # Atomic enterprise ID + barcode assignment
        enterprise_id = await self.registry.get_next_enterprise_id(tenant_id, "ITEM")

        item_doc = {
            "tenant_id": tenant_id,
            "warehouse_id": wh_id,
            "enterprise_id": enterprise_id,
            "barcode": enterprise_id,
            "sku": sku,
            "name": payload.name,
            "category": payload.category,
            "price": payload.price,
            "stock": payload.stock,
            "unit": payload.unit,
            "tax_category": payload.tax_category,
            "images": payload.images or [],
            "created_by": user_id,
            "created_at": datetime.utcnow(),
            "low_stock_threshold": payload.low_stock_threshold
        }

        created = await self.repository.create_item(item_doc)

        # Register inventory item in centralized ledger registry
        await self.registry.register_entity(
            tenant_id=tenant_id,
            entity_type="inventory",
            entity_id=enterprise_id,
            barcode=enterprise_id,
            warehouse_id=wh_id,
            creator_id=str(user_id),
            creator_name=current_user["name"],
            snapshot=created
        )

        # Log audit operation
        await self.audit.log_event(
            user_id=str(user_id),
            user_name=current_user["name"],
            action="item_create",
            description=f"Registered new inventory item: '{payload.name}' (SKU: {sku}, ID: {enterprise_id})",
            tenant_id=tenant_id,
            warehouse_id=wh_id
        )

        # Trigger real-time broadcast fallback for standalone server configurations
        try:
            from src.modules.realtime import ws_manager, normalize_doc
            asyncio.create_task(ws_manager.broadcast_event(
                tenant_id=tenant_id,
                event_type="inventory_change",
                data=normalize_doc(created),
                warehouse_id=wh_id
            ))
        except Exception as e:
            logger.debug(f"Manual WebSocket broadcast failed for item creation: {e}")

        return created

    async def update_item(self, item_id: str, payload: ItemUpdate, current_user: dict) -> dict:
        """Update inventory parameters enforcing hierarchical privilege locks."""
        role = current_user["role"]
        tenant_id = current_user["tenant_id"]
        user_id = current_user.get("_id") or current_user.get("id")

        # Privilege Check: Only super_admin, admin, manager can update items
        if role not in ["super_admin", "admin", "manager"]:
            raise PermissionException("Unauthorized: You do not have permissions to modify inventory entries.")

        item = await self.repository.find_by_id(item_id, tenant_id)
        if not item:
            raise NotFoundException("Inventory item not found.")

        # Non-super_admins can only update items in their assigned warehouse
        if role != "super_admin" and item["warehouse_id"] != current_user.get("warehouse_id"):
            raise PermissionException("Unauthorized: You can only edit items inside your assigned warehouse.")

        update_data = payload.dict(exclude_unset=True)
        if not update_data:
            return item

        # If warehouse is reassigned (Super Admin only), enforce SKU uniqueness in the target
        target_wh = update_data.get("warehouse_id") or item["warehouse_id"]
        if role != "super_admin" and "warehouse_id" in update_data and update_data["warehouse_id"] != item["warehouse_id"]:
            raise PermissionException("Unauthorized: You cannot reassign items to other warehouses.")

        # Check SKU collision if SKU is updated
        new_sku = update_data.get("sku")
        if new_sku and new_sku != item["sku"]:
            if not await self.verify_sku_uniqueness(new_sku, target_wh, tenant_id):
                raise ValidationException(f"Catalog SKU '{new_sku}' already exists in the target warehouse partition.")

        update_data["updated_at"] = datetime.utcnow()
        updated = await self.repository.update_item(item_id, tenant_id, update_data)

        # Snapshot update logic scoped inside Central Registry
        enterprise_id = updated.get("enterprise_id")
        if not enterprise_id:
            # Backward compatibility fallback
            enterprise_id = await self.registry.get_next_enterprise_id(tenant_id, "ITEM")
            await self.repository.update_item(item_id, tenant_id, {"enterprise_id": enterprise_id, "barcode": enterprise_id})
            updated["enterprise_id"] = enterprise_id
            updated["barcode"] = enterprise_id

        await self.registry.register_entity(
            tenant_id=tenant_id,
            entity_type="inventory",
            entity_id=enterprise_id,
            barcode=enterprise_id,
            warehouse_id=item["warehouse_id"],
            creator_id=str(user_id),
            creator_name=current_user["name"],
            snapshot=updated
        )

        # Log audit operation
        await self.audit.log_event(
            user_id=str(user_id),
            user_name=current_user["name"],
            action="item_update",
            description=f"Updated inventory item details for: '{item['name']}' (ID: {enterprise_id})",
            tenant_id=tenant_id,
            warehouse_id=item["warehouse_id"]
        )

        # Trigger real-time broadcast fallback for standalone server configurations
        try:
            from src.modules.realtime import ws_manager, normalize_doc
            asyncio.create_task(ws_manager.broadcast_event(
                tenant_id=tenant_id,
                event_type="inventory_change",
                data=normalize_doc(updated),
                warehouse_id=updated.get("warehouse_id")
            ))
        except Exception as e:
            logger.debug(f"Manual WebSocket broadcast failed for item update: {e}")

        return updated

    async def delete_item(self, item_id: str, current_user: dict) -> bool:
        """Delete inventory document cleanly."""
        role = current_user["role"]
        tenant_id = current_user["tenant_id"]
        user_id = current_user.get("_id") or current_user.get("id")

        # Privilege Check: Only super_admin, admin, manager can delete items
        if role not in ["super_admin", "admin", "manager"]:
            raise PermissionException("Unauthorized: You do not have permissions to delete catalog items.")

        item = await self.repository.find_by_id(item_id, tenant_id)
        if not item:
            raise NotFoundException("Inventory item not found.")

        # Non-super_admins can only delete items in their assigned warehouse
        if role != "super_admin" and item["warehouse_id"] != current_user.get("warehouse_id"):
            raise PermissionException("Unauthorized: You do not have access to this warehouse registry.")

        # Move document to trash to act as a soft-delete
        item_data = dict(item)
        # Avoid timezone-offset issues with datetime in JSON/Pydantic
        if "created_at" in item_data and isinstance(item_data["created_at"], datetime):
            item_data["created_at"] = item_data["created_at"].isoformat()
        if "updated_at" in item_data and isinstance(item_data["updated_at"], datetime):
            item_data["updated_at"] = item_data["updated_at"].isoformat()
        if "price" in item_data and isinstance(item_data["price"], Decimal):
            item_data["price"] = float(item_data["price"])

        await self.trash.soft_delete(
            doc_id=item_id,
            original_collection="inventory_items",
            tenant_id=tenant_id,
            deleted_by=str(user_id),
            data=item_data
        )

        deleted = await self.repository.delete_item(item_id, tenant_id)

        if deleted:
            # Log audit operation
            await self.audit.log_event(
                user_id=str(user_id),
                user_name=current_user["name"],
                action="item_delete",
                description=f"Deleted inventory item: '{item['name']}' (SKU: {item['sku']})",
                tenant_id=tenant_id,
                warehouse_id=item["warehouse_id"]
            )

            # Trigger real-time broadcast fallback for standalone server configurations
            try:
                from src.modules.realtime import ws_manager
                asyncio.create_task(ws_manager.broadcast_event(
                    tenant_id=tenant_id,
                    event_type="inventory_change",
                    data={"id": item_id, "_id": item_id, "action": "delete"},
                    warehouse_id=item["warehouse_id"]
                ))
            except Exception as e:
                logger.debug(f"Manual WebSocket broadcast failed for item deletion: {e}")

        return deleted

    async def get_analytics_summary(self, current_user: dict, warehouse_id: str = None) -> dict:
        """Compute top-level inventory KPI stats utilizing native MongoDB aggregates."""
        tenant_id = current_user["tenant_id"]
        role = current_user["role"]

        query = {"tenant_id": tenant_id}
        if role != "super_admin":
            query["warehouse_id"] = current_user.get("warehouse_id")
        elif warehouse_id:
            query["warehouse_id"] = warehouse_id

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": None,
                "total_items": {"$sum": 1},
                "total_stock": {"$sum": "$stock"},
                "total_valuation": {"$sum": {"$multiply": ["$price", "$stock"]}},
                "low_stock": {"$sum": {"$cond": [{"$lt": ["$stock", {"$ifNull": ["$low_stock_threshold", 20]}]}, 1, 0]}},
                "out_of_stock": {"$sum": {"$cond": [{"$eq": ["$stock", 0]}, 1, 0]}}
            }}
        ]

        cursor = self.db.inventory_items.aggregate(pipeline)
        res = await cursor.to_list(length=1)

        if not res:
            return {
                "totalItems": 0,
                "totalStock": 0,
                "totalValuation": 0.0,
                "lowStockItems": 0,
                "outOfStockItems": 0
            }

        data = res[0]
        return {
            "totalItems": data.get("total_items", 0),
            "totalStock": data.get("total_stock", 0),
            "totalValuation": self._convert_decimal128_value(data.get("total_valuation")),
            "lowStockItems": data.get("low_stock", 0),
            "outOfStockItems": data.get("out_of_stock", 0)
        }

    async def get_analytics_categories(self, current_user: dict, warehouse_id: str = None) -> list[dict]:
        """Aggregate product counts and monetary valuation per category segment."""
        tenant_id = current_user["tenant_id"]
        role = current_user["role"]

        query = {"tenant_id": tenant_id}
        if role != "super_admin":
            query["warehouse_id"] = current_user.get("warehouse_id")
        elif warehouse_id:
            query["warehouse_id"] = warehouse_id

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$category",
                "item_count": {"$sum": 1},
                "total_stock": {"$sum": "$stock"},
                "total_valuation": {"$sum": {"$multiply": ["$price", "$stock"]}}
            }},
            {"$sort": {"total_valuation": -1}}
        ]

        cursor = self.db.inventory_items.aggregate(pipeline)
        res = await cursor.to_list(length=100)

        categories_res = []
        for cat in res:
            categories_res.append({
                "category": cat["_id"] or "Other",
                "itemCount": cat["item_count"],
                "totalStock": cat["total_stock"],
                "totalValuation": self._convert_decimal128_value(cat["total_valuation"])
            })
        return categories_res

    async def get_analytics_stock_status(self, current_user: dict, warehouse_id: str = None) -> dict:
        """Categorize and count stock records into active health buckets."""
        tenant_id = current_user["tenant_id"]
        role = current_user["role"]

        query = {"tenant_id": tenant_id}
        if role != "super_admin":
            query["warehouse_id"] = current_user.get("warehouse_id")
        elif warehouse_id:
            query["warehouse_id"] = warehouse_id

        pipeline = [
            {"$match": query},
            {"$project": {
                "status": {
                    "$cond": [
                        {"$eq": ["$stock", 0]},
                        "out_of_stock",
                        {"$cond": [{"$lt": ["$stock", {"$ifNull": ["$low_stock_threshold", 20]}]}, "low_stock", "in_stock"]}
                    ]
                }
            }},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]

        cursor = self.db.inventory_items.aggregate(pipeline)
        res = await cursor.to_list(length=5)

        status_counts = {"in_stock": 0, "low_stock": 0, "out_of_stock": 0}
        for bucket in res:
            status_counts[bucket["_id"]] = bucket["count"]

        return {
            "inStock": status_counts["in_stock"],
            "lowStock": status_counts["low_stock"],
            "outOfStock": status_counts["out_of_stock"]
        }

    async def get_analytics_trends(self, current_user: dict, warehouse_id: str = None) -> list[dict]:
        """Aggregate monthly inventory registrations trend."""
        tenant_id = current_user["tenant_id"]
        role = current_user["role"]

        query = {"tenant_id": tenant_id}
        if role != "super_admin":
            query["warehouse_id"] = current_user.get("warehouse_id")
        elif warehouse_id:
            query["warehouse_id"] = warehouse_id

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"}
                },
                "items_added": {"$sum": 1},
                "stock_volume": {"$sum": "$stock"}
            }},
            {"$sort": {"_id.year": 1, "_id.month": 1}}
        ]

        cursor = self.db.inventory_items.aggregate(pipeline)
        res = await cursor.to_list(length=12)

        trends = []
        months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for trend in res:
            yr = trend["_id"]["year"]
            mn = trend["_id"]["month"]
            label = f"{months[mn]} {yr}"
            trends.append({
                "period": label,
                "itemsAdded": trend["items_added"],
                "stockVolume": trend["stock_volume"]
            })
        return trends

    async def generate_barcodes(self, payload: any, current_user: dict) -> dict:
        """Batch generate unique barcodes for an item, syncing stock level and registry logs."""
        role = current_user["role"]
        tenant_id = current_user["tenant_id"]
        user_id = current_user.get("_id") or current_user.get("id")

        if role not in ["super_admin", "admin", "manager"]:
            raise PermissionException("Unauthorized to generate barcodes.")

        item = None
        generated_barcodes = []

        if payload.itemId:
            # Existing Item
            item = await self.get_item_detail(payload.itemId, current_user)
            wh_id = item["warehouse_id"]
            
            # Generate unique barcodes
            for _ in range(payload.quantity):
                barcode = await self.registry.get_next_enterprise_id(tenant_id, "ITEM")
                generated_barcodes.append(barcode)
                
                # Register in Central Ledger
                await self.registry.register_entity(
                    tenant_id=tenant_id,
                    entity_type="inventory",
                    entity_id=barcode,
                    barcode=barcode,
                    warehouse_id=wh_id,
                    creator_id=str(user_id),
                    creator_name=current_user["name"],
                    snapshot=item
                )

            # Update item barcodes list and stock count in db
            existing_barcodes = item.get("barcodes") or []
            if item.get("barcode") and item.get("barcode") not in existing_barcodes:
                existing_barcodes.append(item["barcode"])
            
            new_barcodes = existing_barcodes + generated_barcodes
            new_stock = item["stock"] + payload.quantity

            updated = await self.repository.update_item(
                item["id"],
                tenant_id,
                {
                    "stock": new_stock,
                    "barcodes": new_barcodes,
                    "status": "in_stock" if new_stock > 0 else "out_of_stock"
                }
            )
            item = updated
        else:
            # New Item: payload.newItem must be provided
            if not payload.newItem:
                raise ValidationException("newItem configuration required to create a new item.")

            # Non-super_admins can only register items to their assigned warehouse
            wh_id = payload.newItem.warehouse_id
            if role != "super_admin" and wh_id != current_user.get("warehouse_id"):
                raise PermissionException("Unauthorized: You can only register items inside your assigned warehouse.")

            # Create item document with stock = payload.quantity
            # Create it with stock = 0, then generate barcodes and update it
            payload_new = payload.newItem
            payload_new.stock = 0
            new_item = await self.create_item(payload_new, current_user)
            
            # Generate N unique barcodes
            for _ in range(payload.quantity):
                barcode = await self.registry.get_next_enterprise_id(tenant_id, "ITEM")
                generated_barcodes.append(barcode)
                
                # Register in Central Ledger
                await self.registry.register_entity(
                    tenant_id=tenant_id,
                    entity_type="inventory",
                    entity_id=barcode,
                    barcode=barcode,
                    warehouse_id=wh_id,
                    creator_id=str(user_id),
                    creator_name=current_user["name"],
                    snapshot=new_item
                )
            
            # Update the item with the list of barcodes and stock
            existing_barcodes = [new_item["barcode"]] if new_item.get("barcode") else []
            new_barcodes = existing_barcodes + generated_barcodes
            
            updated = await self.repository.update_item(
                new_item["id"],
                tenant_id,
                {
                    "stock": payload.quantity,
                    "barcodes": new_barcodes,
                    "status": "in_stock" if payload.quantity > 0 else "out_of_stock"
                }
            )
            item = updated

        # Log audit operation
        await self.audit.log_event(
            user_id=str(user_id),
            user_name=current_user["name"],
            action="item_barcodes_generate",
            description=f"Generated {payload.quantity} barcodes for item: '{item['name']}' (SKU: {item['sku']})",
            tenant_id=tenant_id,
            warehouse_id=wh_id
        )

        # Trigger WebSocket refresh
        try:
            from src.modules.realtime import ws_manager, normalize_doc
            asyncio.create_task(ws_manager.broadcast_event(
                tenant_id=tenant_id,
                event_type="inventory_change",
                data=normalize_doc(item),
                warehouse_id=wh_id
            ))
        except Exception as e:
            logger.debug(f"WS broadcast failed: {e}")

        from src.modules.items.schema import ItemResponse
        serialized = ItemResponse.model_validate(item).model_dump(by_alias=True)
        serialized["barcodes"] = item.get("barcodes", [])
        
        return {
            "item": serialized,
            "barcodes": generated_barcodes
        }

