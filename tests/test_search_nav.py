"""Tests that back-navigation return_to is propagated through search redirects.

Bug: when search_verb or search_verb_by_lang found a verb and redirected to
/learn, the return_to query param was dropped.  The Learn page Back button
then defaulted to home (/) instead of /verbs.

Covers:
- search_verb direct Firestore hit: return_to forwarded to /learn
- search_verb direct Firestore hit: no return_to when not supplied
- search_verb fuzzy fallback hit: return_to forwarded to /learn
- search_verb_by_lang hit after translation: return_to forwarded alongside
  translated_from and source_lang
"""

from __future__ import annotations

import types

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# /search_verb -- direct Firestore hit
# ---------------------------------------------------------------------------


def test_search_verb_hit_passes_return_to(client: TestClient, monkeypatch) -> None:
    """When Firestore returns a hit and return_to is set, the redirect to /learn
    must include the return_to param so the Learn page Back button goes back."""
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: {"verb_id": "en_go"},
    )

    response = client.get(
        "/search_verb?language=en&q=go&return_to=%2Fverbs%3Flanguage%3Den",
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" in location
    assert "return_to" in location
    # The value /verbs must appear somewhere in the return_to param
    assert "%2Fverbs" in location or "/verbs" in location


def test_search_verb_hit_no_return_to(client: TestClient, monkeypatch) -> None:
    """When return_to is absent, the redirect to /learn must NOT contain return_to
    (the Learn page applies its own default; we must not inject a blank param)."""
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: {"verb_id": "en_go"},
    )

    response = client.get(
        "/search_verb?language=en&q=go",
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" in location
    assert "return_to" not in location


# ---------------------------------------------------------------------------
# /search_verb -- fuzzy fallback hit
# ---------------------------------------------------------------------------


def test_search_verb_fuzzy_hit_passes_return_to(client: TestClient, monkeypatch) -> None:
    """When Firestore misses but the fuzzy fallback finds a verb, return_to must
    still be forwarded to the /learn redirect."""
    # Firestore always misses
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: None,
    )

    # Fake entry object with an .id attribute that find_best_entry will return
    fake_entry = types.SimpleNamespace(id="en_run")
    monkeypatch.setattr(
        "app.routes.home.find_best_entry",
        lambda entries, query, **kw: fake_entry,
    )

    response = client.get(
        "/search_verb?language=en&q=running&return_to=%2Fverbs%3Flanguage%3Den",
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" in location
    assert "en_run" in location
    assert "return_to" in location
    assert "%2Fverbs" in location or "/verbs" in location


# ---------------------------------------------------------------------------
# /search_verb_by_lang -- hit after translation
# ---------------------------------------------------------------------------


def test_search_verb_by_lang_hit_passes_return_to(client: TestClient, monkeypatch) -> None:
    """After a successful translation + Firestore hit, the redirect to /learn
    must carry return_to alongside translated_from and source_lang."""
    monkeypatch.setattr(
        "app.routes.home.translate_search_query",
        lambda query, source_lang, target_lang, **kw: "correr",
    )
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: {"verb_id": "es_correr"} if query == "correr" else None,
    )

    response = client.get(
        "/search_verb_by_lang?language=es&q=run&source_lang=en&return_to=%2Fverbs%3Flanguage%3Des",
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" in location
    assert "translated_from=run" in location
    assert "source_lang=en" in location
    assert "return_to" in location
    assert "%2Fverbs" in location or "/verbs" in location
