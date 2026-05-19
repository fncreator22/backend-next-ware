from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class WarehouseDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    tenant_id: str
    name: str
    address: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
