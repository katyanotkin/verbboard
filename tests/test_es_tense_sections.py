from core.languages.es.plugin import build_board
from core.models import VerbEntry

_SLOTS = {"yo": "a", "tu": "b", "el": "c", "nos": "d", "vosotros": "e", "ellos": "f"}


def _titles(forms: dict) -> list[str]:
    verb = VerbEntry(id="es_x", rank=1, lemma="x", forms=forms, examples=[])
    return [s["title"] for s in build_board(verb, "female", "F").sections if s.get("title")]


def test_new_sections_render_when_present():
    titles = _titles(
        {
            "present": _SLOTS,
            "conditional": _SLOTS,
            "subjunctive_present": _SLOTS,
            "subjunctive_imperfect": _SLOTS,
        }
    )
    assert "board.tense_conditional" in titles
    assert "board.tense_subjunctive_present" in titles
    assert "board.tense_subjunctive_imperfect" in titles


def test_sections_absent_for_verbs_without_the_data():
    titles = _titles({"present": _SLOTS})
    assert not any("conditional" in t or "subjunctive" in t for t in titles)


def test_all_empty_slots_do_not_render_a_section():
    empty = {slot: "" for slot in _SLOTS}
    assert "board.tense_subjunctive_imperfect" not in _titles({"subjunctive_imperfect": empty})
