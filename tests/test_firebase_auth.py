from __future__ import annotations

from unittest.mock import patch

from fastapi import Request

from core.auth.firebase_auth import (
    get_bearer_token,
    get_optional_auth_user,
)
from core.settings import Settings


def _build_request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
    }
    return Request(scope)


def _mock_settings(environment: str, allow_local_dev_auth: bool = True) -> Settings:
    """Return a minimal Settings with the given environment and auth flag."""
    return Settings(
        environment=environment,
        host="localhost",
        port=8080,
        google_cloud_project="test-project",
        audio_bucket="test-bucket",
        verb_signals_collection="demand_signal",
        verb_signal_labels_collection="demand_signal_labels",
        verbs_collection="verbs",
        verb_candidates_collection="verb_candidates",
        log_level="INFO",
        admin_secret="test-secret",
        firebase_web_config_json="{}",
        allow_local_dev_auth=allow_local_dev_auth,
        badge_compact_threshold=20,
        verbs_page_limit=300,
        verbs_display_batch=20,
        gcp_region="us-east1",
    )


# ---------------------------------------------------------------------------
# get_bearer_token
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# local-dev bypass
# ---------------------------------------------------------------------------


def test_get_optional_auth_user_local_dev() -> None:
    request = _build_request({"Authorization": "Bearer local-dev"})

    user = get_optional_auth_user(request)

    assert user is not None
    assert user.uid == "local-dev-user"
    assert user.email == "dev@example.com"


def test_local_dev_token_rejected_on_stage() -> None:
    """local-dev must not be accepted when environment is stage."""
    request = _build_request({"Authorization": "Bearer local-dev"})

    with patch("core.auth.firebase_auth.load_settings", return_value=_mock_settings("stage")):
        user = get_optional_auth_user(request)

    assert user is None


def test_local_dev_token_rejected_when_flag_off() -> None:
    """local-dev is rejected when allow_local_dev_auth is False."""
    request = _build_request({"Authorization": "Bearer local-dev"})

    with patch(
        "core.auth.firebase_auth.load_settings",
        return_value=_mock_settings("local", allow_local_dev_auth=False),
    ):
        user = get_optional_auth_user(request)

    assert user is None


# ---------------------------------------------------------------------------
# user-stage bypass
# ---------------------------------------------------------------------------


def test_user_stage_token_accepted_on_stage() -> None:
    request = _build_request({"Authorization": "Bearer user-stage"})

    with patch("core.auth.firebase_auth.load_settings", return_value=_mock_settings("stage")):
        user = get_optional_auth_user(request)

    assert user is not None
    assert user.uid == "stage-mock-user"
    assert user.email == "dev-stage@example.com"


def test_user_stage_token_rejected_on_local() -> None:
    """user-stage must not work in local environment."""
    request = _build_request({"Authorization": "Bearer user-stage"})

    with patch("core.auth.firebase_auth.load_settings", return_value=_mock_settings("local")):
        user = get_optional_auth_user(request)

    assert user is None


def test_user_stage_token_rejected_on_prod() -> None:
    """user-stage must not work in prod environment."""
    request = _build_request({"Authorization": "Bearer user-stage"})

    with patch("core.auth.firebase_auth.load_settings", return_value=_mock_settings("prod")):
        user = get_optional_auth_user(request)

    assert user is None


def test_user_stage_token_rejected_when_flag_off() -> None:
    request = _build_request({"Authorization": "Bearer user-stage"})

    with patch(
        "core.auth.firebase_auth.load_settings",
        return_value=_mock_settings("stage", allow_local_dev_auth=False),
    ):
        user = get_optional_auth_user(request)

    assert user is None


# ---------------------------------------------------------------------------
# user-prod bypass
# ---------------------------------------------------------------------------


def test_user_prod_token_accepted_on_prod() -> None:
    request = _build_request({"Authorization": "Bearer user-prod"})

    with patch("core.auth.firebase_auth.load_settings", return_value=_mock_settings("prod")):
        user = get_optional_auth_user(request)

    assert user is not None
    assert user.uid == "prod-mock-user"
    assert user.email == "dev-prod@example.com"


def test_user_prod_token_rejected_on_local() -> None:
    request = _build_request({"Authorization": "Bearer user-prod"})

    with patch("core.auth.firebase_auth.load_settings", return_value=_mock_settings("local")):
        user = get_optional_auth_user(request)

    assert user is None


def test_user_prod_token_rejected_on_stage() -> None:
    """user-prod must not bleed into stage."""
    request = _build_request({"Authorization": "Bearer user-prod"})

    with patch("core.auth.firebase_auth.load_settings", return_value=_mock_settings("stage")):
        user = get_optional_auth_user(request)

    assert user is None


def test_user_prod_token_rejected_when_flag_off() -> None:
    request = _build_request({"Authorization": "Bearer user-prod"})

    with patch(
        "core.auth.firebase_auth.load_settings",
        return_value=_mock_settings("prod", allow_local_dev_auth=False),
    ):
        user = get_optional_auth_user(request)

    assert user is None
