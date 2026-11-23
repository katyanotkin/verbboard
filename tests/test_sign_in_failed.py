"""Tests for POST /api/analytics/sign_in_failed (issue #140).

Unauthenticated, fail-open diagnostic beacon with a per-session rate limit.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.routes import api_analytics


@pytest.fixture(autouse=True)
def _reset_limiters():
    for limiter in (api_analytics._SIGN_IN_FAILED_SESSION_LIMITER, api_analytics._SIGN_IN_FAILED_GLOBAL_LIMITER):
        limiter._hits.clear()
    yield
    for limiter in (api_analytics._SIGN_IN_FAILED_SESSION_LIMITER, api_analytics._SIGN_IN_FAILED_GLOBAL_LIMITER):
        limiter._hits.clear()


def _post(client: TestClient, **kwargs):
    with patch("app.routes.api_analytics.record_sign_in_failure", new_callable=AsyncMock) as mock_record:
        resp = client.post("/api/analytics/sign_in_failed", **kwargs)
    return resp, mock_record


def test_requires_no_auth_and_passes_branch_and_code(client: TestClient) -> None:
    resp, mock_record = _post(client, json={"branch": "mobile", "code": "popup_closed"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_record.assert_awaited_once()
    assert mock_record.call_args.args[2:] == ("mobile", "popup_closed")


def test_malformed_body_fails_open(client: TestClient) -> None:
    resp, mock_record = _post(client, content=b"not json", headers={"Content-Type": "application/json"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert mock_record.call_args.args[2:] == ("", "")


def test_non_dict_body_fails_open(client: TestClient) -> None:
    resp, mock_record = _post(client, json=[1, 2])

    assert resp.status_code == 200
    assert mock_record.call_args.args[2:] == ("", "")


def test_long_values_are_truncated(client: TestClient) -> None:
    _, mock_record = _post(client, json={"branch": "x" * 500, "code": "y" * 500})

    assert len(mock_record.call_args.args[2]) == 32
    assert len(mock_record.call_args.args[3]) == 32


def test_per_session_limit_drops_silently(client: TestClient) -> None:
    with patch("app.routes.api_analytics.record_sign_in_failure", new_callable=AsyncMock) as mock_record:
        statuses = [
            client.post("/api/analytics/sign_in_failed", json={"branch": "mobile", "code": "network"})
            for _ in range(12)
        ]

    assert all(r.status_code == 200 and r.json() == {"ok": True} for r in statuses)
    assert mock_record.await_count == 10
