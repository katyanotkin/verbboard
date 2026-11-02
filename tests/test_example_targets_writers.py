"""Every writer of examples tags them; the prompts ask for the hint; the backfill tool is safe."""

from __future__ import annotations

import pytest

from core.example_targets import tag_examples
from core.settings_ai import _LANG_PROMPTS
from core.verb_autogen import _normalize_generated
from tools.backfill_example_targets import plan_verb

ES_FORMS = {"preterite": {"el": "abrió"}, "present": {"el": "abre"}}


@pytest.mark.parametrize("language", sorted(_LANG_PROMPTS))
def test_every_language_prompt_asks_for_form_and_answer_hints(language):
    prompt = _LANG_PROMPTS[language]
    assert '"form"' in prompt and '"answer"' in prompt, f"{language} prompt lacks the example tagging contract"


def test_autogen_normalizer_tags_examples_for_both_providers():
    generated = {
        "lemma": "abrir",
        "forms": ES_FORMS,
        "examples": [{"dst": "El camarero abrió una botella.", "form": "preterite.el", "answer": "abrió"}],
    }
    (example,) = _normalize_generated("es", generated)["examples"]
    assert example["target"]["answer"] == "abrió"
    assert "form" not in example and "answer" not in example


def test_autogen_normalizer_tags_russian_after_stripping_stress_marks():
    generated = {
        "lemma": "мыть",
        "forms": {"present": {"1sg": "мою"}},
        "examples": [{"dst": "Я мо́ю посуду."}],
    }
    (example,) = _normalize_generated("ru", generated)["examples"]
    assert example["dst"] == "Я мою посуду."
    assert example["target"]["answer"] == "мою"
    assert example["dst"][example["target"]["start"] : example["target"]["end"]] == "мою"


def test_bad_generator_hint_falls_back_to_deterministic_tagging():
    examples = [{"dst": "El camarero abrió una botella.", "form": "present.el", "answer": "abre"}]
    (tagged,) = tag_examples("es", ES_FORMS, examples)
    assert tagged["target"]["tense"] == "preterite"


def test_translations_survive_tagging():
    (tagged,) = tag_examples("es", ES_FORMS, [{"dst": "El camarero abrió una botella.", "translations": {"en": "x"}}])
    assert tagged["translations"] == {"en": "x"}


# --- backfill planning (pure) --------------------------------------------------------------


def _doc(examples):
    return {"verb_id": "es_abrir", "language": "es", "forms": ES_FORMS, "examples": examples}


def test_plan_tags_untagged_and_reports_status():
    new, rows, changed = plan_verb("es", _doc([{"dst": "El camarero abrió una botella."}, {"dst": "Quiero comer."}]))
    assert changed
    assert [r["status"] for r in rows] == ["tagged", "no_match"]
    assert new[0]["target"]["answer"] == "abrió" and "target" not in new[1]


def test_plan_is_idempotent_second_run_changes_nothing():
    first, _, _ = plan_verb("es", _doc([{"dst": "El camarero abrió una botella."}]))
    second, rows, changed = plan_verb("es", _doc(first))
    assert not changed and second == first
    assert [r["status"] for r in rows] == ["kept"]


def test_plan_drops_stale_target_and_says_so():
    tagged, _, _ = plan_verb("es", _doc([{"dst": "El camarero abrió una botella."}]))
    stale = [{**tagged[0], "dst": "El mesero abrió una botella."}]
    new, rows, changed = plan_verb("es", _doc(stale))
    assert rows[0]["status"] == "tagged"  # the new sentence is re-tagged from scratch
    assert changed and new[0]["target"]["start"] == len("El mesero ")


def test_plan_does_not_write_anything_for_verbs_without_examples():
    new, rows, changed = plan_verb("es", {"verb_id": "x", "language": "es", "forms": ES_FORMS})
    assert (new, rows, changed) == ([], [], False)
