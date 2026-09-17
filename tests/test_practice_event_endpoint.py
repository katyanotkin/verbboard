"""Tests for POST /api/analytics/practice_event.

Diagnostic-only endpoint (issue #48): records an auth-independent practice
engagement signal ("started" / "completed") on analytics_sessions, since
practice_loop.js has no auth gate and the uid-keyed user_practice collection
misses anonymous sessions. Unauthenticated, fail-open shape -- same as
/api/analytics/enrich and /api/analytics/sign_in_tapped.

Note: a non-dict JSON body (e.g. a bare list) 500s on this endpoint via the
unguarded `body.get(...)` call -- a known, already-flagged pre-existing bug
shared with /sign_in_tapped and /enrich, tracked separately. Not covered or
asserted-as-correct here; see code review notes on issue #48.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_practice_event_started_requires_no_auth(client: TestClient) -> None:
    """No Authorization header at all -- must not 401, unlike /api/analytics/session."""
    with (
        patch("app.routes.api_analytics.record_practice_started", new_callable=AsyncMock) as mock_started,
        patch("app.routes.api_analytics.record_practice_completed", new_callable=AsyncMock) as mock_completed,
    ):
        resp = client.post("/api/analytics/practice_event", json={"event": "started"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_started.assert_awaited_once()
    mock_completed.assert_not_awaited()


def test_practice_event_completed_dispatches_to_completed_tracker(client: TestClient) -> None:
    with (
        patch("app.routes.api_analytics.record_practice_started", new_callable=AsyncMock) as mock_started,
        patch("app.routes.api_analytics.record_practice_completed", new_callable=AsyncMock) as mock_completed,
    ):
        resp = client.post("/api/analytics/practice_event", json={"event": "completed"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_completed.assert_awaited_once()
    mock_started.assert_not_awaited()


def test_practice_event_invalid_event_fails_open(client: TestClient) -> None:
    """An unrecognized event value returns {"ok": False} at 200, not a 500 --
    fail-open, same as the other diagnostic-only analytics endpoints -- and
    neither tracker function is dispatched."""
    with (
        patch("app.routes.api_analytics.record_practice_started", new_callable=AsyncMock) as mock_started,
        patch("app.routes.api_analytics.record_practice_completed", new_callable=AsyncMock) as mock_completed,
    ):
        resp = client.post("/api/analytics/practice_event", json={"event": "bogus"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": False}
    mock_started.assert_not_awaited()
    mock_completed.assert_not_awaited()


def test_practice_event_missing_event_field_fails_open(client: TestClient) -> None:
    """A well-formed JSON body with no "event" key also fails open, not 500."""
    with (
        patch("app.routes.api_analytics.record_practice_started", new_callable=AsyncMock) as mock_started,
        patch("app.routes.api_analytics.record_practice_completed", new_callable=AsyncMock) as mock_completed,
    ):
        resp = client.post("/api/analytics/practice_event", json={})

    assert resp.status_code == 200
    assert resp.json() == {"ok": False}
    mock_started.assert_not_awaited()
    mock_completed.assert_not_awaited()


def test_practice_event_malformed_body_fails_open(client: TestClient) -> None:
    """A non-JSON body must not 500 -- request.json() raising is caught and
    treated as an empty body, same fail-open shape as /sign_in_tapped."""
    with (
        patch("app.routes.api_analytics.record_practice_started", new_callable=AsyncMock) as mock_started,
        patch("app.routes.api_analytics.record_practice_completed", new_callable=AsyncMock) as mock_completed,
    ):
        resp = client.post(
            "/api/analytics/practice_event",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": False}
    mock_started.assert_not_awaited()
    mock_completed.assert_not_awaited()
