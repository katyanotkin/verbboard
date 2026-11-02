"""Example -> form tagging (core/example_targets.py): matcher, validator, loader hook, writers."""

from __future__ import annotations

import pytest

from core.example_targets import (
    MAX_LABELS_PER_TARGET,
    FormCell,
    explain_untagged,
    parse_example_target,
    tag_examples,
    tag_from_hint,
    tag_generated_payload,
    tag_sentence,
    validate_target,
    variants_for,
)
from core.verb_loader import _firestore_document_to_verb_entry

ES = {
    "present": {"yo": "abro", "el": "abre"},
    "imperfect": {"yo": "abría", "el": "abría"},
    "preterite": {"yo": "abrí", "el": "abrió"},
    "subjunctive_imperfect": {"yo": "abriera"},
}
EN = {"base": "put", "past": "put", "past_participle": "put", "present_3sg": "puts", "gerund": "putting"}
FR = {
    "present": {"je": "j'aime", "il": "il aime"},
    "imparfait": {"il": "il aimait"},
    "passe_compose": {"il": "il a aimé"},
}


def _slice(sentence: str, target: dict) -> str:
    return sentence[target["start"] : target["end"]]


# (language, forms, sentence, expected tense, expected person, expected answer)
SINGLE_TAG_CASES = [
    ("es", ES, "El camarero abrió una botella.", "preterite", "el", "abrió"),
    ("en", EN, "She puts it away.", "present_3sg", None, "puts"),
    ("fr", FR, "Mon père aimait le café.", "imparfait", "il", "aimait"),
    ("ru", {"present": {"1sg": "бегаю"}}, "Я бегаю каждое утро.", "present", "1sg", "бегаю"),
    (
        "tr",
        {"present_continuous": {"ben": "alıyorum"}},
        "Her sabah ekmek alıyorum.",
        "present_continuous",
        "ben",
        "alıyorum",
    ),
    ("it", {"presente": {"io": "aiuto"}}, "Aiuto sempre i miei vicini.", "presente", "io", "Aiuto"),
]


@pytest.mark.parametrize("language,forms,sentence,tense,person,answer", SINGLE_TAG_CASES)
def test_unambiguous_sentence_is_tagged(language, forms, sentence, tense, person, answer):
    target = tag_sentence(language, sentence, forms)
    assert target is not None
    assert (target["tense"], target["person"], target["answer"]) == (tense, person, answer)
    assert _slice(sentence, target) == answer  # offsets point into the original text
    assert validate_target(language, sentence, forms, target) == []


def test_shared_surface_form_keeps_all_labels_up_to_the_cap():
    target = tag_sentence("en", "They put it away.", EN)
    assert target is not None
    assert [target["tense"], *target["also"]] == ["base", "past", "past_participle"]
    assert len(target["also"]) + 1 <= MAX_LABELS_PER_TARGET


def test_more_labels_than_cap_is_untagged():
    forms = {f"t{i}": {"yo": "canto"} for i in range(MAX_LABELS_PER_TARGET + 1)}
    assert tag_sentence("es", "Yo canto bien.", forms) is None
    assert explain_untagged("es", "Yo canto bien.", forms) == "too_many_forms"


def test_same_form_twice_in_a_sentence_is_untagged():
    assert tag_sentence("es", "Abre la puerta y abre la ventana.", {"present": {"el": "abre"}}) is None
    assert (
        explain_untagged("es", "Abre la puerta y abre la ventana.", {"present": {"el": "abre"}}) == "ambiguous_position"
    )


def test_no_matching_form_is_untagged():
    assert tag_sentence("es", "La puerta estaba cerrada.", ES) is None
    assert explain_untagged("es", "La puerta estaba cerrada.", ES) == "no_match"


def test_accents_are_strict_outside_he_ru():
    # "abri" without the accent is a different word from the stored "abrí"
    assert tag_sentence("es", "Yo abri la puerta.", {"preterite": {"yo": "abrí"}}) is None


def test_word_boundaries_are_respected():
    assert tag_sentence("es", "Los abrelatas son útiles.", {"present": {"el": "abre"}}) is None


def test_contained_shorter_form_does_not_make_it_ambiguous():
    forms = {"passato_prossimo": {"io": "ho aiutato"}, "participio": "aiutato"}
    target = tag_sentence("it", "Ieri ho aiutato mia madre.", forms)
    assert target is not None and target["answer"] == "ho aiutato"
    assert target["tense"] == "passato_prossimo"


