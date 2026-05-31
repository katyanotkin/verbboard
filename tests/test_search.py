from __future__ import annotations

from fastapi.testclient import TestClient

from core.models import VerbEntry

# ---------------------------------------------------------------------------
# /search_verb -- native-language search
# ---------------------------------------------------------------------------


def test_search_hit_via_firestore_redirects_to_learn(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: {"verb_id": "en_go"},
    )
    response = client.get("/search_verb?language=en&q=go", follow_redirects=False)
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" in location
    assert "en_go" in location
    assert "language=en" in location


def test_search_hit_sets_cookies(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: {"verb_id": "en_go"},
    )
    response = client.get("/search_verb?language=en&q=go", follow_redirects=False)
    assert "language" in response.cookies or "language" in response.headers.get(
        "set-cookie", ""
    )


def test_search_miss_logs_demand_signal(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: None,
    )
    log_calls: list[dict] = []
    monkeypatch.setattr(
        "app.routes.home.log_missing_verb_search",
        lambda **kwargs: log_calls.append(kwargs),
    )
    client.get("/search_verb?language=en&q=xyzzyverb", follow_redirects=False)
    assert len(log_calls) == 1
    assert log_calls[0]["language"] == "en"
    assert log_calls[0]["query"] == "xyzzyverb"


def test_search_miss_redirects_with_not_available(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: None,
    )
    monkeypatch.setattr(
        "app.routes.home.log_missing_verb_search",
        lambda **kwargs: None,
    )
    response = client.get(
        "/search_verb?language=en&q=xyzzyverb", follow_redirects=False
    )
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "not_available=1" in location
    assert "learn" not in location


def test_search_empty_query_redirects_to_home(client: TestClient) -> None:
    response = client.get("/search_verb?language=en&q=", follow_redirects=False)
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "learn" not in location
    assert "not_available" not in location


# ---------------------------------------------------------------------------
# /search_verb_by_lang -- cross-language search (EN pill -> Spanish verb)
# The primary scenario: user studies Spanish, types "run" in English,
# expects to land on correr's /learn page.
# ---------------------------------------------------------------------------

_CORRER_DOC = {
    "verb_id": "es_correr",
    "language": "es",
    "lemma": "correr",
    "search_extract": ["correr", "run"],
    "rank": 10,
    "forms": {},
    "examples": [],
}

_CORRER_ENTRY = VerbEntry(
    id="es_correr",
    rank=10,
    lemma="correr",
    forms={"infinitive": "correr"},
    examples=[],
)


def _stub_translate(query, source_lang, target_lang, project, **kwargs):
    """Synchronous Gemini stub: translates 'run' (EN) -> 'correr' (ES)."""
    mapping = {("run", "en", "es"): "correr"}
    return mapping.get((query.lower(), source_lang, target_lang))


def test_search_by_lang_run_to_correr_redirects_to_learn(
    client: TestClient, monkeypatch
) -> None:
    """Happy path: EN search 'run' with lang=es redirects to correr's learn page."""
    monkeypatch.setattr(
        "app.routes.home.translate_search_query",
        _stub_translate,
    )
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: _CORRER_DOC
        if (lang == "es" and query == "correr")
        else None,
    )

    response = client.get(
        "/search_verb_by_lang?language=es&q=run&source_lang=en",
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" in location
    assert "es_correr" in location
    assert "language=es" in location


def test_search_by_lang_includes_translated_from_param(
    client: TestClient, monkeypatch
) -> None:
    """Redirect URL carries translated_from=run and source_lang=en for UI breadcrumb."""
    monkeypatch.setattr(
        "app.routes.home.translate_search_query",
        _stub_translate,
    )
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: _CORRER_DOC
        if (lang == "es" and query == "correr")
        else None,
    )

    response = client.get(
        "/search_verb_by_lang?language=es&q=run&source_lang=en",
        follow_redirects=False,
    )

    location = response.headers["location"]
    assert "translated_from=run" in location
    assert "source_lang=en" in location


def test_search_by_lang_sets_language_cookie(client: TestClient, monkeypatch) -> None:
    """On successful match, language cookie is set to the target language."""
    monkeypatch.setattr(
        "app.routes.home.translate_search_query",
        _stub_translate,
    )
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: _CORRER_DOC
        if (lang == "es" and query == "correr")
        else None,
    )

    response = client.get(
        "/search_verb_by_lang?language=es&q=run&source_lang=en",
        follow_redirects=False,
    )

    set_cookie = response.headers.get("set-cookie", "")
    assert "language" in response.cookies or "language" in set_cookie


