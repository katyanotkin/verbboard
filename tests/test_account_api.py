"""
Tests for DELETE /api/account (self-serve account deletion).

Coverage:
- 401 without auth, and delete_account is never called in that case
- 200 {"ok": True} on success, with delete_account called once with the uid
- 500 with a JSON body (not an unhandled exception) if delete_account raises
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

AUTH = {"Authorization": "Bearer local-dev"}


def test_delete_account_requires_auth() -> None:
    with patch("app.routes.api_account.delete_account") as mock_delete:
        response = client.delete("/api/account")

    assert response.status_code == 401
    mock_delete.assert_not_called()


def test_delete_account_local_dev_success() -> None:
    with patch("app.routes.api_account.delete_account") as mock_delete:
        response = client.delete("/api/account", headers=AUTH)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_delete.assert_called_once_with("local-dev-user")


def test_delete_account_failure_returns_500_not_unhandled_exception() -> None:
    with patch("app.routes.api_account.delete_account", side_effect=RuntimeError("boom")):
        response = client.delete("/api/account", headers=AUTH)

    assert response.status_code == 500
    assert "detail" in response.json()
