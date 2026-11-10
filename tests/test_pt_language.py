"""Brazilian Portuguese (pt): plugin board, registration, voices, pronouns, example tagging."""

from core.example_targets import tag_sentence
from core.languages.config import ALL_STUDY_LANGUAGES, FREE_STUDY_LANGUAGES, STUDY_LANGUAGE_SCRIPTS
from core.languages.pt.plugin import build_board
from core.models import VerbEntry
from core.pronouns import PRONOUNS
from core.registry import all_plugins
from core.settings_ai import _LANG_PROMPTS
from core.tts import VOICES

_SLOTS = {"eu": "a", "ele": "b", "nos": "c", "eles": "d"}
PT = {
    "present": {"eu": "falo", "ele": "fala", "nos": "falamos", "eles": "falam"},
    "preterite": {"eu": "falei", "ele": "falou", "nos": "falamos", "eles": "falaram"},
    "imperative": {"voce": "fale", "nos": "falemos", "voces": "falem"},
}


def _board(forms: dict):
    verb = VerbEntry(id="pt_x", rank=1, lemma="falar", forms=forms, examples=[])
    return build_board(verb, "female", "F")


def test_pt_is_a_free_registered_study_language():
    assert "pt" in FREE_STUDY_LANGUAGES
    assert "pt" in ALL_STUDY_LANGUAGES
    assert "pt" in all_plugins()
    assert "pt" in STUDY_LANGUAGE_SCRIPTS
    assert set(VOICES["pt"]) == {"female", "male"}
    assert VOICES["pt"]["female"].edge_id.startswith("pt-BR-")
    assert len(PRONOUNS["pt"]) == 6


def test_optional_sections_render_only_when_present():
    titles = [s["title"] for s in _board({"present": _SLOTS}).sections if s.get("title")]
    assert not any("conditional" in t or "subjunctive" in t or "imperative" in t for t in titles)
    full = {
        "present": _SLOTS,
        "conditional": _SLOTS,
        "subjunctive_present": _SLOTS,
        "subjunctive_imperfect": _SLOTS,
        "imperative": {"voce": "fale"},
    }
    titles = [s["title"] for s in _board(full).sections if s.get("title")]
    for key in ("conditional", "subjunctive_present", "subjunctive_imperfect", "imperative"):
        assert f"board.tense_{key}" in titles


def test_prompt_asks_for_brazilian_forms():
    prompt = _LANG_PROMPTS["pt"]
    assert "Brazilian" in prompt and "voce" in prompt


def test_example_is_tagged_with_pronoun_aware_cell():
    target = tag_sentence("pt", "Ontem eu falei com minha mãe.", PT)
    assert target is not None
    assert (target["tense"], target["person"], target["answer"]) == ("preterite", "eu", "falei")


def test_board_row_keys_and_others_section():
    forms = {**PT, "gerund": "falando", "participle": "falado"}
    sections = _board(forms).sections
    keys = [row["key"] for section in sections for row in section["rows"]]
    assert {"lemma", "pres_eu", "pres_eles", "pret_ele", "imper_voce", "imper_voces", "gerund", "participle"} <= set(
        keys
    )


def test_autogen_uses_gemini_not_claude_for_pt():
    from core.verb_autogen import _CLAUDE_AUTOGEN_LANGUAGES, AUTOGEN_LANGUAGES

    assert "pt" in AUTOGEN_LANGUAGES
    assert "pt" not in _CLAUDE_AUTOGEN_LANGUAGES


def test_fill_form_shape_matches_board_slots():
    from core.fill_practice_service import _FORM_SHAPES

    shape = _FORM_SHAPES["pt"]
    assert shape["present"] == ("eu", "ele", "nos", "eles")
    assert shape["imperative"] == ("voce", "nos", "voces")


def test_sentence_opening_with_shared_form_is_labelled_imperative():
    forms = {"subjunctive_present": {"eu": "fale", "ele": "fale"}, "imperative": {"voce": "fale"}}
    target = tag_sentence("pt", "Fale mais alto!", forms)
    assert target is not None
    assert target["tense"] == "imperative"


def test_pt_plausible_query_gate():
    from core.verb_autogen import is_plausible_verb_query

    assert is_plausible_verb_query("falar", "pt")
    assert is_plausible_verb_query("pôr", "pt")
    assert is_plausible_verb_query("começar", "pt")
    for stop_word in ("um", "os", "as", "uma"):
        assert not is_plausible_verb_query(stop_word, "pt")
    assert not is_plausible_verb_query("falar muito bem", "pt")
    assert not is_plausible_verb_query("привет", "pt")


def _run_seed(monkeypatch, provider):
    import asyncio

    from core import verb_autogen
    from tools import seed_verbs

    monkeypatch.setattr(verb_autogen, "_CLAUDE_AUTOGEN_LANGUAGES", frozenset({"ru"}))
    monkeypatch.setattr(seed_verbs, "load_settings", lambda: type("S", (), {"audio_bucket": "b"})())
    monkeypatch.setattr(seed_verbs, "create_audio_backend", lambda settings: object())
    monkeypatch.setattr(seed_verbs, "list_verbs", lambda language: [])
    calls = []

    async def fake_autogen(**kwargs):
        calls.append(kwargs["query"])

    monkeypatch.setattr(seed_verbs.verb_autogen, "autogenerate_missing_verb", fake_autogen)
    asyncio.run(seed_verbs.main("pt", provider))
    return verb_autogen._CLAUDE_AUTOGEN_LANGUAGES, calls


def test_seed_provider_gemini_leaves_claude_set_untouched(monkeypatch):
    claude_languages, calls = _run_seed(monkeypatch, "gemini")
    assert "pt" not in claude_languages
    assert calls


def test_seed_provider_claude_adds_language(monkeypatch):
    claude_languages, calls = _run_seed(monkeypatch, "claude")
    assert "pt" in claude_languages
    assert calls
