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
