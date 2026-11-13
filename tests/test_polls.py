from __future__ import annotations

import pytest

from core.i18n import SUPPORTED_UI_LANGS
from core.polls import (
    ACTIVE_POLL_ID,
    POLL_OPTIONS,
    POLL_QUESTIONS,
    get_poll_options,
    get_poll_question,
    get_poll_valid_answers,
)

POLL_ID = "feature_priority"


def test_no_active_poll_by_default() -> None:
    assert ACTIVE_POLL_ID == ""


def test_retired_poll_infrastructure_still_defined() -> None:
    assert POLL_ID in POLL_QUESTIONS
    assert POLL_ID in POLL_OPTIONS
    assert get_poll_valid_answers("") == set()


@pytest.mark.parametrize("lang", sorted(SUPPORTED_UI_LANGS))
def test_poll_question_supported_language(lang: str) -> None:
    q = get_poll_question(POLL_ID, lang)
    assert len(q) > 5


def test_poll_question_unknown_language_falls_back_to_english() -> None:
    en = get_poll_question(POLL_ID, "en")
    zh = get_poll_question(POLL_ID, "zh")
    assert zh == en


def test_poll_question_unknown_poll_id_returns_empty() -> None:
    assert get_poll_question("nonexistent_poll_xyz", "en") == ""


def test_poll_question_empty_poll_id_returns_empty() -> None:
    assert get_poll_question("", "en") == ""


@pytest.mark.parametrize("lang", sorted(SUPPORTED_UI_LANGS))
def test_poll_options_all_languages(lang: str) -> None:
    opts = get_poll_options(POLL_ID, lang)
    assert len(opts) >= 2
    for value, label in opts:
        assert value and label


def test_poll_options_unknown_poll_id_returns_empty() -> None:
    assert get_poll_options("nonexistent_poll_xyz", "en") == []


def test_poll_valid_answers_match_options() -> None:
    valid = get_poll_valid_answers(POLL_ID)
    opts = get_poll_options(POLL_ID, "en")
    assert valid == {v for v, _ in opts}
    assert len(valid) >= 2
