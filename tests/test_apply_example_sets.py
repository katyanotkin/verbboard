"""tools/apply_example_sets.py: build_examples (pure) and main() against the in-memory fake."""

from __future__ import annotations

import json
import sys

import pytest

from core.example_targets import tag_sentence
from tools import apply_example_sets as tool

FORMS = {
    "present": {"я": "читаю", "ты": "читаешь", "он": "читает", "мы": "читаем", "вы": "читаете", "они": "читают"},
    "past": {"m": "читал", "f": "читала", "n": "читало", "pl": "читали"},
    "future": {"я": "прочитаю", "ты": "прочитаешь"},
    "imperative": {"ты": "читай", "вы": "читайте"},
}
# Same surface form in present and future, so the sentence is multi-label.
SHARED_FORMS = {
    "present": {"я": "прочитаю", "ты": "читаешь"},
    "future": {"я": "прочитаю", "ты": "прочитаешь"},
}
TR = {"en": "I read.", "es": "Leo.", "he": "אני קורא."}
SENTENCE = "Я читаю книгу каждый вечер дома"


def _doc(forms=FORMS, examples=None) -> dict:
    return {"language": "ru", "verb_id": "ru_chitat", "forms": forms, "examples": examples or []}


def _new(dst=SENTENCE, form="present.я", **extra) -> dict:
    return {"dst": dst, "form": form, "tr": dict(TR), **extra}


def _build(entries, doc=None):
    return tool.build_examples("ru", doc or _doc(), entries)


def _existing() -> dict:
    sentence = "Вчера он читал очень длинную книгу"
    return {
        "dst": sentence,
        "translations": {"en": "x", "es": "y", "he": "z"},
        "target": tag_sentence("ru", sentence, FORMS),
        "audio": "keepme",
    }


def test_keep_copies_existing_example_unchanged() -> None:
    existing = _existing()
    result, problems = _build([{"keep": 0}], _doc(examples=[existing]))
    assert problems == []
    assert result == [existing]
    assert result[0] is not existing
    assert result[0]["target"]["tense"] == "past"


@pytest.mark.parametrize("index", [1, -1, "0", None])
def test_keep_with_bad_index_is_a_problem(index) -> None:
    _, problems = _build([{"keep": index}], _doc(examples=[_existing()]))
    assert any("not an existing example" in p for p in problems)


def test_new_entry_gets_target_and_translations() -> None:
    result, problems = _build([_new()])
    assert problems == []
    assert result[0]["dst"] == SENTENCE
    assert result[0]["translations"] == TR
    target = result[0]["target"]
    assert (target["tense"], target["person"], target["answer"]) == ("present", "я", "читаю")
    assert SENTENCE[target["start"] : target["end"]] == "читаю"


def test_form_in_also_is_resolved_via_hint() -> None:
    primary = tag_sentence("ru", SENTENCE.replace("читаю", "прочитаю"), SHARED_FORMS)
    assert primary and primary.get("also"), "fixture must be multi-label"
    other = "future.я" if f"{primary['tense']}.{primary['person']}" != "future.я" else "present.я"
    sentence = SENTENCE.replace("читаю", "прочитаю")
    result, problems = _build([_new(sentence, other)], _doc(SHARED_FORMS))
    assert problems == []
    target = result[0]["target"]
    assert f"{target['tense']}.{target['person']}" == other
    assert target["source"] == "generated"
    assert "also" not in target


def test_sentence_not_resolving_to_requested_form_is_rejected() -> None:
    result, problems = _build([_new(form="past.m")])
    assert result == []
    assert any("does not resolve to past.m" in p for p in problems)


def test_untaggable_sentence_is_rejected() -> None:
    _, problems = _build([_new("Сегодня очень хорошая погода дома")])
    assert any("could not tag" in p for p in problems)


