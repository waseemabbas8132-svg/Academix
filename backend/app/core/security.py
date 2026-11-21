from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings

_bearer_scheme = HTTPBearer()


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    role: str | None = None,
) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expires_at}
    if role is not None:
        payload["role"] = role
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def get_token_subject(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    settings = get_settings()
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as error:
        raise unauthorized from error

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise unauthorized
    return subject
