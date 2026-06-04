from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any, Dict


class TableColumnCreate(BaseModel):
    id: str  # e.g. c1
    name: str  # e.g. Task
    type: str  # text, number, price, date, checkbox, dropdown, status, tags
    options: Optional[str] = ""  # comma-separated string for options
    required: bool = False

    model_config = ConfigDict(populate_by_name=True)


class TableSchemaCreate(BaseModel):
    name: str = Field(..., min_length=2)
    category: Optional[str] = "Custom"
    description: Optional[str] = ""
    warehouse_id: Optional[str] = Field(None, alias="warehouseId")
    columns: List[TableColumnCreate]
    roles: Optional[List[str]] = []
    header_color: Optional[str] = Field("#6366f1", alias="headerColor")

    model_config = ConfigDict(populate_by_name=True)


class TableSchemaResponse(BaseModel):
    id: str = Field(..., alias="id")
    name: str
    category: str
    description: str
    warehouse_id: Optional[str] = Field(None, alias="warehouseId")
    columns: List[TableColumnCreate]
    roles: List[str]
    header_color: str = Field(..., alias="headerColor")
    created_by: str = Field(..., alias="createdBy")
    created_at: str = Field(..., alias="createdAt")
    status: str
    pages: Optional[List[dict]] = []

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )

    @classmethod
    def from_doc(cls, doc: dict) -> "TableSchemaResponse":
        """Factory helper to build a schema response from MongoDB dictionary."""
        created_at_val = doc.get("created_at")
        if isinstance(created_at_val, datetime):
            created_at_str = created_at_val.isoformat()
        else:
            created_at_str = str(created_at_val)

        pages_raw = doc.get("pages") or []
        if not pages_raw:
            pages_raw = [{
                "page_number": 1,
                "created_at": created_at_str,
                "created_by": doc.get("created_by", ""),
                "permissions": doc.get("roles", []),
                "storage_usage": 0
            }]

        return cls(
            id=str(doc["_id"]),
            name=doc["name"],
            category=doc.get("category", "Custom"),
            description=doc.get("description", ""),
            warehouseId=doc.get("warehouse_id"),
            columns=[TableColumnCreate(**c) for c in doc.get("columns", [])],
            roles=doc.get("roles", []),
            headerColor=doc.get("header_color", "#6366f1"),
            createdBy=doc.get("created_by", ""),
            createdAt=created_at_str,
            status=doc.get("status", "active"),
            pages=pages_raw
        )
