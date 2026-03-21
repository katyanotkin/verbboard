from __future__ import annotations

SUPPORTED_LANGUAGES = {"en", "ru", "he", "es"}


def supported_languages_list() -> list[str]:
    return sorted(SUPPORTED_LANGUAGES)


def supported_languages_with_all() -> list[str]:
    return supported_languages_list() + ["all"]
