from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

_bearer = HTTPBearer(auto_error=False)


def create_access_token() -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": "admin",
        "iat": now,
        "exp": now + timedelta(seconds=settings.auth_ttl_seconds),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm="HS256")


def verify_password(password: str) -> bool:
    return secrets.compare_digest(password, get_settings().admin_password)


async def get_current_admin(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ],
    token: Annotated[str | None, Query()] = None,
) -> str:
    """Accept a bearer token or a `?token=` query parameter.

    The query parameter exists for direct download links; the dashboard uses
    the Authorization header and blob downloads.
    """

    raw = credentials.credentials if credentials else token
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )

    try:
        payload = jwt.decode(
            raw, get_settings().auth_secret, algorithms=["HS256"]
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен",
        ) from exc

    if payload.get("sub") != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен",
        )
    return "admin"
