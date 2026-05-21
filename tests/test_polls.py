from __future__ import annotations

import pytest

from core.polls import (
    ACTIVE_POLL_ID,
    get_poll_options,
    get_poll_question,
    get_poll_valid_answers,
)


def test_active_poll_id_is_set() -> None:
    assert ACTIVE_POLL_ID


@pytest.mark.parametrize("lang", ["en", "ru", "es", "he"])
def test_poll_question_supported_language(lang: str) -> None:
    q = get_poll_question(ACTIVE_POLL_ID, lang)
    assert len(q) > 5


def test_poll_question_unknown_language_falls_back_to_english() -> None:
    en = get_poll_question(ACTIVE_POLL_ID, "en")
    zh = get_poll_question(ACTIVE_POLL_ID, "zh")
    assert zh == en


def test_poll_question_unknown_poll_id_returns_empty() -> None:
    assert get_poll_question("nonexistent_poll_xyz", "en") == ""


def test_poll_question_empty_poll_id_returns_empty() -> None:
    assert get_poll_question("", "en") == ""


@pytest.mark.parametrize("lang", ["en", "ru", "es", "he"])
def test_poll_options_all_languages(lang: str) -> None:
    opts = get_poll_options(ACTIVE_POLL_ID, lang)
    assert len(opts) >= 2
    for value, label in opts:
        assert value and label


def test_poll_options_unknown_poll_id_returns_empty() -> None:
    assert get_poll_options("nonexistent_poll_xyz", "en") == []


def test_poll_valid_answers_match_options() -> None:
    valid = get_poll_valid_answers(ACTIVE_POLL_ID)
    opts = get_poll_options(ACTIVE_POLL_ID, "en")
    assert valid == {v for v, _ in opts}
    assert len(valid) >= 2
