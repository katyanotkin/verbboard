"""Curated stress marks for Russian verb forms that TTS and readers confuse with another word.

Edge TTS cannot be told the stress (marked text sounds worse, issue #46), so
the mark is display-only: the board shows it, audio keeps the plain text. Each
entry is scoped to one verb id so the same spelling on another verb's page
(e.g. "мою" as a pronoun) is never touched. Write a stress as "+" right after
the stressed vowel; it is stored as the combining acute (U+0301).

To cover a new verb, add one line here; nothing in Firestore needs editing.
"""

from __future__ import annotations

import re

from core.languages.ru.stress import STRESS_MARK

_WORD = re.compile(r"[а-яёА-ЯЁ]+")


def _stressed(spec: str) -> str:
    return spec.replace("+", STRESS_MARK)


def _plain(spec: str) -> str:
    return spec.replace("+", "")


_SPECS: dict[str, tuple[str, ...]] = {
    "ru_platit": ("плачу+",),
    "ru_zaplatit": ("заплачу+",),
    "ru_myt": ("мо+ю", "мо+ем"),
    "ru_nachat": ("начала+", "на+чало", "на+чали"),
    "ru_pognat": ("погоню+", "погони+"),
}

HOMOGRAPH_MARKS: dict[str, dict[str, str]] = {
    verb_id: {_plain(spec): _stressed(spec) for spec in specs} for verb_id, specs in _SPECS.items()
}


def mark_word(verb_id: str, word: str) -> str:
    """Return word with its curated stress mark, or unchanged. Keeps a capital first letter."""
    marked = HOMOGRAPH_MARKS.get(verb_id, {}).get(word.lower())
    if marked is None:
        return word
    return marked[0].upper() + marked[1:] if word[:1].isupper() else marked


def mark_text(verb_id: str, text: str) -> str:
    """Mark every curated word in a sentence for display."""
    if verb_id not in HOMOGRAPH_MARKS:
        return text
    return _WORD.sub(lambda match: mark_word(verb_id, match.group(0)), text)
