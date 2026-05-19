from pydantic import BaseModel, Field
from typing import Optional


class WarehouseCreate(BaseModel):
    name: str = Field(..., min_length=2)
    address: str = Field(..., min_length=5)


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