def test_stress_mark_rejected() -> None:
    _, problems = _build([_new("Я чита́ю книгу каждый вечер дома")])
    assert any("stress mark" in p for p in problems)


def test_ru_compound_future_rejected() -> None:
    _, problems = _build([_new("Я буду читать вечером", "future.я")])
    assert any("compound future" in p for p in problems)


@pytest.mark.parametrize("dst", ["Я читаю книгу", "", " ", " ".join(["слово"] * 17)])
def test_too_short_or_long_rejected(dst) -> None:
    _, problems = _build([_new(dst)])
    assert any("sentence length" in p for p in problems)


@pytest.mark.parametrize("missing", ["en", "es", "he"])
def test_missing_translation_rejected(missing) -> None:
    entry = _new()
    del entry["tr"][missing]
    _, problems = _build([entry])
    assert any("missing translations" in p and missing in p for p in problems)


def test_blank_translation_rejected() -> None:
    entry = _new()
    entry["tr"]["es"] = "  "
    _, problems = _build([entry])
    assert any("missing translations" in p for p in problems)


def test_untagged_entry_keeps_no_target_and_skips_tagging() -> None:
    # The sentence has no matching form at all; untagged must bypass tagging.
    result, problems = _build([_new("Сегодня очень хорошая погода дома", "present.я", untagged=True)])
    assert problems == []
    assert "target" not in result[0]
    assert result[0]["translations"] == TR


def test_zero_results_rejected() -> None:
    _, problems = _build([])
    assert "0 examples" in problems


def test_more_than_twelve_rejected() -> None:
    result, problems = _build([_new() for _ in range(13)])
    assert len(result) == 13
    assert "13 examples" in problems


def test_twelve_is_accepted() -> None:
    _, problems = _build([_new() for _ in range(12)])
    assert problems == []


# --- main() -----------------------------------------------------------------


IT_FORMS = {
    "presente": {
        "io": "mangio",
        "tu": "mangi",
        "lui": "mangia",
        "noi": "mangiamo",
        "voi": "mangiate",
        "loro": "mangiano",
    },
    "congiuntivo_presente": {
        "io": "mangi",
        "tu": "mangi",
        "lui": "mangi",
        "noi": "mangiamo",
        "voi": "mangiate",
        "loro": "mangino",
    },
}
IT_SENTENCE = "Il medico vuole che mio padre mangi meno sale."
IT_TR = {"en": "x", "ru": "y", "he": "z", "es": "w"}


def _it_build(entries, forms=IT_FORMS):
    doc = {"language": "it", "verb_id": "it_mangiare", "forms": forms, "examples": []}
    return tool.build_examples("it", doc, entries)


def _it_entry(dst=IT_SENTENCE, form="congiuntivo_presente.lui") -> dict:
    return {"dst": dst, "form": form, "tr": dict(IT_TR)}


def test_fallback_tags_requested_cell_when_tagger_gives_up() -> None:
    assert tag_sentence("it", IT_SENTENCE, IT_FORMS) is None, "fixture must defeat tag_sentence"
    result, problems = _it_build([_it_entry()])
    assert problems == []
    target = result[0]["target"]
    assert (target["tense"], target["person"]) == ("congiuntivo_presente", "lui")
    assert target["source"] == "generated"
    assert IT_SENTENCE[target["start"] : target["end"]] == "mangi"


def test_fallback_rejects_sentence_lacking_stored_form() -> None:
    result, problems = _it_build([_it_entry("Il medico vuole che mio padre beva meno vino.")])
    assert result == []
    assert any("could not tag" in p for p in problems)


@pytest.mark.parametrize("form", ["congiuntivo_presente.egli", "condizionale.lui", "bogus"])
def test_form_missing_from_forms_is_a_problem(form) -> None:
    result, problems = _it_build([_it_entry(form=form)])
    assert result == []
    assert problems