def test_french_pronoun_is_not_part_of_the_blank_and_agreement_is_accepted():
    target = tag_sentence("fr", "Elle a aimée ce film.", FR)
    assert target["answer"] == "a aimée"
    assert "a aimé" in target["alternatives"]
    assert "il a aimé" in target["alternatives"]


def test_slash_alternatives_are_each_accepted():
    cell = FormCell("present", "el", "le gusta / le gustan")
    assert {"le gusta", "le gustan"} <= set(variants_for("es", cell))


def test_spanish_subjunctive_se_variant():
    cell = FormCell("subjunctive_imperfect", "yo", "abriera")
    assert "abriese" in variants_for("es", cell)


# --- subject pronoun picks the label -------------------------------------------------------

HE_PAST = {"past": {"1pl": "נָתַנּוּ", "3pl": "נָתְנוּ"}}


def test_hebrew_subject_pronoun_chooses_between_homographs():
    assert tag_sentence("he", "הם נתנו תשובה.", HE_PAST)["person"] == "3pl"
    assert tag_sentence("he", "אנחנו נתנו תשובה.", HE_PAST)["person"] == "1pl"


def test_hebrew_without_subject_keeps_both_labels():
    target = tag_sentence("he", "נתנו תשובה.", HE_PAST)
    assert target is not None and target.get("also")


def test_hebrew_pointed_word_is_matched_by_its_points():
    forms = {"past": {"3msg": "הֶעֱדִיף"}}
    # a pointed imperative must not be treated as a plene spelling of the past form
    assert tag_sentence("he", "הַעֲדֵף אֶת הַבְּרִיאוּת שֶׁלְּךָ.", forms) is None


def test_hebrew_plene_spelling_is_not_guessed():
    # ביקשו vs the stored בקשו: indistinguishable from a different word (כתוב vs כתב), so untagged
    assert tag_sentence("he", "הם ביקשו מים.", {"past": {"3pl": "בִּקְשׁוּ"}}) is None


def test_hebrew_different_word_with_inner_vav_is_not_tagged_as_the_verb():
    forms = {"past": {"3msg": "כתב"}, "present": {"m_sg": "כותב"}}
    assert tag_sentence("he", "הוא כתוב", forms) is None


def test_trailing_combining_mark_belongs_to_the_span():
    sentence = "אני הולֵךְ הביתה"
    target = tag_sentence("he", sentence, {"present": {"m_sg": "הולך"}})
    assert target is not None and target["answer"] == "הולֵךְ"
    assert validate_target("he", sentence, {"present": {"m_sg": "הולך"}}, target) == []


def test_hebrew_span_never_starts_inside_a_pointed_word():
    # "סְעְנָה" is the tail of "תִּסְעְנָה"; the vowel point under ת must count as part of the word
    forms = {"future": {"2fpl": "תִּסְעְנָה"}, "past": {"3pl": "סְעְנָה"}}
    target = tag_sentence("he", "אתן תִּסְעְנָה ביחד.", forms)
    assert target is not None
    assert (target["tense"], target["answer"]) == ("future", "תִּסְעְנָה")


def test_hebrew_feminine_plural_imperative_is_never_a_target():
    forms = {"imperative": {"fp": "שְׁבְנָה"}}
    assert tag_sentence("he", "שְׁבְנָה כאן.", forms) is None


# --- validation / loader hook -------------------------------------------------------------


def _valid_target():
    return tag_sentence("es", "El camarero abrió una botella.", ES)


def test_validate_rejects_stale_span_after_sentence_edit():
    target = _valid_target()
    assert validate_target("es", "El mesero abrió una botella.", ES, target) != []


def test_validate_rejects_target_when_form_removed():
    target = _valid_target()
    assert "form missing from forms" in validate_target("es", "El camarero abrió una botella.", {"present": {}}, target)


def test_validate_rejects_mid_word_span_and_bad_shapes():
    target = {**_valid_target(), "start": 13, "end": 16, "answer": "rió"}
    assert validate_target("es", "El camarero abrió una botella.", ES, target) != []
    assert validate_target("es", "x", ES, "nope") != []
    assert validate_target("es", "x", ES, {"tense": "present"}) != []


