import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import create_access_token, get_token_subject


def test_access_token_round_trip() -> None:
    token = create_access_token("teacher-123")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    assert get_token_subject(credentials) == "teacher-123"


def test_invalid_access_token_is_rejected() -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid")

    with pytest.raises(HTTPException) as error:
        get_token_subject(credentials)

    assert error.value.status_code == 401
