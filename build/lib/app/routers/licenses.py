from datetime import datetime, timedelta, timezone
from typing import List, Optional
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.settings import settings
from app.db.session import get_db
from app.models.package import Package, License, LicensePackage
from app.models.user import User
from app.schemas.license import (
    LicenseCreateRequest,
    LicenseExtendRequest,
    LicenseRevokeRequest,
    LicenseValidateRequest,
    LicenseValidateResponse,
    LicensePackagesRequest,
    LicensePackagesResponse,
    LicenseRecord,
)
from app.security.deps import require_admin


router = APIRouter()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _license_to_record(lic: License) -> LicenseRecord:
    package_ids = [p.id for p in getattr(lic, "packages", [])]
    return LicenseRecord(
        id=lic.id,
        key=lic.key,
        user_id=lic.user_id,
        expires_at=lic.expires_at,
        revoked_at=lic.revoked_at,
        revoked_reason=lic.revoked_reason,
        package_ids=package_ids,
    )


@router.post("/", response_model=LicenseRecord, status_code=status.HTTP_201_CREATED)
def create_license(
    payload: LicenseCreateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LicenseRecord:
    user: Optional[User] = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user_id")

    unique_package_ids = list({pid for pid in payload.package_ids})
    packages = (
        db.query(Package)
        .filter(Package.id.in_(unique_package_ids), Package.is_deprecated == False)
        .all()
    )
    if len(packages) != len(unique_package_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or deprecated package id(s)")

    base_count = sum(1 for p in packages if p.is_base)
    if base_count != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exactly one base package is required")

    days = payload.license_days or settings.license_default_days
    expires_at = _utcnow() + timedelta(days=days)

    lic = License(user_id=user.id, key=secrets.token_urlsafe(32), expires_at=expires_at)
    # Use relationship to manage association rows efficiently
    lic.packages = packages
    db.add(lic)
    db.commit()
    db.refresh(lic)

    return _license_to_record(lic)


@router.get("/", response_model=List[LicenseRecord])
def list_licenses(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> List[LicenseRecord]:
    licenses = db.query(License).options(joinedload(License.packages)).all()
    return [_license_to_record(lic) for lic in licenses]


@router.post("/{license_id}/revoke", response_model=LicenseRecord)
def revoke_license(
    license_id: int,
    payload: LicenseRevokeRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LicenseRecord:
    lic: Optional[License] = db.query(License).filter(License.id == license_id).first()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    if lic.revoked_at:
        return _license_to_record(lic)
    lic.revoked_at = _utcnow()
    lic.revoked_reason = payload.reason
    db.add(lic)
    db.commit()
    db.refresh(lic)
    return _license_to_record(lic)


@router.post("/{license_id}/extend", response_model=LicenseRecord)
def extend_license(
    license_id: int,
    payload: LicenseExtendRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LicenseRecord:
    lic: Optional[License] = db.query(License).filter(License.id == license_id).first()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    lic.expires_at = lic.expires_at + timedelta(days=payload.extra_days)
    db.add(lic)
    db.commit()
    db.refresh(lic)
    return _license_to_record(lic)


@router.post("/validate", response_model=LicenseValidateResponse)
def validate_license(payload: LicenseValidateRequest, db: Session = Depends(get_db)) -> LicenseValidateResponse:
    lic: Optional[License] = db.query(License).filter(License.key == payload.key).first()
    if not lic:
        return LicenseValidateResponse(valid=False)
    now = _utcnow()
    if lic.revoked_at is not None:
        return LicenseValidateResponse(valid=False, expires_at=lic.expires_at, revoked_at=lic.revoked_at, reason=lic.revoked_reason)
    if lic.expires_at <= now:
        return LicenseValidateResponse(valid=False, expires_at=lic.expires_at)
    return LicenseValidateResponse(valid=True, expires_at=lic.expires_at)


@router.post("/packages", response_model=LicensePackagesResponse)
def license_packages(payload: LicensePackagesRequest, db: Session = Depends(get_db)) -> LicensePackagesResponse:
    lic: Optional[License] = (
        db.query(License).options(joinedload(License.packages)).filter(License.key == payload.key).first()
    )
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    # Enforce that only valid (not revoked, not expired) licenses can access packages
    now = _utcnow()
    if lic.revoked_at is not None or lic.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="License not valid")
    # Must have exactly one base in current license to access add-ons
    packages = [p for p in lic.packages if p.is_deprecated == False]
    base_count = sum(1 for p in packages if p.is_base)
    if base_count != 1:
        # Only return base if invalid add-on configuration
        packages = [p for p in packages if p.is_base]
    names = [p.name for p in packages]
    return LicensePackagesResponse(key=lic.key, package_names=names)



@router.get("/{license_key}/packages", response_model=LicensePackagesResponse)
def license_packages_get(license_key: str, db: Session = Depends(get_db)) -> LicensePackagesResponse:
    lic: Optional[License] = (
        db.query(License).options(joinedload(License.packages)).filter(License.key == license_key).first()
    )
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    now = _utcnow()
    if lic.revoked_at is not None or lic.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="License not valid")
    packages = [p for p in lic.packages if p.is_deprecated == False]
    base_count = sum(1 for p in packages if p.is_base)
    if base_count != 1:
        packages = [p for p in packages if p.is_base]
    names = [p.name for p in packages]
    return LicensePackagesResponse(key=lic.key, package_names=names)

