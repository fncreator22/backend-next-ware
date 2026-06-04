import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import Depends
from pydantic import create_model, Field
from src.modules.dynamic_tables.repository import DynamicTableRepository
from src.modules.dynamic_tables.model import TableSchemaDocument, TableColumnModel, TableRowDocument
from src.modules.audit_logs.service import AuditLogService
from src.middleware.exceptions import ValidationException, PermissionException, NotFoundException
from src.modules.realtime.websocket_manager import manager

from src.modules.audit_logs.service import AuditLogService
from src.modules.trash.service import TrashService
from src.modules.registry.service import CentralRegistryService

logger = logging.getLogger("wareops_erp.modules.dynamic_tables.service")


class DynamicTableService:
    def __init__(
        self,
        repository: DynamicTableRepository = Depends(),
        audit_service: AuditLogService = Depends(),
        trash_service: TrashService = Depends(),
        registry: CentralRegistryService = Depends()
    ):
        self.repo = repository
        self.audit = audit_service
        self.trash = trash_service
        self.registry = registry

    # --- SCHEMAS BUSINESS LOGIC ---

    async def list_schemas(self, current_user: dict, warehouse_id: Optional[str] = None) -> List[dict]:
        """List custom table schemas matching active tenant bounds and role scoped boundaries."""
        tenant_id = current_user["tenant_id"]
        role = current_user.get("role")

        query = {"tenant_id": tenant_id}

        if role != "super_admin":
            query["warehouse_id"] = current_user.get("warehouse_id")
        elif warehouse_id:
            query["warehouse_id"] = warehouse_id

        schemas = await self.repo.list_schemas(query)
        return schemas

    async def get_schema_detail(self, table_id: str, current_user: dict) -> dict:
        """Fetch custom table schema detailed configurations."""
        schema = await self.repo.find_schema_by_id(table_id, current_user["tenant_id"])
        if not schema:
            raise NotFoundException("Custom operational table schema not found.")

        if current_user.get("role") != "super_admin" and schema.get("warehouse_id") != current_user.get("warehouse_id"):
            raise PermissionException("You do not have access to this warehouse's schemas.")

        return schema

    async def create_schema(self, payload: Any, current_user: dict) -> dict:
        """Register a new custom operational table schema validation registry."""
        tenant_id = current_user["tenant_id"]
        role = current_user.get("role")

        warehouse_id = payload.warehouse_id
        if role != "super_admin":
            warehouse_id = current_user.get("warehouse_id")

        existing = await self.repo.find_schema_by_name_and_warehouse(payload.name, warehouse_id, tenant_id)
        if existing:
            raise ValidationException(f"A custom table named '{payload.name}' already exists in this warehouse workspace.")

        cols = []
        for c in payload.columns:
            cols.append(TableColumnModel(
                id=c.id,
                name=c.name,
                type=c.type,
                options=self._normalize_options(c.options or ""),
                required=c.required
            ))

        # Atomic enterprise ID + barcode assignment
        enterprise_id = await self.registry.get_next_enterprise_id(tenant_id, "TBL")

        doc = TableSchemaDocument(
            name=payload.name,
            table_name=payload.name,
            category=payload.category or "Custom",
            description=payload.description or "",
            warehouse_id=warehouse_id,
            tenant_id=tenant_id,
            columns=cols,
            roles=payload.roles or [],
            header_color=payload.header_color or "#6366f1",
            created_by=str(current_user["_id"]),
            created_at=datetime.utcnow(),
            status="active"
        )

        # Merge enterprise tracking parameters
        schema_dict = doc.model_dump(by_alias=True, exclude_none=True)
        schema_dict["enterprise_id"] = enterprise_id
        schema_dict["barcode"] = enterprise_id

        schema = await self.repo.create_schema(schema_dict)

        # Register dynamic custom table in centralized tracking registry
        await self.registry.register_entity(
            tenant_id=tenant_id,
            entity_type="table_registry",
            entity_id=enterprise_id,
            barcode=enterprise_id,
            warehouse_id=warehouse_id,
            creator_id=str(current_user["_id"]),
            creator_name=current_user["name"],
            snapshot=schema
        )

        wh_name = warehouse_id if warehouse_id else "Global"
        await self.audit.log_event(
            user_id=str(current_user["_id"]),
            user_name=current_user["name"],
            action="table_schema_create",
            description=f"Created custom table schema: {payload.name} (Scope: {wh_name}, ID: {enterprise_id})",
            tenant_id=tenant_id,
            warehouse_id=warehouse_id
        )

        # Broadcast schema creation event
        await manager.broadcast_event(
            tenant_id=tenant_id,
            event_type="table_schema_created",
            data={"tableId": str(schema["_id"]), "name": payload.name},
            warehouse_id=warehouse_id
        )

        return schema

    async def update_schema(self, table_id: str, payload: Any, current_user: dict) -> dict:
        """Update existing custom table configuration schemas."""
        schema = await self.get_schema_detail(table_id, current_user)
        tenant_id = current_user["tenant_id"]

        if payload.name != schema["name"]:
            existing = await self.repo.find_schema_by_name_and_warehouse(payload.name, schema.get("warehouse_id"), tenant_id)
            if existing and str(existing["_id"]) != table_id:
                raise ValidationException(f"A custom table named '{payload.name}' already exists in this warehouse workspace.")

        cols = []
        for c in payload.columns:
            cols.append({
                "id": c.id,
                "name": c.name,
                "type": c.type,
                "options": self._normalize_options(c.options or ""),
                "required": c.required
            })

        update_data = {
            "name": payload.name,
            "table_name": payload.name,
            "category": payload.category or "Custom",
            "description": payload.description or "",
            "columns": cols,
            "roles": payload.roles or [],
            "header_color": payload.header_color or "#6366f1"
        }

        updated = await self.repo.update_schema(table_id, tenant_id, update_data)

        # Snapshot update logic scoped inside Central Registry
        enterprise_id = updated.get("enterprise_id")
        if not enterprise_id:
            # Backward compatibility fallback
            enterprise_id = await self.registry.get_next_enterprise_id(tenant_id, "TBL")
            await self.repo.update_schema(table_id, tenant_id, {"enterprise_id": enterprise_id, "barcode": enterprise_id})
            updated["enterprise_id"] = enterprise_id
            updated["barcode"] = enterprise_id

        await self.registry.register_entity(
            tenant_id=tenant_id,
            entity_type="table_registry",
            entity_id=enterprise_id,
            barcode=enterprise_id,
            warehouse_id=schema.get("warehouse_id"),
            creator_id=str(current_user["_id"]),
            creator_name=current_user["name"],
            snapshot=updated
        )

        await self.audit.log_event(
            user_id=str(current_user["_id"]),
            user_name=current_user["name"],
            action="table_schema_update",
            description=f"Updated custom table schema: {payload.name} (ID: {enterprise_id})",
            tenant_id=tenant_id,
            warehouse_id=schema.get("warehouse_id")
        )

        await manager.broadcast_event(
            tenant_id=tenant_id,
            event_type="table_schema_updated",
            data={"tableId": table_id, "name": payload.name},
            warehouse_id=schema.get("warehouse_id")
        )

        return updated

    async def delete_schema(self, table_id: str, current_user: dict) -> bool:
        """Delete custom table and cascade purge all dynamic rows documents."""
        schema = await self.get_schema_detail(table_id, current_user)
        tenant_id = current_user["tenant_id"]

        rows_deleted = await self.repo.delete_all_rows_for_table(table_id, tenant_id)
        logger.info(f"Cascaded delete cleared {rows_deleted} row documents for table_id: {table_id}")

        # Move schema to trash before deleting
        schema_data = dict(schema)
        if "_id" in schema_data:
            schema_data["_id"] = str(schema_data["_id"])
        if "created_at" in schema_data and isinstance(schema_data["created_at"], datetime):
            schema_data["created_at"] = schema_data["created_at"].isoformat()
        if "updated_at" in schema_data and isinstance(schema_data["updated_at"], datetime):
            schema_data["updated_at"] = schema_data["updated_at"].isoformat()

        await self.trash.soft_delete(
            doc_id=table_id,
            original_collection="table_schemas",
            tenant_id=tenant_id,
            deleted_by=str(current_user["_id"]),
            data=schema_data
        )

        res = await self.repo.delete_schema(table_id, tenant_id)

        await self.audit.log_event(
            user_id=str(current_user["_id"]),
            user_name=current_user["name"],
            action="table_schema_delete",
            description=f"Deleted custom table schema: {schema['name']} (Purged {rows_deleted} rows)",
            tenant_id=tenant_id,
            warehouse_id=schema.get("warehouse_id")
        )

        await manager.broadcast_event(
            tenant_id=tenant_id,
            event_type="table_schema_deleted",
            data={"tableId": table_id},
            warehouse_id=schema.get("warehouse_id")
        )

        return res

    # --- TABLE ROWS BUSINESS LOGIC ---

    async def list_rows(self, table_id: str, current_user: dict, page: int = 1) -> List[dict]:
        """Fetch custom row documents from MongoDB collections matching isolation scopes and page number."""
        schema = await self.get_schema_detail(table_id, current_user)
        self._assert_role_access(current_user, schema)

        rows = await self.repo.list_rows_by_table_and_page(table_id, page, current_user["tenant_id"])
        flattened = [self._flatten_row(r) for r in rows]
        return flattened

    async def append_row(self, table_id: str, row_data: Dict[str, Any], current_user: dict, page: int = 1) -> dict:
        """Append validated custom row documents into database collections."""
        schema = await self.get_schema_detail(table_id, current_user)
        self._assert_role_access(current_user, schema)

        # Enforce 100-row limit per page
        existing_rows = await self.repo.list_rows_by_table_and_page(table_id, page, current_user["tenant_id"])
        if len(existing_rows) >= 100:
            raise ValidationException("This page has reached its maximum capacity of 100 rows.")

        validated_data = self.validate_row_against_schema(schema, row_data)

        doc = TableRowDocument(
            table_id=table_id,
            warehouse_id=schema.get("warehouse_id") or current_user.get("warehouse_id") or "Global",
            tenant_id=current_user["tenant_id"],
            data=validated_data,
            page_number=page,
            created_at=datetime.utcnow()
        )

        row = await self.repo.create_row(doc.model_dump(by_alias=True, exclude_none=True))
        flat = self._flatten_row(row)

        await self.update_page_storage(table_id, page, current_user["tenant_id"])

        # Log audit trail
        await self.audit.log_event(
            user_id=str(current_user["_id"]),
            user_name=current_user["name"],
            action="table_row_create",
            description=f"Added new row in table '{schema['name']}' (Page {page})",
            tenant_id=current_user["tenant_id"],
            warehouse_id=schema.get("warehouse_id")
        )

        # Broadcast row insertion to all connected collaborators on this table
        await manager.broadcast_event(
            tenant_id=current_user["tenant_id"],
            event_type="table_row_created",
            data={
                "tableId": table_id,
                "row": flat,
                "actorName": current_user.get("name", "Unknown"),
                "actorId": str(current_user["_id"])
            },
            warehouse_id=schema.get("warehouse_id")
        )

        return flat

    async def update_row(self, table_id: str, row_id: str, row_data: Dict[str, Any], current_user: dict) -> dict:
        """Update validated custom row fields."""
        schema = await self.get_schema_detail(table_id, current_user)
        self._assert_role_access(current_user, schema)

        tenant_id = current_user["tenant_id"]
        row = await self.repo.find_row_by_id(row_id, tenant_id)
        if not row or row["table_id"] != table_id:
            raise NotFoundException("Row document not found in this table.")

        page = row.get("page_number", 1)
        validated_data = self.validate_row_against_schema(schema, row_data)
        updated_row = await self.repo.update_row(row_id, tenant_id, validated_data)
        flat = self._flatten_row(updated_row)

        await self.update_page_storage(table_id, page, tenant_id)

        # Log audit trail
        await self.audit.log_event(
            user_id=str(current_user["_id"]),
            user_name=current_user["name"],
            action="table_row_update",
            description=f"Updated row {row_id} in table '{schema['name']}' (Page {page})",
            tenant_id=tenant_id,
            warehouse_id=schema.get("warehouse_id")
        )

        # Broadcast row update to collaborators
        await manager.broadcast_event(
            tenant_id=tenant_id,
            event_type="table_row_updated",
            data={
                "tableId": table_id,
                "rowId": row_id,
                "row": flat,
                "actorName": current_user.get("name", "Unknown"),
                "actorId": str(current_user["_id"])
            },
            warehouse_id=schema.get("warehouse_id")
        )

        return flat

    async def delete_row(self, table_id: str, row_id: str, current_user: dict) -> bool:
        """Delete custom row document."""
        schema = await self.get_schema_detail(table_id, current_user)
        self._assert_role_access(current_user, schema)

        tenant_id = current_user["tenant_id"]
        row = await self.repo.find_row_by_id(row_id, tenant_id)
        if not row or row["table_id"] != table_id:
            raise NotFoundException("Row document not found in this table.")

        page = row.get("page_number", 1)
        # Move row to trash before deleting
        row_data = dict(row)
        if "_id" in row_data:
            row_data["_id"] = str(row_data["_id"])
        if "created_at" in row_data and isinstance(row_data["created_at"], datetime):
            row_data["created_at"] = row_data["created_at"].isoformat()
        if "updated_at" in row_data and isinstance(row_data["updated_at"], datetime):
            row_data["updated_at"] = row_data["updated_at"].isoformat()

        await self.trash.soft_delete(
            doc_id=row_id,
            original_collection="table_rows",
            tenant_id=tenant_id,
            deleted_by=str(current_user["_id"]),
            data=row_data
        )

        res = await self.repo.delete_row(row_id, tenant_id)
        if res:
            await self.update_page_storage(table_id, page, tenant_id)

        # Log audit trail
        await self.audit.log_event(
            user_id=str(current_user["_id"]),
            user_name=current_user["name"],
            action="table_row_delete",
            description=f"Deleted row {row_id} in table '{schema['name']}' (Page {page})",
            tenant_id=tenant_id,
            warehouse_id=schema.get("warehouse_id")
        )

        # Broadcast row deletion
        await manager.broadcast_event(
            tenant_id=tenant_id,
            event_type="table_row_deleted",
            data={
                "tableId": table_id,
                "rowId": row_id,
                "actorName": current_user.get("name", "Unknown"),
                "actorId": str(current_user["_id"])
            },
            warehouse_id=schema.get("warehouse_id")
        )

        return res

    async def import_rows(self, table_id: str, rows_data: List[Dict[str, Any]], current_user: dict, page: int = 1) -> dict:
        """Bulk import multiple rows into a custom table page (admin/manager only)."""
        schema = await self.get_schema_detail(table_id, current_user)
        self._assert_role_access(current_user, schema)

        tenant_id = current_user["tenant_id"]
        warehouse_id = schema.get("warehouse_id") or current_user.get("warehouse_id") or "Global"

        existing_rows = await self.repo.list_rows_by_table_and_page(table_id, page, tenant_id)
        current_count = len(existing_rows)

        inserted = 0
        errors = []

        for i, row_data in enumerate(rows_data):
            if current_count >= 100:
                errors.append({"row": i + 1, "error": "This page has reached its maximum capacity of 100 rows."})
                continue
            try:
                validated_data = self.validate_row_against_schema(schema, row_data)
                doc = TableRowDocument(
                    table_id=table_id,
                    warehouse_id=warehouse_id,
                    tenant_id=tenant_id,
                    data=validated_data,
                    page_number=page,
                    created_at=datetime.utcnow()
                )
                await self.repo.create_row(doc.model_dump(by_alias=True, exclude_none=True))
                inserted += 1
                current_count += 1
            except Exception as e:
                errors.append({"row": i + 1, "error": str(e)})

        if inserted > 0:
            await self.update_page_storage(table_id, page, tenant_id)

        # Audit the bulk import
        await self.audit.log_event(
            user_id=str(current_user["_id"]),
            user_name=current_user["name"],
            action="table_rows_import",
            description=f"Bulk imported {inserted} rows into table '{schema['name']}' page {page} ({len(errors)} errors)",
            tenant_id=tenant_id,
            warehouse_id=warehouse_id
        )

        # Broadcast import complete so all collaborators refresh
        await manager.broadcast_event(
            tenant_id=tenant_id,
            event_type="table_rows_imported",
            data={
                "tableId": table_id,
                "page": page,
                "inserted": inserted,
                "actorName": current_user.get("name", "Unknown"),
                "actorId": str(current_user["_id"])
            },
            warehouse_id=warehouse_id
        )

        return {"inserted": inserted, "errors": errors, "total": len(rows_data)}

    # --- DYNAMIC VALIDATION SERVICES ---

    def validate_row_against_schema(self, schema_doc: dict, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate dynamic fields against structured metadata schemas at runtime using dynamic Pydantic models."""
        fields = {}
        for col in schema_doc.get("columns", []):
            col_id = col["id"]
            col_type = col["type"]

            py_type = str
            if col_type in ("number", "price"):
                py_type = float
            elif col_type == "checkbox":
                py_type = bool

            is_req = col.get("required", False)
            if is_req:
                fields[col_id] = (py_type, Field(...))
            else:
                fields[col_id] = (Optional[py_type], Field(default=None))

        DynamicRowModel = create_model(f"DynamicRow_{str(schema_doc['_id'])}", **fields)

        row_fields = {k: v for k, v in row_data.items() if k in fields}

        try:
            validated = DynamicRowModel(**row_fields)
            validated_dict = validated.model_dump()
        except Exception as e:
            raise ValidationException(f"Runtime schema type mismatch error: {e}")

        # Custom options constraint validation with proper normalization
        for col in schema_doc.get("columns", []):
            col_id = col["id"]
            col_type = col["type"]
            val = validated_dict.get(col_id)

            if val is not None and val != "":
                if col_type == "dropdown":
                    # FIX: Properly parse and normalize dropdown options case-insensitively
                    raw_options = col.get("options") or ""
                    allowed_opts = [o.strip() for o in raw_options.split(",") if o.strip()]
                    if allowed_opts:
                        normalized_val = str(val).strip()
                        matched_opt = None
                        for opt in allowed_opts:
                            if opt.lower() == normalized_val.lower():
                                matched_opt = opt
                                break
                        if not matched_opt:
                            raise ValidationException(
                                f"Value '{normalized_val}' is not a valid option for dropdown column '{col['name']}'. "
                                f"Allowed values: {allowed_opts}"
                            )
                        # Replace the validated_dict value with the normalized matched option (exact case)
                        validated_dict[col_id] = matched_opt
                elif col_type == "status":
                    allowed_status = ["Todo", "In Progress", "Done"]
                    normalized_val = str(val).strip()
                    if normalized_val not in allowed_status:
                        raise ValidationException(
                            f"Value '{normalized_val}' is not allowed for status column '{col['name']}'. "
                            f"Allowed: {allowed_status}"
                        )
                    validated_dict[col_id] = normalized_val

        return validated_dict

    # --- AUXILIARY UTILITIES ---

    def _normalize_options(self, raw: str) -> str:
        """Normalize comma-separated option strings: trim whitespace, remove empty entries."""
        if not raw:
            return ""
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return ",".join(parts)

    def _assert_role_access(self, current_user: dict, schema: dict):
        """Restrict reads/writes to custom schemas by allowed role definitions."""
        allowed_roles = schema.get("roles", [])
        if allowed_roles:
            user_role = current_user.get("role")
            if user_role not in allowed_roles and user_role not in ("admin", "super_admin"):
                raise PermissionException("You are not authorized to access this custom table.")

    def _flatten_row(self, row_doc: dict) -> dict:
        """Merge dynamic data attributes at top level to ensure exact frontend rendering structures compatibility."""
        res = {
            "id": str(row_doc["_id"]),
            "tableId": row_doc["table_id"],
            "warehouseId": row_doc["warehouse_id"],
            "tenantId": row_doc["tenant_id"],
            "pageNumber": row_doc.get("page_number", 1),
            "createdAt": row_doc["created_at"].isoformat() if isinstance(row_doc["created_at"], datetime) else str(row_doc["created_at"])
        }
        res.update(row_doc.get("data", {}))
        return res

    async def get_tenant_page_limit(self, tenant_id: str) -> int:
        """Scalable architecture to query tenant subscription details and returns table page limits."""
        tenant = await self.repo.db.tenants.find_one({"_id": tenant_id})
        plan = tenant.get("plan", "starter") if tenant else "enterprise"
        if plan == "starter":
            return 2
        return 50

    async def update_page_storage(self, table_id: str, page_number: int, tenant_id: str):
        """Recompute dynamic JSON storage usage metadata for a specific table page and persist it."""
        schema = await self.repo.find_schema_by_id(table_id, tenant_id)
        if not schema:
            return

        pages = schema.get("pages") or []
        if not pages:
            created_at_val = schema.get("created_at")
            created_at_str = created_at_val.isoformat() if isinstance(created_at_val, datetime) else str(created_at_val)
            pages = [{
                "page_number": 1,
                "created_at": created_at_str,
                "created_by": schema.get("created_by", ""),
                "permissions": schema.get("roles", []),
                "storage_usage": 0
            }]

        rows = await self.repo.list_rows_by_table_and_page(table_id, page_number, tenant_id)
        # Dynamic storage estimate by summing stringified data values
        storage = sum(len(str(r.get("data", {}))) for r in rows)

        found = False
        for p in pages:
            if p.get("page_number") == page_number:
                p["storage_usage"] = storage
                found = True
                break

        if not found:
            pages.append({
                "page_number": page_number,
                "created_at": datetime.utcnow().isoformat(),
                "created_by": "",
                "permissions": schema.get("roles", []),
                "storage_usage": storage
            })

        await self.repo.update_schema(table_id, tenant_id, {"pages": pages})

    async def add_page(self, table_id: str, current_user: dict) -> dict:
        """Create a new table page, keeping the same schema and permissions, under subscription limits."""
        schema = await self.get_schema_detail(table_id, current_user)
        self._assert_role_access(current_user, schema)

        tenant_id = current_user["tenant_id"]

        limit = await self.get_tenant_page_limit(tenant_id)
        pages = schema.get("pages") or []
        if not pages:
            created_at_val = schema.get("created_at")
            created_at_str = created_at_val.isoformat() if isinstance(created_at_val, datetime) else str(created_at_val)
            pages = [{
                "page_number": 1,
                "created_at": created_at_str,
                "created_by": schema.get("created_by", ""),
                "permissions": schema.get("roles", []),
                "storage_usage": 0
            }]

        if len(pages) >= limit:
            raise ValidationException(f"Page limit exceeded for your current plan (Limit: {limit} pages). Please upgrade your plan.")

        new_page_number = len(pages) + 1

        pages.append({
            "page_number": new_page_number,
            "created_at": datetime.utcnow().isoformat(),
            "created_by": str(current_user["_id"]),
            "permissions": schema.get("roles", []),
            "storage_usage": 0
        })

        updated = await self.repo.update_schema(table_id, tenant_id, {"pages": pages})

        # Log audit trail
        await self.audit.log_event(
            user_id=str(current_user["_id"]),
            user_name=current_user["name"],
            action="table_page_create",
            description=f"Added new page {new_page_number} to table '{schema['name']}'",
            tenant_id=tenant_id,
            warehouse_id=schema.get("warehouse_id")
        )

        # Broadcast page creation event via WebSocket
        await manager.broadcast_event(
            tenant_id=tenant_id,
            event_type="table_page_created",
            data={
                "tableId": table_id,
                "pageNumber": new_page_number,
                "pages": pages
            },
            warehouse_id=schema.get("warehouse_id")
        )

        return updated
