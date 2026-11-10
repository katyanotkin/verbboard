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
    assert "pt" in all_plugins() or _board({"present": _SLOTS}).language == "pt"
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
