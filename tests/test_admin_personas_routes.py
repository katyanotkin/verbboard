"""Admin Personas page and APIs (issue #143)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from core import persona_review_service as review_svc
from core import persona_snapshot_service as snap_svc
from core.admin_auth import ADMIN_SESSION_COOKIE, create_admin_session_token


def _admin() -> dict[str, str]:
    return {ADMIN_SESSION_COOKIE: create_admin_session_token()}


_MD = """Last review: 2026-11-24. Next review: 2026-12-15.

## Dana

Summary.

| Claim | Status | Evidence | n | Last checked |
|---|---|---|---|---|
| c | assumed | e | 0 | 2026-11-24 |
"""


def _seed_review(fake_db, day: str = "2026-11-24") -> None:
    fake_db._docs[f"{review_svc.COLLECTION}/{day}"] = {
        "date": day,
        "status": "open",
        "window": {"date_from": "2026-11-03", "date_to": "2026-11-23"},
        "body": "figures",
    }


def test_page_redirects_without_admin(client: TestClient) -> None:
    resp = client.get("/admin/personas", follow_redirects=False)

    assert resp.status_code in (302, 303, 307, 308)
    assert "/admin/login" in resp.headers.get("location", "")


def test_apis_require_admin(client: TestClient) -> None:
    assert client.get("/admin/api/personas").status_code == 401
    assert client.post("/admin/api/personas/reviews/2026-11-24/done").status_code == 401


def test_page_renders_for_admin(client: TestClient) -> None:
    resp = client.get("/admin/personas", cookies=_admin())

    assert resp.status_code == 200
    assert "Personas" in resp.text


def test_api_payload_with_data(client: TestClient, fake_db) -> None:
    _seed_review(fake_db)
    snap_svc.publish_snapshot(_MD, "2026-11-24", "abc")

    body = client.get("/admin/api/personas", cookies=_admin()).json()

    assert set(body) == {"open_review", "snapshot", "evolution", "reviews"}
    assert body["open_review"]["date"] == "2026-11-24"
    assert body["snapshot"]["date"] == "2026-11-24"
    assert body["evolution"][0]["date"] == "2026-11-24"
    assert body["reviews"][0]["date"] == "2026-11-24"


def test_api_payload_empty(client: TestClient) -> None:
    body = client.get("/admin/api/personas", cookies=_admin()).json()

    assert body == {"open_review": None, "snapshot": None, "evolution": [], "reviews": []}


def test_done_rejects_bad_dates(client: TestClient) -> None:
    for bad in ("2026-1-1", "..%2Fx", "abc"):
        resp = client.post(f"/admin/api/personas/reviews/{bad}/done", cookies=_admin())
        assert resp.status_code in (400, 404)
    assert client.post("/admin/api/personas/reviews/2026-1-1/done", cookies=_admin()).status_code == 400


def test_done_unknown_review_is_404(client: TestClient) -> None:
    assert client.post("/admin/api/personas/reviews/2026-01-01/done", cookies=_admin()).status_code == 404


def test_done_closes_open_review(client: TestClient, fake_db) -> None:
    _seed_review(fake_db)

    resp = client.post("/admin/api/personas/reviews/2026-11-24/done", cookies=_admin())

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert client.get("/admin/api/personas", cookies=_admin()).json()["open_review"] is None
