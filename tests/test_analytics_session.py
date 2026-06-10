"""Tests for POST /api/analytics/session.

The endpoint ties an anonymous session ID (vb_sid cookie) to a Firebase UID
after login. It requires both a valid auth token and the vb_sid cookie.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class _MockUser:
    def __init__(self, uid: str) -> None:
        self.uid = uid
        self.email = f"{uid}@example.com"


def test_analytics_session_rejects_unauthenticated(client: TestClient) -> None:
    resp = client.post("/api/analytics/session")
    assert resp.status_code == 401


def test_analytics_session_rejects_missing_sid_cookie(client: TestClient) -> None:
    """Auth passes but no vb_sid cookie -> 400."""
    with patch(
        "app.routes.api_analytics.get_optional_auth_user",
        return_value=_MockUser("uid-abc"),
    ):
        resp = client.post("/api/analytics/session")
    assert resp.status_code == 400


def test_analytics_session_returns_ok_with_valid_inputs(client: TestClient) -> None:
    with (
        patch(
            "app.routes.api_analytics.get_optional_auth_user",
            return_value=_MockUser("uid-abc"),
        ),
        patch(
            "app.routes.api_analytics.attach_uid",
            new_callable=AsyncMock,
        ) as mock_attach,
    ):
        resp = client.post(
            "/api/analytics/session",
            cookies={"vb_sid": "test-session-id"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_attach.assert_awaited_once()
    call_args = mock_attach.call_args
    assert call_args.args[0] == "test-session-id"
    assert call_args.args[2] == "uid-abc"
