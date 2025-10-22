from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.event import DownloadEvent
from app.models.package import License
from app.schemas.event import DownloadEventCreate, DownloadEventOut
from app.security.deps import get_current_user, require_admin


router = APIRouter()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@router.post("/events", response_model=DownloadEventOut, status_code=status.HTTP_201_CREATED)
def log_download_event(
    payload: DownloadEventCreate,
    request: Request,
    db: Session = Depends(get_db),
    # Optional: allow anonymous (no auth) to log events; if you want to require auth, add Depends(get_current_user)
) -> DownloadEventOut:
    # Determine validity of license key at log time (if provided)
    valid = False
    if payload.license_key:
        lic: Optional[License] = db.query(License).filter(License.key == payload.license_key).first()
        if lic and lic.revoked_at is None and lic.expires_at > _utcnow():
            valid = True

    client_ip = payload.ip_address or request.client.host if request.client else None

    evt = DownloadEvent(
        user_id=None,  # Could be populated from auth if required
        license_key=payload.license_key,
        package_name=payload.package_name,
        package_version=payload.package_version,
        ip_address=client_ip,
        valid_at_log_time=1 if valid else 0,
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)
    return evt


@router.get("/events", response_model=List[DownloadEventOut])
def list_download_events(
    _: None = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
    license_key: Optional[str] = None,
    package_name: Optional[str] = None,
    valid: Optional[bool] = None,
) -> List[DownloadEventOut]:
    query = db.query(DownloadEvent)
    if license_key:
        query = query.filter(DownloadEvent.license_key == license_key)
    if package_name:
        query = query.filter(DownloadEvent.package_name == package_name)
    if valid is not None:
        query = query.filter(DownloadEvent.valid_at_log_time == (1 if valid else 0))
    return query.order_by(DownloadEvent.id.desc()).offset(offset).limit(limit).all()


