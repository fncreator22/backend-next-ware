from pydantic import BaseModel, Field
from typing import Optional


class ItemCreate(BaseModel):
    sku: str = Field(..., min_length=3)
    name: str = Field(..., min_length=2)
    quantity: int = Field(..., ge=0)
    warehouse_id: str


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=0)
