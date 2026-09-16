"""Tests for core/verb_loader.py's get_verb_of_the_day() (GitHub issue #40).

get_verb_of_the_day() wraps the existing, deterministic pick_verb_of_the_day()
to persist the day's pick in Firestore (collection `verb_of_the_day`, doc id
`f"{language}_{date_str}"`) so the pick can't flip mid-day when the catalog
size changes. This isolates its branching (doc missing / doc valid / doc
stale / create-race) with a mocked Firestore db, following the same
inspectable-MagicMock pattern as tests/test_write_promoted_verb.py and
tests/test_progress_batch_repository.py, rather than relying on
auto-created chained mocks that would silently "pass" without validating
what was actually written.

Indirect, non-mocked coverage of the surrounding home-route wiring lives in
tests/test_nav_links.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from google.api_core.exceptions import AlreadyExists

from core.models import VerbEntry
from core.verb_loader import get_verb_of_the_day, pick_verb_of_the_day

LANGUAGE = "en"
DATE_STR = "2026-09-16"


def _make_entry(verb_id: str, rank: int = 1) -> VerbEntry:
    return VerbEntry(id=verb_id, rank=rank, lemma=verb_id, forms={}, examples=[])


def _make_entries() -> list[VerbEntry]:
    return [_make_entry("en_go", 1), _make_entry("en_be", 2), _make_entry("en_do", 3)]


class _FakeSnapshot:
    def __init__(self, exists: bool, data: dict | None = None) -> None:
        self.exists = exists
        self._data = data

    def to_dict(self) -> dict | None:
        return dict(self._data) if self._data is not None else None


def _make_fake_db(get_results: list[_FakeSnapshot]) -> tuple[MagicMock, MagicMock]:
    """Returns (db, doc_ref). doc_ref.get() yields successive snapshots from
    get_results (one per call, in order) -- lets tests model the
    get-then-maybe-re-get sequence without relying on auto-mock defaults."""
    doc_ref = MagicMock()
    doc_ref.get.side_effect = get_results

    collection = MagicMock()
    collection.document.return_value = doc_ref

    db = MagicMock()
    db.collection.return_value = collection
    return db, doc_ref


# ---------------------------------------------------------------------------
# 1. Empty entries: short-circuits before ever touching Firestore.
# ---------------------------------------------------------------------------


def test_empty_entries_returns_none_without_touching_firestore() -> None:
    with patch("core.storage.firestore_db.get_db") as mock_get_db:
        result = get_verb_of_the_day([], language=LANGUAGE, date_str=DATE_STR)

    assert result is None
    mock_get_db.assert_not_called()


# ---------------------------------------------------------------------------
# 2. Doc doesn't exist yet: first pick of the day, creates the doc.
# ---------------------------------------------------------------------------


def test_first_pick_of_day_creates_doc_with_deterministic_pick() -> None:
    entries = _make_entries()
    expected = pick_verb_of_the_day(entries, language=LANGUAGE, date_str=DATE_STR)
    assert expected is not None

    db, doc_ref = _make_fake_db([_FakeSnapshot(exists=False)])

    with patch("core.storage.firestore_db.get_db", return_value=db):
        result = get_verb_of_the_day(entries, language=LANGUAGE, date_str=DATE_STR)

    assert result is expected

    doc_ref.create.assert_called_once()
    (payload,), _ = doc_ref.create.call_args
    assert payload == {"language": LANGUAGE, "date": DATE_STR, "verb_id": expected.id}
    doc_ref.set.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Doc exists with a still-valid verb_id: pure read path, no writes.
# ---------------------------------------------------------------------------


def test_existing_valid_doc_is_returned_without_any_write() -> None:
    entries = _make_entries()
    stored = entries[1]  # en_be -- not necessarily the deterministic pick

    db, doc_ref = _make_fake_db([_FakeSnapshot(exists=True, data={"verb_id": stored.id})])

    with patch("core.storage.firestore_db.get_db", return_value=db):
        result = get_verb_of_the_day(entries, language=LANGUAGE, date_str=DATE_STR)

    assert result is stored
    doc_ref.create.assert_not_called()
    doc_ref.set.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Race-loser path: create() raises AlreadyExists, re-read wins.
# ---------------------------------------------------------------------------


def test_create_race_loser_defers_to_winners_stored_pick() -> None:
    entries = _make_entries()
    winner_verb_id = entries[2].id  # en_do -- the "winning" request's pick

    db, doc_ref = _make_fake_db(
        [
            _FakeSnapshot(exists=False),  # initial read: doc missing
            _FakeSnapshot(exists=True, data={"verb_id": winner_verb_id}),  # post-exception re-read
        ]
    )
    doc_ref.create.side_effect = AlreadyExists("already exists")

    with patch("core.storage.firestore_db.get_db", return_value=db):
        result = get_verb_of_the_day(entries, language=LANGUAGE, date_str=DATE_STR)

    assert result is entries[2]
    doc_ref.create.assert_called_once()
    doc_ref.set.assert_not_called()
    assert doc_ref.get.call_count == 2


# ---------------------------------------------------------------------------
# 5. Stale-doc fallback -- the bug that was just fixed. Most important test:
#    a stored verb_id that matches no current entry must be corrected via
#    set() (doc already exists), never create() (which would always raise
#    AlreadyExists and silently fail to fix the stale doc).
# ---------------------------------------------------------------------------


def test_stale_doc_is_corrected_via_set_not_create() -> None:
    entries = _make_entries()
    expected = pick_verb_of_the_day(entries, language=LANGUAGE, date_str=DATE_STR)
    assert expected is not None

    db, doc_ref = _make_fake_db([_FakeSnapshot(exists=True, data={"verb_id": "en_no_longer_exists"})])

    with patch("core.storage.firestore_db.get_db", return_value=db):
        result = get_verb_of_the_day(entries, language=LANGUAGE, date_str=DATE_STR)

    assert result is expected

    doc_ref.set.assert_called_once()
    (payload,), _ = doc_ref.set.call_args
    assert payload == {"language": LANGUAGE, "date": DATE_STR, "verb_id": expected.id}

    doc_ref.create.assert_not_called()
