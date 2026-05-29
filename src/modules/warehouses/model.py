from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict


class WarehouseDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    tenant_id: str
    ownerId: str
    name: str
    businessName: str
    address: str
    contact: str
    email: str
    taxPreference: str = "standard"
    logo: str = "🏭"
    status: str = "active"
    currency: str = ""
    taxConfig: Dict[str, float] = Field(default_factory=lambda: {"luxury": 15.0, "normal": 5.0})
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

