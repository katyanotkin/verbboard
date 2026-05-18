from __future__ import annotations

from dataclasses import dataclass


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
