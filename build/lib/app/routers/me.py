from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.package import License
from app.security.deps import get_current_user
from app.schemas.license import LicenseMyRecord


router = APIRouter()


@router.get("/me/licenses", response_model=List[LicenseMyRecord])
def my_licenses(db: Session = Depends(get_db), user=Depends(get_current_user)) -> List[LicenseMyRecord]:
    licenses = (
        db.query(License)
        .options(joinedload(License.packages))
        .filter(License.user_id == user.id)
        .all()
    )
    result: List[LicenseMyRecord] = []
    for lic in licenses:
        package_names = [p.name for p in lic.packages if p.is_deprecated == False]
        result.append(
            LicenseMyRecord(
                id=lic.id,
                key=lic.key,
                expires_at=lic.expires_at,
                revoked_at=lic.revoked_at,
                revoked_reason=lic.revoked_reason,
                package_names=package_names,
            )
        )
    return result


