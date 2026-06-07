import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import Depends
from src.database import get_db
from src.modules.audit_logs.repository import AuditLogRepository
from src.modules.audit_logs.service import AuditLogService
from src.modules.auth.dependencies import check_user_permission
from src.middleware.exceptions import PermissionException

logger = logging.getLogger("wareops_erp.modules.analytics.service")


class AnalyticsService:
    def __init__(self, db=Depends(get_db)):
        self.db = db

    # Helper to convert Decimal128 values cleanly to floats
    def _to_float(self, val: Any) -> float:
        if val is None:
            return 0.0
        if hasattr(val, "to_decimal"):
            return float(val.to_decimal())
        try:
            return float(val)
        except Exception:
            return 0.0

    async def get_dashboard_summary(self, current_user: dict, warehouse_id: Optional[str] = None) -> Dict[str, Any]:
        """Compile a real-time global or scoped operational dashboard summary for quick rendering."""
        if not await check_user_permission(current_user, "dashboard", "view", self.db):
            raise PermissionException("Unauthorized: You do not have permission to view the dashboard summary.")
        tenant_id = current_user["tenant_id"]
        role = current_user.get("role")

        # Base filters
        wh_filter = warehouse_id
        if role != "super_admin":
            wh_filter = current_user.get("warehouse_id")

        bill_query = {"tenant_id": tenant_id}
        item_query = {"tenant_id": tenant_id}
        user_query = {"tenant_id": tenant_id, "status": "active"}
        wh_query = {"ownerId": str(current_user["_id"])} if role == "super_admin" else {"id": wh_filter}

        if wh_filter:
            bill_query["warehouse_id"] = wh_filter
            item_query["warehouse_id"] = wh_filter
            user_query["warehouse_id"] = wh_filter

        # 1. Bills / Revenue summary
        bills_cursor = self.db.bills.find(bill_query).sort("created_at", -1)
        bills = await bills_cursor.to_list(length=1000)

        total_revenue = 0.0
        total_tax = 0.0
        recent_bills = []

        for b in bills:
            t_rev = self._to_float(b.get("total", 0.0))
            t_tax = self._to_float(b.get("tax", 0.0))
            total_revenue += t_rev
            total_tax += t_tax

            # Capture recent 5 bills flattened
            if len(recent_bills) < 5:
                recent_bills.append({
                    "id": str(b["_id"]),
                    "billNo": b.get("bill_no", ""),
                    "customer": b.get("customer", ""),
                    "warehouseId": b.get("warehouse_id", ""),
                    "total": t_rev,
                    "tax": t_tax,
                    "createdAt": b["created_at"].isoformat() if isinstance(b["created_at"], datetime) else str(b["created_at"])
                })

        # 2. Total items & low stock items count
        items_cursor = self.db.inventory_items.find(item_query)
        items = await items_cursor.to_list(length=10000)

        total_stock = 0
        low_stock_items = []
        low_stock_count = 0

        for i in items:
            stock = int(i.get("stock", 0))
            total_stock += stock
            threshold = int(i.get("low_stock_threshold", 20))
            if stock <= threshold:
                low_stock_count += 1
                if len(low_stock_items) < 5:
                    low_stock_items.append({
                        "id": str(i["_id"]),
                        "name": i.get("name", ""),
                        "sku": i.get("sku", ""),
                        "stock": stock,
                        "price": self._to_float(i.get("price", 0.0)),
                        "warehouseId": i.get("warehouse_id", ""),
                        "lowStockThreshold": threshold
                    })

        # 3. Active users count
        active_users = await self.db.users.count_documents(user_query)

        # 4. Total warehouses count
        warehouses_count = await self.db.warehouses.count_documents(wh_query)

        # 5. Smart Restock Suggestions prioritizations
        restock_suggestions = []
        low_for_restock = [i for i in items if int(i.get("stock", 0)) <= int(i.get("low_stock_threshold", 20))]
        
        # Calculate sales count per low-stock item based on bills
        sales_velocity = {}
        for b in bills:
            for item in b.get("items", []):
                i_id = item.get("item_id")
                qty = int(item.get("qty", 0))
                sales_velocity[i_id] = sales_velocity.get(i_id, 0) + qty

        for i in low_for_restock:
            i_id = str(i["_id"])
            stock = int(i.get("stock", 0))
            threshold = int(i.get("low_stock_threshold", 20))
            sales_count = sales_velocity.get(i_id, 0)
            priority = (sales_count * 2) + (threshold - stock)
            restock_suggestions.append({
                "id": i_id,
                "name": i.get("name", ""),
                "sku": i.get("sku", ""),
                "stock": stock,
                "salesCount": sales_count,
                "priority": priority,
                "warehouseId": i.get("warehouse_id", ""),
                "lowStockThreshold": threshold
            })

        # Sort restock suggestions by priority descending
        restock_suggestions.sort(key=lambda x: x["priority"], reverse=True)
        restock_suggestions = restock_suggestions[:4]

        # 6. Recent Audit Logs (Visible users check scoped inside service)
        audit_repo = AuditLogRepository(db=self.db)
        audit_service = AuditLogService(repository=audit_repo)
        
        # Build standard query filter for logs listing
        log_query = {"tenant_id": tenant_id}
        if role != "super_admin":
            wh_id = current_user.get("warehouse_id")
            log_query["warehouse_id"] = wh_id
            
            levels = {"employee": 1, "staff": 2, "manager": 3, "admin": 4, "super_admin": 5}
            caller_level = levels.get(role, 1)

            users_cursor = self.db.users.find({"warehouse_id": wh_id, "tenant_id": tenant_id})
            users_list = await users_cursor.to_list(length=1000)
            
            visible_user_ids = [str(current_user["_id"])]
            for u in users_list:
                u_role = u.get("role", "employee")
                if levels.get(u_role, 1) <= caller_level:
                    visible_user_ids.append(str(u["_id"]))
            
            log_query["user_id"] = {"$in": visible_user_ids}

        recent_logs_cursor = self.db.audit_logs.find(log_query).sort("timestamp", -1).limit(6)
        recent_logs = await recent_logs_cursor.to_list(length=6)
        serialized_logs = []
        for l in recent_logs:
            ts = l["timestamp"]
            serialized_logs.append({
                "id": str(l["_id"]),
                "action": l.get("action", ""),
                "description": l.get("description", ""),
                "userName": l.get("user_name", "System"),
                "timestamp": ts.isoformat() if isinstance(ts, datetime) else str(ts)
            })

        return {
            "totalRevenue": total_revenue,
            "totalTax": total_tax,
            "totalStock": total_stock,
            "activeUsers": active_users,
            "invoicesCount": len(bills),
            "warehousesCount": warehouses_count,
            "lowStockCount": low_stock_count,
            "recentActivity": serialized_logs,
            "recentBills": recent_bills,
            "lowStockItems": low_stock_items,
            "restockSuggestions": restock_suggestions
        }

    async def get_revenue_analytics(self, current_user: dict, warehouse_id: Optional[str] = None) -> Dict[str, Any]:
        """Compute total gross revenue, tax collected, net earnings, and averages."""
        if not await check_user_permission(current_user, "reports", "view", self.db):
            raise PermissionException("Unauthorized: You do not have permission to view revenue analytics.")
        tenant_id = current_user["tenant_id"]
        role = current_user.get("role")

        query = {"tenant_id": tenant_id}
        if role != "super_admin":
            query["warehouse_id"] = current_user.get("warehouse_id")
        elif warehouse_id:
            query["warehouse_id"] = warehouse_id

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": None,
                "totalRevenue": {"$sum": "$total"},
                "totalTax": {"$sum": "$tax"},
                "invoicesCount": {"$sum": 1}
            }}
        ]

        cursor = self.db.bills.aggregate(pipeline)
        res = await cursor.to_list(length=1)

        if not res:
            return {
                "totalRevenue": 0.0,
                "totalTax": 0.0,
                "netRevenue": 0.0,
                "avgInvoiceValue": 0.0,
                "invoicesCount": 0
            }

        data = res[0]
        total_rev = self._to_float(data.get("totalRevenue", 0.0))
        total_tax = self._to_float(data.get("totalTax", 0.0))
        count = data.get("invoicesCount", 0)

        return {
            "totalRevenue": total_rev,
            "totalTax": total_tax,
            "netRevenue": total_rev - total_tax,
            "avgInvoiceValue": total_rev / count if count > 0 else 0.0,
            "invoicesCount": count
        }

    async def get_inventory_analytics(self, current_user: dict, warehouse_id: Optional[str] = None) -> List[dict]:
        """Break down inventory stock totals and financial valuation grouped per category."""
        if not await check_user_permission(current_user, "reports", "view", self.db):
            raise PermissionException("Unauthorized: You do not have permission to view inventory analytics.")
        tenant_id = current_user["tenant_id"]
        role = current_user.get("role")

        query = {"tenant_id": tenant_id}
        if role != "super_admin":
            query["warehouse_id"] = current_user.get("warehouse_id")
        elif warehouse_id:
            query["warehouse_id"] = warehouse_id

        # Aggregate items categories
        pipeline = [
            {"$match": query},
            # Calculate item valuation inside pipeline: stock * price
            {"$project": {
                "category": 1,
                "stock": 1,
                "valuation": {"$multiply": ["$stock", "$price"]}
            }},
            {"$group": {
                "_id": "$category",
                "totalStock": {"$sum": "$stock"},
                "totalValuation": {"$sum": "$valuation"}
            }},
            {"$sort": {"totalValuation": -1}}
        ]

        cursor = self.db.inventory_items.aggregate(pipeline)
        res = await cursor.to_list(length=100)

        breakdown = []
        for r in res:
            breakdown.append({
                "category": r["_id"] or "Uncategorized",
                "totalStock": int(r.get("totalStock", 0)),
                "totalValuation": self._to_float(r.get("totalValuation", 0.0))
            })
        return breakdown

    async def get_workforce_analytics(self, current_user: dict, warehouse_id: Optional[str] = None) -> List[dict]:
        """Aggregate workforce users role distribution totals."""
        if not await check_user_permission(current_user, "reports", "view", self.db):
            raise PermissionException("Unauthorized: You do not have permission to view workforce analytics.")
        tenant_id = current_user["tenant_id"]
        role = current_user.get("role")

        query = {"tenant_id": tenant_id, "status": "active"}
        if role != "super_admin":
            query["warehouse_id"] = current_user.get("warehouse_id")
        elif warehouse_id:
            query["warehouse_id"] = warehouse_id

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$role",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]

        cursor = self.db.users.aggregate(pipeline)
        res = await cursor.to_list(length=100)

        breakdown = []
        for r in res:
            breakdown.append({
                "role": r["_id"] or "employee",
                "count": r.get("count", 0)
            })
        return breakdown

    async def get_trends_analytics(self, current_user: dict, warehouse_id: Optional[str] = None) -> List[dict]:
        """Compute monthly invoices revenue and taxation trends over the last 12 months."""
        if not await check_user_permission(current_user, "reports", "view", self.db):
            raise PermissionException("Unauthorized: You do not have permission to view trends analytics.")
        tenant_id = current_user["tenant_id"]
        role = current_user.get("role")

        query = {"tenant_id": tenant_id}
        if role != "super_admin":
            query["warehouse_id"] = current_user.get("warehouse_id")
        elif warehouse_id:
            query["warehouse_id"] = warehouse_id

        # Subtract 12 months from now
        start_date = datetime.utcnow() - timedelta(days=365)
        query["created_at"] = {"$gte": start_date}

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"}
                },
                "totalRevenue": {"$sum": "$total"},
                "totalTax": {"$sum": "$tax"}
            }},
            {"$sort": {"_id.year": 1, "_id.month": 1}}
        ]

        cursor = self.db.bills.aggregate(pipeline)
        res = await cursor.to_list(length=12)

        # Build lookup table of DB results
        db_results = {}
        for r in res:
            yr = r["_id"]["year"]
            m_idx = r["_id"]["month"]
            db_results[(yr, m_idx)] = r

        # Generate a contiguous sequence of last 12 months in Python
        now = datetime.utcnow()
        last_12_months = []
        for i in range(11, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            last_12_months.append((y, m))

        months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        trends = []
        for yr, m_idx in last_12_months:
            r = db_results.get((yr, m_idx))
            total_rev = self._to_float(r.get("totalRevenue", 0.0)) if r else 0.0
            total_tax = self._to_float(r.get("totalTax", 0.0)) if r else 0.0
            trends.append({
                "year": yr,
                "month": m_idx,
                "monthName": f"{months[m_idx]} {yr}",
                "totalRevenue": total_rev,
                "totalTax": total_tax
            })
        return trends
