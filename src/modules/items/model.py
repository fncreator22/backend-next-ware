from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class ItemDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    sku: str
    name: str
    quantity: int
    warehouse_id: str
    tenant_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
