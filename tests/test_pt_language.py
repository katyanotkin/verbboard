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


def test_future_subjunctive_section_renders_when_present():
    full = {
        "present": _SLOTS,
        "subjunctive_future": {"eu": "falar", "ele": "falar", "nos": "falarmos", "eles": "falarem"},
    }
    titles = [s["title"] for s in _board(full).sections if s.get("title")]
    assert "board.tense_subjunctive_future" in titles
    assert "board.tense_subjunctive_future" not in [
        s["title"] for s in _board({"present": _SLOTS}).sections if s.get("title")
    ]


def test_infinitive_shaped_future_subjunctive_never_tags_a_plain_infinitive():
    forms = {"present": {"eu": "quero"}, "subjunctive_future": {"eu": "falar", "ele": "falar"}}
    target = tag_sentence("pt", "Eu quero falar com você.", forms)
    assert target is not None
    assert target["tense"] == "present"


def test_hint_can_tag_future_subjunctive():
    from core.example_targets import tag_from_hint

    forms = {"subjunctive_future": {"eu": "puder", "ele": "puder"}}
    target = tag_from_hint("pt", "Quando eu puder, ligo para você.", forms, "subjunctive_future.eu", "puder")
    assert target is not None and target["tense"] == "subjunctive_future"


def test_normalizer_rewrites_accented_imperative_keys_and_hints():
    from core.languages.pt.forms import normalize_pt_payload

    payload = {
        "forms": {"imperative": {"você": "durma", "nós": "durmamos", "vocês": "durmam"}, "present": {"eu": "durmo"}},
        "examples": [{"dst": "Durma bem.", "form": "imperative.você", "answer": "Durma"}],
    }
    result = normalize_pt_payload(payload)
    assert set(result["forms"]["imperative"]) == {"voce", "nos", "voces"}
    assert result["examples"][0]["form"] == "imperative.voce"
    assert result["forms"]["present"] == {"eu": "durmo"}


def test_normalizer_is_wired_into_autogen():
    from core.verb_autogen import _normalize_generated

    payload = {"forms": {"imperative": {"você": "fale"}}, "examples": []}
    assert "voce" in _normalize_generated("pt", payload)["forms"]["imperative"]


def test_normalizer_tolerates_garbage():
    from core.languages.pt.forms import normalize_pt_payload

    assert normalize_pt_payload(None) is None
    assert normalize_pt_payload({"forms": "x"}) == {"forms": "x"}


def test_normalizer_maps_voce_to_ele_outside_the_imperative():
    from core.languages.pt.forms import normalize_pt_payload

    payload = {"forms": {"present": {"eu": "falo", "você": "fala", "vocês": "falam", "nós": "falamos"}}, "examples": []}
    assert normalize_pt_payload(payload)["forms"]["present"] == {
        "eu": "falo",
        "ele": "fala",
        "eles": "falam",
        "nos": "falamos",
    }


def test_normalizer_prefers_explicit_canonical_key_over_alias():
    from core.languages.pt.forms import normalize_pt_payload

    payload = {"forms": {"present": {"ela": "y", "ele": "z"}}}
    assert normalize_pt_payload(payload)["forms"]["present"] == {"ele": "z"}


def test_retag_keeps_valid_hint_only_future_subjunctive_target():
    from core.example_targets import tag_examples, tag_from_hint

    forms = {"subjunctive_future": {"eu": "puder", "ele": "puder"}}
    sentence = "Quando eu puder, ligo para você."
    target = tag_from_hint("pt", sentence, forms, "subjunctive_future.eu", "puder")
    result = tag_examples("pt", forms, [{"dst": sentence, "target": target}], retag=True)
    assert result[0]["target"]["tense"] == "subjunctive_future"


def test_backfill_derives_forms_from_preterite_eles():
    from tools.backfill_pt_subjunctive_future import derive_forms

    assert derive_forms("falaram") == {"eu": "falar", "ele": "falar", "nos": "falarmos", "eles": "falarem"}
    assert derive_forms("foram")["nos"] == "formos"
    assert derive_forms("se levantaram")["eu"] == "me levantar"
    assert derive_forms("se levantaram")["eles"] == "se levantarem"
    assert derive_forms("") is None


def test_admin_call_claude_normalizes_pt_only(monkeypatch):
    import asyncio
    import json
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace

    from app.routes import admin_candidates

    payload = {"lemma": "dormir", "forms": {"imperative": {"você": "durma"}}, "examples": []}

    class _Messages:
        async def create(self, **_kwargs):
            return SimpleNamespace(content=[SimpleNamespace(text=json.dumps(payload))])

    monkeypatch.setattr(admin_candidates, "get_anthropic_client", lambda: SimpleNamespace(messages=_Messages()))
    monkeypatch.setattr(admin_candidates, "get_cached_system", lambda _language: "")

    def run(language):
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, admin_candidates._call_claude(language, "dormir")).result()

    assert run("pt")["forms"]["imperative"] == {"voce": "durma"}
    assert "você" in run("es")["forms"]["imperative"]


def test_subjunctive_future_title_in_all_locales():
    import json
    from pathlib import Path

    for locale in ("en", "es", "ru", "he"):
        data = json.loads(Path(f"app/i18n/{locale}.json").read_text(encoding="utf-8"))
        assert data.get("board.tense_subjunctive_future"), locale


def test_backfill_skips_doc_changed_since_read(monkeypatch, fake_db):
    from google.api_core.exceptions import FailedPrecondition

    from tools import backfill_pt_subjunctive_future as tool

    class _Ref:
        def update(self, *_a, **_k):
            raise FailedPrecondition("changed")

    class _Snap:
        id = "pt_falar"
        update_time = None
        reference = _Ref()

        def to_dict(self):
            return {"lemma": "falar", "rank": 1, "forms": {"preterite": {"eles": "falaram"}}, "examples": []}

    class _Query:
        def stream(self):
            return [_Snap()]

        def where(self, *_a, **_k):
            return self

    class _Db:
        def collection(self, _name):
            return _Query()

        def write_option(self, **_k):
            return None

    monkeypatch.setattr(tool, "get_db", lambda: _Db())
    monkeypatch.setattr(tool, "build_example", lambda *_a: {"dst": "x", "translations": {}, "target": {}})
    monkeypatch.setattr("sys.argv", ["tool", "--execute"])
    tool.main()  # must not raise
