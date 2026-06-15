"""
Tests for safe_return_to() (W3) and the /privacy and /auth/signin pages.

Coverage:
- core.safe_return.safe_return_to: valid paths, injection attempts, URL-encoded input
- GET /privacy: status, content-type, required sections
- GET /auth/signin: Jinja2 template rendering (S2), postMessage code present (W5)
- return_to injection: feedback and auth/signin reject external URLs
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.safe_return import safe_return_to

# ---------------------------------------------------------------------------
# safe_return_to unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("/", "/"),
        ("/verbs?language=en", "/verbs?language=en"),
        ("/learn?language=ru&verb_id=ru_idti", "/learn?language=ru&verb_id=ru_idti"),
        ("/verbs?language=en#practice-panel", "/verbs?language=en#practice-panel"),
    ],
)
def test_safe_return_to_accepts_valid_paths(url: str, expected: str) -> None:
    assert safe_return_to(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.com/path",
        "http://evil.com",
        "//evil.com/path",
        "/\\evil",
        "javascript:alert(1)",
        "",
        "   ",
    ],
)
def test_safe_return_to_rejects_unsafe_urls(url: str) -> None:
    result = safe_return_to(url, fallback="/")
    assert not result.startswith("//")
    assert not result.startswith("http")
    assert "\\" not in result
    assert result == "/"


def test_safe_return_to_decodes_url_encoded_path() -> None:
    encoded = "/verbs%3Flanguage%3Den"
    result = safe_return_to(encoded)
    assert result == "/verbs?language=en"


def test_safe_return_to_fallback_slash_by_default() -> None:
    assert safe_return_to("https://evil.com") == "/"


def test_safe_return_to_fallback_empty_string() -> None:
    assert safe_return_to("https://evil.com", fallback="") == ""


def test_safe_return_to_root_path() -> None:
    assert safe_return_to("/") == "/"


def test_safe_return_to_rejects_double_slash() -> None:
    assert safe_return_to("//evil.com", fallback="/") == "/"


def test_safe_return_to_rejects_backslash() -> None:
    assert safe_return_to("/\\windows\\path", fallback="/") == "/"


def test_safe_return_to_empty_string_uses_fallback() -> None:
    assert safe_return_to("", fallback="/home") == "/home"


# ---------------------------------------------------------------------------
# GET /privacy
# ---------------------------------------------------------------------------


def test_privacy_returns_200(client: TestClient) -> None:
    assert client.get("/privacy").status_code == 200


def test_privacy_content_type_is_html(client: TestClient) -> None:
    assert "text/html" in client.get("/privacy").headers["content-type"]


def test_privacy_has_doctype(client: TestClient) -> None:
    html = client.get("/privacy").text
    assert html.lstrip().lower().startswith("<!doctype html>")


def test_privacy_mentions_data_collected(client: TestClient) -> None:
    html = client.get("/privacy").text
    # Must describe what data is collected
    assert "email" in html.lower()


def test_privacy_has_contact_address(client: TestClient) -> None:
    html = client.get("/privacy").text
    assert "assistantderecherche@gmail.com" in html


def test_privacy_has_bottom_nav(client: TestClient) -> None:
    html = client.get("/privacy").text
    assert "bottom-nav" in html


# ---------------------------------------------------------------------------
# GET /auth/signin -- S2: Jinja2 template, W5: postMessage
# ---------------------------------------------------------------------------


def test_auth_signin_template_injects_firebase_config(client: TestClient) -> None:
    """Firebase config must appear as window.FIREBASE_WEB_CONFIG (from template)."""
    html = client.get("/auth/signin").text
    assert "window.FIREBASE_WEB_CONFIG" in html


def test_auth_signin_has_no_raw_fstring_artifacts(client: TestClient) -> None:
    """Jinja2 template must not leave unrendered {{ }} blocks in output."""
    html = client.get("/auth/signin").text
    assert "{{" not in html
    assert "}}" not in html


def test_auth_signin_postmessage_on_success(client: TestClient) -> None:
    """Signin page must send vb:signed-in postMessage to opener after auth (W5)."""
    html = client.get("/auth/signin").text
    assert "vb:signed-in" in html
    assert "postMessage" in html


def test_auth_signin_return_to_rejects_external_url(client: TestClient) -> None:
    """return_to=https://evil.com must not appear in the page JS."""
    html = client.get("/auth/signin?return_to=https://evil.com/steal").text
    assert "evil.com" not in html


