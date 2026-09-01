from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum


class PracticeSessionSize(IntEnum):
    SIZE_THREE = 3
    SIZE_SIX = 6
    SIZE_NINE = 9


# Leitner box ladder: interval (days) a verb waits before resurfacing, indexed
# by box number (box 1 -> LEITNER_INTERVAL_DAYS[0], etc). Box 0 means "not in
# the ladder yet". No SM-2/ease-factor math: there's no recall-quality signal
# in this app finer than the binary "Knew it"/"Show me again" self-report.
LEITNER_INTERVAL_DAYS: tuple[int, ...] = (1, 3, 7, 16, 35)
LEITNER_MAX_BOX = len(LEITNER_INTERVAL_DAYS)


def leitner_next_box(current_box: int, recalled: bool) -> int:
    """Pure box-transition rule. Mirrors app/static/srs.js's nextBox() --
    keep both in lockstep, see tests/test_srs_merge.py for the parity check.

    Recalled -> promote one box (capped at LEITNER_MAX_BOX). Not recalled ->
    demote to box 1 (stays in the ladder, just resurfaces sooner). A verb
    with no prior box (0) starts at box 1 either way -- a review action is
    itself evidence the verb is being actively studied.
    """
    if recalled:
        return min((current_box + 1) if current_box else 1, LEITNER_MAX_BOX)
    return 1


@dataclass(frozen=True)
class VerbProgress:
    language: str
    verb_id: str
    seen: bool
    known: bool
    srs_box: int = 0
    srs_due_at: datetime | None = None
    srs_reviewed_at: datetime | None = None


@dataclass
class PracticeProgress:
    language: str
    badges: list[int]
