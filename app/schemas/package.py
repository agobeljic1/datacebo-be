from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PackageCreate(BaseModel):
    name: str
    is_base: bool
    price: int = Field(ge=0)
    is_deprecated: bool = False


class PackageOut(BaseModel):
    id: int
    name: str
    is_base: bool
    price: int
    is_deprecated: bool

    class Config:
        from_attributes = True


class PurchaseItem(BaseModel):
    base_package_id: int
    addon_package_ids: List[int] = []


class PurchaseRequest(BaseModel):
    items: List[PurchaseItem] = Field(min_items=1)
    license_days: Optional[int] = None


class LicenseOut(BaseModel):
    key: str
    package_ids: List[int]
    expires_at: datetime

    class Config:
        from_attributes = True

