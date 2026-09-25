"""Tests for the Verb of the Day click flag, the home_viewed session flag, and
the per-verb search-hit counter.

These close the measurement gaps behind three product questions: does the
Verb of the Day hero get clicked (votd_clicked / home_viewed), and do people
search again for verbs the app already has, including ones it generated on
the spot (verb_search_hits).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from core.analytics import search_hits, session_tracker

DATE = "2026-09-24"
SESSION_PATH = f"analytics_sessions/{DATE}_fp1"


# ── votd_clicked ────────────────────────────────────────────────────────────


def test_record_votd_clicked_sets_flag(fake_db) -> None:
    fake_db._docs[SESSION_PATH] = {"sid": "fp1"}
    session_tracker._record_votd_clicked("fp1", DATE)
    assert fake_db._docs[SESSION_PATH] == {"sid": "fp1", "votd_clicked": True}


def test_record_votd_clicked_does_not_create_stub_session(fake_db) -> None:
    session_tracker._record_votd_clicked("fp1", DATE)
    assert SESSION_PATH not in fake_db._docs


def test_record_votd_clicked_preserves_existing_session_fields(fake_db) -> None:
    fake_db._docs[SESSION_PATH] = {"sid": "fp1", "language": "es", "practice_started": True}
    session_tracker._record_votd_clicked("fp1", DATE)
    assert fake_db._docs[SESSION_PATH] == {
        "sid": "fp1",
        "language": "es",
        "practice_started": True,
        "votd_clicked": True,
    }


def test_record_votd_clicked_is_set_once(fake_db) -> None:
    fake_db._docs[SESSION_PATH] = {"votd_clicked": True}
    with patch("tests.fake_firestore.FakeDocRef.set") as mock_set:
        session_tracker._record_votd_clicked("fp1", DATE)
    mock_set.assert_not_called()


def test_votd_clicked_endpoint_records_against_fingerprint(client: TestClient) -> None:
    with patch("app.routes.api_analytics.record_votd_clicked", new_callable=AsyncMock) as mock_record:
        resp = client.post("/api/analytics/votd_clicked")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_record.assert_awaited_once()
    assert mock_record.await_args is not None
    fingerprint, date = mock_record.await_args.args
    assert len(fingerprint) == 32
    assert len(date) == 10


# ── home_viewed ─────────────────────────────────────────────────────────────


def test_create_session_stores_home_viewed(fake_db) -> None:
    session_tracker._create_session("fp1", DATE, "mobile", "es", "en", False, "", True)
    doc = fake_db._docs[SESSION_PATH]
    assert doc["home_viewed"] is True
    assert doc["verb_viewed"] is False


def test_create_session_home_viewed_defaults_false(fake_db) -> None:
    session_tracker._create_session("fp1", DATE, "mobile", "es", "en")
    assert fake_db._docs[SESSION_PATH]["home_viewed"] is False


def test_home_viewed_flips_true_on_existing_session_and_never_back(fake_db) -> None:
    session_tracker._create_session("fp1", DATE, "mobile", "es", "en", True, "", False)
    session_tracker._create_session("fp1", DATE, "mobile", "es", "en", False, "", True)
    assert fake_db._docs[SESSION_PATH]["home_viewed"] is True
    # A later non-home hit must not reset it.
    session_tracker._create_session("fp1", DATE, "mobile", "es", "en", False, "", False)
    assert fake_db._docs[SESSION_PATH]["home_viewed"] is True
    assert fake_db._docs[SESSION_PATH]["verb_viewed"] is True


# ── verb_search_hits ────────────────────────────────────────────────────────


def test_record_search_hit_writes_counter_doc(fake_db) -> None:
    search_hits._record_search_hit("it", "it_parlare", "search")
    doc = fake_db._docs["verb_search_hits/it_it_parlare"]
    assert doc["language"] == "it"
    assert doc["verb_id"] == "it_parlare"
    assert doc["hits"] == 1
    assert doc["hits_search"] == 1
    assert "hits_search_by_lang" not in doc
    assert doc["last_hit_at"] is not None


def test_record_search_hit_tracks_source_separately(fake_db) -> None:
    search_hits._record_search_hit("ru", "ru_idti", "search_by_lang")
    doc = fake_db._docs["verb_search_hits/ru_ru_idti"]
    assert doc["hits_search_by_lang"] == 1
    assert "hits_search" not in doc


def test_record_search_hit_swallows_firestore_errors() -> None:
    with patch("core.storage.firestore_db.get_db", side_effect=RuntimeError("boom")):
        search_hits._record_search_hit("it", "it_parlare", "search")  # must not raise


@pytest.mark.parametrize(
    ("language", "verb_id", "source"),
    [("", "it_parlare", "search"), ("it", "", "search"), ("it", "it_parlare", "bogus")],
)
def test_record_search_hit_ignores_invalid_input(language, verb_id, source) -> None:
    with patch("core.analytics.search_hits.asyncio.create_task") as mock_create_task:
        search_hits.record_search_hit(language=language, verb_id=verb_id, source=source)
    mock_create_task.assert_not_called()


# ── search routes record hits ───────────────────────────────────────────────


def test_native_search_hit_records_search_hit(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", lambda lang, query: {"verb_id": "en_go"})
    calls: list[dict] = []
    monkeypatch.setattr("app.routes.home.record_search_hit", lambda **kw: calls.append(kw))
    client.get("/search_verb?language=en&q=go", follow_redirects=False)
    assert calls == [{"language": "en", "verb_id": "en_go", "source": "search"}]


def test_native_search_miss_does_not_record_search_hit(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", lambda lang, query: None)
    monkeypatch.setattr("app.routes.home.log_missing_verb_search", lambda **kw: None)
    calls: list[dict] = []
    monkeypatch.setattr("app.routes.home.record_search_hit", lambda **kw: calls.append(kw))
    client.get("/search_verb?language=en&q=xyzzyverb", follow_redirects=False)
    assert calls == []


def test_cross_language_search_hit_records_search_hit(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.home.translate_search_query", lambda q, src, tgt: "correr")
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", lambda lang, query: {"verb_id": "es_correr"})
    calls: list[dict] = []
    monkeypatch.setattr("app.routes.home.record_search_hit", lambda **kw: calls.append(kw))
    client.get("/search_verb_by_lang?language=es&q=run&source_lang=en", follow_redirects=False)
    assert calls == [{"language": "es", "verb_id": "es_correr", "source": "search_by_lang"}]


# ── ui_lang_selected (Hebrew UI review, issue #60) ──────────────────────────


def test_record_ui_lang_selected_sets_latest_pick(fake_db) -> None:
    fake_db._docs[SESSION_PATH] = {"sid": "fp1", "ui_lang": "en"}
    session_tracker._record_ui_lang_selected("fp1", DATE, "he")
    session_tracker._record_ui_lang_selected("fp1", DATE, "es")
    assert fake_db._docs[SESSION_PATH] == {"sid": "fp1", "ui_lang": "en", "ui_lang_selected": "es"}


def test_record_ui_lang_selected_rejects_non_ui_languages_and_missing_sessions(fake_db) -> None:
    fake_db._docs[SESSION_PATH] = {"sid": "fp1"}
    session_tracker._record_ui_lang_selected("fp1", DATE, "it")  # study-only, not a UI language
    session_tracker._record_ui_lang_selected("fp1", DATE, "")
    assert "ui_lang_selected" not in fake_db._docs[SESSION_PATH]

    session_tracker._record_ui_lang_selected("nobody", DATE, "he")
    assert f"analytics_sessions/{DATE}_nobody" not in fake_db._docs


def test_ui_lang_selected_endpoint_passes_the_choice(client: TestClient) -> None:
    with patch("app.routes.api_analytics.record_ui_lang_selected", new_callable=AsyncMock) as mock_record:
        resp = client.post("/api/analytics/ui_lang_selected", json={"ui_lang": "he"})
    assert resp.status_code == 200
    mock_record.assert_awaited_once()
    assert mock_record.await_args is not None
    assert mock_record.await_args.args[2] == "he"


def test_ui_lang_selected_endpoint_tolerates_a_bad_body(client: TestClient) -> None:
    with patch("app.routes.api_analytics.record_ui_lang_selected", new_callable=AsyncMock) as mock_record:
        resp = client.post("/api/analytics/ui_lang_selected", content="not json")
    assert resp.status_code == 200
    assert mock_record.await_args is not None
    assert mock_record.await_args.args[2] == ""


def test_record_search_hit_accumulates_across_searches(fake_db) -> None:
    for _ in range(3):
        search_hits._record_search_hit("it", "it_parlare", "search")
    search_hits._record_search_hit("it", "it_parlare", "search_by_lang")
    doc = fake_db._docs["verb_search_hits/it_it_parlare"]
    assert (doc["hits"], doc["hits_search"], doc["hits_search_by_lang"]) == (4, 3, 1)


# ── practice_gate_shown (anonymous visitors must sign in to start practice) ──


def test_practice_gate_shown_is_set_once_and_never_creates_a_stub_session(fake_db) -> None:
    session_tracker._record_practice_gate_shown("nobody", DATE)
    assert f"analytics_sessions/{DATE}_nobody" not in fake_db._docs

    fake_db._docs[SESSION_PATH] = {"sid": "fp1"}
    session_tracker._record_practice_gate_shown("fp1", DATE)
    session_tracker._record_practice_gate_shown("fp1", DATE)
    assert fake_db._docs[SESSION_PATH] == {"sid": "fp1", "practice_gate_shown": True}


def test_practice_event_endpoint_accepts_gate_shown(client: TestClient) -> None:
    with patch("app.routes.api_analytics.record_practice_gate_shown", new_callable=AsyncMock) as mock_record:
        resp = client.post("/api/analytics/practice_event", json={"event": "gate_shown"})
    assert resp.status_code == 200 and resp.json() == {"ok": True}
    mock_record.assert_awaited_once()


def test_admin_summary_counts_gate_impressions_and_the_ones_that_signed_in(fake_db) -> None:
    from datetime import UTC, datetime

    from core import admin_feedback_service

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    fake_db.seed(
        "analytics_sessions",
        {
            "a": {"date": today, "device_type": "mobile", "practice_gate_shown": True},
            "b": {"date": today, "device_type": "mobile", "practice_gate_shown": True, "uid": "u1"},
            "c": {"date": today, "device_type": "desktop", "uid": "u2"},
            "d": {"date": today, "device_type": "bot", "practice_gate_shown": True, "uid": "u3"},
        },
    )
    engagement = admin_feedback_service._read_sessions_summary(days=60)["engagement"]
    assert engagement["practice_gate_shown"] == 2
    assert engagement["practice_gate_then_signed_in"] == 1
