"""Pure functions for practice-streak merging.

A streak record is `{"last_day": "YYYY-MM-DD", "len": N}` where `last_day` is a
client-local calendar day string. The server never computes "today" -- it only
stores and merges client-provided day strings. Mirrors the client-side logic
in `app/static/streak.js` (`VerbBoardStreak.merge`); keep the two in sync.
"""

from __future__ import annotations

from datetime import date
from typing import TypedDict


class StreakRecord(TypedDict):
    last_day: str
    len: int


def is_next_day(earlier: str, later: str) -> bool:
    """True if `later` is exactly one calendar day after `earlier` (ISO date strings)."""
    d1 = date.fromisoformat(earlier)
    d2 = date.fromisoformat(later)
    return (d2 - d1).days == 1


def merge_streak(a: StreakRecord | None, b: StreakRecord | None) -> StreakRecord | None:
    """Merge two streak records, never shrinking a legitimate streak.

    - Either side missing -> the other side wins.
    - Same day -> keep the larger length.
    - Consecutive days -> extend to the later day, length is max(later.len, earlier.len + 1).
    - Otherwise (gap of 2+ days) -> the later day wins outright (streak was broken).
    """
    if a is None:
        return b
    if b is None:
        return a

    if a["last_day"] == b["last_day"]:
        return {"last_day": a["last_day"], "len": max(a["len"], b["len"])}

    if a["last_day"] < b["last_day"]:
        earlier, later = a, b
    else:
        earlier, later = b, a

    if is_next_day(earlier["last_day"], later["last_day"]):
        return {"last_day": later["last_day"], "len": max(later["len"], earlier["len"] + 1)}

    return later
