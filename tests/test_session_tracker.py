"""Tests for session tracking pure-Python helpers.

Covers:
- ensure_sid: returns existing cookie or generates a new UUID
- get_seen_pages: parses vb_seen cookie (date-prefixed CSV); returns empty on mismatch
- set_seen_cookie: writes sorted, date-prefixed value; round-trips with get_seen_pages
- tracked_page: maps URL paths to page names; returns None for untracked paths
"""

from __future__ import annotations

from http.cookies import SimpleCookie

import pytest
from starlette.requests import Request
from starlette.responses import Response

from core.analytics.daily_counters import tracked_page
from core.analytics.session_tracker import (
    ensure_sid,
    get_seen_pages,
    set_seen_cookie,
)

# ── request / response helpers ────────────────────────────────────────────────


def _build_request(cookies: dict[str, str] | None = None) -> Request:
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
    raw = response.headers.get("set-cookie", "")
    sc = SimpleCookie()
    sc.load(raw)
    return sc[name].value if name in sc else ""


# ── ensure_sid ────────────────────────────────────────────────────────────────


def test_ensure_sid_returns_existing_cookie() -> None:
    req = _build_request(cookies={"vb_sid": "existing-sid"})
    sid, is_new = ensure_sid(req)
    assert sid == "existing-sid"
    assert is_new is False


def test_ensure_sid_generates_new_uuid_when_no_cookie() -> None:
    req = _build_request()
    sid, is_new = ensure_sid(req)
    assert is_new is True
    parts = sid.split("-")
    assert len(parts) == 5


def test_ensure_sid_new_uuids_are_unique() -> None:
    req = _build_request()
    sid1, _ = ensure_sid(req)
    sid2, _ = ensure_sid(req)
    assert sid1 != sid2


# ── get_seen_pages ────────────────────────────────────────────────────────────


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


# ── set_seen_cookie ───────────────────────────────────────────────────────────


def test_set_seen_cookie_contains_date_prefix() -> None:
    response = Response()
    set_seen_cookie(response, "2026-05-27", {"verbs", "home", "learn"})
    value = _parse_set_cookie_value(response, "vb_seen")
    assert value.startswith("2026-05-27|")


def test_set_seen_cookie_writes_sorted_pages() -> None:
    response = Response()
    set_seen_cookie(response, "2026-05-27", {"verbs", "home", "learn"})
    value = _parse_set_cookie_value(response, "vb_seen")
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


# ── tracked_page ──────────────────────────────────────────────────────────────


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
