from __future__ import annotations

from core.models import VerbEntry
from core.verb_loader import pick_verb_of_the_day


def _entry(entry_id: str, rank: int) -> VerbEntry:
    return VerbEntry(id=entry_id, rank=rank, lemma=entry_id, forms={}, examples=[])


def _pick(entries: list[VerbEntry], *, language: str, date_str: str) -> VerbEntry:
    result = pick_verb_of_the_day(entries, language=language, date_str=date_str)
    assert result is not None
    return result


def test_empty_entries_returns_none() -> None:
    assert pick_verb_of_the_day([], language="en", date_str="2026-09-05") is None


def test_single_entry_returns_that_entry() -> None:
    only = _entry("en_go", rank=1)
    assert pick_verb_of_the_day([only], language="en", date_str="2026-09-05") is only


def test_pick_is_deterministic_for_same_inputs() -> None:
    entries = [_entry(f"en_{i}", rank=i) for i in range(20)]
    first = pick_verb_of_the_day(entries, language="en", date_str="2026-09-05")
    second = pick_verb_of_the_day(entries, language="en", date_str="2026-09-05")
    assert first is second


def test_pick_is_stable_against_rank_reordering() -> None:
    # Same set of verbs, different rank/list order (e.g. an admin edit shifted
    # ranks between cache refreshes) must still pick the same verb for the day.
    entries = [_entry(f"en_{i}", rank=i) for i in range(20)]
    reordered = [_entry(f"en_{i}", rank=19 - i) for i in reversed(range(20))]

    original_pick = _pick(entries, language="en", date_str="2026-09-05")
    reordered_pick = _pick(reordered, language="en", date_str="2026-09-05")

    assert original_pick.id == reordered_pick.id


def test_pick_can_differ_across_dates() -> None:
    entries = [_entry(f"en_{i}", rank=i) for i in range(50)]
    picks = {_pick(entries, language="en", date_str=f"2026-09-{day:02d}").id for day in range(1, 15)}
    assert len(picks) > 1


def test_pick_can_differ_across_languages_for_same_date() -> None:
    entries = [_entry(f"x_{i}", rank=i) for i in range(50)]
    en_pick = _pick(entries, language="en", date_str="2026-09-05")
    ru_pick = _pick(entries, language="ru", date_str="2026-09-05")
    assert en_pick.id != ru_pick.id or len(entries) == 1
