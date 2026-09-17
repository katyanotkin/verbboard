"""Tests for POST /api/analytics/enrich.

Diagnostic-only endpoint: fills in `language`/`ui_lang` on the caller's
analytics_sessions doc once known (they aren't available at session-creation
time). Unlike /sign_in_tapped and /practice_event, this endpoint does not
fail open on a JSON-decode failure -- it returns 400 with {"ok": False}.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_enrich_valid_dict_body_succeeds(client: TestClient) -> None:
    with patch(
        "app.routes.api_analytics.enrich_lang",
        new_callable=AsyncMock,
    ) as mock_enrich:
        resp = client.post(
            "/api/analytics/enrich",
            json={"language": "es", "ui_lang": "en"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_enrich.assert_awaited_once()
    call_args = mock_enrich.call_args
    assert call_args.args[2] == "es"
    assert call_args.args[3] == "en"


def test_enrich_no_recognized_language_fields_fails_open_at_200(client: TestClient) -> None:
    """A well-formed dict with no usable language fields returns {"ok": False}
    at 200 (not a 400) -- the 400 path is reserved for a body that isn't a
    dict at all or couldn't be parsed as JSON."""
    with patch(
        "app.routes.api_analytics.enrich_lang",
        new_callable=AsyncMock,
    ) as mock_enrich:
        resp = client.post("/api/analytics/enrich", json={})

    assert resp.status_code == 200
    assert resp.json() == {"ok": False}
    mock_enrich.assert_not_awaited()


def test_enrich_non_dict_body_returns_400(client: TestClient) -> None:
    """A syntactically valid but non-dict JSON body (e.g. a bare list) must
    not 500 via an unguarded body.get(...) call -- it returns 400."""
    with patch(
        "app.routes.api_analytics.enrich_lang",
        new_callable=AsyncMock,
    ) as mock_enrich:
        resp = client.post("/api/analytics/enrich", json=[1, 2, 3])

    assert resp.status_code == 400
    assert resp.json() == {"ok": False}
    mock_enrich.assert_not_awaited()


def test_enrich_malformed_body_returns_400(client: TestClient) -> None:
    """A body that fails to parse as JSON at all also returns 400, not a 500."""
    with patch(
        "app.routes.api_analytics.enrich_lang",
        new_callable=AsyncMock,
    ) as mock_enrich:
        resp = client.post(
            "/api/analytics/enrich",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 400
    assert resp.json() == {"ok": False}
    mock_enrich.assert_not_awaited()
