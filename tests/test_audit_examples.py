"""Tests for the read-only example audit (issue #99, tools/audit_examples.py)."""

from __future__ import annotations

import csv
import json

import pytest

from core.languages.config import ALL_STUDY_LANGUAGES, UI_LANGUAGES
from tools import audit_examples as audit
from tools.audit_examples import audit_payload, load_from_json, main

pytestmark = pytest.mark.unit


def run(language, data, check):
    return [f for f in audit_payload(language, data, only=[check]) if f.check == check]


def severities(findings):
    return sorted(f.severity for f in findings)


def translations_for(language, text="A fine translated sentence here"):
    return {ui: text for ui in UI_LANGUAGES if ui != language}


def tag(tense, person, sentence, answer):
    start = sentence.index(answer)
    return {"tense": tense, "person": person, "start": start, "end": start + len(answer), "answer": answer}


ES_FORMS = {"present": {"yo": "hablo", "tu": "hablas"}, "preterite": {"yo": "hablé"}}


def es_verb(examples, **extra):
    return {
        "verb_id": "es_hablar",
        "language": "es",
        "lemma": "hablar",
        "forms": ES_FORMS,
        "examples": examples,
        **extra,
    }


# --- coverage and tagging -------------------------------------------------


def test_coverage_per_tense_fires_for_uncovered_tense():
    sentence = "Yo hablo con ella"
    data = es_verb([{"dst": sentence, "target": tag("present", "yo", sentence, "hablo")}])
    findings = run("es", data, "coverage_per_tense")
    assert [f.severity for f in findings] == [audit.WARNING]
    assert "preterite" in findings[0].message


def test_coverage_per_tense_silent_when_all_covered_including_also():
    s1, s2 = "Yo hablo con ella", "Ayer yo hablé mucho"
    t1 = tag("present", "yo", s1, "hablo")
    t2 = tag("present", "tu", s2, "hablé")
    t2["also"] = ["preterite.yo"]
    assert run("es", es_verb([{"dst": s1, "target": t1}, {"dst": s2, "target": t2}]), "coverage_per_tense") == []


def test_unused_forms_is_info_only():
    sentence = "Yo hablo con ella"
    findings = run(
        "es", es_verb([{"dst": sentence, "target": tag("present", "yo", sentence, "hablo")}]), "unused_forms"
    )
    assert [f.severity for f in findings] == [audit.INFO]
    assert "1 of 3" in findings[0].message


def test_untagged_example_fires_without_target_and_silent_with_one():
    sentence = "Yo hablo con ella"
    assert severities(run("es", es_verb([{"dst": sentence}]), "untagged_example")) == [audit.WARNING]
    tagged = es_verb([{"dst": sentence, "target": tag("present", "yo", sentence, "hablo")}])
    assert run("es", tagged, "untagged_example") == []


def test_stale_target_fires_when_span_does_not_match_sentence():
    bad = {"tense": "present", "person": "yo", "start": 0, "end": 5, "answer": "hablo"}
    findings = run("es", es_verb([{"dst": "Yo hablo con ella", "target": bad}]), "stale_target")
    assert severities(findings) == [audit.ERROR]


def test_stale_target_silent_for_valid_target():
    sentence = "Yo hablo con ella"
    data = es_verb([{"dst": sentence, "target": tag("present", "yo", sentence, "hablo")}])
    assert run("es", data, "stale_target") == []


def test_duplicate_cell_fires_on_repeated_target_path():
    s1, s2 = "Yo hablo con ella", "Yo hablo con él"
    examples = [
        {"dst": s1, "target": tag("present", "yo", s1, "hablo")},
        {"dst": s2, "target": tag("present", "yo", s2, "hablo")},
    ]
    findings = run("es", es_verb(examples), "duplicate_cell")
    assert [(f.severity, f.example_index) for f in findings] == [(audit.WARNING, 1)]