def test_tag_requested_cell_none_for_flat_cell_with_person() -> None:
    forms = {"participio": "mangiato"}
    assert tool._tag_requested_cell("it", "Ho mangiato troppo ieri sera", forms, "participio.lui") is None


def test_tag_requested_cell_none_for_missing_tense() -> None:
    assert tool._tag_requested_cell("it", IT_SENTENCE, IT_FORMS, "condizionale.lui") is None
    assert tool._tag_requested_cell("it", IT_SENTENCE, IT_FORMS, "") is None


def test_tag_requested_cell_flat_without_person_is_none_for_dict_cell() -> None:
    # A dict cell with no person named has no single answer.
    assert tool._tag_requested_cell("it", IT_SENTENCE, IT_FORMS, "congiuntivo_presente") is None


class _Snapshot:
    update_time = "t0"

    def __init__(self, inner) -> None:
        self._inner = inner
        self.id = inner.id

    def to_dict(self):
        return self._inner.to_dict()


class _Query:
    def __init__(self, inner) -> None:
        self._inner = inner

    def where(self, *args):
        return _Query(self._inner.where(*args))

    def stream(self):
        return (_Snapshot(s) for s in self._inner.stream())

    def document(self, doc_id):
        return _Ref(self._inner.document(doc_id))


class _Ref:
    def __init__(self, ref) -> None:
        self._ref = ref

    def update(self, data, option=None):
        assert option == ("last_update_time", "t0")
        self._ref.update(data)


class _Db:
    def __init__(self, fake) -> None:
        self._fake = fake

    def collection(self, name):
        return _Query(self._fake.collection(name))

    def write_option(self, last_update_time):
        return ("last_update_time", last_update_time)


@pytest.fixture()
def run(fake_db, monkeypatch, tmp_path):
    original = _existing()
    fake_db.seed(
        "verbs",
        {
            "ru_chitat": {**_doc(examples=[original])},
            "ru_pisat": {**_doc(examples=[original]), "verb_id": "ru_pisat"},
        },
    )
    monkeypatch.setattr(tool, "get_db", lambda: _Db(fake_db))

    def _run(sets: dict, *flags: str) -> None:
        path = tmp_path / "sets.json"
        path.write_text(json.dumps(sets), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["apply", "--language", "ru", "--sets", str(path), *flags])
        tool.main()

    return _run


def test_dry_run_writes_nothing(run, fake_db) -> None:
    before = fake_db.data
    run({"ru_chitat": [{"keep": 0}, _new()]})
    assert fake_db.data == before


def test_execute_writes_new_list_with_updated_at(run, fake_db) -> None:
    run({"ru_chitat": [{"keep": 0}, _new()]}, "--execute")
    doc = fake_db.data["verbs/ru_chitat"]
    assert [e["dst"] for e in doc["examples"]] == ["Вчера он читал очень длинную книгу", SENTENCE]
    assert doc["examples"][1]["target"]["answer"] == "читаю"
    assert doc["updated_at"]


def test_verb_with_problem_is_rejected_and_not_written(run, fake_db, caplog) -> None:
    before = fake_db.data
    with caplog.at_level("WARNING"):
        run({"ru_chitat": [_new(form="past.m")]}, "--execute")
    assert fake_db.data == before
    assert "rejected" in caplog.text


def test_verbs_not_in_sets_are_untouched(run, fake_db) -> None:
    other_before = fake_db.data["verbs/ru_pisat"]
    run({"ru_chitat": [_new()]}, "--execute")
    assert fake_db.data["verbs/ru_pisat"] == other_before
    assert fake_db.data["verbs/ru_chitat"]["examples"][0]["dst"] == SENTENCE


def test_unknown_verb_id_is_counted(run, fake_db, caplog) -> None:
    with caplog.at_level("INFO"):
        run({"ru_nonexistent": [_new()]}, "--execute")
    assert "ru_nonexistent: not found" in caplog.text
    assert "'unknown_verb': 1" in caplog.text
