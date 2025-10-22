from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.package import PurchaseRequest, LicenseOut
from app.security.deps import get_current_user
from app.services.store import (
    validate_and_price_items,
    calculate_expiry,
    charge_and_create_licenses,
)

router = APIRouter()

@router.post("/purchase", response_model=List[LicenseOut], status_code=status.HTTP_201_CREATED)
def purchase_packages(
    payload: PurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[LicenseOut]:
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No items provided")

    validated_items, total_price = validate_and_price_items(db, payload.items)
    expires_at = calculate_expiry(payload.license_days)
    return charge_and_create_licenses(
        db=db,
        user_id=current_user.id,
        validated_items=validated_items,
        expires_at=expires_at,
        total_price=total_price,
    )