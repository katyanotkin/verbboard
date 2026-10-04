from core.languages.it.plugin import build_board
from core.models import VerbEntry

_SLOTS = {"io": "a", "tu": "b", "lui": "c", "noi": "d", "voi": "e", "loro": "f"}


def _titles(forms: dict) -> list[str]:
    verb = VerbEntry(id="it_x", rank=1, lemma="x", forms=forms, examples=[])
    return [s["title"] for s in build_board(verb, "female", "F").sections if s.get("title")]


def test_new_sections_render_when_present():
    titles = _titles(
        {
            "presente": _SLOTS,
            "condizionale_presente": _SLOTS,
            "congiuntivo_presente": _SLOTS,
            "congiuntivo_imperfetto": _SLOTS,
        }
    )
    assert "board.tense_conditional" in titles
    assert "board.tense_subjunctive_present" in titles
    assert "board.tense_subjunctive_imperfect" in titles


def test_sections_absent_for_verbs_without_the_data():
    titles = _titles({"presente": _SLOTS})
    assert not any("conditional" in t or "subjunctive" in t for t in titles)
