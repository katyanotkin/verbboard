from __future__ import annotations

from fastapi import Request

from core.auth.firebase_auth import (
    get_bearer_token,
    get_optional_auth_user,
)


def _build_request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "headers": [
            (key.lower().encode(), value.encode()) for key, value in headers.items()
        ],
    }
    return Request(scope)


def test_get_bearer_token_missing() -> None:
    request = _build_request({})
    assert get_bearer_token(request) == ""


def test_get_bearer_token_invalid_prefix() -> None:
    request = _build_request(
        {
            "Authorization": "Token abc123",
        }
    )

    assert get_bearer_token(request) == ""


def test_get_bearer_token_success() -> None:
    request = _build_request(
        {
            "Authorization": "Bearer abc123",
        }
    )

    assert get_bearer_token(request) == "abc123"


def test_get_optional_auth_user_local_dev() -> None:
    request = _build_request(
        {
            "Authorization": "Bearer local-dev",
        }
    )

    user = get_optional_auth_user(request)

    assert user is not None
    assert user.uid == "local-dev-user"
    assert user.email == "dev@example.com"