def test_duplicate_cell_silent_for_distinct_paths():
    s1, s2 = "Yo hablo con ella", "Tú hablas con él"
    examples = [
        {"dst": s1, "target": tag("present", "yo", s1, "hablo")},
        {"dst": s2, "target": tag("present", "tu", s2, "hablas")},
    ]
    assert run("es", es_verb(examples), "duplicate_cell") == []


def _spread_examples(persons):
    return [{"dst": f"s{i}", "target": {"tense": "present", "person": p}} for i, p in enumerate(persons)]


def test_person_spread_fires_when_one_person_dominates():
    findings = run("es", es_verb(_spread_examples(["yo"] * 4 + ["tu"])), "person_spread")
    assert severities(findings) == [audit.WARNING]


def test_person_spread_silent_when_balanced_or_too_few():
    assert run("es", es_verb(_spread_examples(["yo", "tu", "el", "nos", "ellos"])), "person_spread") == []
    assert run("es", es_verb(_spread_examples(["yo"] * 4)), "person_spread") == []


# --- sentence quality ------------------------------------------------------


def test_duplicate_text_fires_ignoring_case_and_whitespace():
    examples = [{"dst": "Yo hablo con ella"}, {"dst": "yo  HABLO con   ella"}]
    findings = run("es", es_verb(examples), "duplicate_text")
    assert [(f.severity, f.example_index) for f in findings] == [(audit.ERROR, 1)]


def test_duplicate_text_silent_for_distinct_sentences():
    assert run("es", es_verb([{"dst": "Yo hablo mucho"}, {"dst": "Tú hablas poco"}]), "duplicate_text") == []


def test_sentence_length_flags_short_and_long():
    long_sentence = " ".join(["palabra"] * 23)
    findings = run("es", es_verb([{"dst": "Hola"}, {"dst": long_sentence}]), "sentence_length")
    assert [(f.severity, f.example_index) for f in findings] == [(audit.WARNING, 0), (audit.WARNING, 1)]


def test_sentence_length_silent_for_normal_sentence():
    assert run("es", es_verb([{"dst": "Yo hablo con ella"}]), "sentence_length") == []


def test_stock_opener_fires_when_most_sentences_share_opener():
    examples = [{"dst": f"Yo hablo {i}"} for i in range(4)] + [{"dst": "Tú hablas bien"}]
    assert severities(run("es", es_verb(examples), "stock_opener")) == [audit.WARNING]


def test_stock_opener_silent_for_varied_or_few_sentences():
    varied = [{"dst": s} for s in ("Yo hablo", "Tú hablas", "Él habla", "Ella habló")]
    assert run("es", es_verb(varied), "stock_opener") == []
    assert run("es", es_verb([{"dst": "Yo a"}, {"dst": "Yo b"}, {"dst": "Yo c"}]), "stock_opener") == []


def test_banned_phrase_fires_for_en_and_ru_and_silent_on_clean_text():
    en = {"verb_id": "en_x", "language": "en", "lemma": "x", "examples": [{"dst": "Please discuss about it"}]}
    assert severities(run("en", en, "banned_phrase")) == [audit.ERROR]
    ru = {"verb_id": "ru_x", "language": "ru", "lemma": "x", "examples": [{"dst": "Радио покупал вчера"}]}
    assert severities(run("ru", ru, "banned_phrase")) == [audit.ERROR]
    en["examples"] = [{"dst": "Please discuss it with me"}]
    assert run("en", en, "banned_phrase") == []
    assert run("es", es_verb([{"dst": "Please discuss about it"}]), "banned_phrase") == []


# --- Russian ---------------------------------------------------------------


def ru_verb(examples, aspect="perfective"):
    return {
        "verb_id": "ru_x",
        "language": "ru",
        "lemma": "сделать",
        "morph": {"aspect": aspect},
        "forms": {},
        "examples": examples,
    }


