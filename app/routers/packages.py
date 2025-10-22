from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.package import Package
from app.schemas.package import PackageCreate, PackageOut
from app.security.deps import require_admin


router = APIRouter()


@router.get("/", response_model=List[PackageOut])
def list_packages(include_deprecated: bool = False, db: Session = Depends(get_db)) -> List[PackageOut]:
    query = db.query(Package)
    if not include_deprecated:
        query = query.filter(Package.is_deprecated == False)
    return query.all()


@router.post("/", response_model=PackageOut, status_code=status.HTTP_201_CREATED)
def create_package(payload: PackageCreate, _: None = Depends(require_admin), db: Session = Depends(get_db)) -> PackageOut:
    exists = db.query(Package).filter(Package.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Package name already exists")
    pkg = Package(
        name=payload.name,
        is_base=payload.is_base,
        price=payload.price,
        is_deprecated=payload.is_deprecated,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg


@router.post("/{package_id}/deprecate", response_model=PackageOut)
def deprecate_package(package_id: int, _: None = Depends(require_admin), db: Session = Depends(get_db)) -> PackageOut:
    pkg: Optional[Package] = db.query(Package).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    if pkg.is_deprecated:
        return pkg
    pkg.is_deprecated = True
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg


@router.post("/{package_id}/undeprecate", response_model=PackageOut)
def undeprecate_package(package_id: int, _: None = Depends(require_admin), db: Session = Depends(get_db)) -> PackageOut:
    pkg: Optional[Package] = db.query(Package).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    if not pkg.is_deprecated:
        return pkg
    pkg.is_deprecated = False
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg


