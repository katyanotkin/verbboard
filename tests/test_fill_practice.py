"""Backend of the "fill the form" practice page: page data, route, counters, analytics, board link."""

from __future__ import annotations

import json
import re
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from core import fill_practice_service as service
from core.audio_service import build_hashed_audio_key
from core.auth.models import AuthUser
from core.example_targets import tag_sentence
from core.models import Board, Example, VerbEntry

ES_FORMS = {
    "present": {"yo": "abro", "tu": "abres", "el": "abre", "nos": "abrimos", "vosotros": "abrís", "ellos": "abren"},
    "preterite": {
        "yo": "abrí",
        "tu": "abriste",
        "el": "abrió",
        "nos": "abrimos",
        "vosotros": "abristeis",
        "ellos": "abrieron",
    },
    "gerund": "abriendo",
}


def _tagged(sentence: str, translation: str = "") -> Example:
    target = tag_sentence("es", sentence, ES_FORMS)
    assert target is not None, sentence
    return Example(dst=sentence, translations={"en": translation} if translation else {}, target=target)


def _es_verb(verb_id: str = "es_abrir") -> VerbEntry:
    return VerbEntry(
        id=verb_id,
        rank=1,
        lemma="abrir",
        forms=ES_FORMS,
        examples=[
            Example(dst="Una frase sin etiqueta."),
            _tagged("El camarero abrió una botella.", "The waiter opened a bottle."),
            _tagged("Nosotros abrimos la puerta."),
            _tagged("Ella está abriendo la ventana."),
        ],
    )


@pytest.fixture()
def es_entries(monkeypatch):
    entries = [_es_verb("es_abrir"), _es_verb("es_abrir2")]
    monkeypatch.setattr(service, "load_entries_for_language", lambda language: entries if language == "es" else [])
    return entries


# ── page data ───────────────────────────────────────────────────────────────


def test_items_only_from_tagged_examples_with_audio_matching_render(es_entries) -> None:
    data = service.build_fill_page_data("es", "en", "es_abrir", seed=1)
    assert {item["id"] for item in data["items"]} == {"es_abrir:2", "es_abrir:3", "es_abrir:4"}
    item = next(i for i in data["items"] if i["id"] == "es_abrir:2")
    assert (item["prefix"], item["answer"], item["suffix"]) == ("El camarero ", "abrió", " una botella.")
    assert item["translation"] == "The waiter opened a bottle."
    assert item["audioSrc"] == (
        f"/audio/es/es_abrir/female/{build_hashed_audio_key('example_2', 'El camarero abrió una botella.')}.mp3"
    )
    assert item["verbId"] == "es_abrir" and item["lemma"] == "abrir"


def test_audio_url_equals_what_render_emits(es_entries) -> None:
    from core.render import render_board_html

    verb = es_entries[0]
    board = Board(language="es", verb=verb, voice_key="female", voice_label="F", sections=[])
    html = render_board_html(board, ui_strings={}, ui_lang="en")
    for item in service.build_fill_page_data("es", "en", "es_abrir", seed=1)["items"]:
        assert f"src='{item['audioSrc']}'" in html


def test_label_has_tense_and_person_localized(es_entries) -> None:
    items = {i["id"]: i for i in service.build_fill_page_data("es", "en", "es_abrir", seed=1)["items"]}
    assert items["es_abrir:2"]["label"] == "Preterite · él/ella/Ud."
    ru_items = {i["id"]: i for i in service.build_fill_page_data("es", "ru", "es_abrir", seed=1)["items"]}
    assert "abrir" not in ru_items["es_abrir:2"]["label"]  # the page shows the lemma separately
    assert "Preterite" not in ru_items["es_abrir:2"]["label"]
    assert "_" not in ru_items["es_abrir:4"]["label"]


def test_also_labels_joined(es_entries) -> None:
    example = es_entries[0].examples[2]
    example.target["also"] = ["present.nos"]  # type: ignore[index]
    item = next(
        i for i in service.build_fill_page_data("es", "en", "es_abrir", seed=1)["items"] if i["id"] == "es_abrir:3"
    )
    assert item["label"].count(" / ") >= 1 and "Present" in item["label"]


def test_unknown_cell_label_never_leaks_underscores() -> None:
    label = service._cell_label("es", "weird_tense.some_person", {}, {})
    assert label == "weird tense · some person"


def test_translation_never_native_sentence(es_entries) -> None:
    items = service.build_fill_page_data("es", "es", "es_abrir", seed=1)["items"]
    assert all(i["translation"] == "" for i in items)
    items = service.build_fill_page_data("es", "en", "es_abrir", seed=1)["items"]
    assert [i["translation"] for i in items if i["id"] == "es_abrir:3"] == [""]


def test_spread_seed_and_scoping(es_entries) -> None:
    first = service.build_fill_page_data("es", "en", seed=7, max_per_verb=1)
    assert len(first["items"]) == 2 and {i["verbId"] for i in first["items"]} == {"es_abrir", "es_abrir2"}
    assert first == service.build_fill_page_data("es", "en", seed=7, max_per_verb=1)
    assert len(service.build_fill_page_data("es", "en", seed=7, max_per_verb=2)["items"]) == 4
    assert len(service.build_fill_page_data("es", "en", seed=7, max_items=3, max_per_verb=3)["items"]) == 3
    scoped = service.build_fill_page_data("es", "en", "es_abrir2", seed=7)
    assert {i["verbId"] for i in scoped["items"]} == {"es_abrir2"} and scoped["verbId"] == "es_abrir2"


def test_strings_filtered_to_fill_prefix_and_empty_pool(es_entries, monkeypatch) -> None:
    data = service.build_fill_page_data("es", "en", seed=1)
    assert all(key.startswith("fill.") for key in data["strings"])
    assert data["limits"] == {"sessionSize": 8} and data["studyDir"] == "ltr"
    assert service.build_fill_page_data("it", "en")["items"] == []


def test_board_labels_cover_every_shape_cell() -> None:
    for language, shape in service._FORM_SHAPES.items():
        labels = service._board_labels(language)
        for tense, persons in shape.items():
            paths = [tense] if persons is None else [f"{tense}.{p}" for p in persons]
            for path in paths:
                assert path in labels, (language, path)


def test_default_languages_exclude_hebrew(monkeypatch) -> None:
    from core.settings import load_settings

    monkeypatch.delenv("FILL_PRACTICE_LANGUAGES", raising=False)
    assert set(load_settings().fill_practice_languages) == {"en", "es", "it", "fr", "ru", "tr"}
    monkeypatch.setenv("FILL_PRACTICE_LANGUAGES", "he,es,xx")
    assert load_settings().fill_practice_languages == ("he", "es")


def test_page_data_json_escapes_script_breakers() -> None:
    out = service.page_data_to_json({"x": "</script><b>&\u2028\u2029"})
    assert not any(ch in out for ch in "<>&\u2028\u2029")
    assert json.loads(out)["x"] == "</script><b>&\u2028\u2029"


# ── route ───────────────────────────────────────────────────────────────────


@pytest.fixture()
def stub_template(tmp_path, monkeypatch):
    (tmp_path / "practice_fill.html").write_text(
        "empty={{ empty }}|dir={{ html_dir }}|study={{ study_dir }}|back={{ back_href }}|"
        "lang={{ language }}|ui={{ ui_language }}|DATA={{ page_data_json | safe }}"
    )
    monkeypatch.setattr("app.routes.practice_fill.templates", Jinja2Templates(directory=str(tmp_path)))


def test_route_renders_with_context(client: TestClient, es_entries, stub_template) -> None:
    resp = client.get("/practice/fill?language=es&ui_language=he&verb_id=es_abrir")
    assert resp.status_code == 200
    assert "empty=False" in resp.text and "dir=rtl" in resp.text and "study=ltr" in resp.text
    assert "back=/learn?language=es&amp;verb_id=es_abrir&amp;ui_language=he" in resp.text
    data = json.loads(resp.text.split("DATA=", 1)[1])
    assert data["verbId"] == "es_abrir" and data["items"]


def test_route_back_href_without_verb(client: TestClient, es_entries, stub_template) -> None:
    resp = client.get("/practice/fill?language=es&ui_language=en")
    assert "back=/verbs?language=es&amp;ui_language=en" in resp.text


def test_route_empty_pool_still_renders(client: TestClient, monkeypatch, stub_template) -> None:
    monkeypatch.setattr(service, "load_entries_for_language", lambda language: [])
    resp = client.get("/practice/fill?language=es&ui_language=en")
    assert resp.status_code == 200 and "empty=True" in resp.text


def test_route_escapes_script_close_in_sentence(client: TestClient, monkeypatch, stub_template) -> None:
    verb = _es_verb()
    sentence = "Ella abrió </script><script>alert(1)</script>."
    target = tag_sentence("es", sentence, ES_FORMS)
    assert target is not None
    verb.examples.append(Example(dst=sentence, target=target))
    monkeypatch.setattr(service, "load_entries_for_language", lambda language: [verb])
    body = client.get("/practice/fill?language=es&ui_language=en&verb_id=es_abrir").text
    assert "</script>" not in body and "<script>" not in body
    assert "\\u003c/script\\u003e" in body


def test_real_template_embeds_escaped_data_and_no_answer_outside_the_json(client: TestClient, monkeypatch) -> None:
    verb = _es_verb()
    sentence = "Ella abrió </script><script>alert(1)</script>."
    target = tag_sentence("es", sentence, ES_FORMS)
    assert target is not None
    verb.examples.append(Example(dst=sentence, target=target))
    monkeypatch.setattr(service, "load_entries_for_language", lambda language: [verb])
    body = client.get("/practice/fill?language=es&ui_language=en&verb_id=es_abrir").text
    assert "<script>alert(1)" not in body
    start = body.index('<script id="fill-data"')
    block = body[body.index(">", start) + 1 : body.index("</script>", start)]
    data = json.loads(block)
    assert any("</script>" in item["suffix"] for item in data["items"])
    assert data["strings"]["fill.check"]


def test_route_404_when_switch_off_or_language_not_allowed(
    client: TestClient, es_entries, stub_template, monkeypatch
) -> None:
    assert client.get("/practice/fill?language=he&ui_language=en").status_code == 404
    assert client.get("/practice/fill?language=xx&ui_language=en").status_code == 404
    monkeypatch.setenv("FILL_PRACTICE_ENABLED", "false")
    assert client.get("/practice/fill?language=es&ui_language=en").status_code == 404


def test_route_he_enabled_via_allow_list(client: TestClient, monkeypatch, stub_template) -> None:
    monkeypatch.setenv("FILL_PRACTICE_LANGUAGES", "he")
    monkeypatch.setattr(service, "load_entries_for_language", lambda language: [])
    resp = client.get("/practice/fill?language=he&ui_language=en")
    assert resp.status_code == 200 and "study=rtl" in resp.text


