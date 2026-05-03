from __future__ import annotations

from core.languages.config import LANGUAGE

SUPPORTED_LANGUAGES = tuple(LANGUAGE.keys())


def supported_languages_list() -> list[str]:
    return list(SUPPORTED_LANGUAGES)


def supported_languages_with_all() -> list[str]:
    return supported_languages_list() + ["all"]
