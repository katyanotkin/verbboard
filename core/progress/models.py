from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class PracticeSessionSize(IntEnum):
    SIZE_THREE = 3
    SIZE_SIX = 6
    SIZE_NINE = 9


@dataclass(frozen=True)
class VerbProgress:
    language: str
    verb_id: str
    seen: bool
    known: bool


@dataclass
class PracticeProgress:
    language: str
    badges: list[int]
    streak_last_day: str | None = None
    streak_len: int = 0
