import logging
import asyncio
from datetime import datetime
from decimal import Decimal
from fastapi import Depends
from bson import ObjectId
from bson.decimal128 import Decimal128
from src.modules.billing.repository import InvoiceRepository
from src.modules.billing.schema import InvoiceCreate
from src.modules.billing.tax_engine import TaxEngine
from src.modules.warehouses.repository import WarehouseRepository
from src.modules.items.repository import ItemRepository
from src.middleware.exceptions import PermissionException, NotFoundException, ValidationException
from src.database import get_db
from src.modules.auth.dependencies import check_user_permission
from src.modules.audit_logs.service import AuditLogService
from src.modules.trash.service import TrashService
from src.modules.registry.service import CentralRegistryService, CustomerService

logger = logging.getLogger("wareops_erp.modules.billing.service")


class BillingService:
    def __init__(
        self,
        repository: InvoiceRepository = Depends(),
        warehouse_repo: WarehouseRepository = Depends(),
        item_repo: ItemRepository = Depends(),
        db=Depends(get_db),
        audit: AuditLogService = Depends(),
        trash: TrashService = Depends(),
        registry: CentralRegistryService = Depends(),
        customer_service: CustomerService = Depends()
    ):
        self.repository = repository
        self.warehouse_repo = warehouse_repo
        self.item_repo = item_repo
        self.db = db
        self.audit = audit
        self.trash = trash
        self.registry = registry
        self.customer_service = customer_service

    def _convert_decimal128_value(self, val) -> float:
        """Helper to convert BSON Decimal128 fields back to float."""
        if isinstance(val, Decimal128):
            return float(val.to_decimal())
        elif isinstance(val, Decimal):
            return float(val)
        return float(val or 0.0)

    async def create_invoice(self, payload: InvoiceCreate, current_user: dict) -> dict:
        """Generate invoice, trigger atomic stock reductions, and record tax snapshots."""
        role = current_user["role"]
        tenant_id = current_user["tenant_id"]
        user_id = str(current_user.get("_id") or current_user.get("id"))

        # Privilege Check: super_admin, admin, manager, staff are allowed to bill
        if not await check_user_permission(current_user, "billing", "create", self.db):
            raise PermissionException("Unauthorized: You do not have billing permissions.")

        # Scoping Check: Non-super_admins can only generate bills for their assigned warehouse
        wh_id = payload.warehouse_id
        if role != "super_admin" and wh_id != current_user.get("warehouse_id"):
            raise PermissionException("Unauthorized: You can only issue invoices inside your assigned warehouse.")

        # Retrieve warehouse to fetch regional tax configs
        wh = await self.warehouse_repo.find_by_id_and_tenant(wh_id, tenant_id)
        if not wh:
            raise NotFoundException("Warehouse registry not found.")

        tax_config = wh.get("taxConfig", {"luxury": 15.0, "normal": 5.0})
        tax_snapshot = {
            "normal": Decimal(str(tax_config.get("normal", 5.0))),
            "luxury": Decimal(str(tax_config.get("luxury", 15.0)))
        }

        tax_rates_decimal = {
            "normal": Decimal(str(tax_config.get("normal", 5.0))) / Decimal("100"),
            "luxury": Decimal(str(tax_config.get("luxury", 15.0))) / Decimal("100")
        }

        # Check if database is configured as a replica set supporting transactions
        try:
            hello_res = await self.db.command("hello")
            is_replica_set = "setName" in hello_res
        except Exception:
            is_replica_set = False

        # Load active items catalog, check stock counts, and deduct stock atomically
        if is_replica_set:
            client = self.db.client
            async with await client.start_session() as session:
                async with session.start_transaction():
                    try:
                        for it in payload.items:
                            item = await self.item_repo.find_by_id(it.item_id, tenant_id)
                            if not item:
                                raise NotFoundException(f"Catalog Item '{it.name}' not found.")
                            
                            # Enforce warehouse boundaries on items
                            if item["warehouse_id"] != wh_id:
                                raise PermissionException(f"Item '{it.name}' does not belong to the target warehouse.")

                            # Prevent negative inventory states
                            current_stock = item.get("stock", 0)
                            if current_stock < it.qty:
                                raise ValidationException(
                                    f"Insufficient stock for '{it.name}'. Requested: {it.qty}, Available: {current_stock}."
                                )

                            # Atomic deduction using find_one_and_update in session
                            new_stock = current_stock - it.qty
                            try:
                                obj_id = ObjectId(item["_id"])
                            except Exception:
                                obj_id = item["_id"]
                            await self.db.inventory_items.update_one(
                                {"_id": obj_id},
                                {"$set": {"stock": new_stock}},
                                session=session
                            )

                        # Core decimal tax calculations
                        items_for_engine = []
                        for it in payload.items:
                            items_for_engine.append({
                                "id": it.item_id,
                                "name": it.name,
                                "qty": it.qty,
                                "price": Decimal(str(it.price)),
                                "tax_category": it.tax_category,
                                "taxes": [t.model_dump() for t in it.taxes] if it.taxes else None
                            })

                        engine_res = TaxEngine.calculate_taxes(items_for_engine, tax_rates_decimal)
                        bill_no = await self.registry.get_next_enterprise_id(tenant_id, "INV")

                        # Setup seller defaults from warehouse
                        wh_email = wh.get("email", "")
                        wh_contact = wh.get("contact", "")
                        gstin_fallback = f"27{wh_email.upper()[:3]}C{wh_contact[-4:] if len(wh_contact) >= 4 else '1234'}F1Z5" if wh_email else "27AAPCW1234F1Z5"

                        invoice_doc = {
                            "tenant_id": tenant_id,
                            "warehouse_id": wh_id,
                            "bill_no": bill_no,
                            "enterprise_id": bill_no,
                            "barcode": bill_no,
                            "customer": payload.customer,
                            "items": engine_res["items"],
                            "subtotal": engine_res["subtotal"],
                            "tax": engine_res["tax"],
                            "total": engine_res["total"],
                            "tax_config_snapshot": tax_snapshot,
                            "tax_details": engine_res["tax_details"],
                            "currency": payload.currency,
                            "exchange_rate": payload.exchange_rate,
                            "created_by": user_id,
                            "created_at": datetime.utcnow(),
                            # Seller info
                            "seller_address": payload.seller_address or wh.get("address") or "Primary Logistics Hub",
                            "seller_contact": payload.seller_contact or wh.get("contact") or "Contact Office",
                            "seller_tax_number": payload.seller_tax_number or wh.get("tax_number") or wh.get("gstin") or gstin_fallback,
                            # Buyer info
                            "buyer_billing_address": payload.buyer_billing_address,
                            "buyer_shipping_address": payload.buyer_shipping_address,
                            "customer_phone": payload.customer_phone,
                            "customer_email": payload.customer_email,
                            # Employee session snapshot
                            "employee_id": user_id,
                            "employee_name": current_user.get("name") or "System Creator",
                            "employee_role": current_user.get("role") or "staff"
                        }

                        created = await self.repository.create_invoice(invoice_doc, session=session)

                        # Register in centralized tracking registry
                        await self.registry.register_entity(
                            tenant_id=tenant_id,
                            entity_type="invoice",
                            entity_id=bill_no,
                            barcode=bill_no,
                            warehouse_id=wh_id,
                            creator_id=user_id,
                            creator_name=current_user["name"],
                            snapshot=created
                        )

                        # Auto CRM repeat customer registration/update
                        cust_payload = {
                            "name": payload.customer,
                            "phone": payload.customer_phone or "",
                            "email": payload.customer_email or "",
                            "address": payload.buyer_billing_address or "",
                            "tax_number": ""
                        }
                        await self.customer_service.register_invoice_to_customer(
                            tenant_id=tenant_id,
                            customer_payload=cust_payload,
                            invoice_doc=created,
                            creator_id=user_id
                        )

                        # Insert audit log inside session
                        await self.audit.log_event(
                            user_id=user_id,
                            user_name=current_user["name"],
                            action="bill_create",
                            description=f"Bill generated: {bill_no} — ${engine_res['total']}",
                            tenant_id=tenant_id,
                            warehouse_id=wh_id,
                            session=session
                        )

                        # Trigger real-time broadcast fallback for standalone server configurations
                        try:
                            from src.modules.realtime import ws_manager, normalize_doc
                            asyncio.create_task(ws_manager.broadcast_event(
                                tenant_id=tenant_id,
                                event_type="billing_completion",
                                data=normalize_doc(created),
                                warehouse_id=wh_id
                            ))
                        except Exception as e:
                            logger.debug(f"Manual WebSocket broadcast failed for billing completion: {e}")

                        return created
                    except Exception as e:
                        logger.error(f"Transaction aborted. Rolling back changes. Reason: {e}")
                        raise e
        else:
            # Standalone fallback: execute sequential deductions with manual rollback
            logger.warning("MongoDB is running in Standalone mode. Executing manual sequential rollback fallback...")
            original_stocks = {}
            deducted_items = []
            try:
                for it in payload.items:
                    item = await self.item_repo.find_by_id(it.item_id, tenant_id)
                    if not item:
                        raise NotFoundException(f"Catalog Item '{it.name}' not found.")
                    
                    if item["warehouse_id"] != wh_id:
                        raise PermissionException(f"Item '{it.name}' does not belong to the target warehouse.")

                    current_stock = item.get("stock", 0)
                    if current_stock < it.qty:
                        raise ValidationException(
                            f"Insufficient stock for '{it.name}'. Requested: {it.qty}, Available: {current_stock}."
                        )

                    # Store original stock for rollback
                    original_stocks[item["_id"]] = current_stock

                    # Deduct sequentially
                    new_stock = current_stock - it.qty
                    try:
                        obj_id = ObjectId(item["_id"])
                    except Exception:
                        obj_id = item["_id"]
                    await self.db.inventory_items.update_one(
                        {"_id": obj_id},
                        {"$set": {"stock": new_stock}}
                    )
                    deducted_items.append(item["_id"])

                # Core decimal tax calculations
                items_for_engine = []
                for it in payload.items:
                    items_for_engine.append({
                        "id": it.item_id,
                        "name": it.name,
                        "qty": it.qty,
                        "price": Decimal(str(it.price)),
                        "tax_category": it.tax_category,
                        "taxes": [t.model_dump() for t in it.taxes] if it.taxes else None
                    })

                engine_res = TaxEngine.calculate_taxes(items_for_engine, tax_rates_decimal)
                bill_no = await self.registry.get_next_enterprise_id(tenant_id, "INV")

                # Setup seller defaults from warehouse
                wh_email = wh.get("email", "")
                wh_contact = wh.get("contact", "")
                gstin_fallback = f"27{wh_email.upper()[:3]}C{wh_contact[-4:] if len(wh_contact) >= 4 else '1234'}F1Z5" if wh_email else "27AAPCW1234F1Z5"

                invoice_doc = {
                    "tenant_id": tenant_id,
                    "warehouse_id": wh_id,
                    "bill_no": bill_no,
                    "enterprise_id": bill_no,
                    "barcode": bill_no,
                    "customer": payload.customer,
                    "items": engine_res["items"],
                    "subtotal": engine_res["subtotal"],
                    "tax": engine_res["tax"],
                    "total": engine_res["total"],
                    "tax_config_snapshot": tax_snapshot,
                    "tax_details": engine_res["tax_details"],
                    "currency": payload.currency,
                    "exchange_rate": payload.exchange_rate,
                    "created_by": user_id,
                    "created_at": datetime.utcnow(),
                    # Seller info
                    "seller_address": payload.seller_address or wh.get("address") or "Primary Logistics Hub",
                    "seller_contact": payload.seller_contact or wh.get("contact") or "Contact Office",
                    "seller_tax_number": payload.seller_tax_number or wh.get("tax_number") or wh.get("gstin") or gstin_fallback,
                    # Buyer info
                    "buyer_billing_address": payload.buyer_billing_address,
                    "buyer_shipping_address": payload.buyer_shipping_address,
                    "customer_phone": payload.customer_phone,
                    "customer_email": payload.customer_email,
                    # Employee session snapshot
                    "employee_id": user_id,
                    "employee_name": current_user.get("name") or "System Creator",
                    "employee_role": current_user.get("role") or "staff"
                }

                created = await self.repository.create_invoice(invoice_doc, session=None)

                # Register in centralized tracking registry
                await self.registry.register_entity(
                    tenant_id=tenant_id,
                    entity_type="invoice",
                    entity_id=bill_no,
                    barcode=bill_no,
                    warehouse_id=wh_id,
                    creator_id=user_id,
                    creator_name=current_user["name"],
                    snapshot=created
                )

                # Auto CRM repeat customer registration/update
                cust_payload = {
                    "name": payload.customer,
                    "phone": payload.customer_phone or "",
                    "email": payload.customer_email or "",
                    "address": payload.buyer_billing_address or "",
                    "tax_number": ""
                }
                await self.customer_service.register_invoice_to_customer(
                    tenant_id=tenant_id,
                    customer_payload=cust_payload,
                    invoice_doc=created,
                    creator_id=user_id
                )

                # Insert audit log
                await self.audit.log_event(
                    user_id=user_id,
                    user_name=current_user["name"],
                    action="bill_create",
                    description=f"Bill generated: {bill_no} — ${engine_res['total']}",
                    tenant_id=tenant_id,
                    warehouse_id=wh_id
                )

                # Trigger real-time broadcast fallback for standalone server configurations
                try:
                    from src.modules.realtime import ws_manager, normalize_doc
                    asyncio.create_task(ws_manager.broadcast_event(
                        tenant_id=tenant_id,
                        event_type="billing_completion",
                        data=normalize_doc(created),
                        warehouse_id=wh_id
                    ))
                except Exception as e:
                    logger.debug(f"Manual WebSocket broadcast failed for billing completion: {e}")

                return created

            except Exception as e:
                logger.warning(f"Standalone deduction failed. Triggering manual rollback for {len(deducted_items)} items...")
                for item_id in deducted_items:
                    orig = original_stocks.get(item_id)
                    if orig is not None:
                        try:
                            obj_id = ObjectId(item_id)
                        except Exception:
                            obj_id = item_id
                        await self.db.inventory_items.update_one(
                            {"_id": obj_id},
                            {"$set": {"stock": orig}}
                        )
                raise e

    async def list_invoices(
        self,
        current_user: dict,
        search_q: str = "",
        warehouse_filter: str = "",
        page: int = 1,
        limit: int = 10
    ) -> dict:
        """List active invoices scoped according to role privilege hierarchies."""
        if not await check_user_permission(current_user, "billing", "view", self.db):
            raise PermissionException("Unauthorized: You do not have permission to view invoices.")
        tenant_id = current_user["tenant_id"]
        role = current_user["role"]

        query = {"tenant_id": tenant_id}

        # Enforce warehouse isolation scoping
        if role != "super_admin":
            my_wh = current_user.get("warehouse_id")
            if not my_wh:
                return {"bills": [], "total": 0, "pages": 0}
            query["warehouse_id"] = my_wh

            # Scoping Check: non-super_admins see only invoices created by users in their warehouse <= their role level
            levels = {"employee": 1, "staff": 2, "manager": 3, "admin": 4, "super_admin": 5}
            my_level = levels.get(role, 1)

            # Query workforce list
            cursor = self.db.users.find({
                "tenant_id": tenant_id,
                "warehouse_id": my_wh
            })
            workforce = await cursor.to_list(length=1000)
            visible_users_ids = [str(u["_id"]) for u in workforce if levels.get(u.get("role", "employee"), 1) <= my_level]
            # Ensure the user can always see their own bills
            user_id = str(current_user.get("_id") or current_user.get("id"))
            if user_id not in visible_users_ids:
                visible_users_ids.append(user_id)

            query["created_by"] = {"$in": visible_users_ids}
        else:
            # Super Admin can filter by warehouse
            if warehouse_filter:
                query["warehouse_id"] = warehouse_filter

        # Apply search matching customer or bill number
        if search_q:
            query["$or"] = [
                {"customer": {"$regex": search_q, "$options": "i"}},
                {"bill_no": {"$regex": search_q, "$options": "i"}}
            ]

        skip = (page - 1) * limit
        total = await self.repository.count_invoices(query)
        bills = await self.repository.list_invoices(query, skip=skip, limit=limit)
        pages = (total + limit - 1) // limit

        return {"bills": bills, "total": total, "pages": pages}

    async def get_invoice_detail(self, bill_id: str, current_user: dict) -> dict:
        """Query individual invoice details asserting scoping restrictions."""
        if not await check_user_permission(current_user, "billing", "view", self.db):
            raise PermissionException("Unauthorized: You do not have permission to view invoice details.")
        tenant_id = current_user["tenant_id"]
        role = current_user["role"]

        bill = await self.repository.find_by_id(bill_id, tenant_id)
        if not bill:
            raise NotFoundException("Invoice registry not found.")

        # Scoping bounds check
        if role != "super_admin" and bill["warehouse_id"] != current_user.get("warehouse_id"):
            raise PermissionException("Unauthorized: You do not have permissions to access this invoice.")

        return bill

    async def get_analytics_revenue(self, current_user: dict, warehouse_id: str = None) -> dict:
        """Compute aggregated revenue, tax, net earnings, and average invoicing size."""
        if not await check_user_permission(current_user, "reports", "view", self.db):
            raise PermissionException("Unauthorized: You do not have permission to view billing analytics.")
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
                "gross_revenue": {"$sum": "$total"},
                "tax_collected": {"$sum": "$tax"},
                "subtotal": {"$sum": "$subtotal"},
                "invoice_count": {"$sum": 1}
            }}
        ]

        cursor = self.db.bills.aggregate(pipeline)
        res = await cursor.to_list(length=1)

        if not res:
            return {
                "grossRevenue": 0.0,
                "taxCollected": 0.0,
                "netRevenue": 0.0,
                "avgInvoice": 0.0,
                "invoiceCount": 0
            }

        data = res[0]
        gross = self._convert_decimal128_value(data.get("gross_revenue"))
        tax = self._convert_decimal128_value(data.get("tax_collected"))
        count = data.get("invoice_count", 0)

        return {
            "grossRevenue": gross,
            "taxCollected": tax,
            "netRevenue": gross - tax,
            "avgInvoice": gross / count if count > 0 else 0.0,
            "invoiceCount": count
        }

    async def get_analytics_trends(self, current_user: dict, warehouse_id: str = None) -> list[dict]:
        """Aggregate monthly gross and tax trends for drawing charts."""
        if not await check_user_permission(current_user, "reports", "view", self.db):
            raise PermissionException("Unauthorized: You do not have permission to view revenue analytics trends.")
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
                "revenue": {"$sum": "$total"},
                "tax": {"$sum": "$tax"}
            }},
            {"$sort": {"_id.year": 1, "_id.month": 1}}
        ]

        cursor = self.db.bills.aggregate(pipeline)
        res = await cursor.to_list(length=12)

        trends = []
        months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for trend in res:
            yr = trend["_id"]["year"]
            mn = trend["_id"]["month"]
            label = f"{months[mn]} {yr}"
            trends.append({
                "period": label,
                "revenue": self._convert_decimal128_value(trend["revenue"]),
                "tax": self._convert_decimal128_value(trend["tax"])
            })
        return trends

    async def get_analytics_top_items(self, current_user: dict, warehouse_id: str = None) -> list[dict]:
        """Aggregate sales quantities grouped by item name to define bestselling items."""
        if not await check_user_permission(current_user, "reports", "view", self.db):
            raise PermissionException("Unauthorized: You do not have permission to view bestseller analytics.")
        tenant_id = current_user["tenant_id"]
        role = current_user["role"]

        query = {"tenant_id": tenant_id}
        if role != "super_admin":
            query["warehouse_id"] = current_user.get("warehouse_id")
        elif warehouse_id:
            query["warehouse_id"] = warehouse_id

        pipeline = [
            {"$match": query},
            {"$unwind": "$items"},
            {"$group": {
                "_id": "$items.name",
                "units_sold": {"$sum": "$items.qty"},
                "revenue_generated": {"$sum": {"$multiply": ["$items.price", "$items.qty"]}}
            }},
            {"$sort": {"units_sold": -1}},
            {"$limit": 5}
        ]

        cursor = self.db.bills.aggregate(pipeline)
        res = await cursor.to_list(length=5)

        items = []
        for doc in res:
            items.append({
                "name": doc["_id"],
                "unitsSold": doc["units_sold"],
                "revenueGenerated": self._convert_decimal128_value(doc["revenue_generated"])
            })
        return items

    async def get_analytics_warehouse_performance(self, current_user: dict) -> list[dict]:
        """Super Admin aggregation showing revenue and invoice stats grouped per warehouse."""
        if not await check_user_permission(current_user, "reports", "view", self.db):
            raise PermissionException("Unauthorized: You do not have permission to view performance reports.")
        if current_user["role"] != "super_admin":
            raise PermissionException("Unauthorized: Only Super Admins can aggregate warehouse performance indexes.")

        tenant_id = current_user["tenant_id"]

        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {"$group": {
                "_id": "$warehouse_id",
                "revenue": {"$sum": "$total"},
                "tax": {"$sum": "$tax"},
                "invoice_count": {"$sum": 1}
            }}
        ]

        cursor = self.db.bills.aggregate(pipeline)
        res = await cursor.to_list(length=100)

        # Map warehouse names dynamically
        whs = await self.db.warehouses.find({"tenant_id": tenant_id}).to_list(length=100)
        wh_names = {str(w["_id"]): w["name"] for w in whs}

        performance = []
        for perf in res:
            wh_id = perf["_id"]
            name = wh_names.get(wh_id, f"Warehouse {wh_id}")
            performance.append({
                "warehouseId": wh_id,
                "warehouseName": name,
                "revenue": self._convert_decimal128_value(perf["revenue"]),
                "tax": self._convert_decimal128_value(perf["tax"]),
                "invoiceCount": perf["invoice_count"]
            })
        return performance

    async def delete_invoice(self, invoice_id: str, current_user: dict) -> bool:
        """Soft delete invoice registry and archive in recovery trash bin (super_admin or admin only)."""
        role = current_user["role"]
        tenant_id = current_user["tenant_id"]
        user_id = str(current_user.get("_id") or current_user.get("id"))

        # Privilege Check: Only super_admin and admin can delete invoices
        if not await check_user_permission(current_user, "billing", "delete", self.db):
            raise PermissionException("Unauthorized: Only Super Admins and Admins can delete invoices.")

        bill = await self.repository.find_by_id(invoice_id, tenant_id)
        if not bill:
            raise NotFoundException("Invoice not found.")

        # Scoping Check: Non-super_admins can only delete invoices inside their assigned warehouse
        if role != "super_admin" and bill["warehouse_id"] != current_user.get("warehouse_id"):
            raise PermissionException("Unauthorized: You do not have permissions to delete invoices in this warehouse.")

        # Snapshot data for recovery bin
        bill_data = dict(bill)
        if "created_at" in bill_data and isinstance(bill_data["created_at"], datetime):
            bill_data["created_at"] = bill_data["created_at"].isoformat()
        # Avoid Decimal128 serialization issue
        if "subtotal" in bill_data:
            bill_data["subtotal"] = self._convert_decimal128_value(bill_data["subtotal"])
        if "tax" in bill_data:
            bill_data["tax"] = self._convert_decimal128_value(bill_data["tax"])
        if "total" in bill_data:
            bill_data["total"] = self._convert_decimal128_value(bill_data["total"])
        for it in bill_data.get("items", []):
            if "price" in it:
                it["price"] = float(it["price"])
            if "tax_rate_snapshot" in it:
                it["tax_rate_snapshot"] = float(it["tax_rate_snapshot"])

        # Soft-delete snapshot
        await self.trash.soft_delete(
            doc_id=invoice_id,
            original_collection="bills",
            tenant_id=tenant_id,
            deleted_by=user_id,
            data=bill_data
        )

        # Erase from main registry
        await self.repository.collection.delete_one({"_id": invoice_id, "tenant_id": tenant_id})

        # Log audit operation
        await self.audit.log_event(
            user_id=user_id,
            user_name=current_user["name"],
            action="invoice_delete",
            description=f"Deleted invoice: '{bill['bill_no']}' for customer '{bill['customer']}'",
            tenant_id=tenant_id,
            warehouse_id=bill["warehouse_id"]
        )

        return True
