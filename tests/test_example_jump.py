"""Form -> example jump (issue #123): path -> board row key mapping and button rendering."""

from __future__ import annotations

import importlib
import re

import pytest

from core.example_jump import examples_by_row_key, path_to_row_key
from core.fill_practice_service import _FORM_SHAPES, _placeholder_board
from core.models import Board, Example, VerbEntry
from core.registry import get as get_plugin
from core.render import render_board_html

for _lang in _FORM_SHAPES:
    importlib.import_module(f"core.languages.{_lang}.plugin")


def _paths(language: str) -> list[str]:
    paths = []
    for tense, persons in _FORM_SHAPES[language].items():
        paths += [tense] if persons is None else [f"{tense}.{person}" for person in persons]
    return paths


@pytest.mark.parametrize("language", sorted(_FORM_SHAPES))
def test_every_form_path_maps_to_a_real_row_key(language: str) -> None:
    mapping = path_to_row_key(language)
    board = _placeholder_board(language)
    existing = {str(row["key"]) for section in board.sections for row in section["rows"]}
    for path in _paths(language):
        assert path in mapping, (language, path)
        assert mapping[path] in existing, (language, path)


def test_special_shapes() -> None:
    assert path_to_row_key("pt")["subjunctive_future.eles"]
    assert path_to_row_key("ru")["past.f"]
    assert path_to_row_key("he")["imperative.ms"] == "imper_ms"
    assert path_to_row_key("tr")["aorist.onlar"]
    assert path_to_row_key("en")["gerund"] == "gerund"
    # No path maps to the lemma row.
    assert "present_continuous" not in path_to_row_key("tr")


def _tgt(tense: str, person: str | None, *, also: list[str] | None = None) -> dict:
    target: dict = {"tense": tense, "person": person, "start": 0, "end": 3, "answer": "abr", "alternatives": []}
    if also:
        target["also"] = also
    return target


def _verb(examples: list[Example]) -> VerbEntry:
    return VerbEntry(
        id="es_abrir",
        rank=1,
        lemma="abrir",
        forms={"present": {"yo": "abro", "el": "abre"}, "imperfect": {"yo": "abria", "el": "abria"}},
        examples=examples,
    )


def _render(verb: VerbEntry, **kwargs) -> str:
    board = get_plugin("es").build_board(verb, "female", "F")
    return render_board_html(
        Board(language="es", verb=verb, voice_key="female", voice_label="F", sections=board.sections), **kwargs
    )


def _row_html(html: str, row_key_text: str) -> str:
    return next(
        r
        for r in re.findall(r"<tr[^>]*data-form='[^']*'.*?</tr>", html, flags=re.S)
        if f"data-form='{row_key_text}'" in r
    )


def test_indexes_include_also_paths_and_skip_untagged() -> None:
    examples = [
        Example(dst="abro la puerta", target=_tgt("present", "yo")),
        Example(dst="sin etiqueta"),
        Example(dst="abria la puerta", target=_tgt("imperfect", "yo", also=["imperfect.el"])),
        Example(dst="abro otra", target=_tgt("present", "yo")),
    ]
    result = examples_by_row_key("es", examples)
    assert result["pres_yo"] == [1, 4]
    assert sorted(v[0] for k, v in result.items() if k != "pres_yo") == [3, 3]


def test_button_only_on_matched_rows_with_indexes() -> None:
    verb = _verb(
        [
            Example(dst="abro la puerta", target=_tgt("present", "yo")),
            Example(dst="abro otra", target=_tgt("present", "yo")),
        ]
    )
    html = _render(verb)
    assert html.count("jump-example-btn' title") == 1
    assert "data-jump-examples='1,2'" in html
    assert "data-example-index='1'" in html and "data-example-index='2'" in html
    assert "jump-example-btn" in _row_html(html, "abro")
    assert "jump-example-btn" not in _row_html(html, "abre")


def test_shared_form_also_cells_each_get_a_button() -> None:
    verb = _verb([Example(dst="abria", target=_tgt("imperfect", "yo", also=["imperfect.el"]))])
    html = _render(verb)
    assert html.count("data-jump-examples='1'") == 2


def test_no_button_without_match_or_when_disabled() -> None:
    assert "jump-example-btn' title" not in _render(_verb([Example(dst="sin etiqueta")]))
    verb = _verb([Example(dst="abro", target=_tgt("present", "yo"))])
    assert "jump-example-btn' title" not in _render(verb, jump_to_example_enabled=False)


def test_index_attribute_is_numeric_only() -> None:
    verb = _verb([Example(dst="abro", target=_tgt("present", "yo"))])
    assert re.search(r"data-jump-examples='[0-9,]+'", _render(verb))


def test_lemma_row_never_gets_a_button() -> None:
    en = VerbEntry(
        id="en_go",
        rank=1,
        lemma="go",
        forms={"base": "go", "past": "went", "past_participle": "gone", "present_3sg": "goes", "gerund": "going"},
        examples=[
            Example(
                dst="I go",
                target={"tense": "base", "person": None, "start": 2, "end": 4, "answer": "go", "alternatives": []},
            )
        ],
    )
    board = get_plugin("en").build_board(en, "female", "F")
    html = render_board_html(
        Board(language="en", verb=en, voice_key="female", voice_label="F", sections=board.sections)
    )
    for row in re.findall(r"<tr[^>]*data-form='go'.*?</tr>", html, flags=re.S):
        if "conj-label" in row and ">Base<" in row:
            assert "jump-example-btn" not in row
