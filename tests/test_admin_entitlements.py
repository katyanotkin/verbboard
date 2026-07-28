"""Tests for the /admin/entitlements manual grant/revoke page."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from core.admin_auth import ADMIN_SESSION_COOKIE, create_admin_session_token


def _admin_cookies() -> dict[str, str]:
    return {ADMIN_SESSION_COOKIE: create_admin_session_token()}


def test_entitlements_page_requires_admin(client: TestClient) -> None:
    resp = client.get("/admin/entitlements", follow_redirects=False)
    assert resp.status_code in (302, 303, 307, 308)
    assert "/admin/login" in resp.headers.get("location", "")


def test_entitlements_page_renders_with_admin_cookie(client: TestClient) -> None:
    resp = client.get("/admin/entitlements", cookies=_admin_cookies())
    assert resp.status_code == 200
    assert "Plus entitlements" in resp.text


def test_entitlements_lookup_by_uid_shows_no_record(client: TestClient) -> None:
    with patch("app.routes.admin_entitlements.get_entitlement", return_value=None):
        resp = client.get("/admin/entitlements?q=some-uid", cookies=_admin_cookies())
    assert resp.status_code == 200
    assert "No entitlement record yet" in resp.text


def test_entitlements_lookup_by_email_not_found_shows_error(client: TestClient) -> None:
    with patch("app.routes.admin_entitlements.lookup_uid_by_email", return_value=None):
        resp = client.get("/admin/entitlements?q=nobody@example.com", cookies=_admin_cookies())
    assert resp.status_code == 200
    assert "No Firebase Auth account found" in resp.text


def test_entitlements_lookup_by_email_resolves_uid(client: TestClient) -> None:
    with (
        patch("app.routes.admin_entitlements.lookup_uid_by_email", return_value="uid-123"),
        patch(
            "app.routes.admin_entitlements.get_entitlement",
            return_value={"status": "active", "plan": "plus", "source": "manual_admin"},
        ),
    ):
        resp = client.get("/admin/entitlements?q=someone@example.com", cookies=_admin_cookies())
    assert resp.status_code == 200
    assert "uid-123" in resp.text
    assert "active" in resp.text


def test_entitlements_post_grants_active_status(client: TestClient) -> None:
    with patch("app.routes.admin_entitlements.set_entitlement") as mock_set:
        resp = client.post(
            "/admin/entitlements",
            data={"identifier": "uid-123", "status": "active", "note": "manual comp"},
            cookies=_admin_cookies(),
            follow_redirects=False,
        )
    assert resp.status_code == 303
    mock_set.assert_called_once_with(uid="uid-123", status="active", note="manual comp")


def test_entitlements_post_rejects_unknown_status(client: TestClient) -> None:
    with (
        patch("app.routes.admin_entitlements.set_entitlement") as mock_set,
        patch("app.routes.admin_entitlements.get_entitlement", return_value=None),
    ):
        resp = client.post(
            "/admin/entitlements",
            data={"identifier": "uid-123", "status": "bogus", "note": ""},
            cookies=_admin_cookies(),
        )
    assert resp.status_code == 200
    assert "Unsupported status" in resp.text
    mock_set.assert_not_called()


def test_entitlements_post_requires_admin(client: TestClient) -> None:
    resp = client.post(
        "/admin/entitlements",
        data={"identifier": "uid-123", "status": "active", "note": ""},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303, 307, 308)
    assert "/admin/login" in resp.headers.get("location", "")


def test_entitlements_post_email_not_found_does_not_call_set(client: TestClient) -> None:
    with (
        patch("app.routes.admin_entitlements.lookup_uid_by_email", return_value=None),
        patch("app.routes.admin_entitlements.set_entitlement") as mock_set,
    ):
        resp = client.post(
            "/admin/entitlements",
            data={"identifier": "nobody@example.com", "status": "active", "note": ""},
            cookies=_admin_cookies(),
        )
    assert resp.status_code == 200
    assert "No Firebase Auth account found" in resp.text
    mock_set.assert_not_called()
