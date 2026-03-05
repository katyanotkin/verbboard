from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Example:
    dst: str


@dataclass(frozen=True)
class VerbEntry:
    id: str
    rank: int
    # Language-specific lemma object (str for en/he, dict for ru) stored as Any
    lemma: Any
    forms: Dict[str, Any]
    examples: List[Example]
    morph: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


@dataclass(frozen=True)
class Board:
    language: str
    verb: VerbEntry
    voice_key: str
    voice_label: str
    sections: List[Dict[str, Any]]  # renderer-friendly structure
