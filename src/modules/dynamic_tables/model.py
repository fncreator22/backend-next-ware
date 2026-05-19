from datetime import datetime
from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class TableColumnModel(BaseModel):
    key: str
    header: str
    type: str
    options: Optional[List[str]] = None
    required: bool = False


class TableSchemaDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    warehouse_id: str
    tenant_id: str
    created_by: str
    columns: List[TableColumnModel]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TableRowDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    table_id: str
    warehouse_id: str
    tenant_id: str
    data: Dict[str, str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
