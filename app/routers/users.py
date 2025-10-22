from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.security.deps import require_admin
from app.schemas.auth import UserOut, UpdateUserRoleRequest


router = APIRouter()


@router.get("/users", response_model=List[UserOut])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> List[UserOut]:
    return db.query(User).all()


@router.patch("/users/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: int,
    payload: UpdateUserRoleRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    u: Optional[User] = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    u.role = payload.role
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


