from __future__ import annotations

from core.languages.config import ALL_STUDY_LANGUAGES, UI_LANGUAGES

# Derived from the single source of truth (core/languages/config.py) so a new
# study language can't be silently blanked out of analytics again (Italian and
# French sessions were recorded with no language while this was a hand-kept list).
_KNOWN_LANGUAGES: frozenset[str] = frozenset(ALL_STUDY_LANGUAGES) | frozenset(UI_LANGUAGES)


def _clean_lang(value: str) -> str:
    """Return value only if it is a known language code, else empty string."""
    return value if value in _KNOWN_LANGUAGES else ""


_KNOWN_UI_LANGUAGES: frozenset[str] = frozenset(UI_LANGUAGES)


def _clean_ui_lang(value: str) -> str:
    """Like _clean_lang, but only the interface languages (not study-only ones)."""
    return value if value in _KNOWN_UI_LANGUAGES else ""