def test_route_plus_language_redirects(client: TestClient, monkeypatch, stub_template) -> None:
    monkeypatch.setenv("FILL_PRACTICE_LANGUAGES", "tr")
    resp = client.get("/practice/fill?language=tr&ui_language=en", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/verbs?language=tr&plus_required=1&ui_language=en"


def test_route_plus_only_feature_redirects_anonymous(
    client: TestClient, es_entries, stub_template, monkeypatch
) -> None:
    monkeypatch.setenv("FILL_PRACTICE_PLUS_ONLY", "true")
    resp = client.get("/practice/fill?language=es&ui_language=en", follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"].startswith("/feedback?page=plus&language=es")


# ── board: inline fill mode (replaces the old entry pill) ─────────────────


def _render(verb: VerbEntry, language: str = "es", ui_lang: str = "en", **kwargs) -> str:
    from core.render import render_board_html

    board = Board(language=language, verb=verb, voice_key="female", voice_label="F", sections=[])
    return render_board_html(board, ui_lang=ui_lang, **kwargs)


def test_no_entry_pill_rendered() -> None:
    html = _render(_es_verb())
    assert "fill-entry-link" not in html and "/practice/fill" not in html


def test_toggle_renders_for_tagged_verb_with_row_attributes() -> None:
    from html import unescape

    html = _render(_es_verb())
    assert "id='fill-toggle'" in html and "Fill in the blank" in html
    assert "id='fill-banner'" in html
    assert "/static/fill_inline.js" in html and "/static/fill_grade.js" in html
    assert html.index("fill_grade.js") < html.index("fill_inline.js")
    # Three tagged rows; the untagged first sentence carries no fill attributes.
    assert html.count("class='fill-row'") == 3
    row = re.search(
        r"<tr class='fill-row' data-fill-index='\d+' data-fill-lemma='[^']*' data-fill-start='(\d+)' data-fill-end='(\d+)' data-fill-label='([^']*)'",
        html,
    )
    assert row is not None
    start, end = int(row.group(1)), int(row.group(2))
    assert "El camarero abrió una botella."[start:end] == "abrió"
    assert unescape(row.group(3)) == "Preterite · él/ella/Ud."
    assert "data-fill-alts='[]'" in html


def test_row_attributes_are_attribute_escaped() -> None:
    verb = _es_verb()
    verb.examples[1].target["also"] = ["present.nos"]  # type: ignore[index]
    verb.examples[1].target["alternatives"] = ["a'b\"<x>"]  # type: ignore[index]
    html = _render(verb)
    assert "a'b" not in html and "<x>" not in html
    assert "&quot;" in html and "&#x27;" in html and "&lt;x&gt;" in html


@pytest.mark.parametrize("language", ["he", "ru", "tr"])
def test_toggle_absent_for_languages_outside_inline_list(language) -> None:
    html = _render(_es_verb(), language=language)
    assert "fill-toggle" not in html and "fill-row" not in html


def test_toggle_absent_without_targets_candidate_disabled_or_plus_gate(monkeypatch) -> None:
    untagged = VerbEntry(id="es_x", rank=1, lemma="x", forms={}, examples=[Example(dst="Hola.")])
    assert "fill-toggle" not in _render(untagged)
    assert "fill-toggle" not in _render(_es_verb(), candidate_verb_id="es_abrir")
    assert "fill-toggle" not in _render(_es_verb(), fill_practice_allowed=False)
    monkeypatch.setenv("FILL_PRACTICE_ENABLED", "false")
    assert "fill-toggle" not in _render(_es_verb())


def test_inline_languages_setting_parses(monkeypatch) -> None:
    from core.settings import _parse_fill_inline_languages

    assert _parse_fill_inline_languages("") == ("en", "es", "it", "fr")
    assert _parse_fill_inline_languages(" ES , xx, fr ") == ("es", "fr")
    monkeypatch.setenv("FILL_INLINE_LANGUAGES", "it")
    assert service.fill_inline_available("it") and not service.fill_inline_available("es")


# ── counters ────────────────────────────────────────────────────────────────

USER = AuthUser(uid="u1", email="u@example.com", name="U", picture="")


@pytest.fixture()
def signed_in(monkeypatch):
    monkeypatch.setattr("app.routes.api_progress.get_optional_auth_user", lambda request: USER)


def _post(client, **body):
    payload = {"language": "es", "answers": 8, "correct": 6, "completed": True}
    payload.update(body)
    return client.post("/api/progress/fill_session", json=payload)


def test_fill_session_requires_auth(client: TestClient) -> None:
    assert _post(client).status_code == 401


def test_fill_session_increments_and_creates_missing_doc(client, signed_in, fake_db) -> None:
    path = "user_practice/u1/languages/es"
    assert _post(client).status_code == 200
    doc = fake_db.collection("user_practice").document("u1").collection("languages").document("es").get().to_dict()
    assert (doc["fill_started"], doc["fill_completed"], doc["fill_answers"], doc["fill_correct"]) == (1, 1, 8, 6)
    assert doc["fill_last_at"] is not None and "badges" not in doc, path
    assert _post(client, answers=4, correct=1, completed=False).status_code == 200
    doc = fake_db.collection("user_practice").document("u1").collection("languages").document("es").get().to_dict()
    assert (doc["fill_started"], doc["fill_completed"], doc["fill_answers"], doc["fill_correct"]) == (2, 1, 12, 7)


def test_fill_session_inline_only_touches_answer_counters(client, signed_in, fake_db) -> None:
    assert _post(client, answers=5, correct=3, completed=False, mode="inline").status_code == 200
    ref = fake_db.collection("user_practice").document("u1").collection("languages").document("es")
    doc = ref.get().to_dict()
    assert (doc["fill_answers"], doc["fill_correct"]) == (5, 3)
    assert "fill_started" not in doc and "fill_completed" not in doc and doc["fill_last_at"] is not None
    assert _post(client).status_code == 200  # a practice round still counts started/completed
    doc = ref.get().to_dict()
    assert (doc["fill_started"], doc["fill_completed"], doc["fill_answers"]) == (1, 1, 13)


def test_fill_session_rejects_unknown_mode(client, signed_in, fake_db) -> None:
    assert _post(client, mode="bogus").status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"language": "xx"},
        {"answers": 201, "correct": 0},
        {"answers": 3, "correct": 4},
        {"answers": -1, "correct": -1},
        {"correct": -1},
    ],
)
def test_fill_session_validation(client, signed_in, fake_db, body) -> None:
    assert _post(client, **body).status_code == 400


