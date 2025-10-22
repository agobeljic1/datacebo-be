from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class LicenseCreateRequest(BaseModel):
    user_id: int
    package_ids: List[int] = Field(min_items=1)
    license_days: Optional[int] = None


class LicenseExtendRequest(BaseModel):
    extra_days: int = Field(gt=0)


class LicenseRevokeRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=255)


class LicenseValidateRequest(BaseModel):
    key: str


class LicenseValidateResponse(BaseModel):
    valid: bool
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    reason: Optional[str] = None


class LicensePackagesRequest(BaseModel):
    key: str


class LicensePackagesResponse(BaseModel):
    key: str
    package_names: List[str]


class LicenseRecord(BaseModel):
    id: int
    key: str
    user_id: int
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
    package_ids: List[int]

    class Config:
        from_attributes = True


