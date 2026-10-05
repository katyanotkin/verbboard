"""Anthropic circuit breaker, its call sites, the queued search path and the replay tool."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import pytest
from fastapi import HTTPException

import core.provider_health as ph
from core.provider_health import ANTHROPIC, ProviderUnavailable, classify


def _run(coro):
    # Run in a worker thread: earlier e2e tests can leave a running loop in this thread.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


CREDIT_MSG = "Your credit balance is too low to access the Anthropic API"


def _response(status: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"), headers=headers
    )


def _credit_error() -> anthropic.BadRequestError:
    return anthropic.BadRequestError(CREDIT_MSG, response=_response(400), body=None)


def _status_error(cls, status: int, headers: dict | None = None):
    return cls("boom", response=_response(status, headers), body=None)


def _status_doc(fake_db) -> dict:
    return fake_db.collection("provider_status").document("anthropic").get().to_dict()


# --- classify ---------------------------------------------------------------


def test_classify_outage_errors() -> None:
    assert classify(_credit_error()) == "out_of_credit"
    assert classify(_status_error(anthropic.AuthenticationError, 401)) == "auth_error"
    assert classify(_status_error(anthropic.PermissionDeniedError, 403)) == "auth_error"
    assert classify(_status_error(anthropic.APIStatusError, 402)) == "out_of_credit"
    spaced = anthropic.BadRequestError("Your  CREDIT\nbalance is low", response=_response(400), body=None)
    assert classify(spaced) == "out_of_credit"
    assert classify(_status_error(anthropic.RateLimitError, 429)) == "rate_limited"
    assert classify(_status_error(anthropic.APIStatusError, 529)) == "overloaded"


def test_classify_ignores_other_errors() -> None:
    other_400 = anthropic.BadRequestError("max_tokens too large", response=_response(400), body=None)
    assert classify(other_400) is None
    assert classify(_status_error(anthropic.APIStatusError, 500)) is None
    assert classify(ValueError("x")) is None


# --- breaker ----------------------------------------------------------------


def _call(client_mock) -> None:
    with ANTHROPIC.guard():
        client_mock()


def test_breaker_trips_and_makes_no_calls_while_open(fake_db) -> None:
    api = MagicMock(side_effect=_credit_error())
    with pytest.raises(ProviderUnavailable) as info:
        _call(api)
    assert info.value.reason == "out_of_credit"
    assert api.call_count == 1

    api2 = MagicMock()
    with pytest.raises(ProviderUnavailable):
        _call(api2)
    api2.assert_not_called()
    assert ph.provider_unavailable_reason() == "out_of_credit"


def test_non_outage_error_does_not_trip(fake_db) -> None:
    with pytest.raises(ValueError):
        _call(MagicMock(side_effect=ValueError("bad json")))
    assert ph.provider_unavailable_reason() is None
    assert not fake_db.collection("provider_status").document("anthropic").get().exists


def test_half_open_allows_one_probe_and_success_resets(fake_db, monkeypatch) -> None:
    with pytest.raises(ProviderUnavailable):
        _call(MagicMock(side_effect=_credit_error()))
    ANTHROPIC._open_until = 0.0  # cool-down elapsed

    probe_results: list[str] = []

    def probe() -> None:
        # While the probe is in flight, a second caller is refused.
        with pytest.raises(ProviderUnavailable):
            _call(MagicMock())
        probe_results.append("ran")

    _call(probe)
    assert probe_results == ["ran"]
    assert ph.provider_unavailable_reason() is None
    _call(MagicMock())  # closed again: calls flow
    assert _status_doc(fake_db)["state"] == "closed"


def test_failed_probe_reopens_without_second_transition(fake_db, caplog) -> None:
    with pytest.raises(ProviderUnavailable):
        _call(MagicMock(side_effect=_credit_error()))
    ANTHROPIC._open_until = 0.0
    with pytest.raises(ProviderUnavailable):
        _call(MagicMock(side_effect=_credit_error()))
    assert ph.provider_unavailable_reason() == "out_of_credit"
    assert sum("PROVIDER_UNAVAILABLE" in r.message for r in caplog.records) == 1


def test_status_doc_and_logs_only_on_transitions(fake_db, caplog) -> None:
    caplog.set_level("INFO")
    with pytest.raises(ProviderUnavailable):
        _call(MagicMock(side_effect=_credit_error()))
    doc = _status_doc(fake_db)
    assert doc["state"] == "open" and doc["reason"] == "out_of_credit"
    assert doc["last_error"].startswith("Your credit balance")
    assert any("PROVIDER_UNAVAILABLE provider=anthropic reason=out_of_credit" in r.message for r in caplog.records)

    ANTHROPIC._open_until = 0.0
    _call(MagicMock())
    assert _status_doc(fake_db)["state"] == "closed"
    assert any("PROVIDER_RECOVERED provider=anthropic" in r.message for r in caplog.records)

    _call(MagicMock())  # steady-state success: no further transition logs
    assert sum("PROVIDER_RECOVERED" in r.message for r in caplog.records) == 1


def test_cooldown_values(monkeypatch) -> None:
    assert ph.OUT_OF_CREDIT_COOLDOWN_SECONDS == 120
    assert (
        ph._cooldown_seconds("rate_limited", _status_error(anthropic.RateLimitError, 429, {"retry-after": "30"})) == 30
    )
    assert ph._cooldown_seconds("rate_limited", _status_error(anthropic.RateLimitError, 429)) == 60
    assert ph._cooldown_seconds("overloaded", None) == 120


def test_force_down_env_not_in_prod(monkeypatch) -> None:
    monkeypatch.setenv("VB_FORCE_PROVIDER_DOWN", "1")
    monkeypatch.setenv("ENVIRONMENT", "local")
    assert ph.provider_unavailable_reason() == "out_of_credit"
    monkeypatch.setenv("ENVIRONMENT", "prod")
    assert ph.provider_unavailable_reason() is None


# --- call sites -------------------------------------------------------------


def test_admin_call_claude_returns_503_with_detail(monkeypatch) -> None:
    from app.routes import admin_candidates

    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=_credit_error())
    monkeypatch.setattr(admin_candidates, "get_anthropic_client", lambda: client)
    with pytest.raises(HTTPException) as info:
        _run(admin_candidates._call_claude("ru", "бежать"))
    assert info.value.status_code == 503
    assert "Claude unavailable (out_of_credit): top up Anthropic credit" in info.value.detail
    # Second call is refused without touching the client.
    client.messages.create.reset_mock()
    with pytest.raises(HTTPException):
        _run(admin_candidates._call_claude("ru", "бежать"))
    client.messages.create.assert_not_called()


def test_pair_completion_writes_no_marker_on_credit_error(fake_db, monkeypatch) -> None:
    from core import verb_service

    client = MagicMock()
    client.messages.create.side_effect = _credit_error()
    monkeypatch.setattr(verb_service, "_load_anthropic_api_key", lambda: "k")
    monkeypatch.setattr(verb_service.anthropic, "Anthropic", lambda api_key: client)
    assert verb_service.generate_and_promote_verb("ru", "бежать") is None
    docs = list(fake_db.collection("verb_pair_generation_attempts").stream())
    assert docs == []


def test_autogen_claude_returns_none_when_unavailable(monkeypatch) -> None:
    from core import verb_autogen

    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=_credit_error())
    monkeypatch.setattr(verb_autogen, "get_anthropic_client", lambda: client)
    assert _run(verb_autogen._generate_verb_claude("ru", "бежать")) is None


def test_missing_translation_targets() -> None:
    from core.translation_service import missing_translation_targets

    examples = [{"dst": "Я бегу", "translations": {"en": "I run", "es": "Corro", "he": "אני רץ"}}]
    full = {"en": "to run", "es": "correr", "he": "לרוץ"}
    assert missing_translation_targets("ru", examples, full) == []
    no_he = [{"dst": "Я бегу", "translations": {"en": "I run", "es": "Corro"}}]
    assert "he" in missing_translation_targets("ru", no_he, full)


# --- search routes ----------------------------------------------------------


def _trip() -> None:
    with pytest.raises(ProviderUnavailable):
        _call(MagicMock(side_effect=_credit_error()))


def test_search_verb_queued_when_breaker_open(client, fake_db, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", lambda lang, query: None)
    monkeypatch.setattr("app.routes.home._load_entries", lambda language: [])
    limiter_calls: list[str] = []

    def _record_rate_limit_check(ip: str) -> bool:
        limiter_calls.append(ip)
        return False

    monkeypatch.setattr("app.routes.home.autogen_rate_limited", _record_rate_limit_check)
    tasks: list[dict] = []

    async def _fake_autogen(**kwargs):
        tasks.append(kwargs)

    monkeypatch.setattr("app.routes.home.autogenerate_missing_verb", _fake_autogen)
    _trip()

    response = client.get("/search_verb?language=ru&q=бежать", follow_redirects=False)
    location = response.headers["location"]
    assert "queued=1" in location and "not_available=1" in location
    assert "generating=1" not in location
    assert tasks == [] and limiter_calls == []
    signals = [d.to_dict() for d in fake_db.collection("demand_signal").stream()]
    assert signals and signals[0]["provider_unavailable"] is True


def test_search_verb_still_generates_when_breaker_closed(client, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", lambda lang, query: None)
    monkeypatch.setattr("app.routes.home._load_entries", lambda language: [])
    monkeypatch.setattr("app.routes.home.autogen_rate_limited", lambda ip: False)

    async def _fake_autogen(**kwargs):
        return None

    monkeypatch.setattr("app.routes.home.autogenerate_missing_verb", _fake_autogen)
    response = client.get("/search_verb?language=ru&q=бежать", follow_redirects=False)
    assert "generating=1" in response.headers["location"]


def test_home_shows_queued_notice(client) -> None:
    html = client.get("/?language=ru&not_available=1&search=бежать&queued=1&ui_language=en").text
    assert "saved your request" in html
    assert "search-notice-countdown" not in html


# --- admin banner -----------------------------------------------------------


def test_admin_banner_only_when_open(fake_db) -> None:
    assert ph.admin_banner_text() is None
    _trip()
    text = ph.admin_banner_text()
    assert text and "Claude unavailable since" in text and "out_of_credit" in text
    ANTHROPIC._open_until = 0.0
    _call(MagicMock())
    assert ph.admin_banner_text() is None


# --- replay tool ------------------------------------------------------------


def test_replay_dry_run_selects_and_skips(fake_db, monkeypatch, capsys) -> None:
    from tools import replay_failed_demand as replay

    now = datetime.now(UTC)
    since, until = now - timedelta(hours=2), now + timedelta(hours=1)

    def signal(query: str, language: str = "ru", source: str = "search", when=now) -> None:
        fake_db.collection("demand_signal").document().set(
            {"created_at": when, "language": language, "query": query, "source": source}
        )

    signal("бежать")
    signal("бежать")  # duplicate
    signal("идти")  # exists
    signal("петь")  # rejected
    signal("run", language="en")  # not a Claude language
    signal("читать", when=now - timedelta(days=3))  # outside window
    signal("123")  # implausible
    monkeypatch.setattr(
        replay, "find_verb_by_search_extract", lambda lang, q: {"verb_id": "x"} if q == "идти" else None
    )
    monkeypatch.setattr(replay, "check_verb_rejected", lambda lang, q: q == "петь")
    generated: list = []
    monkeypatch.setattr(replay, "autogenerate_missing_verb", AsyncMock(side_effect=lambda **k: generated.append(k)))

    args = MagicMock(
        since=since.isoformat(), until=until.isoformat(), apply=False, clear_pair_markers=True, max_items=50
    )
    fake_db.collection("verb_pair_generation_attempts").document("ru_x").set(
        {"reason": "generation_failed", "attempted_at": now.isoformat()}
    )
    _run(replay._run(args))
    out = capsys.readouterr().out
    assert out.count("would generate: ru/бежать") == 1
    assert "skip (exists): ru/идти" in out and "skip (rejected): ru/петь" in out
    assert "читать" not in out and "implausible" in out
    assert generated == []
    assert fake_db.collection("verb_pair_generation_attempts").document("ru_x").get().exists


# --- review fixes ------------------------------------------------------------


def test_cancelled_probe_releases_slot(fake_db) -> None:
    with pytest.raises(ProviderUnavailable):
        _call(MagicMock(side_effect=_credit_error()))
    ANTHROPIC._open_until = 0.0
    with pytest.raises(asyncio.CancelledError):
        _call(MagicMock(side_effect=asyncio.CancelledError()))
    # The next call may probe (and succeeds, closing the breaker).
    _call(MagicMock())
    assert ph.provider_unavailable_reason() is None


def test_stuck_probe_expires(fake_db) -> None:
    with pytest.raises(ProviderUnavailable):
        _call(MagicMock(side_effect=_credit_error()))
    ANTHROPIC._open_until = 0.0
    ANTHROPIC._acquire()  # probe that never reports back
    with pytest.raises(ProviderUnavailable):
        ANTHROPIC._acquire()
    ANTHROPIC._probe_started_at -= ph.PROBE_TIMEOUT_SECONDS + 1
    assert ANTHROPIC._acquire() is True


def test_failed_probe_refreshes_heartbeat(fake_db) -> None:
    with pytest.raises(ProviderUnavailable):
        _call(MagicMock(side_effect=_credit_error()))
    fake_db.collection("provider_status").document("anthropic").set(
        {"updated_at": "2000-01-01T00:00:00+00:00"}, merge=True
    )
    ANTHROPIC._open_until = 0.0
    with pytest.raises(ProviderUnavailable):
        _call(MagicMock(side_effect=_credit_error()))
    assert _status_doc(fake_db)["updated_at"] > "2020"


def test_banner_ignores_stale_open_doc(fake_db) -> None:
    old = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    fake_db.collection("provider_status").document("anthropic").set(
        {"state": "open", "reason": "out_of_credit", "opened_at": old, "updated_at": old}
    )
    assert ph.admin_banner_text() is None


def test_auth_error_banner_and_503_text(fake_db) -> None:
    with pytest.raises(ProviderUnavailable):
        _call(MagicMock(side_effect=_status_error(anthropic.AuthenticationError, 401)))
    banner = ph.admin_banner_text()
    assert banner is not None and "Claude API key rejected or lacks permission" in banner


def _admin_cookies() -> dict[str, str]:
    from core.admin_auth import ADMIN_SESSION_COOKIE, create_admin_session_token

    return {ADMIN_SESSION_COOKIE: create_admin_session_token()}


def test_regenerate_succeeds_with_translations_incomplete_when_breaker_opens(client, fake_db, monkeypatch) -> None:
    from app.routes import admin_candidates

    fake_db.collection("verbs").document("ru_bezhat").set(
        {"verb_id": "ru_bezhat", "language": "ru", "lemma": "бежать", "rank": 1}
    )
    generated = {"lemma": "бежать", "forms": {"present": {"я": "бегу"}}, "examples": [{"dst": "Я бегу"}]}
    monkeypatch.setattr(admin_candidates, "_call_claude", AsyncMock(return_value=generated))
    monkeypatch.setattr(admin_candidates, "_warm_verb_audio", AsyncMock())

    def _down(**kwargs):
        raise ProviderUnavailable("out_of_credit")

    monkeypatch.setattr(admin_candidates, "translate_examples", _down)
    monkeypatch.setattr(admin_candidates, "translate_lemma", _down)
    response = client.post("/admin/api/verbs/ru_bezhat/regenerate", cookies=_admin_cookies())
    assert response.status_code == 200
    assert response.json()["translations_incomplete"] is True
    assert fake_db.collection("verbs").document("ru_bezhat").get().to_dict()["forms"] == generated["forms"]


def test_primary_generation_failure_writes_nothing(client, fake_db, monkeypatch) -> None:
    from app.routes import admin_candidates

    fake_db.collection("verbs").document("ru_bezhat").set(
        {"verb_id": "ru_bezhat", "language": "ru", "lemma": "бежать", "forms": {"old": 1}}
    )
    monkeypatch.setattr(
        admin_candidates, "_call_claude", AsyncMock(side_effect=HTTPException(status_code=503, detail="x"))
    )
    response = client.post("/admin/api/verbs/ru_bezhat/regenerate", cookies=_admin_cookies())
    assert response.status_code == 503
    assert fake_db.collection("verbs").document("ru_bezhat").get().to_dict()["forms"] == {"old": 1}


def test_hebrew_source_translation_outage_does_not_500(fake_db, monkeypatch) -> None:
    from app.routes import admin_candidates

    def _down(**kwargs):
        raise ProviderUnavailable("out_of_credit")

    monkeypatch.setattr(admin_candidates, "translate_examples", _down)
    monkeypatch.setattr(admin_candidates, "translate_lemma", _down)
    monkeypatch.setattr(admin_candidates, "_load_anthropic_api_key", lambda: "k")
    examples = [{"dst": "אני רץ"}]
    out_examples, lemma_tr, incomplete = _run(admin_candidates._translate_verb("he", "לרוץ", examples))
    assert out_examples is examples and incomplete is True and lemma_tr == {}


def test_hebrew_source_translation_service_raises_provider_unavailable(monkeypatch) -> None:
    from core import translation_service as ts

    monkeypatch.setattr(ts, "_call_claude", MagicMock(side_effect=ProviderUnavailable("out_of_credit")))
    with pytest.raises(ProviderUnavailable):
        ts.translate_examples(verb_lang="he", lemma="לרוץ", examples=[{"dst": "אני רץ"}], project="p", api_key="k")


def test_replay_max_items(fake_db, monkeypatch, capsys) -> None:
    from tools import replay_failed_demand as replay

    now = datetime.now(UTC)
    for q in ("бежать", "идти", "петь"):
        fake_db.collection("demand_signal").document().set(
            {"created_at": now, "language": "ru", "query": q, "source": "search"}
        )
    monkeypatch.setattr(replay, "find_verb_by_search_extract", lambda lang, q: None)
    monkeypatch.setattr(replay, "check_verb_rejected", lambda lang, q: False)
    args = MagicMock(
        since=(now - timedelta(hours=1)).isoformat(), until=None, apply=False, clear_pair_markers=False, max_items=2
    )
    _run(replay._run(args))
    out = capsys.readouterr().out
    assert "1 queries left out" in out and out.count("would generate") == 2