def test_fill_session_rate_limited(client, signed_in, monkeypatch) -> None:
    from core.rate_limit import SlidingWindowRateLimiter

    monkeypatch.setattr(
        "app.routes.api_progress._FILL_SESSION_RATE_LIMITER", SlidingWindowRateLimiter(max_calls=1, window_seconds=600)
    )
    assert _post(client).status_code == 200
    assert _post(client).status_code == 429


def test_account_deletion_removes_fill_counters(client, signed_in, fake_db) -> None:
    from core.progress.progress_repository import delete_all_progress_data

    _post(client)
    delete_all_progress_data("u1")
    snap = fake_db.collection("user_practice").document("u1").collection("languages").document("es").get()
    assert not snap.exists


# ── analytics ───────────────────────────────────────────────────────────────


def test_fill_started_event_dispatches(client: TestClient) -> None:
    with patch("app.routes.api_analytics.record_fill_started", new_callable=AsyncMock) as mock:
        resp = client.post("/api/analytics/practice_event", json={"event": "fill_started"})
    assert resp.json() == {"ok": True}
    mock.assert_awaited_once()


def test_record_fill_started_set_once_without_stub(fake_db) -> None:
    from core.analytics.session_tracker import _record_fill_started

    _record_fill_started("fp9", "2026-11-01")
    assert not fake_db.collection("analytics_sessions").document("2026-11-01_fp9").get().exists
    fake_db.collection("analytics_sessions").document("2026-11-01_fp9").set({"uid": "a"})
    _record_fill_started("fp9", "2026-11-01")
    data = fake_db.collection("analytics_sessions").document("2026-11-01_fp9").get().to_dict()
    assert data["fill_started"] is True and data["uid"] == "a"


def test_report_engagement_includes_fill_started() -> None:
    from core.admin_report_service import _REPORT_FLAGS

    assert "fill_started" in _REPORT_FLAGS
