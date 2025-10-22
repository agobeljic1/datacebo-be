import secrets
from datetime import timedelta, datetime, timezone
from typing import List, Tuple, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.package import Package, License, LicensePackage
from app.models.user import User
from app.schemas.package import LicenseOut, PurchaseItem


def validate_and_price_items(
    db: Session, items: List[PurchaseItem]
) -> Tuple[List[Tuple[Package, List[Package]]], int]:
    validated_items: List[Tuple[Package, List[Package]]] = []
    total_price: int = 0

    for item in items:
        base_pkg = (
            db.query(Package)
            .filter(
                Package.id == item.base_package_id,
                Package.is_base.is_(True),
                Package.is_deprecated.is_(False),
            )
            .first()
        )
        if not base_pkg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid base package: {item.base_package_id}")

        addon_ids: List[int] = list(dict.fromkeys(item.addon_package_ids or []))
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

        total_price += base_pkg.price + sum(p.price for p in addon_pkgs)
        validated_items.append((base_pkg, addon_pkgs))

    return validated_items, total_price


def calculate_expiry(license_days: Optional[int]) -> datetime:
    days = license_days if license_days and license_days > 0 else settings.license_default_days
    return datetime.now(tz=timezone.utc) + timedelta(days=days)


def charge_and_create_licenses(
    db: Session,
    user_id: int,
    validated_items: List[Tuple[Package, List[Package]]],
    expires_at: datetime,
    total_price: int,
) -> List[LicenseOut]:
    created: List[LicenseOut] = []

    with db.begin():
        user_locked = (
            db.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .one()
        )

        if user_locked.balance < total_price:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient balance")

        user_locked.balance -= total_price
        db.add(user_locked)

        for base_pkg, addon_pkgs in validated_items:
            license_obj = License(
                user_id=user_locked.id,
                key=secrets.token_urlsafe(32),
                expires_at=expires_at,
            )
            db.add(license_obj)
            db.flush()

            package_ids: List[int] = [base_pkg.id] + [p.id for p in addon_pkgs]
            if package_ids:
                db.add_all(
                    [LicensePackage(license_id=license_obj.id, package_id=pid) for pid in package_ids]
                )

            created.append(
                LicenseOut(key=license_obj.key, package_ids=package_ids, expires_at=license_obj.expires_at)
            )

    return created


