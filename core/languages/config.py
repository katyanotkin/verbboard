from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageConfig:
    display: str  # English canonical name
    native: str  # name in the language itself
    rtl: bool

    @property
    def home_label(self) -> str:
        if self.display == self.native:
            return self.display
        return f"{self.display} / {self.native}"


LANGUAGE: dict[str, LanguageConfig] = {
    "en": LanguageConfig("English", "English", False),
    "ru": LanguageConfig("Russian", "Русский", False),
    "he": LanguageConfig("Hebrew", "עברית", True),
    "es": LanguageConfig("Spanish", "Español", False),
}

# UI-language list (EN/RU/HE/ES) is identical across editions -- not edition config.
UI_LANGUAGES: tuple[str, ...] = tuple(LANGUAGE.keys())

# Study-language allowlists per edition. Free ships today's five languages
# (the original four plus Italian, moved to free 2026-09-07 -- an owner
# product call, not a content-readiness change); Plus adds French on top.
FREE_STUDY_LANGUAGES: tuple[str, ...] = tuple(LANGUAGE.keys()) + ("it",)
PLUS_EXTRA_STUDY_LANGUAGES: tuple[str, ...] = ("fr",)


def default_study_languages(edition: str) -> tuple[str, ...]:
    if edition == "plus":
        return FREE_STUDY_LANGUAGES + PLUS_EXTRA_STUDY_LANGUAGES
    return FREE_STUDY_LANGUAGES
