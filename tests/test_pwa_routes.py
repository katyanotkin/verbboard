"""
Tests for PWA-related server endpoints added in the mobile/app-shell branch.

Coverage:
- GET /auth/signin: status, content-type, HTML structure, Firebase config injection
- GET /.well-known/assetlinks.json: status, content-type, JSON shape
- POST /api/analytics/session: auth required, sid cookie required, happy path
- Bottom-nav inclusion: each page template includes the bottom-nav fragment
- PWA meta tags: manifest link, theme-color, viewport-fit=cover present on all pages
- Session tracker pure-Python helpers: ensure_sid, get_seen_pages, set_seen_cookie
- tracked_page helper in daily_counters
- manifest.json scope field (W8)
- Bottom-nav bnav_lang URL encoding (W6)
- Bottom-nav login button aria-label initial state and JS update (W7)
- Practice tab href and verbs_page.js hashchange handler (W2)
"""

from __future__ import annotations

import dataclasses
import re as _re
from http.cookies import SimpleCookie
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from core.analytics.daily_counters import tracked_page
from core.analytics.session_tracker import (
    ensure_sid,
    get_seen_pages,
    set_seen_cookie,
)
from core.settings import load_settings as _real_load_settings

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _settings_with_firebase(cfg: str = '{"apiKey":"test-key"}'):
    return dataclasses.replace(_real_load_settings(), firebase_web_config_json=cfg)


def _settings_no_firebase():
    return dataclasses.replace(_real_load_settings(), firebase_web_config_json="")


