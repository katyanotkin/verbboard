"""Tests for the bottom navigation bar (_bottom_nav.html).

The bottom nav is a 5-tab bar (Back / Search / List / Practice / Login) included
in every major page template. Labels are intentionally hardcoded English and must
not be localized.

Covers:
- Presence: bottom-nav included in home, verbs, about
- Active state: correct tab highlighted per page
- Language propagation: Search and Browse links carry language + ui_language as
  URL params (cookies are stripped by Firebase Hosting / Fastly CDN)
- Back tab: present on verbs/about, absent on home
- Back link destination: links to home with language params
- Practice tab: present, links to #practice-panel anchor with language
- Login button: initial aria-label="Login"; auth.js updates it after sign-in
- hashchange handler in verbs_page.js syncs Practice tab active state
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ── bottom nav present in all major page templates ────────────────────────────


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


# ── active state ──────────────────────────────────────────────────────────────


def test_home_bottom_nav_search_tab_active(client: TestClient) -> None:
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert "bnav-tab--active" in html
    browse_idx = html.index(">List<")
    active_idx = html.index("bnav-tab--active")
    assert active_idx < browse_idx


def test_verbs_bottom_nav_browse_tab_active(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        html = client.get("/verbs?language=en").text
    browse_idx = html.index(">List<")
    nav_fragment = html[:browse_idx]
    assert "bnav-tab--active" in nav_fragment


# ── language propagation ──────────────────────────────────────────────────────


def test_home_bottom_nav_search_link_carries_language(client: TestClient) -> None:
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=ru&ui_language=ru").text
    assert "/?language=ru&amp;ui_language=ru" in html


def test_verbs_bottom_nav_browse_link_carries_language(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        html = client.get("/verbs?language=he&ui_language=en").text
    assert "/verbs?language=he&amp;ui_language=en" in html


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
    """Search and Browse links must carry both language and ui_language as URL params."""
    with patch(patch_target, return_value=[]):
        html = client.get(url).text
    assert f'href="/?language={lang}&amp;ui_language=en"' in html
    assert f'href="/verbs?language={lang}&amp;ui_language=en"' in html


# ── back tab ──────────────────────────────────────────────────────────────────


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


# ── profile / login button ────────────────────────────────────────────────────


def test_bottom_nav_profile_button_calls_tap_profile(client: TestClient) -> None:
    """Profile tab must call VerbBoardAuth.tapProfile() directly (not .click())."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert "tapProfile()" in html


def test_bottom_nav_login_label_present(client: TestClient) -> None:
    """bnav-login-label span must be present for auth.js to update dynamically."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert 'id="bnav-login-label"' in html


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


# ── practice tab ─────────────────────────────────────────────────────────────


def test_bottom_nav_has_practice_tab(client: TestClient) -> None:
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert ">Practice<" in html


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
