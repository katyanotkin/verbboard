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

# Study-language allowlists per edition -- deliberately independent of
# UI_LANGUAGES/LANGUAGE.keys(). UI languages (what the interface itself is
# translated into) and study languages (what verbs a learner can pick) are
# separate axes that only historically coincided for the original four; a
# language can be a study language with no UI locale file (French has none)
# and, in principle, the reverse. Keeping this list explicit rather than
# derived from LANGUAGE.keys() prevents a real mistake that already
# happened once: a stray edit added "it" straight to LANGUAGE to "fix"
# something, which would have made Italian a UI language too and crashed
# every page calling get_strings("it") -- there is no app/i18n/it.json.
#
# Free ships today's five languages (the original four plus Italian, moved
# to free 2026-09-07 -- an owner product call, not a content-readiness
# change); Plus adds French on top.
FREE_STUDY_LANGUAGES: tuple[str, ...] = ("en", "ru", "he", "es", "it")
PLUS_EXTRA_STUDY_LANGUAGES: tuple[str, ...] = ("fr",)

# Every study language regardless of tier -- for tooling that must cover all
# registered study content irrespective of who's entitled to study it (e.g.
# audio caching), not just the currently-active edition's allowlist. Import
# this instead of hand-reconstructing FREE_STUDY_LANGUAGES + PLUS_EXTRA_
# STUDY_LANGUAGES, which silently drops a language out of such tooling the
# next time a language moves between tiers (bit us once: tools/cache_audio.py
# lost Italian from its --language choices when Italian moved to free, since
# it had its own FREE_STUDY_LANGUAGES-independent free/Plus union).
ALL_STUDY_LANGUAGES: tuple[str, ...] = FREE_STUDY_LANGUAGES + PLUS_EXTRA_STUDY_LANGUAGES


@dataclass(frozen=True)
class ScriptConfig:
    """Valid-letter definition for a study language's script, used by the
    garbage-query filter (core/verb_autogen.py's is_plausible_verb_query).
    Deliberately keyed by ALL_STUDY_LANGUAGES, not LANGUAGE -- that gate runs
    per study language regardless of UI-language status, so it needs it/fr
    too, which have no LANGUAGE/UI entry (see the comment on FREE_STUDY_
    LANGUAGES above for why LANGUAGE must not be extended to cover them)."""

    ascii_ok: bool  # True for Latin-script languages (plain ASCII a-z is valid)
    extra_letters: str = ""  # additional valid letters beyond the ascii_ok baseline:
    # accented Latin for es/it/fr, or the full alphabet for a non-Latin script


STUDY_LANGUAGE_SCRIPTS: dict[str, ScriptConfig] = {
    "en": ScriptConfig(ascii_ok=True),
    "es": ScriptConfig(ascii_ok=True, extra_letters="ñ"),
    "it": ScriptConfig(ascii_ok=True, extra_letters="àèéìíîòóùú"),
    "fr": ScriptConfig(ascii_ok=True, extra_letters="àâäéèêëïîôöùûüÿçœæ"),
    "ru": ScriptConfig(ascii_ok=False, extra_letters="абвгдеёжзийклмнопрстуфхцчшщъыьэюя"),
    "he": ScriptConfig(ascii_ok=False, extra_letters="אבגדהוזחטיכלמנסעפצקרשת"),
}


def default_study_languages(edition: str) -> tuple[str, ...]:
    if edition == "plus":
        return ALL_STUDY_LANGUAGES
    return FREE_STUDY_LANGUAGES
