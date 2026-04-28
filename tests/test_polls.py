from __future__ import annotations

from core.polls import ACTIVE_POLL_ID, get_poll_question


def test_active_poll_id_is_set() -> None:
    assert ACTIVE_POLL_ID


def test_poll_question_english() -> None:
    q = get_poll_question(ACTIVE_POLL_ID, "en")
    assert len(q) > 5


def test_poll_question_russian() -> None:
    q = get_poll_question(ACTIVE_POLL_ID, "ru")
    assert len(q) > 5


def test_poll_question_spanish() -> None:
    q = get_poll_question(ACTIVE_POLL_ID, "es")
    assert len(q) > 5


def test_poll_question_hebrew() -> None:
    q = get_poll_question(ACTIVE_POLL_ID, "he")
    assert len(q) > 5


def test_poll_question_unknown_language_falls_back_to_english() -> None:
    en = get_poll_question(ACTIVE_POLL_ID, "en")
    zh = get_poll_question(ACTIVE_POLL_ID, "zh")
    assert zh == en


def test_poll_question_unknown_poll_id_returns_empty() -> None:
    assert get_poll_question("nonexistent_poll_xyz", "en") == ""


def test_poll_question_empty_poll_id_returns_empty() -> None:
    assert get_poll_question("", "en") == ""
