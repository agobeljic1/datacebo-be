from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.balance import BalanceIncreaseRequest, BalanceResponse
from app.security.deps import get_current_user


router = APIRouter()


@router.post("/increase", response_model=BalanceResponse)
def increase_balance(
    payload: BalanceIncreaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BalanceResponse:
    current_user.balance += payload.amount
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return BalanceResponse(balance=current_user.balance)


