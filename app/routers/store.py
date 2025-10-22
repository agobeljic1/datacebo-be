import secrets
from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.session import get_db
from app.models.package import Package, License, LicensePackage
from app.models.user import User
from app.schemas.package import PurchaseRequest, LicenseOut
from app.security.deps import get_current_user


router = APIRouter()


@router.post("/purchase", response_model=LicenseOut)
def purchase_packages(
    payload: PurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LicenseOut:
    base_pkg = (
        db.query(Package)
        .filter(
            Package.id == payload.base_package_id,
            Package.is_base == True, 
            Package.is_deprecated == False, 
        )
        .first()
    )
    if not base_pkg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base package")
    addon_pkgs = []
    if payload.addon_package_ids:
        addon_pkgs = (
            db.query(Package)
            .filter(
                Package.id.in_(payload.addon_package_ids),
                Package.is_base == False,   
                Package.is_deprecated == False,
            )
            .all()
        )
        if len(addon_pkgs) != len(payload.addon_package_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or deprecated add-on package id(s)",
            )

    total_price = base_pkg.price + sum(p.price for p in addon_pkgs)
    if current_user.balance < total_price:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient balance")

    # charge
    current_user.balance -= total_price
    db.add(current_user)

    days = payload.license_days or settings.license_default_days
    expires_at = (current_user.created_at + timedelta(days=0))  # to appease mypy about tz; overwritten below
    from datetime import datetime, timezone
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=days)

    # create single license and associate packages
    key = secrets.token_urlsafe(32)
    license_obj = License(user_id=current_user.id, key=key, expires_at=expires_at)
    db.add(license_obj)
    db.commit()
    db.refresh(license_obj)

    package_ids: List[int] = [base_pkg.id] + [p.id for p in addon_pkgs]
    for pid in package_ids:
        db.add(LicensePackage(license_id=license_obj.id, package_id=pid))

    db.commit()
    return LicenseOut(key=license_obj.key, package_ids=package_ids, expires_at=license_obj.expires_at)


