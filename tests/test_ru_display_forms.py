from core.languages.ru.plugin import build_board
from core.models import VerbEntry


def _verb(display_forms):
    return VerbEntry(
        id="ru_test_verb",
        rank=1,
        lemma="платить",
        forms={
            "present": {"1sg": "плачу", "2sg": "платишь"},
            "past": {"m": "платил"},
            "imperative": {"sg": "плати"},
        },
        examples=[],
        morph={"aspect": "imperfective"},
        display_forms=display_forms,
    )


def _rows(board):
    return {row["key"]: row for section in board.sections for row in section["rows"]}


def test_display_form_is_shown_but_audio_keeps_plain_text():
    rows = _rows(build_board(_verb({"present": {"1sg": "плачу́"}}), "female", "Female"))

    assert rows["present_1sg"]["text"] == "плачу́"
    assert rows["present_1sg"]["tts_text"] == "плачу"
    assert rows["present_2sg"]["text"] == "платишь"
    assert "tts_text" not in rows["present_2sg"]


def test_no_display_forms_leaves_board_unchanged():
    rows = _rows(build_board(_verb(None), "female", "Female"))

    assert rows["present_1sg"]["text"] == "плачу"
    assert "tts_text" not in rows["present_1sg"]


def test_past_and_imperative_overrides_apply():
    rows = _rows(
        build_board(
            _verb({"past": {"m": "плати́л"}, "imperative": {"sg": "плати́"}}),
            "female",
            "Female",
        )
    )

    assert rows["past_m"]["text"] == "плати́л"
    assert rows["past_m"]["tts_text"] == "платил"
    assert rows["imp_sg"]["tts_text"] == "плати"


def test_empty_form_slot_is_not_filled_from_display_forms():
    rows = _rows(build_board(_verb({"present": {"3sg": "плати́т"}}), "female", "Female"))

    assert rows["present_3sg"]["text"] == ""
    assert "tts_text" not in rows["present_3sg"]


def test_stale_override_that_no_longer_matches_plain_form_is_ignored():
    rows = _rows(build_board(_verb({"present": {"1sg": "плачу́ю"}}), "female", "Female"))

    assert rows["present_1sg"]["text"] == "плачу"
    assert "tts_text" not in rows["present_1sg"]


def test_audio_hash_is_same_with_and_without_override():
    from core.audio_service import build_hashed_audio_key

    marked = _rows(build_board(_verb({"present": {"1sg": "плачу́"}}), "female", "Female"))["present_1sg"]
    plain = _rows(build_board(_verb(None), "female", "Female"))["present_1sg"]

    assert build_hashed_audio_key("present_1sg", marked["tts_text"]) == build_hashed_audio_key(
        "present_1sg", plain["text"]
    )
