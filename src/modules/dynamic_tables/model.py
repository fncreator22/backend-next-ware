from datetime import datetime
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any


class TableColumnModel(BaseModel):
    id: str  # maps to frontend key/id (e.g. c1)
    name: str  # maps to frontend column name/header (e.g. Task)
    type: str  # text, number, price, date, checkbox, dropdown, status, tags
    options: Optional[str] = ""  # comma-separated options for dropdown
    required: bool = False


class TableSchemaDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    table_name: str  # for unique compound index [warehouse_id, table_name]
    category: str = "Custom"
    description: Optional[str] = ""
    warehouse_id: Optional[str] = None  # Scoped per warehouse (None means all-warehouses scope)
    tenant_id: str
    columns: List[TableColumnModel]
    roles: List[str] = []  # Restrictive roles allowed to access this table
    header_color: Optional[str] = "#6366f1"
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "active"


class TableRowDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    table_id: str
    warehouse_id: str
    tenant_id: str
    data: Dict[str, Any]  # Stores custom dynamic values as key-value pairs (key is column id)
    created_at: datetime = Field(default_factory=datetime.utcnow)