def test_search_by_lang_token_fallback_handles_punctuation(
    client: TestClient, monkeypatch
) -> None:
    """If Gemini returns 'correr.' with trailing punctuation, token fallback strips it."""

    def translate_with_punctuation(query, source_lang, target_lang, project, **kwargs):
        return "correr."  # Gemini added a period

    call_count = {"n": 0}

    def find_by_extract(lang, query):
        call_count["n"] += 1
        # First call with "correr." -> None; second call with "correr" -> match
        if query == "correr":
            return _CORRER_DOC
        return None

    monkeypatch.setattr(
        "app.routes.home.translate_search_query", translate_with_punctuation
    )
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", find_by_extract)

    response = client.get(
        "/search_verb_by_lang?language=es&q=run&source_lang=en",
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" in location
    assert "es_correr" in location
    # Both calls should have happened: once with "correr." and once with "correr"
    assert call_count["n"] >= 2


def test_search_by_lang_fuzzy_fallback_when_firestore_misses(
    client: TestClient, monkeypatch
) -> None:
    """If Firestore search_extract misses, fuzzy match against all cached entries finds correr."""
    monkeypatch.setattr(
        "app.routes.home.translate_search_query",
        _stub_translate,
    )
    # Firestore always returns None (verb has no search_extract entry for "correr")
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: None,
    )
    # Full entry list contains correr -- fuzzy match should hit it
    monkeypatch.setattr(
        "app.routes.home.load_entries_for_language",
        lambda language: [_CORRER_ENTRY],
    )

    response = client.get(
        "/search_verb_by_lang?language=es&q=run&source_lang=en",
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" in location
    assert "es_correr" in location


def test_search_by_lang_translation_failure_redirects_with_original_query(
    client: TestClient, monkeypatch
) -> None:
    """If Gemini fails to translate, redirect shows original query and search_mode=en."""
    monkeypatch.setattr(
        "app.routes.home.translate_search_query",
        lambda *a, **kw: None,  # Gemini failure
    )

    response = client.get(
        "/search_verb_by_lang?language=es&q=run&source_lang=en",
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "not_available=1" in location
    assert "search=run" in location
    assert "search_mode=en" in location
    assert "/learn" not in location


def test_search_by_lang_verb_not_in_db_logs_demand_signal(
    client: TestClient, monkeypatch
) -> None:
    """If translation succeeds but verb is absent, demand signal is logged."""
    monkeypatch.setattr(
        "app.routes.home.translate_search_query",
        _stub_translate,
    )
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: None,
    )
    monkeypatch.setattr(
        "app.routes.home.load_entries_for_language",
        lambda language: [],  # empty -- fuzzy also fails
    )
    log_calls: list[dict] = []
    monkeypatch.setattr(
        "app.routes.home.log_missing_verb_search",
        lambda **kwargs: log_calls.append(kwargs),
    )

    client.get(
        "/search_verb_by_lang?language=es&q=run&source_lang=en",
        follow_redirects=False,
    )

    assert len(log_calls) == 1
    assert log_calls[0]["language"] == "es"
    assert log_calls[0]["query"] == "correr"  # the translated word is logged


def test_search_by_lang_verb_not_in_db_shows_translated_word(
    client: TestClient, monkeypatch
) -> None:
    """When verb absent, redirect shows the translated word (correr) not the English query."""
    monkeypatch.setattr(
        "app.routes.home.translate_search_query",
        _stub_translate,
    )
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: None,
    )
    monkeypatch.setattr(
        "app.routes.home.load_entries_for_language",
        lambda language: [],
    )
    monkeypatch.setattr(
        "app.routes.home.log_missing_verb_search",
        lambda **kwargs: None,
    )

    response = client.get(
        "/search_verb_by_lang?language=es&q=run&source_lang=en",
        follow_redirects=False,
    )

    location = response.headers["location"]
    assert "not_available=1" in location
    assert "search=correr" in location
    assert "search_mode=native" in location
    assert "/learn" not in location


def test_search_by_lang_empty_query_redirects_to_home(client: TestClient) -> None:
    """Empty query skips translation and redirects to home."""
    response = client.get(
        "/search_verb_by_lang?language=es&q=",
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" not in location
    assert "not_available" not in location


# ---------------------------------------------------------------------------
# /search_verb_by_lang -- English -> Russian ("run" -> "бежать")
# ---------------------------------------------------------------------------

_BEZHAT_DOC = {
    "verb_id": "ru_bezhat",
    "language": "ru",
    "lemma": "бежать",
    "search_extract": ["бежать", "run"],
    "rank": 10,
    "forms": {},
    "examples": [],
}

_BEZHAT_ENTRY = VerbEntry(
    id="ru_bezhat",
    rank=10,
    lemma="бежать",
    forms={"infinitive": "бежать"},
    examples=[],
)


def _stub_translate_ru(query, source_lang, target_lang, project, **kwargs):
    mapping = {("run", "en", "ru"): "бежать"}
    return mapping.get((query.lower(), source_lang, target_lang))


def test_search_by_lang_run_to_bezhat_redirects_to_learn(
    client: TestClient, monkeypatch
) -> None:
    """EN search 'run' with lang=ru redirects to бежать's learn page."""
    monkeypatch.setattr("app.routes.home.translate_search_query", _stub_translate_ru)
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: _BEZHAT_DOC
        if (lang == "ru" and query == "бежать")
        else None,
    )

    response = client.get(
        "/search_verb_by_lang?language=ru&q=run&source_lang=en",
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" in location
    assert "ru_bezhat" in location
    assert "language=ru" in location


def test_search_by_lang_run_ru_includes_translated_from_param(
    client: TestClient, monkeypatch
) -> None:
    """Redirect URL carries translated_from=run and source_lang=en for UI breadcrumb."""
    monkeypatch.setattr("app.routes.home.translate_search_query", _stub_translate_ru)
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: _BEZHAT_DOC
        if (lang == "ru" and query == "бежать")
        else None,
    )

    response = client.get(
        "/search_verb_by_lang?language=ru&q=run&source_lang=en",
        follow_redirects=False,
    )

    location = response.headers["location"]
    assert "translated_from=run" in location
    assert "source_lang=en" in location


