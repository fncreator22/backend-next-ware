from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class AuditLogCreate(BaseModel):
    action: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., min_length=2, max_length=500)
    warehouse_id: Optional[str] = Field(None, alias="warehouseId")

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True
    )


class AuditLogResponse(BaseModel):
    id: str = Field(..., alias="id")
    action: str
    description: str
    user_id: str = Field(..., alias="userId")
    user_name: str = Field(..., alias="userName")
    warehouse_id: Optional[str] = Field(None, alias="warehouseId")
    timestamp: str = Field(..., alias="timestamp")
    tenant_id: str = Field(..., alias="tenantId")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )

    @classmethod
    def from_doc(cls, doc: dict) -> "AuditLogResponse":
        """Factory helper to build audit log responses matching frontend camelCase expectations."""
        ts = doc.get("timestamp")
        if isinstance(ts, datetime):
            ts_str = ts.isoformat()
        else:
            ts_str = str(ts)

        return cls(
            id=str(doc["_id"]),
            action=doc.get("action", ""),
            description=doc.get("description", ""),
            userId=doc.get("user_id", ""),
            userName=doc.get("user_name", "System"),
            warehouseId=doc.get("warehouse_id"),
            timestamp=ts_str,
            tenantId=doc.get("tenant_id", "")
        )
