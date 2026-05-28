import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import Depends
from pydantic import create_model, Field
from src.modules.dynamic_tables.repository import DynamicTableRepository
from src.modules.dynamic_tables.model import TableSchemaDocument, TableColumnModel, TableRowDocument
from src.modules.audit_logs.service import AuditLogService
from src.middleware.exceptions import ValidationException, PermissionException, NotFoundException

logger = logging.getLogger("wareops_erp.modules.dynamic_tables.service")


class DynamicTableService:
    def __init__(
        self,
        repository: DynamicTableRepository = Depends(),
        audit_service: AuditLogService = Depends()
    ):
        self.repo = repository
        self.audit = audit_service

    # --- SCHEMAS BUSINESS LOGIC ---

    async def list_schemas(self, current_user: dict, warehouse_id: Optional[str] = None) -> List[dict]:
        """List custom table schemas matching active tenant bounds and role scoped boundaries."""
        tenant_id = current_user["tenant_id"]
        role = current_user.get("role")

        # Base query scopes per tenant
        query = {"tenant_id": tenant_id}

        # Multi-Tenant warehouse boundary restriction
        if role != "super_admin":
            # Other roles can only access tables in their assigned warehouse
            query["warehouse_id"] = current_user.get("warehouse_id")
        elif warehouse_id:
            # Super Admin can filter by warehouse
            query["warehouse_id"] = warehouse_id

        schemas = await self.repo.list_schemas(query)
        return schemas

    async def get_schema_detail(self, table_id: str, current_user: dict) -> dict:
        """Fetch custom table schema detailed configurations."""
        schema = await self.repo.find_schema_by_id(table_id, current_user["tenant_id"])
        if not schema:
            raise NotFoundException("Custom operational table schema not found.")

        # Non-Super Admins are bounded by assigned warehouse location
        if current_user.get("role") != "super_admin" and schema.get("warehouse_id") != current_user.get("warehouse_id"):
            raise PermissionException("You do not have access to this warehouse's schemas.")

        return schema

    async def create_schema(self, payload: Any, current_user: dict) -> dict:
        """Register a new custom operational table schema validation registry."""
        tenant_id = current_user["tenant_id"]
        role = current_user.get("role")

        warehouse_id = payload.warehouse_id
        if role != "super_admin":
            # Force Admin warehouse scope to their own assigned workspace
            warehouse_id = current_user.get("warehouse_id")

        # Uniqueness assertion scoped per warehouse bounds
        existing = await self.repo.find_schema_by_name_and_warehouse(payload.name, warehouse_id, tenant_id)
        if existing:
            raise ValidationException(f"A custom table named '{payload.name}' already exists in this warehouse workspace.")

        # Map column models
        cols = []
        for c in payload.columns:
            cols.append(TableColumnModel(
                id=c.id,
                name=c.name,
                type=c.type,
                options=c.options or "",
                required=c.required
            ))

        doc = TableSchemaDocument(
            name=payload.name,
            table_name=payload.name,  # unique compound index matches table_name
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

        schema = await self.repo.create_schema(doc.model_dump(by_alias=True, exclude_none=True))
        
        # Log audit trail
        wh_name = warehouse_id if warehouse_id else "Global"
        await self.audit.log_event(
            user_id=str(current_user["_id"]),
            user_name=current_user["name"],
            action="table_schema_create",
            description=f"Created custom table schema: {payload.name} (Scope: {wh_name})",
            tenant_id=tenant_id,
            warehouse_id=warehouse_id
        )

        return schema

    async def update_schema(self, table_id: str, payload: Any, current_user: dict) -> dict:
        """Update existing custom table configuration schemas."""
        schema = await self.get_schema_detail(table_id, current_user)
        tenant_id = current_user["tenant_id"]

        # Validate unique constraint if name changes
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
                "options": c.options or "",
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

        # Log audit trail
        await self.audit.log_event(
            user_id=str(current_user["_id"]),
            user_name=current_user["name"],
            action="table_schema_update",
            description=f"Updated custom table schema: {payload.name}",
            tenant_id=tenant_id,
            warehouse_id=schema.get("warehouse_id")
        )

        return updated

    async def delete_schema(self, table_id: str, current_user: dict) -> bool:
        """Delete custom table and cascade purge all dynamic rows documents."""
        schema = await self.get_schema_detail(table_id, current_user)
        tenant_id = current_user["tenant_id"]

        # Cascade purge rows under this table
        rows_deleted = await self.repo.delete_all_rows_for_table(table_id, tenant_id)
        logger.info(f"Cascaded delete cleared {rows_deleted} row documents for table_id: {table_id}")

        # Delete table schema
        res = await self.repo.delete_schema(table_id, tenant_id)

        # Log audit trail
        await self.audit.log_event(
            user_id=str(current_user["_id"]),
            user_name=current_user["name"],
            action="table_schema_delete",
            description=f"Deleted custom table schema: {schema['name']} (Purged {rows_deleted} rows)",
            tenant_id=tenant_id,
            warehouse_id=schema.get("warehouse_id")
        )

        return res

    # --- TABLE ROWS BUSINESS LOGIC ---

    async def list_rows(self, table_id: str, current_user: dict) -> List[dict]:
        """Fetch custom row documents from MongoDB collections matching isolation scopes."""
        schema = await self.get_schema_detail(table_id, current_user)
        self._assert_role_access(current_user, schema)

        rows = await self.repo.list_rows_by_table(table_id, current_user["tenant_id"])
        
        # Symmetrically flatten dynamic rows mapping for direct SPA compatibility
        flattened = [self._flatten_row(r) for r in rows]
        return flattened

    async def append_row(self, table_id: str, row_data: Dict[str, Any], current_user: dict) -> dict:
        """Append validated custom row documents into database collections."""
        schema = await self.get_schema_detail(table_id, current_user)
        self._assert_role_access(current_user, schema)

        # Compile schemas and validate fields dynamically at runtime
        validated_data = self.validate_row_against_schema(schema, row_data)

        doc = TableRowDocument(
            table_id=table_id,
            warehouse_id=schema.get("warehouse_id") or current_user.get("warehouse_id") or "Global",
            tenant_id=current_user["tenant_id"],
            data=validated_data,
            created_at=datetime.utcnow()
        )

        row = await self.repo.create_row(doc.model_dump(by_alias=True, exclude_none=True))

        # Row-level audits are omitted to avoid high-frequency log clutter

        return self._flatten_row(row)

    async def update_row(self, table_id: str, row_id: str, row_data: Dict[str, Any], current_user: dict) -> dict:
        """Update validated custom row fields."""
        schema = await self.get_schema_detail(table_id, current_user)
        self._assert_role_access(current_user, schema)

        tenant_id = current_user["tenant_id"]
        row = await self.repo.find_row_by_id(row_id, tenant_id)
        if not row or row["table_id"] != table_id:
            raise NotFoundException("Row document not found in this table.")

        # Compile schemas and validate fields dynamically at runtime
        validated_data = self.validate_row_against_schema(schema, row_data)

        updated_row = await self.repo.update_row(row_id, tenant_id, validated_data)

        # Row-level audits are omitted to avoid high-frequency log clutter

        return self._flatten_row(updated_row)

    async def delete_row(self, table_id: str, row_id: str, current_user: dict) -> bool:
        """Delete custom row document."""
        schema = await self.get_schema_detail(table_id, current_user)
        self._assert_role_access(current_user, schema)

        tenant_id = current_user["tenant_id"]
        row = await self.repo.find_row_by_id(row_id, tenant_id)
        if not row or row["table_id"] != table_id:
            raise NotFoundException("Row document not found in this table.")

        res = await self.repo.delete_row(row_id, tenant_id)

        # Row-level audits are omitted to avoid high-frequency log clutter

        return res

    # --- DYNAMIC VALIDATION SERVICES ---

    def validate_row_against_schema(self, schema_doc: dict, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate dynamic fields against structured metadata schemas at runtime using dynamic Pydantic models."""
        fields = {}
        for col in schema_doc.get("columns", []):
            col_id = col["id"]
            col_type = col["type"]

            # Map to runtime Python types
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

        # Compile dynamic Pydantic validator model
        DynamicRowModel = create_model(f"DynamicRow_{str(schema_doc['_id'])}", **fields)

        # Remove system fields from row_data to avoid Pydantic validation errors
        row_fields = {k: v for k, v in row_data.items() if k in fields}

        # Execute structural type and presence validations
        try:
            validated = DynamicRowModel(**row_fields)
            validated_dict = validated.model_dump()
        except Exception as e:
            # Raise detailed error envelopes
            raise ValidationException(f"Runtime schema type mismatch error: {e}")

        # Execute custom options constraints validations
        for col in schema_doc.get("columns", []):
            col_id = col["id"]
            col_type = col["type"]
            val = validated_dict.get(col_id)

            if val is not None and val != "":
                if col_type == "dropdown":
                    allowed_opts = [o.strip() for o in (col.get("options") or "").split(",") if o.strip()]
                    if allowed_opts and str(val) not in allowed_opts:
                        raise ValidationException(f"Value '{val}' is not allowed for dropdown column '{col['name']}'. Allowed: {allowed_opts}")
                elif col_type == "status":
                    allowed_status = ["Todo", "In Progress", "Done"]
                    if str(val) not in allowed_status:
                        raise ValidationException(f"Value '{val}' is not allowed for status column '{col['name']}'. Allowed: {allowed_status}")

        return validated_dict

    # --- AUXILIARY UTILITIES ---

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
            "createdAt": row_doc["created_at"].isoformat() if isinstance(row_doc["created_at"], datetime) else str(row_doc["created_at"])
        }
        res.update(row_doc.get("data", {}))
        return res
