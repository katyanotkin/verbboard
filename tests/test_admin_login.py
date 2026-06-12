"""Tests for the admin login flow (/admin/login).

Covers:
- GET /admin/login renders the form (200)
- GET /admin/login?error=1 shows the error box
- POST /admin/login with wrong password redirects to login?error=1
- POST /admin/login with correct password (from settings) returns 200 and sets cookie
- GET /admin without session cookie redirects to /admin/login
- GET /admin with a valid session cookie returns 200
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from core.admin_auth import ADMIN_SESSION_COOKIE, create_admin_session_token
from core.settings import load_settings


def _correct_password() -> str:
    return load_settings().admin_secret


# ── GET /admin/login ──────────────────────────────────────────────────────────


def test_admin_login_page_returns_200(client: TestClient) -> None:
    assert client.get("/admin/login").status_code == 200


def test_admin_login_page_has_form(client: TestClient) -> None:
    html = client.get("/admin/login").text
    assert "<form" in html
    assert 'name="password"' in html


def test_admin_login_page_no_error_box_by_default(client: TestClient) -> None:
    html = client.get("/admin/login").text
    assert "error-box" not in html


def test_admin_login_page_shows_error_box_on_error_param(client: TestClient) -> None:
    html = client.get("/admin/login?error=1").text
    assert "error-box" in html


# ── POST /admin/login ─────────────────────────────────────────────────────────


def test_admin_login_wrong_password_redirects_to_login(client: TestClient) -> None:
    resp = client.post(
        "/admin/login",
        data={"password": "wrong-password"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303, 307, 308)
    assert "error=1" in resp.headers.get("location", "")


def test_admin_login_correct_password_returns_200(client: TestClient) -> None:
    resp = client.post(
        "/admin/login",
        data={"password": _correct_password()},
        follow_redirects=False,
    )
    assert resp.status_code == 200


def test_admin_login_correct_password_sets_session_cookie(client: TestClient) -> None:
    resp = client.post(
        "/admin/login",
        data={"password": _correct_password()},
        follow_redirects=False,
    )
    assert (
        ADMIN_SESSION_COOKIE in resp.cookies
    ), f"Expected '{ADMIN_SESSION_COOKIE}' cookie in response. Cookies present: {list(resp.cookies.keys())}"


def test_admin_login_correct_password_redirects_to_callback(
    client: TestClient,
) -> None:
    resp = client.post(
        "/admin/login",
        data={"password": _correct_password()},
        follow_redirects=False,
    )
    assert "login-callback" in resp.text


# ── Admin page auth guard ─────────────────────────────────────────────────────


def test_admin_page_without_cookie_redirects_to_login(client: TestClient) -> None:
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code in (302, 303, 307, 308)
    location = resp.headers.get("location", "")
    assert "/admin/login" in location


def test_admin_page_with_valid_cookie_returns_200(client: TestClient) -> None:
    token = create_admin_session_token()
    resp = client.get("/admin", cookies={ADMIN_SESSION_COOKIE: token})
    assert resp.status_code == 200
