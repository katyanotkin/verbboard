"""Pure functions for practice-streak merging.

A streak record is `{"last_day": "YYYY-MM-DD", "len": N, "grace_used": bool}`
where `last_day` is a client-local calendar day string. The server never
computes "today" -- it only stores and merges client-provided day strings.
Mirrors the client-side logic in `app/static/streak.js`
(`VerbBoardStreak.merge`); keep the two in sync.

Streak grace (N2): one free miss per streak. A single missed day (a gap of
exactly two calendar days between the stored streak and the incoming one)
never breaks the streak -- it extends it exactly like a consecutive day
would, and consumes the grace by setting `grace_used=True`. The grace
resets (`grace_used=False`) only when the streak itself resets to length 1
(an actual gap of 3+ days, or a fresh start). A second missed day before
the grace resets breaks the streak normally. This logic is gated by the
caller-supplied `grace_enabled` flag (`Settings.streak_grace_enabled`) so
that with the flag off, behavior is byte-for-byte identical to the
pre-grace implementation (a gap of 2+ days always breaks the streak).
"""

from __future__ import annotations

from datetime import date
from typing import NotRequired, TypedDict


class StreakRecord(TypedDict):
    last_day: str
    len: int
    grace_used: NotRequired[bool]


def days_between(earlier: str, later: str) -> int:
    """Number of calendar days between two ISO date strings (`later` - `earlier`)."""
    d1 = date.fromisoformat(earlier)
    d2 = date.fromisoformat(later)
    return (d2 - d1).days


def is_next_day(earlier: str, later: str) -> bool:
    """True if `later` is exactly one calendar day after `earlier` (ISO date strings)."""
    return days_between(earlier, later) == 1


def _grace_used(rec: StreakRecord) -> bool:
    return bool(rec.get("grace_used", False))


def merge_streak(
    a: StreakRecord | None,
    b: StreakRecord | None,
    grace_enabled: bool = False,
) -> StreakRecord | None:
    """Merge two streak records, never shrinking a legitimate streak.

    - Either side missing -> the other side wins.
    - Same day -> keep the larger length; `grace_used` is sticky (True if
      either side has already consumed the grace this streak).
    - Consecutive days (gap of 1) -> extend to the later day, length is
      max(later.len, earlier.len + 1); `grace_used` carries forward.
    - Gap of exactly 2 days, `grace_enabled` and grace not yet used by
      either side -> treated like a consecutive day (streak preserved,
      extended by one), and `grace_used` is set True (grace consumed).
    - Otherwise (gap of 2+ days, or grace already used, or grace disabled)
      -> the later day wins outright (streak was broken); its own
      `grace_used` travels with it unchanged.
    """
    if a is None:
        return b
    if b is None:
        return a

    if a["last_day"] == b["last_day"]:
        return {
            "last_day": a["last_day"],
            "len": max(a["len"], b["len"]),
            "grace_used": _grace_used(a) or _grace_used(b),
        }

    if a["last_day"] < b["last_day"]:
        earlier, later = a, b
    else:
        earlier, later = b, a

    gap = days_between(earlier["last_day"], later["last_day"])

    if gap == 1:
        return {
            "last_day": later["last_day"],
            "len": max(later["len"], earlier["len"] + 1),
            "grace_used": _grace_used(earlier) or _grace_used(later),
        }

    if gap == 2 and grace_enabled and not (_grace_used(earlier) or _grace_used(later)):
        return {
            "last_day": later["last_day"],
            "len": max(later["len"], earlier["len"] + 1),
            "grace_used": True,
        }

    return later
