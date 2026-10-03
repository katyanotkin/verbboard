from core.languages.fr.plugin import build_board
from core.models import VerbEntry

_SLOTS = {"je": "a", "tu": "b", "il": "c", "nous": "d", "vous": "e", "ils": "f"}


def _titles(forms: dict) -> list[str]:
    verb = VerbEntry(id="fr_x", rank=1, lemma="x", forms=forms, examples=[])
    return [s["title"] for s in build_board(verb, "female", "F").sections if s.get("title")]


def test_conditional_and_subjunctive_sections_render_when_present():
    titles = _titles({"present": _SLOTS, "conditionnel_present": _SLOTS, "subjonctif_present": _SLOTS})
    assert "board.tense_conditional" in titles
    assert "board.tense_subjunctive" in titles


def test_sections_absent_for_verbs_without_the_data():
    titles = _titles({"present": _SLOTS})
    assert "board.tense_conditional" not in titles
    assert "board.tense_subjunctive" not in titles


def test_all_empty_slots_do_not_render_a_section():
    empty = {slot: "" for slot in _SLOTS}
    assert "board.tense_subjunctive" not in _titles({"subjonctif_present": empty})
