from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.package import Package
from app.schemas.package import PackageCreate, PackageOut
from app.security.deps import require_admin


router = APIRouter()


@router.get("/", response_model=List[PackageOut])
def list_packages(db: Session = Depends(get_db)) -> List[PackageOut]:
    return db.query(Package).all()


@router.post("/", response_model=PackageOut, status_code=status.HTTP_201_CREATED)
def create_package(payload: PackageCreate, _: None = Depends(require_admin), db: Session = Depends(get_db)) -> PackageOut:
    exists = db.query(Package).filter(Package.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Package name already exists")
    pkg = Package(name=payload.name, is_base=payload.is_base, price=payload.price)
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg


