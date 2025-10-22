import secrets
from datetime import timedelta, datetime, timezone
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


@router.post("/purchase", response_model=LicenseOut, status_code=status.HTTP_201_CREATED)
def purchase_packages(
    payload: PurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LicenseOut:
    # Validate base package
    base_pkg = (
        db.query(Package)
        .filter(
            Package.id == payload.base_package_id,
            Package.is_base.is_(True),
            Package.is_deprecated.is_(False),
        )
        .first()
    )
    if not base_pkg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base package")

    # Prepare and validate add-on packages (deduplicated, cannot include base package)
    addon_ids: List[int] = list(dict.fromkeys(payload.addon_package_ids or []))
    if base_pkg.id in addon_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Base package cannot be an add-on")

    addon_pkgs: List[Package] = []
    if addon_ids:
        addon_pkgs = (
            db.query(Package)
            .filter(
                Package.id.in_(addon_ids),
                Package.is_base.is_(False),
                Package.is_deprecated.is_(False),
            )
            .all()
        )
        if len(addon_pkgs) != len(addon_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or deprecated add-on package id(s)",
            )

    total_price = base_pkg.price + sum(p.price for p in addon_pkgs)

    # License duration
    days_input = payload.license_days
    days = days_input if days_input and days_input > 0 else settings.license_default_days
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=days)

    # Single transaction with user row lock to prevent race conditions on balance
    with db.begin():
        user_locked = (
            db.query(User)
            .filter(User.id == current_user.id)
            .with_for_update()
            .one()
        )

        if user_locked.balance < total_price:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient balance")

        user_locked.balance -= total_price
        db.add(user_locked)

        license_obj = License(
            user_id=user_locked.id,
            key=secrets.token_urlsafe(32),
            expires_at=expires_at,
        )
        db.add(license_obj)
        db.flush()  # ensure license_obj.id is available

        package_ids: List[int] = [base_pkg.id] + [p.id for p in addon_pkgs]
        if package_ids:
            db.add_all(
                [LicensePackage(license_id=license_obj.id, package_id=pid) for pid in package_ids]
            )

    return LicenseOut(key=license_obj.key, package_ids=package_ids, expires_at=license_obj.expires_at)


