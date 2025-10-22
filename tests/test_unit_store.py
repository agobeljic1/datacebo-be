from datetime import datetime, timedelta, timezone
import math

import pytest
from fastapi import HTTPException, status

from app.db.session import Base, engine, SessionLocal
from app.models.package import Package, License, LicensePackage
from app.models.user import User
from app.services.store import validate_and_price_items, calculate_expiry, charge_and_create_licenses
from app.schemas.package import PurchaseItem
from app.core.settings import settings


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def seed_packages(db):
    base = Package(name="baseA", is_base=True, price=100, is_deprecated=False)
    addon1 = Package(name="addonX", is_base=False, price=30, is_deprecated=False)
    addon2 = Package(name="addonY", is_base=False, price=20, is_deprecated=False)
    db.add_all([base, addon1, addon2])
    db.commit()
    db.refresh(base)
    db.refresh(addon1)
    db.refresh(addon2)
    return base, addon1, addon2


def test_validate_and_price_items_success():
    db = SessionLocal()
    try:
        base, addon1, addon2 = seed_packages(db)
        items = [PurchaseItem(base_package_id=base.id, addon_package_ids=[addon1.id, addon2.id])]
        validated, total = validate_and_price_items(db, items)
        assert len(validated) == 1
        (vbase, vaddons) = validated[0]
        assert vbase.id == base.id
        assert {a.id for a in vaddons} == {addon1.id, addon2.id}
        assert total == base.price + addon1.price + addon2.price
    finally:
        db.close()


def test_validate_and_price_items_invalid_base():
    db = SessionLocal()
    try:
        seed_packages(db)
        with pytest.raises(HTTPException) as ei:
            validate_and_price_items(db, [PurchaseItem(base_package_id=9999, addon_package_ids=[])])
        assert ei.value.status_code == status.HTTP_400_BAD_REQUEST
    finally:
        db.close()


def test_validate_and_price_items_base_cannot_be_addon():
    db = SessionLocal()
    try:
        base, addon1, _ = seed_packages(db)
        with pytest.raises(HTTPException) as ei:
            validate_and_price_items(db, [PurchaseItem(base_package_id=base.id, addon_package_ids=[base.id, addon1.id])])
        assert ei.value.status_code == status.HTTP_400_BAD_REQUEST
    finally:
        db.close()


def test_validate_and_price_items_invalid_addon():
    db = SessionLocal()
    try:
        base, addon1, _ = seed_packages(db)
        with pytest.raises(HTTPException) as ei:
            validate_and_price_items(db, [PurchaseItem(base_package_id=base.id, addon_package_ids=[addon1.id, 424242])])
        assert ei.value.status_code == status.HTTP_400_BAD_REQUEST
    finally:
        db.close()


def test_calculate_expiry_respects_days_and_default():
    # specific days
    before = datetime.now(tz=timezone.utc)
    dt = calculate_expiry(10)
    after = datetime.now(tz=timezone.utc)
    assert before + timedelta(days=10) <= dt <= after + timedelta(days=10, seconds=1)

    # default when None or <=0
    before = datetime.now(tz=timezone.utc)
    dt2 = calculate_expiry(None)
    after = datetime.now(tz=timezone.utc)
    assert before + timedelta(days=settings.license_default_days) <= dt2 <= after + timedelta(days=settings.license_default_days, seconds=1)

    before = datetime.now(tz=timezone.utc)
    dt3 = calculate_expiry(0)
    after = datetime.now(tz=timezone.utc)
    assert before + timedelta(days=settings.license_default_days) <= dt3 <= after + timedelta(days=settings.license_default_days, seconds=1)

    # negative falls back to default
    before = datetime.now(tz=timezone.utc)
    dt4 = calculate_expiry(-5)
    after = datetime.now(tz=timezone.utc)
    assert before + timedelta(days=settings.license_default_days) <= dt4 <= after + timedelta(days=settings.license_default_days, seconds=1)


def test_charge_and_create_licenses_happy_path_and_insufficient_balance():
    db = SessionLocal()
    try:
        base, addon1, addon2 = seed_packages(db)
        # Create user with enough balance
        user = User(email="u@example.com", hashed_password="x", balance=1000)
        db.add(user)
        db.commit()
        db.refresh(user)

        # Prepare validated items and price
        validated, total = validate_and_price_items(
            db,
            [PurchaseItem(base_package_id=base.id, addon_package_ids=[addon1.id, addon2.id])],
        )
        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=5)

        created = charge_and_create_licenses(
            db=db,
            user_id=user.id,
            validated_items=validated,
            expires_at=expires_at,
            total_price=total,
        )
        assert len(created) == 1
        # Reload user and check balance
        refreshed_user = db.query(User).filter(User.id == user.id).one()
        assert refreshed_user.balance == 1000 - total
        # Verify license in DB
        lic = db.query(License).filter(License.user_id == user.id).one()
        links = db.query(LicensePackage).filter(LicensePackage.license_id == lic.id).all()
        assert {lp.package_id for lp in links} == {base.id, addon1.id, addon2.id}

        # Insufficient balance case
        poor = User(email="poor@example.com", hashed_password="x", balance=0)
        db.add(poor)
        db.commit()
        db.refresh(poor)

        with pytest.raises(HTTPException) as ei:
            charge_and_create_licenses(
                db=db,
                user_id=poor.id,
                validated_items=validated,
                expires_at=expires_at,
                total_price=total,
            )
        assert ei.value.status_code == status.HTTP_402_PAYMENT_REQUIRED
        # Ensure no license created for poor user
        assert db.query(License).filter(License.user_id == poor.id).count() == 0
    finally:
        db.close()


def test_validate_and_price_items_deduplicates_addons_and_sums_price_once():
    db = SessionLocal()
    try:
        base, addon1, _ = seed_packages(db)
        items = [PurchaseItem(base_package_id=base.id, addon_package_ids=[addon1.id, addon1.id, addon1.id])]
        validated, total = validate_and_price_items(db, items)
        assert len(validated) == 1
        vbase, vaddons = validated[0]
        assert vbase.id == base.id
        assert [a.id for a in vaddons] == [addon1.id]
        assert total == base.price + addon1.price
    finally:
        db.close()


def test_charge_and_create_licenses_multiple_items_creates_multiple_licenses_and_deducts_total():
    db = SessionLocal()
    try:
        base, addon1, addon2 = seed_packages(db)
        user = User(email="multi@example.com", hashed_password="x", balance=10_000)
        db.add(user)
        db.commit()
        db.refresh(user)

        items = [
            PurchaseItem(base_package_id=base.id, addon_package_ids=[addon1.id]),
            PurchaseItem(base_package_id=base.id, addon_package_ids=[addon2.id]),
        ]
        validated, total = validate_and_price_items(db, items)
        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=1)

        created = charge_and_create_licenses(
            db=db,
            user_id=user.id,
            validated_items=validated,
            expires_at=expires_at,
            total_price=total,
        )
        assert len(created) == 2
        # Balance reduced appropriately
        user_after = db.query(User).filter(User.id == user.id).one()
        assert user_after.balance == 10_000 - total
        # Verify two licenses exist
        assert db.query(License).filter(License.user_id == user.id).count() == 2
    finally:
        db.close()


