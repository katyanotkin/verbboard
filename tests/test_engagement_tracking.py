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
from google.cloud import firestore

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
    assert isinstance(doc["hits"], firestore.Increment)
    assert isinstance(doc["hits_search"], firestore.Increment)
    assert "hits_search_by_lang" not in doc
    assert doc["last_hit_at"] is not None


def test_record_search_hit_tracks_source_separately(fake_db) -> None:
    search_hits._record_search_hit("ru", "ru_idti", "search_by_lang")
    doc = fake_db._docs["verb_search_hits/ru_ru_idti"]
    assert isinstance(doc["hits_search_by_lang"], firestore.Increment)
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