def test_parse_returns_none_for_invalid_and_target_for_valid():
    sentence = "El camarero abrió una botella."
    assert parse_example_target("es", sentence, ES, None) is None
    assert parse_example_target("es", sentence, ES, {**_valid_target(), "end": 99}) is None
    parsed = parse_example_target("es", sentence, ES, _valid_target())
    assert parsed["answer"] == "abrió"


def test_loader_attaches_valid_target_and_heals_stale_one():
    sentence = "El camarero abrió una botella."
    document = {
        "verb_id": "es_abrir",
        "language": "es",
        "lemma": "abrir",
        "forms": ES,
        "examples": [
            {"dst": sentence, "target": _valid_target()},
            {"dst": "El mesero abrió una botella.", "target": _valid_target()},
            {"dst": "Sin etiqueta."},
        ],
    }
    entry = _firestore_document_to_verb_entry(document)
    assert entry.examples[0].target["answer"] == "abrió"
    assert entry.examples[1].target is None
    assert entry.examples[2].target is None


def test_loader_reads_target_offsets_against_src_when_present():
    sentence = "El camarero abrió una botella."
    document = {
        "verb_id": "es_abrir",
        "language": "es",
        "lemma": "abrir",
        "forms": ES,
        "examples": [{"src": sentence, "dst": "The waiter opened a bottle.", "target": _valid_target()}],
    }
    assert _firestore_document_to_verb_entry(document).examples[0].target["answer"] == "abrió"


# --- hints, tag_examples, generated payloads ---------------------------------------------


def test_valid_hint_resolves_an_ambiguous_sentence():
    sentence = "Yo abría la puerta."
    assert tag_sentence("es", sentence, ES)["person"] in {"yo", "el"}  # shares its spelling with el
    target = tag_from_hint("es", sentence, ES, "imperfect.yo", "abría")
    assert target["person"] == "yo" and target["source"] == "generated" and not target.get("also")


@pytest.mark.parametrize(
    "path,answer",
    [("imperfect.tu", "abría"), ("imperfect.yo", "abrías"), ("imperfect.yo", "puerta"), (None, "abría")],
)
def test_bad_hints_are_rejected(path, answer):
    assert tag_from_hint("es", "Yo abría la puerta.", ES, path, answer) is None


def test_tag_examples_consumes_hint_keys_and_keeps_other_fields():
    examples = [{"dst": "Yo abría la puerta.", "form": "imperfect.yo", "answer": "abría", "translations": {"en": "x"}}]
    (tagged,) = tag_examples("es", ES, examples)
    assert "form" not in tagged and "answer" not in tagged
    assert tagged["translations"] == {"en": "x"}
    assert tagged["target"]["person"] == "yo"


def test_tag_examples_is_idempotent_and_keeps_valid_targets():
    once = tag_examples("es", ES, [{"dst": "El camarero abrió una botella."}])
    twice = tag_examples("es", ES, once)
    assert once == twice


def test_tag_examples_retag_drops_stale_targets():
    once = tag_examples("es", ES, [{"dst": "El camarero abrió una botella."}])
    new_forms = {"present": {"yo": "abro"}}
    assert "target" not in tag_examples("es", new_forms, once, retag=True)[0]


def test_tag_examples_leaves_untaggable_and_non_dict_items_alone():
    out = tag_examples("es", ES, [{"dst": "Quiero comer."}, "junk"])
    assert out == [{"dst": "Quiero comer."}, "junk"]


def test_tag_generated_payload_uses_forms_of_the_payload():
    payload = {"lemma": "abrir", "forms": ES, "examples": [{"dst": "El camarero abrió una botella.", "form": None}]}
    tagged = tag_generated_payload("es", payload)
    assert tagged["examples"][0]["target"]["tense"] == "preterite"
    assert "form" not in tagged["examples"][0]
    assert payload["examples"][0].get("target") is None  # input not mutated
    assert tag_generated_payload("es", {"lemma": None}) == {"lemma": None}
    assert tag_generated_payload("es", "not a dict") == "not a dict"


def test_russian_stress_marks_do_not_break_tagging():
    forms = {"present": {"1sg": "мою"}}
    target = tag_sentence("ru", "Я мо́ю посуду.", forms)
    assert target is not None and target["answer"] == "мо́ю"
    assert validate_target("ru", "Я мо́ю посуду.", forms, target) == []
