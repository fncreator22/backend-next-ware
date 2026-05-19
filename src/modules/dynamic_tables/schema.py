from pydantic import BaseModel, Field
from typing import List, Optional


class ColumnDefinition(BaseModel):
    key: str
    header: str
    type: str  # text, number, select, date
    options: Optional[List[str]] = None  # for select dropdown values
    required: bool = False


class TableSchemaCreate(BaseModel):
    name: str = Field(..., min_length=2)
    warehouse_id: str
    columns: List[ColumnDefinition]
