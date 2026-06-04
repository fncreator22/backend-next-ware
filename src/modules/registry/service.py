import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import Depends
from bson import ObjectId
from src.database import get_db
from src.modules.audit_logs.service import AuditLogService
from src.modules.realtime import ws_manager, normalize_doc
from src.middleware.exceptions import NotFoundException, PermissionException, ValidationException

logger = logging.getLogger("wareops_erp.modules.registry.service")

# Code 39 binary pattern representation dictionary
CODE39_PATTERNS = {
    '0': '000110100', '1': '100100001', '2': '001100001', '3': '101100000',
    '4': '000110001', '5': '100110000', '6': '001110000', '7': '000100101',
    '8': '100100100', '9': '001100100', 'A': '100001001', 'B': '001001001',
    'C': '101001000', 'D': '000011001', 'E': '100011000', 'F': '001011000',
    'G': '000001101', 'H': '100001100', 'I': '001001100', 'J': '000011100',
    'K': '100000011', 'L': '001000011', 'M': '101000010', 'N': '000010011',
    'O': '100010010', 'P': '001010010', 'Q': '000000111', 'R': '100000110',
    'S': '001000110', 'T': '000010110', 'U': '110000001', 'V': '011000001',
    'W': '111000000', 'X': '010010001', 'Y': '110010000', 'Z': '011010000',
    '-': '010000101', '.': '110000100', ' ': '011000100', '*': '010010100',
    '$': '010101000', '/': '010100010', '+': '010001010', '%': '000101010'
}


def generate_code39_svg(text: str) -> str:
    """Lightweight, self-contained Code 39 SVG rendering engine for offline laser scanners."""
    # Clean text to contain only supported Code 39 chars
    text = "".join(c for c in text.upper() if c in CODE39_PATTERNS)
    if not text:
        text = "EMPTY"

    # Frame with start/stop character *
    full_text = f"*{text}*"

    narrow = 2
    wide = 6
    gap = 2

    elements = []
    for char in full_text:
        pattern = CODE39_PATTERNS.get(char, CODE39_PATTERNS[' '])
        for idx, val in enumerate(pattern):
            is_bar = (idx % 2 == 0)
            width = wide if val == '1' else narrow
            elements.append((is_bar, width))
        # Inter-character spacing
        elements.append((False, narrow))

    # Pop trailing inter-character gap
    if elements:
        elements.pop()

    total_width = sum(w for _, w in elements)
    padding = 20
    svg_width = total_width + (padding * 2)
    svg_height = 80

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}">',
        f'  <rect width="100%" height="100%" fill="#ffffff" rx="4" />'
    ]

    x = padding
    for is_bar, w in elements:
        if is_bar:
            svg_lines.append(f'  <rect x="{x}" y="10" width="{w}" height="46" fill="#000000" />')
        x += w

    svg_lines.append(f'  <text x="{svg_width / 2}" y="70" font-family="monospace" font-size="12" font-weight="bold" text-anchor="middle" fill="#1f2937">{text}</text>')
    svg_lines.append('</svg>')

    return "\n".join(svg_lines)


