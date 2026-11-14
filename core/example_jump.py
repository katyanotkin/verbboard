"""Form -> example jump (issue #123): which examples illustrate which conjugation row.

A target path ("tense" or "tense.person", as written by core/example_targets.py) is mapped to the
board row key (e.g. "pres_yo") by reading the language's own placeholder board, the same
approach core/fill_practice_service.py uses for labels, so there is no second per-language table.
"""

from __future__ import annotations

from functools import lru_cache

from core.fill_practice_service import _placeholder_board, usable_target
from core.models import Example


@lru_cache(maxsize=None)
def path_to_row_key(language: str) -> dict[str, str]:
    """Map "tense" / "tense.person" -> board row key for the language."""
    board = _placeholder_board(language)
    if board is None:
        return {}
    mapping: dict[str, str] = {}
    for section in board.sections:
        if not section.get("title"):
            continue
        for row in section["rows"]:  # type: ignore[attr-defined]
            text = str(row.get("text") or "")
            if text and text not in mapping:
                mapping[text] = str(row["key"])
    return mapping


def examples_by_row_key(language: str, examples: list[Example]) -> dict[str, list[int]]:
    """Row key -> sorted 1-based example indexes whose target (or an `also` path) is that row."""
    mapping = path_to_row_key(language)
    result: dict[str, list[int]] = {}
    for index, example in enumerate(examples or [], start=1):
        target = usable_target(example)
        if target is None:
            continue
        tense = str(target.get("tense") or "")
        person = target.get("person")
        paths = [f"{tense}.{person}" if person else tense]
        paths += [str(p) for p in target.get("also") or []]
        for path in paths:
            key = mapping.get(path)
            if key is not None and index not in result.setdefault(key, []):
                result[key].append(index)
    return result
