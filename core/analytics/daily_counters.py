from __future__ import annotations

_KNOWN_LANGUAGES: frozenset[str] = frozenset({"en", "ru", "he", "es"})


def _clean_lang(value: str) -> str:
    """Return value only if it is a known language code, else empty string."""
    return value if value in _KNOWN_LANGUAGES else ""
