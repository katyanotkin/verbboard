from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.auth.models import AuthUser


@pytest.fixture(autouse=True)
def _fresh_limiter():
    from app.routes import api_plus
    from core.rate_limit import SlidingWindowRateLimiter

    api_plus._PLUS_REQUEST_RATE_LIMITER = SlidingWindowRateLimiter(max_calls=20, window_seconds=600)


@pytest.fixture()
def token_user(monkeypatch):
    def fake_verify(token):
        if token == "good":
            return AuthUser(uid="u1", email="acct@example.com", name="", picture="")
        if token == "noemail":
            return AuthUser(uid="u2", email="", name="", picture="")
        raise ValueError("bad token")

    monkeypatch.setattr(
        "app.routes.api_plus.get_optional_auth_user", lambda request: _from_header(request, fake_verify)
    )


def _from_header(request, verify):
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        return verify(header[7:])
    except Exception:
        return None


def _post(client: TestClient, token: str | None = "good", **body):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    payload = {"language": "tr", "ui_language": "en", **body}
    return client.post("/api/plus/request", json=payload, headers=headers)


def test_post_stores_on_user_doc_with_token_identity(client, token_user, fake_db) -> None:
    response = _post(client, uid="forged", email="forged@example.com")
    assert response.status_code == 200 and response.json() == {"ok": True, "duplicate": False}
    data = fake_db.collection("users").document("u1").get().to_dict()
    assert data["email"] == "acct@example.com"
    entry = data["plus_requests"]["tr"]
    assert entry["status"] == "open" and entry["ui_language"] == "en" and "note" not in entry
    assert not list(fake_db.collection("plus_requests").stream())


def test_post_is_idempotent_and_does_not_overwrite(client, token_user, fake_db) -> None:
    _post(client)
    first = fake_db.collection("users").document("u1").get().to_dict()["plus_requests"]["tr"]["requested_at"]
    again = _post(client, ui_language="ru")
    assert again.json() == {"ok": True, "duplicate": True}
    entry = fake_db.collection("users").document("u1").get().to_dict()["plus_requests"]["tr"]
    assert entry["requested_at"] == first and entry["ui_language"] == "en"


def test_post_requires_token_with_email(client, token_user, fake_db) -> None:
    assert _post(client, token=None).status_code == 401
    assert _post(client, token="bad").status_code == 401
    assert _post(client, token="noemail").status_code == 401


def test_post_rejects_non_plus_language(client, token_user) -> None:
    assert _post(client, language="fr").status_code == 400
    assert _post(client, language="zz").status_code == 400


def test_post_rate_limited(client, token_user) -> None:
    codes = [_post(client).status_code for _ in range(21)]
    assert codes[-1] == 429


def test_get_status(client, token_user) -> None:
    headers = {"Authorization": "Bearer good"}
    assert client.get("/api/plus/request?language=tr", headers=headers).json() == {"requested": False, "status": None}
    _post(client)
    assert client.get("/api/plus/request?language=tr", headers=headers).json() == {"requested": True, "status": "open"}
    assert client.get("/api/plus/request?language=tr").status_code == 401
    assert client.get("/api/plus/request?language=fr", headers=headers).status_code == 400


def test_grant_marks_request_granted_and_clears_admin_list(client, token_user, fake_db) -> None:
    from core.entitlements import set_entitlement
    from core.plus_request_service import list_open_requests

    _post(client)
    rows = list_open_requests()
    assert [(r["uid"], r["email"], r["language"]) for r in rows] == [("u1", "acct@example.com", "tr")]
    set_entitlement(uid="u1", status="active")
    assert fake_db.collection("users").document("u1").get().to_dict()["plus_requests"]["tr"]["status"] == "granted"
    assert list_open_requests() == []


def test_account_deletion_no_longer_touches_plus_collection() -> None:
    import core.account_deletion as mod

    assert not hasattr(mod, "delete_plus_requests_for_uid")


def test_plus_notice_event_is_accepted(client) -> None:
    response = client.post("/api/analytics/practice_event", json={"event": "plus_notice_shown"})
    assert response.json() == {"ok": True}