def test_ru_aspect_slot_perfective_tagged_present_is_error():
    data = ru_verb([{"dst": "Я делаю это", "target": {"tense": "present", "person": "1sg"}}])
    assert severities(run("ru", data, "ru_aspect_slot")) == [audit.ERROR]


def test_ru_aspect_slot_imperfective_present_is_fine():
    data = ru_verb([{"dst": "Я делаю это", "target": {"tense": "present", "person": "1sg"}}], aspect="imperfective")
    assert run("ru", data, "ru_aspect_slot") == []


def test_ru_aspect_slot_compound_future_is_warning():
    data = ru_verb([{"dst": "Завтра я буду делать это"}], aspect="imperfective")
    assert severities(run("ru", data, "ru_aspect_slot")) == [audit.WARNING]


def test_ru_aspect_slot_skips_other_languages():
    assert run("es", es_verb([{"dst": "Завтра я буду делать это"}]), "ru_aspect_slot") == []


def _neuter(sentence, answer):
    return ru_verb([{"dst": sentence, "target": tag("past", "n", sentence, answer)}])


def test_ru_forced_neuter_fires_without_neuter_subject():
    assert severities(run("ru", _neuter("Мой брат сделало работу вчера", "сделало"), "ru_forced_neuter")) == [
        audit.WARNING
    ]


def test_ru_forced_neuter_silent_with_neuter_subject():
    assert run("ru", _neuter("Солнце село за горы вчера", "село"), "ru_forced_neuter") == []


def en_verb(lemma, gerund, examples):
    return {
        "verb_id": f"en_{lemma}",
        "language": "en",
        "lemma": lemma,
        "forms": {"gerund": gerund},
        "examples": examples,
    }


@pytest.mark.parametrize(
    "lemma,gerund",
    [("begin", "begining"), ("make", "makeing")],
)
def test_en_gerund_misspelled_is_error(lemma, gerund):
    data = en_verb(lemma, gerund, [{"dst": f"I like {gerund} early"}])
    assert audit.ERROR in severities(run("en", data, "en_gerund"))


@pytest.mark.parametrize("lemma,gerund", [("begin", "beginning"), ("make", "making"), ("be", "being")])
def test_en_gerund_correct_spelling_is_silent(lemma, gerund):
    data = en_verb(lemma, gerund, [{"dst": f"I like {gerund} early"}])
    assert run("en", data, "en_gerund") == []


def test_en_gerund_unused_is_warning():
    data = en_verb("make", "making", [{"dst": "I make bread every day"}])
    assert severities(run("en", data, "en_gerund")) == [audit.WARNING]


def test_en_stative_progressive_fires_and_stays_silent():
    bad = {"verb_id": "en_x", "language": "en", "lemma": "want", "examples": [{"dst": "We are wanting more time"}]}
    assert severities(run("en", bad, "en_stative_progressive")) == [audit.WARNING]
    good = dict(bad, examples=[{"dst": "We are running late"}])
    assert run("en", good, "en_stative_progressive") == []


def he_verb(sentence):
    return {"verb_id": "he_x", "language": "he", "lemma": "x", "examples": [{"dst": sentence}]}


def test_he_niqqud_fires_without_points_even_with_maqaf():
    assert severities(run("he", he_verb("הוא כותב ספר"), "he_niqqud")) == [audit.WARNING]
    assert severities(run("he", he_verb("הוא כותב את־הספר"), "he_niqqud")) == [audit.WARNING]


def test_he_niqqud_silent_with_points():
    assert run("he", he_verb("הוּא כּוֹתֵב סֵפֶר"), "he_niqqud") == []


# --- translations ----------------------------------------------------------


def test_translation_missing_is_error_per_example_and_lemma_gap_is_warning():
    data = es_verb([{"dst": "Yo hablo con ella", "translations": {}}], lemma_translations={})
    findings = run("es", data, "translation_missing")
    assert sorted((f.severity, f.example_index) for f in findings) == [(audit.ERROR, 0), (audit.WARNING, None)]