def test_auth_signin_return_to_accepts_relative_path(client: TestClient) -> None:
    html = client.get("/auth/signin?return_to=/verbs%3Flanguage%3Den").text
    assert "/verbs" in html


def test_auth_signin_return_to_empty_when_unsafe(client: TestClient) -> None:
    """Unsafe return_to must result in empty string (tab-close path), not a redirect."""
    html = client.get("/auth/signin?return_to=//evil.com").text
    assert "evil.com" not in html
    # The JS variable must be an empty string (fallback="" for auth/signin)
    assert 'returnTo = ""' in html or "returnTo = ''" in html


# ---------------------------------------------------------------------------
# SW precache version bump (S3)
# ---------------------------------------------------------------------------


def test_sw_cache_version_is_v19() -> None:
    import pathlib

    sw = pathlib.Path("app/static/sw.js").read_text()
    assert '"vb-v20"' in sw


def test_sw_precache_includes_pwa_js() -> None:
    import pathlib

    sw = pathlib.Path("app/static/sw.js").read_text()
    assert "/static/pwa.js" in sw


def test_sw_precache_includes_learn_js() -> None:
    import pathlib

    sw = pathlib.Path("app/static/sw.js").read_text()
    assert "/static/learn.js" in sw


# ---------------------------------------------------------------------------
# QA-1: home.py search redirect rejects unsafe return_to (W3-x)
# ---------------------------------------------------------------------------


def test_home_search_rejects_double_slash_return_to(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", lambda *a: None)
    monkeypatch.setattr("app.routes.home.list_verbs_recent", lambda *a, **kw: [])
    monkeypatch.setattr("app.routes.home.find_best_entry", lambda *a: None)
    resp = client.get(
        "/search_verb?language=en&q=notfound&return_to=//evil.com",
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303, 307)
    assert "evil.com" not in resp.headers["location"]


def test_home_search_rejects_backslash_return_to(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", lambda *a: None)
    monkeypatch.setattr("app.routes.home.list_verbs_recent", lambda *a, **kw: [])
    monkeypatch.setattr("app.routes.home.find_best_entry", lambda *a: None)
    resp = client.get(
        "/search_verb?language=en&q=notfound&return_to=/\\evil",
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303, 307)
    assert "\\evil" not in resp.headers["location"]


def test_home_search_accepts_valid_return_to(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", lambda *a: None)
    monkeypatch.setattr("app.routes.home.list_verbs_recent", lambda *a, **kw: [])
    monkeypatch.setattr("app.routes.home.find_best_entry", lambda *a: None)
    resp = client.get(
        "/search_verb?language=en&q=notfound&return_to=/verbs%3Flanguage%3Den",
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303, 307)
    assert "/verbs" in resp.headers["location"]


# ---------------------------------------------------------------------------
# QA-3: firebase_cfg_json XSS guard -- </script> neutralized by json round-trip
# ---------------------------------------------------------------------------


def test_auth_signin_firebase_config_script_injection_neutralized(
    client: TestClient,
) -> None:
    import dataclasses
    from unittest.mock import patch

    from core.settings import load_settings as _real_load_settings

    malicious = '{"apiKey":"</script><script>alert(1)</script>"}'
    settings = dataclasses.replace(_real_load_settings(), firebase_web_config_json=malicious)
    with patch("app.routes.auth_pages.load_settings", return_value=settings):
        html = client.get("/auth/signin").text
    assert "</script><script>" not in html


# ---------------------------------------------------------------------------
# QA-4: safe_return_json is a quoted JS string literal in signin response
# ---------------------------------------------------------------------------


def test_auth_signin_return_to_is_quoted_js_string_literal(
    client: TestClient,
) -> None:
    """safe_return_json must render as a JS string with surrounding quotes."""
    html = client.get("/auth/signin?return_to=/verbs%3Flanguage%3Den").text
    assert '"/verbs?language=en"' in html
