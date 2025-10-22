import datetime as dt
from typing import Any, Dict, Optional

import jwt

from app.core.settings import settings


def _utc_now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def create_access_token(subject: str, role: Optional[str] = None) -> str:
    expires = _utc_now() + dt.timedelta(minutes=settings.access_token_expires_minutes)
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "exp": expires,
        "iat": _utc_now(),
    }
    if role is not None:
        payload["role"] = role
    return jwt.encode(payload, settings.access_token_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    expires = _utc_now() + dt.timedelta(days=settings.refresh_token_expires_days)
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": "refresh",
        "exp": expires,
        "iat": _utc_now(),
    }
    return jwt.encode(payload, settings.refresh_token_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.access_token_secret, algorithms=[settings.jwt_algorithm])


def decode_refresh_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.refresh_token_secret, algorithms=[settings.jwt_algorithm])
