from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DownloadEventCreate(BaseModel):
    package_name: str = Field(min_length=1, max_length=100)
    package_version: Optional[str] = Field(default=None, max_length=50)
    license_key: Optional[str] = Field(default=None, max_length=64)
    ip_address: Optional[str] = Field(default=None, max_length=45)


class DownloadEventOut(BaseModel):
    id: int
    user_id: Optional[int]
    license_key: Optional[str]
    package_name: str
    package_version: Optional[str]
    ip_address: Optional[str]
    valid_at_log_time: bool
    created_at: datetime

    class Config:
        from_attributes = True