def _build_request(cookies: dict[str, str] | None = None) -> Request:
    """Build a minimal Starlette Request with optional cookies."""
    cookie_header = "; ".join(f"{k}={v}" for k, v in (cookies or {}).items())
    headers_list = []
    if cookie_header:
        headers_list.append((b"cookie", cookie_header.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": headers_list,
    }
    return Request(scope)


def _parse_set_cookie_value(response: Response, name: str) -> str:
    """Extract the decoded value of a named cookie from a Starlette Response."""
    raw = response.headers.get("set-cookie", "")
    sc = SimpleCookie()
    sc.load(raw)
    return sc[name].value if name in sc else ""


# ---------------------------------------------------------------------------
# GET /auth/signin
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# GET /.well-known/assetlinks.json
# ---------------------------------------------------------------------------


def test_assetlinks_returns_200(client: TestClient) -> None:
    resp = client.get("/.well-known/assetlinks.json")
    assert resp.status_code == 200


def test_assetlinks_content_type_is_json(client: TestClient) -> None:
    resp = client.get("/.well-known/assetlinks.json")
    assert "application/json" in resp.headers["content-type"]


def test_assetlinks_is_a_list(client: TestClient) -> None:
    data = client.get("/.well-known/assetlinks.json").json()
    assert isinstance(data, list)
    assert len(data) == 1


def test_assetlinks_has_required_relation(client: TestClient) -> None:
    data = client.get("/.well-known/assetlinks.json").json()
    entry = data[0]
    assert "relation" in entry
    assert "delegate_permission/common.handle_all_urls" in entry["relation"]


def test_assetlinks_target_has_namespace_and_package(client: TestClient) -> None:
    data = client.get("/.well-known/assetlinks.json").json()
    target = data[0]["target"]
    assert target["namespace"] == "android_app"
    assert target["package_name"] == "com.verbboard.app"


def test_assetlinks_target_has_fingerprints_list(client: TestClient) -> None:
    data = client.get("/.well-known/assetlinks.json").json()
    fps = data[0]["target"]["sha256_cert_fingerprints"]
    assert isinstance(fps, list)
    assert len(fps) >= 1


# ---------------------------------------------------------------------------
# POST /api/analytics/session
# ---------------------------------------------------------------------------


def test_analytics_session_rejects_unauthenticated(client: TestClient) -> None:
    resp = client.post("/api/analytics/session")
    assert resp.status_code == 401


def test_analytics_session_rejects_missing_sid_cookie(client: TestClient) -> None:
    """Auth passes but no vb_sid cookie -> 400."""
    with patch(
        "app.routes.api_analytics.get_optional_auth_user",
        return_value=_MockUser("uid-abc"),
    ):
        resp = client.post("/api/analytics/session")
    assert resp.status_code == 400


def test_analytics_session_returns_ok_with_valid_inputs(client: TestClient) -> None:
    with (
        patch(
            "app.routes.api_analytics.get_optional_auth_user",
            return_value=_MockUser("uid-abc"),
        ),
        patch(
            "app.routes.api_analytics.attach_uid",
            new_callable=AsyncMock,
        ) as mock_attach,
    ):
        resp = client.post(
            "/api/analytics/session",
            cookies={"vb_sid": "test-session-id"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_attach.assert_awaited_once()
    call_args = mock_attach.call_args
    assert call_args.args[0] == "test-session-id"
    assert call_args.args[2] == "uid-abc"


class _MockUser:
    def __init__(self, uid: str) -> None:
        self.uid = uid
        self.email = f"{uid}@example.com"


# ---------------------------------------------------------------------------
# Bottom nav present in all major page templates
# ---------------------------------------------------------------------------


def test_home_includes_bottom_nav(client: TestClient) -> None:
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert "bottom-nav" in html
    assert "bnav-tab" in html


def test_verbs_includes_bottom_nav(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        html = client.get("/verbs?language=en").text
    assert "bottom-nav" in html
    assert "bnav-tab" in html


def test_about_includes_bottom_nav(client: TestClient) -> None:
    html = client.get("/about").text
    assert "bottom-nav" in html
    assert "bnav-tab" in html


# ---------------------------------------------------------------------------
# Bottom nav active state: correct tab is highlighted per page
# ---------------------------------------------------------------------------


def test_home_bottom_nav_search_tab_active(client: TestClient) -> None:
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    # The Search tab must carry the active class; Browse must not precede it
    assert "bnav-tab--active" in html
    browse_idx = html.index(">List<")
    active_idx = html.index("bnav-tab--active")
    # Active marker appears before the Browse label in the Search tab block
    assert active_idx < browse_idx


def test_verbs_bottom_nav_browse_tab_active(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        html = client.get("/verbs?language=en").text
    # The Browse tab should be active; find it and confirm the class
    browse_idx = html.index(">List<")
    # Find the bnav-tab--active that precedes the Browse label
    nav_fragment = html[:browse_idx]
    assert "bnav-tab--active" in nav_fragment


# ---------------------------------------------------------------------------
# Bottom nav carries language to tab links
# ---------------------------------------------------------------------------


def test_home_bottom_nav_search_link_carries_language(client: TestClient) -> None:
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=ru&ui_language=ru").text
    # Search tab must carry both learning language and UI language (ui_language
    # propagated as URL param because Firebase Hosting strips all cookies).
    assert "/?language=ru&amp;ui_language=ru" in html


def test_verbs_bottom_nav_browse_link_carries_language(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        html = client.get("/verbs?language=he&ui_language=en").text
    assert "/verbs?language=he&amp;ui_language=en" in html


# ---------------------------------------------------------------------------
# Bottom nav profile button wires tapProfile
# ---------------------------------------------------------------------------


def test_bottom_nav_profile_button_calls_tap_profile(client: TestClient) -> None:
    """Profile tab must call VerbBoardAuth.tapProfile() directly (not .click())."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert "tapProfile()" in html


def test_bottom_nav_has_practice_tab(client: TestClient) -> None:
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert ">Practice<" in html


def test_bottom_nav_home_has_no_back_tab(client: TestClient) -> None:
    """Home page has no meaningful back destination -- Back tab must be absent."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert ">Back<" not in html


def test_bottom_nav_verbs_has_back_tab(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        html = client.get("/verbs?language=en").text
    assert ">Back<" in html


def test_bottom_nav_verbs_back_links_to_home(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        html = client.get("/verbs?language=ru&ui_language=en").text
    assert 'href="/?language=ru&amp;ui_language=en"' in html


def test_bottom_nav_about_has_back_tab(client: TestClient) -> None:
    html = client.get("/about").text
    assert ">Back<" in html


def test_bottom_nav_login_label_present(client: TestClient) -> None:
    """bnav-login-label span must be present for auth.js to update dynamically."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert 'id="bnav-login-label"' in html


# ---------------------------------------------------------------------------
# PWA meta tags present in all page templates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,patches",
    [
        ("/?language=en", {"app.routes.home.list_verbs_recent": []}),
        ("/verbs?language=en", {"app.routes.verbs.load_entries_for_language": []}),
        ("/about", {}),
    ],
)
def test_page_has_pwa_manifest_link(
    client: TestClient, url: str, patches: dict
) -> None:
    ctx_patches = [patch(target, return_value=val) for target, val in patches.items()]
    with _multi_patch(ctx_patches):
        html = client.get(url).text
    assert 'href="/static/manifest.json"' in html


@pytest.mark.parametrize(
    "url,patches",
    [
        ("/?language=en", {"app.routes.home.list_verbs_recent": []}),
        ("/verbs?language=en", {"app.routes.verbs.load_entries_for_language": []}),
        ("/about", {}),
    ],
)
def test_page_has_theme_color_meta(client: TestClient, url: str, patches: dict) -> None:
    ctx_patches = [patch(target, return_value=val) for target, val in patches.items()]
    with _multi_patch(ctx_patches):
        html = client.get(url).text
    assert 'name="theme-color"' in html
    assert "#2d6a4f" in html


@pytest.mark.parametrize(
    "url,patches",
    [
        ("/?language=en", {"app.routes.home.list_verbs_recent": []}),
        ("/verbs?language=en", {"app.routes.verbs.load_entries_for_language": []}),
        ("/about", {}),
    ],
)
def test_page_has_viewport_fit_cover(
    client: TestClient, url: str, patches: dict
) -> None:
    ctx_patches = [patch(target, return_value=val) for target, val in patches.items()]
    with _multi_patch(ctx_patches):
        html = client.get(url).text
    assert "viewport-fit=cover" in html


@pytest.mark.parametrize(
    "url,patches",
    [
        ("/?language=en", {"app.routes.home.list_verbs_recent": []}),
        ("/verbs?language=en", {"app.routes.verbs.load_entries_for_language": []}),
        ("/about", {}),
    ],
)
def test_page_loads_pwa_js(client: TestClient, url: str, patches: dict) -> None:
    ctx_patches = [patch(target, return_value=val) for target, val in patches.items()]
    with _multi_patch(ctx_patches):
        html = client.get(url).text
    assert "/static/pwa.js" in html


def _multi_patch(patches):
    """Context manager that applies a list of patch objects."""
    import contextlib

    @contextlib.contextmanager
    def _cm():
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            yield

    return _cm()


# ---------------------------------------------------------------------------
# session_tracker pure-Python helpers (no Firestore)
# ---------------------------------------------------------------------------


def test_ensure_sid_returns_existing_cookie() -> None:
    req = _build_request(cookies={"vb_sid": "existing-sid"})
    sid, is_new = ensure_sid(req)
    assert sid == "existing-sid"
    assert is_new is False


def test_ensure_sid_generates_new_uuid_when_no_cookie() -> None:
    req = _build_request()
    sid, is_new = ensure_sid(req)
    assert is_new is True
    # Must be a valid UUID4-like string (36 chars with hyphens)
    parts = sid.split("-")
    assert len(parts) == 5


def test_ensure_sid_new_uuids_are_unique() -> None:
    req = _build_request()
    sid1, _ = ensure_sid(req)
    sid2, _ = ensure_sid(req)
    assert sid1 != sid2


def test_get_seen_pages_empty_when_no_cookie() -> None:
    req = _build_request()
    assert get_seen_pages(req, "2026-05-27") == set()


def test_get_seen_pages_empty_when_cookie_date_mismatch() -> None:
    req = _build_request(cookies={"vb_seen": "2026-01-01|home,verbs"})
    assert get_seen_pages(req, "2026-05-27") == set()


def test_get_seen_pages_returns_pages_for_matching_date() -> None:
    req = _build_request(cookies={"vb_seen": "2026-05-27|home,verbs"})
    pages = get_seen_pages(req, "2026-05-27")
    assert pages == {"home", "verbs"}


def test_get_seen_pages_single_page() -> None:
    req = _build_request(cookies={"vb_seen": "2026-05-27|learn"})
    assert get_seen_pages(req, "2026-05-27") == {"learn"}


def test_set_seen_cookie_contains_date_prefix() -> None:
    response = Response()
    set_seen_cookie(response, "2026-05-27", {"verbs", "home", "learn"})
    value = _parse_set_cookie_value(response, "vb_seen")
    assert value.startswith("2026-05-27|")


def test_set_seen_cookie_writes_sorted_pages() -> None:
    response = Response()
    set_seen_cookie(response, "2026-05-27", {"verbs", "home", "learn"})
    value = _parse_set_cookie_value(response, "vb_seen")
    # Strip the date prefix and check page order
    pages_part = value.split("|", 1)[1]
    assert pages_part == "home,learn,verbs"


def test_set_seen_cookie_round_trips() -> None:
    """Value written by set_seen_cookie must be parseable by get_seen_pages."""
    response = Response()
    pages_in = {"home", "verbs"}
    set_seen_cookie(response, "2026-05-27", pages_in)
    cookie_value = _parse_set_cookie_value(response, "vb_seen")

    req = _build_request(cookies={"vb_seen": cookie_value})
    pages_out = get_seen_pages(req, "2026-05-27")
    assert pages_out == pages_in


# ---------------------------------------------------------------------------
# tracked_page helper in daily_counters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/", "home"),
        ("/verbs", "verbs"),
        ("/learn", "learn"),
        ("/feedback", "feedback"),
    ],
)
def test_tracked_page_known_paths(path: str, expected: str) -> None:
    assert tracked_page(path) == expected


@pytest.mark.parametrize(
    "path",
    [
        "/auth/signin",
        "/.well-known/assetlinks.json",
        "/static/sw.js",
        "/health",
        "/api/analytics/session",
        "/about",
        "/audio/en/en_go/female/base.mp3",
        "",
        "/unknown",
    ],
)
def test_tracked_page_untracked_paths_return_none(path: str) -> None:
    assert tracked_page(path) is None


# ---------------------------------------------------------------------------
# isMobile() UA regex — regression guard
#
# The regex /Mobi|Android|iPhone|iPad|Opera Mini/i in auth.js determines
# whether to use the new-tab sign-in flow (mobile + standalone) or
# signInWithPopup (desktop). Getting this wrong causes auth to silently fail:
#   - false positive (desktop UA matched): new-tab flow on desktop is fine but
#     unnecessary; popup is preferred for desktop UX.
#   - false negative (mobile UA not matched): signInWithPopup on mobile →
#     popup becomes a tab, loses window.opener, auth never completes.
#
# These tests extract the pattern from auth.js and validate it against a
# known set of real-world UAs so any future edit to isMobile() is caught.
# ---------------------------------------------------------------------------


def _is_mobile_pattern() -> str:
    """Extract the isMobile() regex from auth.js."""
    auth_js = __import__("pathlib").Path("app/static/auth.js").read_text()
    # Match: /Mobi|Android|.../i  (the literal regex in the source)
    m = _re.search(r"/([^/]+)/i\.test\(navigator\.userAgent\)", auth_js)
    assert m, "isMobile() regex not found in auth.js"
    return m.group(1)


@pytest.fixture(scope="module")
def is_mobile_re() -> _re.Pattern:
    return _re.compile(_is_mobile_pattern(), _re.IGNORECASE)


# UAs that MUST be classified as mobile (use new-tab sign-in)
_MOBILE_UAS = [
    # Android Chrome (phone)
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.135 Mobile Safari/537.36",
    # Opera for Android
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.135 Mobile Safari/537.36 OPR/78.0.4093.184",
    # Opera Mini
    "Opera/9.80 (Android; Opera Mini/8.0.1807/36.1609; U; en) Presto/2.12.407 Version/12.50",
    # iPhone Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    # iPad (has 'iPad' but not 'Mobi')
    "Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    # Android tablet without 'Mobile' keyword — matched by 'Android'
    "Mozilla/5.0 (Linux; Android 12; SM-T870) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36",
]

# UAs that MUST NOT be classified as mobile (use signInWithPopup)
_DESKTOP_UAS = [
    # Windows Chrome (no touch)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    # macOS Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    # Windows Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/112.0",
    # Linux Chrome
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    # Windows touchscreen laptop (Surface) — MUST stay desktop despite touch hardware
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


# ---------------------------------------------------------------------------
# W8: manifest.json scope field
# ---------------------------------------------------------------------------


def test_manifest_has_scope_root() -> None:
    """manifest.json must declare scope '/' so the SW controls the whole origin."""
    import json
    import pathlib

    manifest = json.loads(pathlib.Path("app/static/manifest.json").read_text())
    assert manifest.get("scope") == "/"


# ---------------------------------------------------------------------------
# W6: bnav_lang is URL-encoded in bottom-nav hrefs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,lang,patch_target",
    [
        ("/?language=en", "en", "app.routes.home.list_verbs_recent"),
        ("/?language=ru", "ru", "app.routes.home.list_verbs_recent"),
        ("/?language=he", "he", "app.routes.home.list_verbs_recent"),
        ("/verbs?language=en", "en", "app.routes.verbs.load_entries_for_language"),
        ("/verbs?language=ru", "ru", "app.routes.verbs.load_entries_for_language"),
    ],
)
def test_bottom_nav_lang_hrefs_contain_language(
    client: TestClient, url: str, lang: str, patch_target: str
) -> None:
    """Bottom-nav Search and Browse links must carry language and ui_language.

    ui_language is propagated as a URL param (not cookie) because Firebase
    Hosting strips all cookies except __session before forwarding to Cloud Run.
    Requests without ui_language default to 'en'. Jinja2 autoescape renders
    the & separator as &amp; inside href attributes.
    """
    with patch(patch_target, return_value=[]):
        html = client.get(url).text
    assert f'href="/?language={lang}&amp;ui_language=en"' in html
    assert f'href="/verbs?language={lang}&amp;ui_language=en"' in html


# ---------------------------------------------------------------------------
# W7: bottom-nav login button aria-label
# ---------------------------------------------------------------------------


def test_bottom_nav_login_button_initial_aria_label(client: TestClient) -> None:
    """Profile button must start with aria-label='Login' before auth.js runs."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert 'aria-label="Login"' in html


def test_auth_js_updates_bnav_aria_label() -> None:
    """auth.js must call setAttribute('aria-label', ...) on the profile button."""
    import pathlib

    auth_js = pathlib.Path("app/static/auth.js").read_text()
    assert "setAttribute('aria-label'" in auth_js


# ---------------------------------------------------------------------------
# W2: Practice tab href and hashchange handler in verbs_page.js
# ---------------------------------------------------------------------------


def test_verbs_bottom_nav_practice_tab_href(client: TestClient) -> None:
    """Practice tab must link to the practice panel anchor on the verbs page."""
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        html = client.get("/verbs?language=en").text
    assert "/verbs?language=en" in html
    assert "#practice-panel" in html


@pytest.mark.parametrize("lang", ["en", "ru", "he"])
def test_verbs_bottom_nav_practice_tab_carries_language(
    client: TestClient, lang: str
) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        html = client.get(f"/verbs?language={lang}").text
    assert f"/verbs?language={lang}" in html
    assert "#practice-panel" in html


def test_verbs_page_js_has_hashchange_handler() -> None:
    """verbs_page.js must register a hashchange listener to sync Practice tab state."""
    import pathlib

    js = pathlib.Path("app/static/verbs_page.js").read_text()
    assert "hashchange" in js
    assert "bnav-tab--active" in js
