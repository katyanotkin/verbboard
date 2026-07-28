"""Regression tests for the shared __session cookie envelope.

core/admin_auth.py generalizes the admin-only session cookie into an envelope
that can carry a "role" claim (admin) and/or a "uid" claim (a signed-in
regular user) in the same __session cookie -- Firebase Hosting's Fastly CDN
only forwards a cookie named exactly __session, so there can never be a
second cookie.

This is the single most safety-critical test file in the Plus entitlement
rollout: every write here must merge with, not clobber, whatever claims are
already present. Covers both the core/admin_auth.py helpers in isolation and
the full HTTP round trip through /admin/login, /admin/logout, and the new
/api/analytics/session[/clear] cookie writes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import Request, Response
from fastapi.testclient import TestClient

from core.admin_auth import (
    ADMIN_SESSION_COOKIE,
    ADMIN_SESSION_MAX_AGE_SECONDS,
    ADMIN_SESSION_SALT,
    _serializer,
    create_admin_session_token,
    get_session_uid,
    read_session_claims,
    update_session_claims,
    write_session_claims,
)
from core.settings import load_settings


def _token(claims: dict) -> str:
    return _serializer().dumps(claims, salt=ADMIN_SESSION_SALT)


def _decode(token: str) -> dict:
    return _serializer().loads(token, salt=ADMIN_SESSION_SALT, max_age=ADMIN_SESSION_MAX_AGE_SECONDS)


def _build_request(cookie_value: str | None) -> Request:
    headers = []
    if cookie_value is not None:
        headers.append((b"cookie", f"{ADMIN_SESSION_COOKIE}={cookie_value}".encode()))
    return Request({"type": "http", "headers": headers})


def _correct_password() -> str:
    return load_settings().admin_secret


class _MockUser:
    def __init__(self, uid: str) -> None:
        self.uid = uid
        self.email = f"{uid}@example.com"


# ---------------------------------------------------------------------------
# Unit-level: read_session_claims / write_session_claims / update_session_claims
# ---------------------------------------------------------------------------


def test_read_session_claims_missing_cookie_is_empty() -> None:
    assert read_session_claims(_build_request(None)) == {}


def test_read_session_claims_tampered_cookie_is_empty_not_error() -> None:
    # Garbage input must be treated as "no claims", never raise.
    assert read_session_claims(_build_request("not-a-valid-token")) == {}


def test_read_session_claims_valid_cookie_decodes() -> None:
    token = _token({"role": "admin", "uid": "u1"})
    assert read_session_claims(_build_request(token)) == {"role": "admin", "uid": "u1"}


def test_get_session_uid_none_when_no_uid_claim() -> None:
    token = _token({"role": "admin"})
    assert get_session_uid(_build_request(token)) is None


def test_get_session_uid_none_on_missing_cookie() -> None:
    assert get_session_uid(_build_request(None)) is None


def test_get_session_uid_returns_uid_claim() -> None:
    token = _token({"uid": "u1"})
    assert get_session_uid(_build_request(token)) == "u1"


def test_write_session_claims_empty_deletes_cookie() -> None:
    response = Response()
    write_session_claims(response, {})
    set_cookie_headers = [h.lower() for h in response.headers.getlist("set-cookie")]
    assert any(f"{ADMIN_SESSION_COOKIE.lower()}=" in h and "max-age=0" in h for h in set_cookie_headers)


def test_write_session_claims_nonempty_sets_httponly_secure_cookie() -> None:
    response = Response()
    write_session_claims(response, {"role": "admin"})
    set_cookie_headers = [h.lower() for h in response.headers.getlist("set-cookie")]
    assert len(set_cookie_headers) == 1
    header = set_cookie_headers[0]
    # Preserve every attribute the original admin-only cookie used -- these
    # are what make the cookie tamper-resistant and inaccessible to XSS.
    assert "httponly" in header
    assert "secure" in header
    assert "samesite=lax" in header
    assert "path=/" in header


def test_update_session_claims_write_preserves_existing_role() -> None:
    request = _build_request(_token({"role": "admin"}))
    response = Response()
    claims = update_session_claims(request, response, uid="u1")
    assert claims == {"role": "admin", "uid": "u1"}
    assert _decode(response.headers.getlist("set-cookie")[0].split(";")[0].split("=", 1)[1]) == claims


def test_update_session_claims_none_value_removes_only_that_key() -> None:
    request = _build_request(_token({"role": "admin", "uid": "u1"}))
    response = Response()
    claims = update_session_claims(request, response, uid=None)
    assert claims == {"role": "admin"}


def test_update_session_claims_removing_last_key_deletes_cookie() -> None:
    request = _build_request(_token({"uid": "u1"}))
    response = Response()
    claims = update_session_claims(request, response, uid=None)
    assert claims == {}
    set_cookie_headers = [h.lower() for h in response.headers.getlist("set-cookie")]
    assert any("max-age=0" in h for h in set_cookie_headers)


# ---------------------------------------------------------------------------
# End-to-end: /admin/login and /admin/logout
# ---------------------------------------------------------------------------


def test_admin_login_sets_role_claim_when_no_prior_cookie(client: TestClient) -> None:
    resp = client.post("/admin/login", data={"password": _correct_password()}, follow_redirects=False)
    assert resp.status_code == 200
    token = resp.cookies.get(ADMIN_SESSION_COOKIE)
    assert token is not None
    assert _decode(token) == {"role": "admin"}


def test_admin_login_preserves_existing_uid_claim(client: TestClient) -> None:
    """The site owner signed in as a regular user first, then logs into
    /admin -- the uid claim already on the browser's cookie must survive."""
    prior_token = _token({"uid": "user-existing"})
    resp = client.post(
        "/admin/login",
        data={"password": _correct_password()},
        cookies={ADMIN_SESSION_COOKIE: prior_token},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    new_token = resp.cookies.get(ADMIN_SESSION_COOKIE)
    assert new_token is not None
    assert _decode(new_token) == {"uid": "user-existing", "role": "admin"}


def test_admin_login_wrong_password_does_not_touch_cookie(client: TestClient) -> None:
    prior_token = _token({"uid": "user-existing"})
    resp = client.post(
        "/admin/login",
        data={"password": "wrong-password"},
        cookies={ADMIN_SESSION_COOKIE: prior_token},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303, 307, 308)
    assert ADMIN_SESSION_COOKIE not in resp.cookies


def test_admin_logout_removes_only_role_claim_leaves_uid_intact(client: TestClient) -> None:
    prior_token = _token({"role": "admin", "uid": "user-existing"})
    resp = client.post(
        "/admin/logout",
        cookies={ADMIN_SESSION_COOKIE: prior_token},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    new_token = resp.cookies.get(ADMIN_SESSION_COOKIE)
    assert new_token is not None
    assert _decode(new_token) == {"uid": "user-existing"}


def test_admin_logout_with_no_other_claims_deletes_cookie(client: TestClient) -> None:
    prior_token = create_admin_session_token()
    resp = client.post(
        "/admin/logout",
        cookies={ADMIN_SESSION_COOKIE: prior_token},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert ADMIN_SESSION_COOKIE.lower() in set_cookie
    assert "max-age=0" in set_cookie


def test_admin_page_accessible_with_combined_role_and_uid_cookie(client: TestClient) -> None:
    token = _token({"role": "admin", "uid": "user-1"})
    resp = client.get("/admin", cookies={ADMIN_SESSION_COOKIE: token})
    assert resp.status_code == 200


def test_admin_page_redirects_with_uid_only_cookie_no_role(client: TestClient) -> None:
    token = _token({"uid": "user-1"})
    resp = client.get("/admin", cookies={ADMIN_SESSION_COOKIE: token}, follow_redirects=False)
    assert resp.status_code in (302, 303, 307, 308)
    assert "/admin/login" in resp.headers.get("location", "")


# ---------------------------------------------------------------------------
# End-to-end: /api/analytics/session (uid write) and /session/clear
# ---------------------------------------------------------------------------


def test_user_session_write_preserves_existing_admin_role_claim(client: TestClient) -> None:
    admin_token = create_admin_session_token()
    with (
        patch("app.routes.api_analytics.get_optional_auth_user", return_value=_MockUser("user-1")),
        patch("app.routes.api_analytics.attach_uid", new_callable=AsyncMock),
    ):
        resp = client.post(
            "/api/analytics/session",
            cookies={ADMIN_SESSION_COOKIE: admin_token},
        )
    assert resp.status_code == 200
    new_token = resp.cookies.get(ADMIN_SESSION_COOKIE)
    assert new_token is not None
    assert _decode(new_token) == {"role": "admin", "uid": "user-1"}


def test_user_session_write_with_no_prior_cookie_sets_uid_only(client: TestClient) -> None:
    with (
        patch("app.routes.api_analytics.get_optional_auth_user", return_value=_MockUser("user-1")),
        patch("app.routes.api_analytics.attach_uid", new_callable=AsyncMock),
    ):
        resp = client.post("/api/analytics/session")
    assert resp.status_code == 200
    new_token = resp.cookies.get(ADMIN_SESSION_COOKIE)
    assert new_token is not None
    assert _decode(new_token) == {"uid": "user-1"}


def test_user_session_write_rejected_unauthenticated_does_not_set_cookie(client: TestClient) -> None:
    resp = client.post("/api/analytics/session")
    assert resp.status_code == 401
    assert ADMIN_SESSION_COOKIE not in resp.cookies


def test_user_sign_out_clear_removes_only_uid_claim_leaves_role_intact(client: TestClient) -> None:
    prior_token = _token({"role": "admin", "uid": "user-1"})
    resp = client.post(
        "/api/analytics/session/clear",
        cookies={ADMIN_SESSION_COOKIE: prior_token},
    )
    assert resp.status_code == 200
    new_token = resp.cookies.get(ADMIN_SESSION_COOKIE)
    assert new_token is not None
    assert _decode(new_token) == {"role": "admin"}


def test_user_sign_out_clear_with_no_role_deletes_cookie(client: TestClient) -> None:
    prior_token = _token({"uid": "user-1"})
    resp = client.post(
        "/api/analytics/session/clear",
        cookies={ADMIN_SESSION_COOKIE: prior_token},
    )
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert ADMIN_SESSION_COOKIE.lower() in set_cookie
    assert "max-age=0" in set_cookie


def test_user_sign_out_clear_with_no_cookie_at_all_is_a_noop_200(client: TestClient) -> None:
    resp = client.post("/api/analytics/session/clear")
    assert resp.status_code == 200
