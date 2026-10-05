from core.languages.he.plugin import build_board
from core.models import VerbEntry

_IMPERATIVE = {"ms": "אֱכֹל", "fs": "אִכְלִי", "mp": "אִכְלוּ", "fp": "אֱכֹלְנָה"}


def _board(imperative):
    forms = {"present": {}, "past": {}, "future": {}, "imperative": imperative}
    verb = VerbEntry(id="he_x", rank=1, lemma="לאכול", forms=forms, examples=[])
    return build_board(verb, "female", "F")


def _imperative_rows(board):
    return [
        row for section in board.sections if section.get("title") == "board.tense_imperative" for row in section["rows"]
    ]


def test_imperative_shows_masculine_feminine_singular_and_masculine_plural_only():
    rows = _imperative_rows(_board(_IMPERATIVE))

    assert [row["key"] for row in rows] == ["imper_ms", "imper_fs", "imper_mp"]
    assert [row["label"] for row in rows] == ["אתה", "את", "אתם"]
    assert [row["text"] for row in rows] == ["אֱכֹל", "אִכְלִי", "אִכְלוּ"]


def test_verb_with_no_natural_imperative_gets_no_section():
    assert _imperative_rows(_board({})) == []
    assert _imperative_rows(_board(None)) == []