def test_search_by_lang_run_ru_fuzzy_fallback(client: TestClient, monkeypatch) -> None:
    """Fuzzy fallback finds бежать when Firestore search_extract misses."""
    monkeypatch.setattr("app.routes.home.translate_search_query", _stub_translate_ru)
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract", lambda lang, query: None
    )
    monkeypatch.setattr(
        "app.routes.home.load_entries_for_language",
        lambda language: [_BEZHAT_ENTRY],
    )

    response = client.get(
        "/search_verb_by_lang?language=ru&q=run&source_lang=en",
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" in location
    assert "ru_bezhat" in location


# ---------------------------------------------------------------------------
# /search_verb_by_lang -- English -> Hebrew ("run" -> "לרוץ")
# ---------------------------------------------------------------------------

_LARUTZ_DOC = {
    "verb_id": "he_larutz",
    "language": "he",
    "lemma": "לרוץ",
    "search_extract": ["לרוץ", "run"],
    "rank": 10,
    "forms": {},
    "examples": [],
}

_LARUTZ_ENTRY = VerbEntry(
    id="he_larutz",
    rank=10,
    lemma="לרוץ",
    forms={"infinitive": "לרוץ"},
    examples=[],
)


def _stub_translate_he(query, source_lang, target_lang, project, **kwargs):
    mapping = {("run", "en", "he"): "לרוץ"}
    return mapping.get((query.lower(), source_lang, target_lang))


def test_search_by_lang_run_to_larutz_redirects_to_learn(
    client: TestClient, monkeypatch
) -> None:
    """EN search 'run' with lang=he redirects to לרוץ's learn page."""
    monkeypatch.setattr("app.routes.home.translate_search_query", _stub_translate_he)
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: _LARUTZ_DOC if (lang == "he" and query == "לרוץ") else None,
    )

    response = client.get(
        "/search_verb_by_lang?language=he&q=run&source_lang=en",
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" in location
    assert "he_larutz" in location
    assert "language=he" in location


def test_search_by_lang_run_he_includes_translated_from_param(
    client: TestClient, monkeypatch
) -> None:
    """Redirect URL carries translated_from=run and source_lang=en for UI breadcrumb."""
    monkeypatch.setattr("app.routes.home.translate_search_query", _stub_translate_he)
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: _LARUTZ_DOC if (lang == "he" and query == "לרוץ") else None,
    )

    response = client.get(
        "/search_verb_by_lang?language=he&q=run&source_lang=en",
        follow_redirects=False,
    )

    location = response.headers["location"]
    assert "translated_from=run" in location
    assert "source_lang=en" in location


def test_search_by_lang_run_he_fuzzy_fallback(client: TestClient, monkeypatch) -> None:
    """Fuzzy fallback finds לרוץ when Firestore search_extract misses."""
    monkeypatch.setattr("app.routes.home.translate_search_query", _stub_translate_he)
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract", lambda lang, query: None
    )
    monkeypatch.setattr(
        "app.routes.home.load_entries_for_language",
        lambda language: [_LARUTZ_ENTRY],
    )

    response = client.get(
        "/search_verb_by_lang?language=he&q=run&source_lang=en",
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" in location
    assert "he_larutz" in location


def test_search_verb_native_mode_cannot_find_es_verb_by_english_word(
    client: TestClient, monkeypatch
) -> None:
    """
    The /search_verb (native) endpoint searches search_extract for the raw query.
    Searching 'run' in native mode for lang=es does NOT hit correr because the
    search_extract array contains Spanish words, not English translations.
    This documents that the EN pill (/search_verb_by_lang) is required for
    cross-language search to work.
    """
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: None,  # "run" not in ES search_extract
    )
    monkeypatch.setattr(
        "app.routes.home.log_missing_verb_search",
        lambda **kwargs: None,
    )
    # _load_entries returns empty list so fuzzy also fails
    monkeypatch.setattr(
        "app.routes.home.list_verbs_recent",
        lambda language, limit=20: [],
    )

    response = client.get(
        "/search_verb?language=es&q=run",
        follow_redirects=False,
    )

    location = response.headers["location"]
    assert "/learn" not in location
    assert "not_available=1" in location