def test_translation_missing_silent_when_complete():
    data = es_verb(
        [{"dst": "Yo hablo con ella", "translations": translations_for("es")}],
        lemma_translations=translations_for("es", "to speak"),
    )
    assert run("es", data, "translation_missing") == []


def test_translation_quality_flags_copy_and_bad_length_ratio():
    sentence = "Yo hablo con ella ahora"
    uis = [ui for ui in UI_LANGUAGES if ui != "es"]
    translations = {ui: "ok" * 6 for ui in uis}
    translations[uis[0]] = sentence
    translations[uis[1]] = "x" * 200
    findings = run("es", es_verb([{"dst": sentence, "translations": translations}]), "translation_quality")
    assert len(findings) >= 2
    assert {f.severity for f in findings} == {audit.WARNING}


def test_translation_quality_silent_for_reasonable_translation():
    sentence = "Yo hablo con ella ahora"
    translations = translations_for("es", "I speak with her now")
    assert run("es", es_verb([{"dst": sentence, "translations": translations}]), "translation_quality") == []


# --- robustness ------------------------------------------------------------


def _malformed_documents(language):
    sentence = "Yo hablo con ella"
    return [
        {"verb_id": "v", "language": language, "lemma": "x", "examples": "not a list"},
        {"verb_id": "v", "language": language, "lemma": "x", "examples": ["a string", None, 5]},
        {
            "verb_id": "v",
            "language": language,
            "lemma": "x",
            "forms": ES_FORMS,
            "examples": [{"dst": sentence, "translations": ["a", "b"]}],
        },
        {
            "verb_id": "v",
            "language": language,
            "lemma": "x",
            "morph": "perfective",
            "forms": ES_FORMS,
            "examples": [{"dst": sentence}],
        },
        {
            "verb_id": "v",
            "language": language,
            "lemma": "x",
            "lemma_translations": ["a"],
            "examples": [{"dst": sentence}],
        },
        {
            "verb_id": "v",
            "language": language,
            "lemma": "x",
            "forms": ES_FORMS,
            "examples": [{"dst": sentence, "target": {"tense": "past", "person": ["n"], "start": 0, "end": 3}}],
        },
        {
            "verb_id": "v",
            "language": language,
            "lemma": "x",
            "forms": ES_FORMS,
            "examples": [{"dst": sentence, "target": {"tense": "past", "person": "n", "start": "a", "end": "b"}}],
        },
        {"verb_id": "v", "language": language, "lemma": None, "forms": "oops", "examples": [{"src": 7, "dst": None}]},
    ]


@pytest.mark.parametrize("language", ALL_STUDY_LANGUAGES)
def test_malformed_documents_neither_raise_nor_crash_a_check(language):
    for document in _malformed_documents(language):
        findings = audit_payload(language, document)
        assert [f for f in findings if f.check == "check_crashed"] == [], document


def test_crashing_check_is_reported_not_propagated(monkeypatch):
    def boom(ctx):
        raise RuntimeError("kaboom")

    monkeypatch.setitem(audit.CHECKS, "coverage_per_tense", boom)
    findings = audit_payload("es", es_verb([]), only=["coverage_per_tense"])
    assert [(f.severity, f.check) for f in findings] == [(audit.ERROR, "check_crashed")]
    assert "kaboom" in findings[0].message


# --- loading ---------------------------------------------------------------


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_load_from_json_accepts_list_wrapper_and_single_dict(tmp_path):
    verb = {"verb_id": "es_a", "language": "es"}
    assert load_from_json(write_json(tmp_path / "a.json", [verb]), "", "") == [verb]
    assert load_from_json(write_json(tmp_path / "b.json", {"verbs": [verb]}), "", "") == [verb]
    assert load_from_json(write_json(tmp_path / "c.json", verb), "", "") == [verb]


