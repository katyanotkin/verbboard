"""Tests for the /auth/signin page and the isMobile() auth-flow selector.

/auth/signin is the standalone sign-in page used by PWA (standalone mode) and
mobile browsers. It injects FIREBASE_WEB_CONFIG_JSON and renders null when the
config is absent.

isMobile() in auth.js determines which Firebase sign-in flow to use:
  - mobile / standalone PWA: window.open('/auth/signin', '_blank') (new-tab)
  - desktop: signInWithPopup
Getting the regex wrong causes silent auth failure on mobile (popup loses
window.opener) or an unnecessary new-tab on desktop.
"""

from __future__ import annotations

import dataclasses
import re as _re
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core.settings import load_settings as _real_load_settings


def _settings_with_firebase(cfg: str = '{"apiKey":"test-key"}'):
    return dataclasses.replace(_real_load_settings(), firebase_web_config_json=cfg)


def _settings_no_firebase():
    return dataclasses.replace(_real_load_settings(), firebase_web_config_json="")


# ── /auth/signin page ─────────────────────────────────────────────────────────


def test_auth_signin_returns_200(client: TestClient) -> None:
    resp = client.get("/auth/signin")
    assert resp.status_code == 200


def test_auth_signin_content_type_is_html(client: TestClient) -> None:
    resp = client.get("/auth/signin")
    assert "text/html" in resp.headers["content-type"]


def test_auth_signin_has_signin_button(client: TestClient) -> None:
    html = client.get("/auth/signin").text
    assert 'id="signin-btn"' in html


def test_auth_signin_has_status_element(client: TestClient) -> None:
    html = client.get("/auth/signin").text
    assert 'id="status"' in html


def test_auth_signin_injects_firebase_config_when_present(client: TestClient) -> None:
    with patch(
        "app.routes.auth_pages.load_settings",
        side_effect=_settings_with_firebase,
    ):
        html = client.get("/auth/signin").text
    assert "window.FIREBASE_WEB_CONFIG" in html
    assert '"apiKey"' in html


def test_auth_signin_renders_null_when_no_firebase_config(client: TestClient) -> None:
    """An empty firebase_web_config_json must produce null, not a bare empty string."""
    with patch(
        "app.routes.auth_pages.load_settings",
        side_effect=_settings_no_firebase,
    ):
        html = client.get("/auth/signin").text
    assert "window.FIREBASE_WEB_CONFIG = null;" in html
    assert "window.FIREBASE_WEB_CONFIG = ;" not in html


def test_auth_signin_has_doctype(client: TestClient) -> None:
    html = client.get("/auth/signin").text
    assert html.lstrip().lower().startswith("<!doctype html>")


def test_auth_signin_has_viewport_meta(client: TestClient) -> None:
    html = client.get("/auth/signin").text
    assert "viewport" in html


# ── isMobile() UA regex in auth.js ───────────────────────────────────────────


def _is_mobile_pattern() -> str:
    """Extract the isMobile() regex literal from auth.js."""
    auth_js = __import__("pathlib").Path("app/static/auth.js").read_text()
    m = _re.search(r"/([^/]+)/i\.test\(navigator\.userAgent\)", auth_js)
    assert m, "isMobile() regex not found in auth.js"
    return m.group(1)


@pytest.fixture(scope="module")
def is_mobile_re() -> _re.Pattern:
    return _re.compile(_is_mobile_pattern(), _re.IGNORECASE)


# UAs that MUST be classified as mobile (use new-tab sign-in)
_MOBILE_UAS = [
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.135 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.135 Mobile Safari/537.36 OPR/78.0.4093.184",
    "Opera/9.80 (Android; Opera Mini/8.0.1807/36.1609; U; en) Presto/2.12.407 Version/12.50",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 12; SM-T870) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36",
]

# UAs that MUST NOT be classified as mobile (use signInWithPopup)
_DESKTOP_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/112.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.48",
]


@pytest.mark.parametrize("ua", _MOBILE_UAS)
def test_is_mobile_matches_mobile_ua(is_mobile_re: _re.Pattern, ua: str) -> None:
    assert is_mobile_re.search(ua), f"Expected mobile UA to match: {ua}"


@pytest.mark.parametrize("ua", _DESKTOP_UAS)
def test_is_mobile_does_not_match_desktop_ua(
    is_mobile_re: _re.Pattern, ua: str
) -> None:
    assert not is_mobile_re.search(ua), f"Expected desktop UA NOT to match: {ua}"
