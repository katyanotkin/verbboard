"""Tests for POST /api/analytics/sign_in_tapped.

Diagnostic-only endpoint (issue #28): records which signIn() branch
(standalone/mobile/desktop) was tapped, before any credential exists.
Unauthenticated, fail-open shape -- same as /api/analytics/enrich.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_sign_in_tapped_requires_no_auth(client: TestClient) -> None:
    """No Authorization header at all -- must not 401, unlike /api/analytics/session."""
    with patch(
        "app.routes.api_analytics.record_sign_in_tap",
        new_callable=AsyncMock,
    ) as mock_record:
        resp = client.post("/api/analytics/sign_in_tapped", json={"branch": "mobile"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_record.assert_awaited_once()
    call_args = mock_record.call_args
    assert call_args.args[2] == "mobile"


def test_sign_in_tapped_passes_branch_through(client: TestClient) -> None:
    with patch(
        "app.routes.api_analytics.record_sign_in_tap",
        new_callable=AsyncMock,
    ) as mock_record:
        resp = client.post("/api/analytics/sign_in_tapped", json={"branch": "desktop"})

    assert resp.status_code == 200
    assert mock_record.call_args.args[2] == "desktop"


def test_sign_in_tapped_fails_open_on_malformed_body(client: TestClient) -> None:
    """A non-JSON body must not 500 -- request.json() raising is caught and
    treated as an empty body, same fail-open shape as /enrich."""
    with patch(
        "app.routes.api_analytics.record_sign_in_tap",
        new_callable=AsyncMock,
    ) as mock_record:
        resp = client.post(
            "/api/analytics/sign_in_tapped",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    # branch resolves to "" on a malformed body; the underlying tracker
    # helper is responsible for rejecting it (see test_session_tracker.py's
    # test_record_sign_in_tap_rejects_invalid_branch), not this route.
    mock_record.assert_awaited_once()
    assert mock_record.call_args.args[2] == ""


def test_sign_in_tapped_missing_branch_field(client: TestClient) -> None:
    """A well-formed JSON body with no "branch" key also resolves to ""."""
    with patch(
        "app.routes.api_analytics.record_sign_in_tap",
        new_callable=AsyncMock,
    ) as mock_record:
        resp = client.post("/api/analytics/sign_in_tapped", json={})

    assert resp.status_code == 200
    assert mock_record.call_args.args[2] == ""


def test_sign_in_tapped_invalid_branch_still_returns_ok(client: TestClient) -> None:
    """End-to-end (no mocking of record_sign_in_tap): an invalid branch value
    is silently rejected by the tracker layer, not surfaced as an error."""
    with patch("core.storage.firestore_db.get_db") as mock_get_db:
        resp = client.post("/api/analytics/sign_in_tapped", json={"branch": "tablet"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_get_db.assert_not_called()
