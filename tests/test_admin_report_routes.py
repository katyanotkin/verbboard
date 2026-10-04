"""Route tests for the Admin Report (issue #67) and POST /api/analytics/app_launch."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from core.admin_auth import ADMIN_SESSION_COOKIE, create_admin_session_token
from core.analytics import session_tracker


def _admin_cookies() -> dict[str, str]:
    return {ADMIN_SESSION_COOKIE: create_admin_session_token()}


def test_reports_api_requires_admin(client: TestClient) -> None:
    resp = client.get("/admin/api/reports?date_from=2026-10-01&date_to=2026-10-03")
    assert resp.status_code == 401


def test_reports_page_redirects_when_not_admin(client: TestClient) -> None:
    resp = client.get("/admin/reports", follow_redirects=False)
    assert resp.status_code in (302, 303, 307, 308)
    assert "/admin/login" in resp.headers.get("location", "")


def test_reports_page_renders_for_admin(client: TestClient) -> None:
    resp = client.get("/admin/reports", cookies=_admin_cookies())
    assert resp.status_code == 200


def test_reports_api_bad_dates_return_400(client: TestClient) -> None:
    resp = client.get("/admin/api/reports?date_from=bad&date_to=2026-10-03", cookies=_admin_cookies())
    assert resp.status_code == 400

    resp = client.get("/admin/api/reports?date_from=2026-10-03&date_to=2026-10-01", cookies=_admin_cookies())
    assert resp.status_code == 400


def test_reports_api_returns_json_report(client: TestClient, fake_db, monkeypatch) -> None:
    monkeypatch.setattr("core.admin_report_service._excluded_uids", lambda: set())
    fake_db._docs["analytics_sessions/2026-10-01_x"] = {"date": "2026-10-01", "device_type": "mobile", "twa": True}

    resp = client.get(
        "/admin/api/reports?date_from=2026-10-01&date_to=2026-10-02&compare=true", cookies=_admin_cookies()
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["non_bot_sessions"] == 1
    assert body["twa"]["sessions"] == 1
    assert "deltas" in body


def test_app_launch_beacon_flips_flag_on_existing_session(client: TestClient, fake_db, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.api_analytics.get_fingerprint_sid", lambda _request, _date: "fp1")

    resp = client.post("/api/analytics/app_launch")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    # No session yet: the launch is dropped, no stub doc.
    assert not any(k.startswith(session_tracker.COLLECTION) for k in fake_db._docs)

    date = datetime.now(UTC).strftime("%Y-%m-%d")
    path = f"{session_tracker.COLLECTION}/{date}_fp1"
    fake_db._docs[path] = {"date": date}

    resp = client.post("/api/analytics/app_launch")

    assert resp.status_code == 200
    # The handler fires the Firestore write as a background task (asyncio.to_thread)
    # and returns before it runs, so wait for it instead of asserting immediately.
    deadline = time.monotonic() + 5
    while "twa" not in fake_db._docs[path] and time.monotonic() < deadline:
        time.sleep(0.01)
    assert fake_db._docs[path]["twa"] is True
