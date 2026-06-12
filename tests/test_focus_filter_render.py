"""Regression tests: conjugation row focus filter — data attributes and filter UI.

Two separate things must be correct for the focus filter (gender / number hide) to work:

1. Every conjugation <tr> that should be filterable carries `data-gender` and/or
   `data-number` attributes. learn.js reads these to decide which rows to hide.

2. The filter button panel (.persona-btn / .number-btn) must be rendered for
   languages that have gendered/numbered rows (HE, RU, ES) and absent for EN.
   render.py passes `show_gender_filter` and `show_number_filter` flags to
   board.html; these tests verify the flags produce the right HTML.
"""

from __future__ import annotations

import pytest

from core.models import Board, VerbEntry
from core.render import render_board_html


def _board(language: str, rows: list[dict]) -> Board:
    verb = VerbEntry(id=f"{language}_test", rank=1, lemma="test", forms={}, examples=[])
    return Board(
        language=language,
        verb=verb,
        voice_key="female",
        voice_label="Female",
        sections=[{"title": "", "rows": rows}],
    )


# ── data-gender / data-number attribute rendering ─────────────────────────────


def test_row_with_gender_and_number_emits_both_attrs() -> None:
    """A row dict carrying both gender and number must produce both data-* attrs."""
    rows = [
        {
            "key": "pres_m_sg",
            "label": "הוא",
            "text": "הולך",
            "gender": "m",
            "number": "sg",
        }
    ]
    html = render_board_html(_board("he", rows), ui_lang="en")
    assert "data-gender='m'" in html
    assert "data-number='sg'" in html


def test_row_with_number_only_emits_number_no_gender() -> None:
    """A row with only `number` must not produce a data-gender attribute."""
    rows = [{"key": "past_pl", "label": "они", "text": "шли", "number": "pl"}]
    html = render_board_html(_board("ru", rows), ui_lang="en")
    assert "data-number='pl'" in html
    assert "data-gender" not in html


def test_row_without_filter_keys_has_no_data_attrs() -> None:
    """Rows with neither gender nor number (e.g. aspect/pair) must produce no data-* attrs."""
    rows = [{"key": "aspect", "label": "Aspect", "text": "несов."}]
    html = render_board_html(_board("ru", rows), ui_lang="en")
    assert "data-gender" not in html
    assert "data-number" not in html


# ── HE present tense — all four gendered forms ───────────────────────────────


@pytest.mark.parametrize(
    "key,label,text,gender,number",
    [
        ("pres_m_sg", "הוא", "הולך", "m", "sg"),
        ("pres_f_sg", "היא", "הולכת", "f", "sg"),
        ("pres_m_pl", "הם", "הולכים", "m", "pl"),
        ("pres_f_pl", "הן", "הולכות", "f", "pl"),
    ],
)
def test_he_present_row_data_attrs(key, label, text, gender, number) -> None:
    rows = [{"key": key, "label": label, "text": text, "gender": gender, "number": number}]
    html = render_board_html(_board("he", rows), ui_lang="en")
    assert f"data-gender='{gender}'" in html, f"missing data-gender for {key}"
    assert f"data-number='{number}'" in html, f"missing data-number for {key}"


# ── RU past tense — gendered singular forms + neutral plural ──────────────────


@pytest.mark.parametrize(
    "key,gender,number",
    [
        ("past_m", "m", "sg"),
        ("past_f", "f", "sg"),
        ("past_n", "n", "sg"),  # neuter: RU has a third gender HE does not
    ],
)
def test_ru_past_gendered_rows_data_attrs(key, gender, number) -> None:
    rows = [
        {
            "key": key,
            "label": "label",
            "text": "шёл",
            "gender": gender,
            "number": number,
        }
    ]
    html = render_board_html(_board("ru", rows), ui_lang="en")
    assert f"data-gender='{gender}'" in html
    assert f"data-number='{number}'" in html


def test_ru_past_plural_has_number_not_gender() -> None:
    """RU past plural (они) has number but no gender — omitting gender is intentional."""
    rows = [{"key": "past_pl", "label": "они", "text": "шли", "number": "pl"}]
    html = render_board_html(_board("ru", rows), ui_lang="en")
    assert "data-number='pl'" in html
    assert "data-gender" not in html


# ── ES — number only, never gender ────────────────────────────────────────────


@pytest.mark.parametrize("number", ["sg", "pl"])
def test_es_rows_have_number_not_gender(number: str) -> None:
    """Spanish plugin never produces gender on rows; only number filtering applies."""
    rows = [{"key": f"pres_{number}", "label": "yo", "text": "hablo", "number": number}]
    html = render_board_html(_board("es", rows), ui_lang="en")
    assert f"data-number='{number}'" in html
    assert "data-gender" not in html


# ── EN — no filter attributes at all ─────────────────────────────────────────


def test_en_rows_have_no_filter_attributes() -> None:
    rows = [{"key": "base", "label": "Base", "text": "go"}]
    html = render_board_html(_board("en", rows), ui_lang="en")
    assert "data-gender" not in html
    assert "data-number" not in html


# ── Filter button panel presence by language ─────────────────────────────────
# render.py passes show_gender_filter / show_number_filter to board.html.
# board.html renders .persona-btn (gender) and .number-btn (number) only when set.


@pytest.mark.parametrize(
    "language,expect_gender_btn,expect_number_btn",
    [
        ("he", True, True),  # Hebrew: both
        ("ru", True, True),  # Russian: both
        ("es", False, True),  # Spanish: number only
        ("en", False, False),  # English: neither
    ],
)
def test_filter_buttons_present_for_correct_languages(
    language: str, expect_gender_btn: bool, expect_number_btn: bool
) -> None:
    """Gender and number filter buttons must appear only for languages that need them.

    This guards against accidentally adding or removing a language from the filter set
    in render.py without also having the data-* attributes on the rows.
    """
    rows = [{"key": "test", "label": "L", "text": "T"}]
    html = render_board_html(_board(language, rows), ui_lang="en")

    gender_present = "persona-btn" in html
    number_present = "number-btn" in html

    assert (
        gender_present == expect_gender_btn
    ), f"language={language}: expected persona-btn present={expect_gender_btn}, got {gender_present}"
    assert (
        number_present == expect_number_btn
    ), f"language={language}: expected number-btn present={expect_number_btn}, got {number_present}"
