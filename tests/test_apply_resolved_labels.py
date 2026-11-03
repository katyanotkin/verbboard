"""tools/apply_resolved_labels.py against the in-memory fake (QATP E1, E2)."""

from __future__ import annotations

import json
import sys

import pytest

from core.example_targets import tag_sentence
from tools import apply_resolved_labels as tool

FR_FORMS = {
    "present": {"je": "aime", "tu": "aimes", "il": "aime"},
    "subjonctif_present": {"je": "aime", "tu": "aimes", "il": "aime"},
}
SENTENCE = "J'aime le café."
OTHER = "Tu aimes le thé."


class _Snapshot:
    """FakeSnapshot plus the update_time the tool passes to write_option."""

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
        ref = self._inner.document(doc_id)
        return _Ref(ref)


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


def _verb(verb_id: str, sentence: str = SENTENCE) -> dict:
    target = tag_sentence("fr", sentence, FR_FORMS)
    assert target is not None
    return {
        "language": "fr",
        "verb_id": verb_id,
        "forms": FR_FORMS,
        "examples": [{"dst": sentence, "target": target}],
    }


@pytest.fixture()
def run(fake_db, monkeypatch, tmp_path):
    fake_db.seed("verbs", {"fr_aimer": _verb("fr_aimer"), "fr_other": _verb("fr_other")})
    monkeypatch.setattr(tool, "get_db", lambda: _Db(fake_db))

    def _run(resolved: dict, *flags: str) -> None:
        path = tmp_path / "resolved.json"
        path.write_text(json.dumps(resolved), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["apply", "--language", "fr", "--resolved", str(path), *flags])
        tool.main()

    return _run


def _target(fake_db, doc_id: str) -> dict:
    return fake_db.data[f"verbs/{doc_id}"]["examples"][0]["target"]


def test_seeded_row_is_multi_label_and_dry_run_writes_nothing(run, fake_db) -> None:
    assert _target(fake_db, "fr_aimer").get("also")
    before = fake_db.data
    run({"fr_aimer#0": "present.je"})
    assert fake_db.data == before


def test_execute_settles_to_one_generated_label_with_valid_offsets(run, fake_db) -> None:
    run({"fr_aimer#0": "subjonctif_present.je"}, "--execute")
    target = _target(fake_db, "fr_aimer")
    assert (target["tense"], target["person"], target["source"]) == ("subjonctif_present", "je", "generated")
    assert "also" not in target
    assert SENTENCE[target["start"] : target["end"]] == target["answer"] == "aime"
    assert fake_db.data["verbs/fr_aimer"]["updated_at"]


def test_verbs_not_in_the_map_are_untouched(run, fake_db) -> None:
    other_before = fake_db.data["verbs/fr_other"]
    run({"fr_aimer#0": "present.je"}, "--execute")
    assert fake_db.data["verbs/fr_other"] == other_before
    assert _target(fake_db, "fr_aimer")["source"] == "generated"


def test_ambiguous_is_kept(run, fake_db) -> None:
    before = fake_db.data
    run({"fr_aimer#0": "ambiguous"}, "--execute")
    assert fake_db.data == before


def test_label_not_among_candidates_is_rejected_and_not_written(run, fake_db, caplog) -> None:
    before = fake_db.data
    with caplog.at_level("WARNING"):
        run({"fr_aimer#0": "present.nous"}, "--execute")
    assert fake_db.data == before
    assert "not a candidate" in caplog.text


def test_missing_index_or_untagged_example_is_skipped(run, fake_db) -> None:
    before = fake_db.data
    run({"fr_aimer#5": "present.je"}, "--execute")
    assert fake_db.data == before
