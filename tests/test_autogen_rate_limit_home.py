"""Tests for app/routes/home.py's autogen rate-limit wiring.

Covers:
- _client_ip(): last X-Forwarded-For hop wins, with fallbacks to
  request.client.host and finally "unknown"
- /search_verb and /search_verb_by_lang short-circuit to a redirect (no
  autogenerate_missing_verb task scheduled) when autogen_rate_limited()
  reports the client is over quota
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from starlette.requests import Request

from app.routes.home import _client_ip

# ---------------------------------------------------------------------------
# _client_ip unit tests
# ---------------------------------------------------------------------------


def _make_request(
    headers: dict[str, str] | None = None, client: tuple[str, int] | None = ("testclient", 1234)
) -> Request:
    scope: dict = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    if client is not None:
        scope["client"] = client
    return Request(scope)


def test_client_ip_uses_last_forwarded_for_hop() -> None:
    """The LAST hop wins, not the first (the first hop is client-controlled)."""
    request = _make_request(headers={"x-forwarded-for": "1.1.1.1, 2.2.2.2, 3.3.3.3"})
    assert _client_ip(request) == "3.3.3.3"


def test_client_ip_single_forwarded_hop() -> None:
    request = _make_request(headers={"x-forwarded-for": "9.9.9.9"})
    assert _client_ip(request) == "9.9.9.9"


def test_client_ip_strips_whitespace_around_hops() -> None:
    request = _make_request(headers={"x-forwarded-for": " 1.1.1.1 , 2.2.2.2 "})
    assert _client_ip(request) == "2.2.2.2"


def test_client_ip_falls_back_to_request_client_host_without_header() -> None:
    request = _make_request(headers={}, client=("5.5.5.5", 1234))
    assert _client_ip(request) == "5.5.5.5"


def test_client_ip_falls_back_to_request_client_host_on_empty_header() -> None:
    request = _make_request(headers={"x-forwarded-for": ""}, client=("6.6.6.6", 1))
    assert _client_ip(request) == "6.6.6.6"


def test_client_ip_falls_back_to_unknown_without_header_or_client() -> None:
    request = _make_request(headers={}, client=None)
    assert _client_ip(request) == "unknown"


def test_client_ip_falls_back_to_unknown_on_blank_forwarded_for_hops() -> None:
    """A header of only commas/whitespace has no usable hops -- falls through
    to request.client.host, and to "unknown" if that's also absent."""
    request = _make_request(headers={"x-forwarded-for": " , , "}, client=None)
    assert _client_ip(request) == "unknown"


# ---------------------------------------------------------------------------
# /search_verb -- short-circuits on rate limit, no autogen task scheduled
# ---------------------------------------------------------------------------


def _patch_search_miss(monkeypatch) -> None:
    """Stub out all search paths to produce a clean miss for language=en."""
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", lambda lang, query: None)
    monkeypatch.setattr("app.routes.home.log_missing_verb_search", lambda **kw: None)
    monkeypatch.setattr("app.routes.home._load_entries", lambda language: [])


def test_search_verb_short_circuits_when_rate_limited(client: TestClient, monkeypatch) -> None:
    _patch_search_miss(monkeypatch)
    monkeypatch.setattr("app.routes.home.autogen_rate_limited", lambda client_ip: True)

    autogen_calls: list[dict] = []

    async def _fake_autogen(**kwargs):
        autogen_calls.append(kwargs)

    monkeypatch.setattr("app.routes.home.autogenerate_missing_verb", _fake_autogen)

    response = client.get("/search_verb?language=en&q=book", follow_redirects=False)

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "not_available=1" in location
    assert "generating=1" not in location
    assert not autogen_calls, "no autogen task should be scheduled once rate-limited"


def test_search_verb_still_autogens_when_not_rate_limited(client: TestClient, monkeypatch) -> None:
    """Sanity complement: the new check itself must not always short-circuit."""
    _patch_search_miss(monkeypatch)
    monkeypatch.setattr("app.routes.home.autogen_rate_limited", lambda client_ip: False)

    autogen_calls: list[dict] = []

    async def _fake_autogen(**kwargs):
        autogen_calls.append(kwargs)

    monkeypatch.setattr("app.routes.home.autogenerate_missing_verb", _fake_autogen)

    response = client.get("/search_verb?language=en&q=book", follow_redirects=False)

    location = response.headers["location"]
    assert "generating=1" in location


# ---------------------------------------------------------------------------
# /search_verb_by_lang -- short-circuits on rate limit, no autogen task
# ---------------------------------------------------------------------------


def _stub_translate_es(query: str, source_lang: str, target_lang: str, **kwargs) -> str:
    return "correr"


def test_search_verb_by_lang_short_circuits_when_rate_limited(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.home.translate_search_query", _stub_translate_es)
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", lambda lang, query: None)
    monkeypatch.setattr("app.routes.home.load_entries_for_language", lambda language: [])
    monkeypatch.setattr("app.routes.home.log_missing_verb_search", lambda **kw: None)
    monkeypatch.setattr("app.routes.home.autogen_rate_limited", lambda client_ip: True)

    autogen_calls: list[dict] = []

    async def _fake_autogen(**kwargs):
        autogen_calls.append(kwargs)

    monkeypatch.setattr("app.routes.home.autogenerate_missing_verb", _fake_autogen)

    response = client.get(
        "/search_verb_by_lang?language=es&q=run&source_lang=en",
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "not_available=1" in location
    assert "generating=1" not in location
    assert not autogen_calls, "no autogen task should be scheduled once rate-limited"


def test_search_verb_by_lang_still_autogens_when_not_rate_limited(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.home.translate_search_query", _stub_translate_es)
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", lambda lang, query: None)
    monkeypatch.setattr("app.routes.home.load_entries_for_language", lambda language: [])
    monkeypatch.setattr("app.routes.home.log_missing_verb_search", lambda **kw: None)
    monkeypatch.setattr("app.routes.home.autogen_rate_limited", lambda client_ip: False)

    async def _fake_autogen(**kwargs):
        pass

    monkeypatch.setattr("app.routes.home.autogenerate_missing_verb", _fake_autogen)

    response = client.get(
        "/search_verb_by_lang?language=es&q=run&source_lang=en",
        follow_redirects=False,
    )

    location = response.headers["location"]
    assert "generating=1" in location
