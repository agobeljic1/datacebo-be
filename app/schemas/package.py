from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PackageCreate(BaseModel):
    name: str
    is_base: bool
    price: int = Field(ge=0)


class PackageOut(BaseModel):
    id: int
    name: str
    is_base: bool
    price: int

    class Config:
        from_attributes = True


class PurchaseRequest(BaseModel):
    base_package_id: int
    addon_package_ids: List[int] = []
    license_days: Optional[int] = None


class LicenseOut(BaseModel):
    key: str
    package_ids: List[int]
    expires_at: datetime

