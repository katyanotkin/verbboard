"""Tests for the bottom navigation bar (_bottom_nav.html).

4-tab icon-only bar: Back / Verbs / Search / Home.
No text labels -- tabs are distinguished by SVG icons and aria-labels.

Covers:
- Presence: bottom-nav included in home, verbs, about
- Active state: correct tab highlighted per page
- Language propagation: Search and Home links carry language + ui_language
- Back tab: linked when bnav_back_href is set; falls back to history.back() on home
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


# ── 4 tabs, no text labels ────────────────────────────────────────────────────


def test_bottom_nav_has_four_tabs(client: TestClient) -> None:
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    nav_start = html.index("bottom-nav")
    nav_end = html.index("</nav>", nav_start)
    nav_html = html[nav_start:nav_end]
    assert nav_html.count("bnav-tab") >= 4


def test_bottom_nav_has_no_text_labels(client: TestClient) -> None:
    """All tabs are icon-only -- no visible text labels inside the nav."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    nav_start = html.index('<nav class="bottom-nav"')
    nav_end = html.index("</nav>", nav_start) + len("</nav>")
    nav_html = html[nav_start:nav_end]
    for label in (">Back<", ">Search<", ">List<", ">Verbs<", ">Practice<", ">Login<", ">Logout<"):
        assert label not in nav_html


# ── active state ──────────────────────────────────────────────────────────────


def test_home_bottom_nav_home_tab_active(client: TestClient) -> None:
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert "bnav-tab--active" in html


def test_verbs_bottom_nav_browse_tab_active(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        html = client.get("/verbs?language=en").text
    assert "bnav-tab--active" in html


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
def test_bottom_nav_lang_hrefs_contain_language(client: TestClient, url: str, lang: str, patch_target: str) -> None:
    """Search and Verbs links must carry both language and ui_language as URL params."""
    with patch(patch_target, return_value=[]):
        html = client.get(url).text
    assert f'href="/?language={lang}&amp;ui_language=en"' in html
    assert f'href="/verbs?language={lang}&amp;ui_language=en"' in html


# ── back tab ──────────────────────────────────────────────────────────────────


def test_bottom_nav_home_back_uses_history_back(client: TestClient) -> None:
    """Home has no back destination -- Back tab falls back to history.back()."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert "history.back()" in html


def test_bottom_nav_verbs_back_is_a_link(client: TestClient) -> None:
    """Verbs page has a back href -- Back tab must be an <a> tag."""
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        html = client.get("/verbs?language=en").text
    assert 'aria-label="Back"' in html
    assert "history.back()" not in html


def test_bottom_nav_verbs_back_links_to_home(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        html = client.get("/verbs?language=ru&ui_language=en").text
    assert 'href="/?language=ru&amp;ui_language=en"' in html


def test_bottom_nav_about_back_is_a_link(client: TestClient) -> None:
    html = client.get("/about").text
    assert 'aria-label="Back"' in html


# ── home tab ──────────────────────────────────────────────────────────────────


def test_bottom_nav_has_home_tab(client: TestClient) -> None:
    """Home tab (house icon) must be present with aria-label='Home'."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert 'aria-label="Home"' in html


def test_bottom_nav_home_tab_active_on_home_page(client: TestClient) -> None:
    """Home page sets bnav_active='home' so the house tab gets bnav-tab--active."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        html = client.get("/?language=en").text
    assert "bnav-tab--active" in html
