from core.languages.ru.homographs import HOMOGRAPH_MARKS, mark_text, mark_word
from core.languages.ru.plugin import build_board
from core.languages.ru.stress import strip_stress_marks
from core.models import VerbEntry


def test_every_entry_is_the_plain_form_plus_marks_only():
    for verb_id, marks in HOMOGRAPH_MARKS.items():
        for plain, marked in marks.items():
            assert strip_stress_marks(marked) == plain, (verb_id, plain)
            assert marked.count("́") == 1, (verb_id, plain)


def test_mark_text_marks_the_verbs_own_words_and_keeps_capitals():
    assert mark_text("ru_myt", "Я мою руки перед каждым приёмом пищи.") == "Я мо́ю руки перед каждым приёмом пищи."
    assert mark_text("ru_pognat", "Погони его со двора!") == "Погони́ его со двора!"
    assert mark_word("ru_nachat", "Начало") == "На́чало"


def test_entries_are_scoped_to_one_verb():
    assert mark_text("ru_platit", "Я мою маму.") == "Я мою маму."
    assert mark_text("ru_unknown", "Я плачу.") == "Я плачу."


def test_words_that_only_contain_a_key_are_not_marked():
    assert mark_text("ru_myt", "Я моюсь и мою.") == "Я моюсь и мо́ю."


def test_board_rows_get_curated_marks_without_display_forms_and_keep_plain_audio_text():
    verb = VerbEntry(
        id="ru_myt",
        rank=1,
        lemma="мыть",
        forms={"present": {"1sg": "мою", "1pl": "моем", "2sg": "моешь"}},
        examples=[],
        morph={"aspect": "imperfective"},
    )

    rows = {row["key"]: row for section in build_board(verb, "female", "Female").sections for row in section["rows"]}

    assert rows["present_1sg"]["text"] == "мо́ю"
    assert rows["present_1sg"]["tts_text"] == "мою"
    assert rows["present_1pl"]["text"] == "мо́ем"
    assert rows["present_2sg"]["text"] == "моешь"
    assert "tts_text" not in rows["present_2sg"]
    assert rows["lemma"]["text"] == "мыть"


def test_example_sentence_shows_the_mark_but_audio_key_stays_plain():
    from core.audio_service import build_hashed_audio_key
    from core.models import Board, Example
    from core.render import render_board_html

    sentence = "Я мою руки перед каждым приёмом пищи."
    verb = VerbEntry(
        id="ru_myt",
        rank=1,
        lemma="мыть",
        forms={"present": {"1sg": "мою"}},
        examples=[Example(dst=sentence)],
        morph={"aspect": "imperfective"},
    )
    board = Board(language="ru", verb=verb, voice_key="female", voice_label="Female", sections=[])

    html = render_board_html(board, ui_lang="en")

    assert "Я мо́ю руки перед каждым приёмом пищи." in html
    assert build_hashed_audio_key("example_1", sentence) in html


def _board_html(verb_id):
    from core.models import Board
    from core.render import render_board_html

    verb = VerbEntry(
        id=verb_id,
        rank=1,
        lemma="x",
        forms={"present": {"1sg": "мою"}},
        examples=[],
        morph={"aspect": "imperfective"},
    )
    board = Board(language="ru", verb=verb, voice_key="female", voice_label="Female", sections=[])
    return render_board_html(board, ui_strings={"board.stress_note": "NOTE-LINE"}, ui_lang="en")


def test_stress_note_is_shown_only_for_curated_verbs():
    assert "NOTE-LINE" in _board_html("ru_myt")
    assert "NOTE-LINE" not in _board_html("ru_idti")


def test_display_forms_override_takes_precedence_over_curated_mark():
    verb = VerbEntry(
        id="ru_myt",
        rank=1,
        lemma="мыть",
        forms={"present": {"1sg": "мою"}},
        examples=[],
        morph={"aspect": "imperfective"},
        display_forms={"present": {"1sg": "мою́"}},
    )

    rows = {row["key"]: row for section in build_board(verb, "female", "Female").sections for row in section["rows"]}

    assert rows["present_1sg"]["text"] == "мою́"