def test_load_from_json_filters_by_language_and_verb_id(tmp_path):
    verbs = [
        {"verb_id": "es_a", "language": "es"},
        {"verb_id": "es_b", "language": "es"},
        {"verb_id": "en_a", "language": "en"},
    ]
    path = write_json(tmp_path / "v.json", verbs)
    assert [v["verb_id"] for v in load_from_json(path, "es", "")] == ["es_a", "es_b"]
    assert [v["verb_id"] for v in load_from_json(path, "", "en_a")] == ["en_a"]
    assert [v["verb_id"] for v in load_from_json(path, "es", "es_b")] == ["es_b"]


# --- CLI -------------------------------------------------------------------


def clean_verb():
    sentence = "Yo hablo con ella ahora"
    return {
        "verb_id": "es_hablar",
        "language": "es",
        "lemma": "hablar",
        "forms": {"present": {"yo": "hablo"}},
        "lemma_translations": translations_for("es", "to speak"),
        "examples": [
            {
                "dst": sentence,
                "target": tag("present", "yo", sentence, "hablo"),
                "translations": translations_for("es", "I speak with her now"),
            }
        ],
    }


def error_verb():
    verb = clean_verb()
    verb["examples"] = [{"dst": "Yo hablo con ella", "translations": {}}]
    return verb


def warning_only_verb():
    verb = clean_verb()
    verb["examples"][0]["dst"] = "Hola"
    verb["examples"][0]["target"] = None
    return verb


def cli(tmp_path, payload, *args):
    path = write_json(tmp_path / "verbs.json", payload)
    return main(["--from-json", str(path), *args])


def test_cli_clean_file_exits_zero(tmp_path, capsys):
    assert cli(tmp_path, [clean_verb()], "--strict") == 0
    assert "verbs audited: 1" in capsys.readouterr().out


def test_cli_error_finding_exits_one(tmp_path):
    assert cli(tmp_path, [error_verb()]) == 1


def test_cli_warnings_only_fail_under_strict(tmp_path):
    assert cli(tmp_path, [warning_only_verb()], "--check", "sentence_length") == 0
    assert cli(tmp_path, [warning_only_verb()], "--check", "sentence_length", "--strict") == 1


@pytest.mark.parametrize(
    "args",
    [["--language", "xx"], ["--check", "nope"], ["--language", "en"]],
)
def test_cli_could_not_run_exits_two(tmp_path, args):
    assert cli(tmp_path, [clean_verb()], *args) == 2


def test_cli_unreadable_file_exits_two(tmp_path):
    assert main(["--from-json", str(tmp_path / "missing.json")]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main(["--from-json", str(bad)]) == 2


def test_cli_report_writes_csv_and_json(tmp_path):
    csv_path, json_path = tmp_path / "out.csv", tmp_path / "out.json"
    assert cli(tmp_path, [error_verb()], "--report", str(csv_path)) == 1
    assert cli(tmp_path, [error_verb()], "--report", str(json_path)) == 1
    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows and set(rows[0]) == set(audit.Finding.__dataclass_fields__)
    assert rows[0]["severity"] == "error"
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded and loaded[0]["severity"] == "error"


def test_cli_document_without_language_gives_missing_language_error(tmp_path, capsys):
    assert cli(tmp_path, [{"verb_id": "x_1", "lemma": "x"}]) == 1
    assert "missing_language" in capsys.readouterr().out


def test_json_document_without_language_uses_the_language_flag(tmp_path) -> None:
    import json

    from tools.audit_examples import main

    document = {"verb_id": "x", "lemma": "x", "forms": {}, "examples": []}
    path = tmp_path / "verbs.json"
    path.write_text(json.dumps([document]), encoding="utf-8")
    assert main(["--from-json", str(path), "--language", "es", "--check", "unused_forms"]) == 0
    assert main(["--from-json", str(path), "--check", "unused_forms"]) == 1  # no language anywhere: missing_language