class CentralRegistryService:
    def __init__(self, db=Depends(get_db), audit: AuditLogService = Depends()):
        self.db = db
        self.audit = audit

    async def get_next_enterprise_id(self, tenant_id: str, prefix: str) -> str:
        """Atomic, thread-safe sequence generator scoped by tenant partition and current calendar year."""
        current_year = datetime.utcnow().year
        
        # Atomically increment counter in MongoDB
        counter = await self.db.enterprise_counters.find_one_and_update(
            {
                "tenant_id": tenant_id,
                "prefix": prefix,
                "year": current_year
            },
            {"$inc": {"sequence": 1}},
            upsert=True,
            return_document=True
        )
        
        seq = counter.get("sequence", 1)
        return f"{prefix}-{current_year}-{seq:04d}"

    async def register_entity(
        self,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        barcode: str,
        warehouse_id: Optional[str],
        creator_id: str,
        creator_name: str,
        snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Atomically upsert catalog registry ledger entry and broadcast real-time sync."""
        clean_snapshot = normalize_doc(snapshot)
        
        doc = {
            "tenant_id": tenant_id,
            "entity_id": entity_id,
            "barcode": barcode,
            "updated_at": datetime.utcnow(),
            "created_by": creator_id,
            "creator_name": creator_name,
            "warehouse_id": warehouse_id or "Global",
            "entity_type": entity_type,
            "metadata_snapshot": clean_snapshot
        }

        # Save to database
        await self.db.enterprise_registry.update_one(
            {"tenant_id": tenant_id, "entity_id": entity_id},
            {
                "$set": doc,
                "$setOnInsert": {"created_at": datetime.utcnow()}
            },
            upsert=True
        )

        saved = await self.db.enterprise_registry.find_one({"tenant_id": tenant_id, "entity_id": entity_id})
        flat = normalize_doc(saved)

        # Trigger real-time pub-sub broadcast
        try:
            asyncio.create_task(ws_manager.broadcast_event(
                tenant_id=tenant_id,
                event_type="registry_update",
                data=flat,
                warehouse_id=warehouse_id
            ))
        except Exception as e:
            logger.debug(f"Registry WS sync broadcast failed: {e}")

        return flat

    async def list_registry_entries(
        self,
        current_user: dict,
        search_q: str = "",
        type_filter: str = "",
        warehouse_filter: str = "",
        page: int = 1,
        limit: int = 20
    ) -> dict:
        """Fetch tracking entries scoped strictly by tenant partition and roles permissions."""
        tenant_id = current_user["tenant_id"]
        role = current_user["role"]

        query = {"tenant_id": tenant_id}

        # Multi-tenant scoping filters
        if role != "super_admin":
            my_wh = current_user.get("warehouse_id")
            if not my_wh:
                return {"entries": [], "total": 0, "pages": 0}
            query["warehouse_id"] = {"$in": [my_wh, "Global"]}
        else:
            if warehouse_filter:
                query["warehouse_id"] = warehouse_filter

        # Keyword filters
        if search_q:
            query["$or"] = [
                {"entity_id": {"$regex": search_q, "$options": "i"}},
                {"barcode": {"$regex": search_q, "$options": "i"}},
                {"creator_name": {"$regex": search_q, "$options": "i"}},
                {"entity_type": {"$regex": search_q, "$options": "i"}}
            ]

        if type_filter:
            query["entity_type"] = type_filter

        skip = (page - 1) * limit
        total = await self.db.enterprise_registry.count_documents(query)
        cursor = self.db.enterprise_registry.find(query).sort("updated_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        
        flat_entries = [normalize_doc(d) for d in docs]
        pages = (total + limit - 1) // limit

        return {"entries": flat_entries, "total": total, "pages": pages}


class CustomerService:
    def __init__(self, db=Depends(get_db), registry: CentralRegistryService = Depends(), audit: AuditLogService = Depends()):
        self.db = db
        self.registry = registry
        self.audit = audit

    async def register_invoice_to_customer(
        self,
        tenant_id: str,
        customer_payload: Dict[str, Any],
        invoice_doc: Dict[str, Any],
        creator_id: str
    ) -> Dict[str, Any]:
        """Auto CRM system creating/updating customer profile and appending transaction history snapshots."""
        phone = customer_payload.get("phone", "").strip()
        email = customer_payload.get("email", "").strip().lower()
        name = customer_payload.get("name", "Walk-in Customer").strip()

        if not name or name == "Walk-in Customer":
            # Avoid duplicate walk-in registry overheads unless a phone or email is declared
            if not phone and not email:
                return {}

        query = {"tenant_id": tenant_id}
        sub_queries = []
        if phone:
            sub_queries.append({"phone": phone})
        if email:
            sub_queries.append({"email": email})
        
        cust = None
        if sub_queries:
            query["$or"] = sub_queries
            cust = await self.db.customers.find_one(query)

        invoice_snapshot = {
            "invoice_id": str(invoice_doc.get("_id", invoice_doc.get("id"))),
            "bill_no": invoice_doc.get("bill_no", ""),
            "subtotal": float(invoice_doc.get("subtotal", 0.0)),
            "tax": float(invoice_doc.get("tax", 0.0)),
            "total": float(invoice_doc.get("total", 0.0)),
            "checkout_at": invoice_doc.get("created_at") or datetime.utcnow()
        }

        if cust:
            # Customer exists, update transaction history and profile info
            cust_id = cust["customer_id"]
            
            # Avoid duplicating invoice tracking snapshots
            existing_invoices = cust.get("invoices", [])
            inv_exists = any(inv.get("invoice_id") == invoice_snapshot["invoice_id"] for inv in existing_invoices)
            
            update_ops = {
                "$set": {
                    "updated_at": datetime.utcnow(),
                    "last_active_at": datetime.utcnow(),
                    "address": customer_payload.get("address") or cust.get("address") or "",
                    "tax_number": customer_payload.get("tax_number") or cust.get("tax_number") or ""
                }
            }

            if not inv_exists:
                update_ops["$push"] = {"invoices": invoice_snapshot}

            await self.db.customers.update_one({"_id": cust["_id"]}, update_ops)
            updated_cust = await self.db.customers.find_one({"_id": cust["_id"]})
        else:
            # New Customer, register with atomic Enterprise CRM ID
            cust_id = await self.registry.get_next_enterprise_id(tenant_id, "CUST")
            
            new_cust = {
                "tenant_id": tenant_id,
                "customer_id": cust_id,
                "barcode": cust_id,
                "name": name,
                "address": customer_payload.get("address", ""),
                "email": email,
                "phone": phone,
                "tax_number": customer_payload.get("tax_number", ""),
                "invoices": [invoice_snapshot],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": creator_id,
                "last_active_at": datetime.utcnow()
            }

            res = await self.db.customers.insert_one(new_cust)
            new_cust["_id"] = res.inserted_id
            updated_cust = new_cust

        flat_cust = normalize_doc(updated_cust)

        # Log automatically inside Central Tracking Registry
        await self.registry.register_entity(
            tenant_id=tenant_id,
            entity_type="customer",
            entity_id=cust_id,
            barcode=cust_id,
            warehouse_id=invoice_doc.get("warehouse_id"),
            creator_id=creator_id,
            creator_name=invoice_doc.get("employee_name") or "Checkout Desk",
            snapshot=flat_cust
        )

        # Trigger WebSocket event
        try:
            asyncio.create_task(ws_manager.broadcast_event(
                tenant_id=tenant_id,
                event_type="customer_update",
                data=flat_cust,
                warehouse_id=invoice_doc.get("warehouse_id")
            ))
        except Exception as e:
            logger.debug(f"CRM Customer WS sync broadcast failed: {e}")

        return flat_cust

    async def list_customers(
        self,
        current_user: dict,
        search_q: str = "",
        page: int = 1,
        limit: int = 10
    ) -> dict:
        """Fetch CRM portfolios scoped to tenant access privileges."""
        tenant_id = current_user["tenant_id"]

        query = {"tenant_id": tenant_id}

        if search_q:
            query["$or"] = [
                {"name": {"$regex": search_q, "$options": "i"}},
                {"phone": {"$regex": search_q, "$options": "i"}},
                {"email": {"$regex": search_q, "$options": "i"}},
                {"customer_id": {"$regex": search_q, "$options": "i"}}
            ]

        skip = (page - 1) * limit
        total = await self.db.customers.count_documents(query)
        cursor = self.db.customers.find(query).sort("last_active_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        flat_custs = [normalize_doc(d) for d in docs]
        pages = (total + limit - 1) // limit

        return {"customers": flat_custs, "total": total, "pages": pages}

    async def get_customer_detail(self, customer_id: str, current_user: dict) -> dict:
        """Retrieve full customer profile logs."""
        tenant_id = current_user["tenant_id"]
        
        try:
            query = {"_id": ObjectId(customer_id), "tenant_id": tenant_id}
        except Exception:
            query = {"customer_id": customer_id, "tenant_id": tenant_id}

        cust = await self.db.customers.find_one(query)
        if not cust:
            raise NotFoundException("Customer profile registry not found.")
            
        return normalize_doc(cust)
