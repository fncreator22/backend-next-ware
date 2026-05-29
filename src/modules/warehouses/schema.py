from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict


class WarehouseCreate(BaseModel):
    name: str = Field(..., min_length=2)
    businessName: str = Field(..., min_length=2)
    address: str = Field(..., min_length=5)
    contact: str = Field(..., min_length=5)
    email: EmailStr
    taxPreference: str = "standard"
    logo: str = "🏭"
    currency: Optional[str] = ""


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    businessName: Optional[str] = None
    address: Optional[str] = None
    contact: Optional[str] = None
    email: Optional[EmailStr] = None
    taxPreference: Optional[str] = None
    logo: Optional[str] = None
    taxConfig: Optional[Dict[str, float]] = None
    currency: Optional[str] = None

