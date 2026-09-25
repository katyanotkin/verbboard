"""tools/backfill_translations.py --language all covers every study language (issue #59)."""

from __future__ import annotations

from core.languages.config import ALL_STUDY_LANGUAGES
from tools.backfill_translations import source_languages


def test_all_means_every_study_language_including_italian_and_french() -> None:
    languages = source_languages("all")
    assert set(languages) == set(ALL_STUDY_LANGUAGES)
    assert {"it", "fr"} <= set(languages)


def test_a_single_language_is_passed_through() -> None:
    assert source_languages("it") == ["it"]
