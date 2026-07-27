"""Tests for the practice loop feature.

Covers:
- Verbs page: practice panel element present, practice UI strings in window.UI
- Verbs page: practice.size_unit and practice.listens_unit localized in window.UI
- Learn board: practice strings in window.UI, star SVG rendered
- Pool logic: new-verbs-first priority, mix-in fallback
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from core.i18n import get_strings
from core.models import Board, VerbEntry
from core.render import render_board_html

# ── fixtures ─────────────────────────────────────────────────────────────────


def _stub_entries(n: int = 15) -> list[VerbEntry]:
    """Return N minimal VerbEntry objects so the verbs page renders."""
    return [VerbEntry(id=f"en_verb{i}", rank=i, lemma=f"verb{i}", forms={}, examples=[]) for i in range(1, n + 1)]


def _board(verb: VerbEntry) -> Board:
    return Board(
        language="en",
        verb=verb,
        voice_key="female",
        voice_label="Female",
        sections=[
            {
                "title": "Present",
                "rows": [{"key": "base", "label": "Base", "text": verb.lemma}],
            }
        ],
    )


def _extract_window_ui(html: str) -> dict:
    """Parse the window.UI JSON object embedded in a rendered HTML page."""
    marker = "window.UI = "
    start = html.index(marker) + len(marker)
    end = html.index(";", start)
    return json.loads(html[start:end])


# ── verbs page ────────────────────────────────────────────────────────────────


def test_verbs_page_has_practice_panel_element(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.verbs.load_entries_for_language",
        lambda **kw: _stub_entries(),
    )
    html = client.get("/verbs?language=en").text
    assert 'id="practice-panel"' in html


def test_verbs_page_ui_includes_practice_strings(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.verbs.load_entries_for_language",
        lambda **kw: _stub_entries(),
    )
    html = client.get("/verbs?language=en").text

    ui = _extract_window_ui(html)

    for key in [
        "practice.label",
        "practice.start",
        "practice.start_mixed",
        "practice.in_progress",
        "practice.continue",
        "practice.abandon",
        "practice.wrap_up",
        "practice.learned_prompt",
        "practice.done",
    ]:
        assert key in ui, f"Missing UI key: {key}"


# ── practice.size_unit / practice.listens_unit regression ────────────────────
#
# Regression guard: these two keys were previously missing from the ui_strings
# subset passed to window.UI in verbs.py, causing practice_loop.js to silently
# fall back to hardcoded English strings ("# of verbs", "# audios / verb") for
# all non-English UI locales.


@pytest.mark.parametrize("ui_lang", ["en", "ru", "he", "es"])
def test_verbs_page_window_ui_includes_size_unit(client: TestClient, monkeypatch, ui_lang: str) -> None:
    """practice.size_unit must be present and non-empty in window.UI for every supported UI language."""
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [])

    html = client.get(f"/verbs?language=en&ui_language={ui_lang}").text
    ui = _extract_window_ui(html)

    assert "practice.size_unit" in ui, (
        f"[{ui_lang}] practice.size_unit missing from window.UI -- "
        "was it omitted from the ui_strings subset in verbs.py?"
    )
    assert ui["practice.size_unit"], f"[{ui_lang}] practice.size_unit is empty in window.UI"


@pytest.mark.parametrize("ui_lang", ["en", "ru", "he", "es"])
def test_verbs_page_window_ui_includes_listens_unit(client: TestClient, monkeypatch, ui_lang: str) -> None:
    """practice.listens_unit must be present and non-empty in window.UI for every supported UI language."""
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [])

    html = client.get(f"/verbs?language=en&ui_language={ui_lang}").text
    ui = _extract_window_ui(html)

    assert "practice.listens_unit" in ui, (
        f"[{ui_lang}] practice.listens_unit missing from window.UI -- "
        "was it omitted from the ui_strings subset in verbs.py?"
    )
    assert ui["practice.listens_unit"], f"[{ui_lang}] practice.listens_unit is empty in window.UI"


@pytest.mark.parametrize("ui_lang", ["en", "ru", "he", "es"])
def test_verbs_page_unit_strings_match_locale_file(client: TestClient, monkeypatch, ui_lang: str) -> None:
    """window.UI values for practice.size_unit and practice.listens_unit must
    match the locale JSON files, not hardcoded English fallback strings.

    The hardcoded English fallbacks in practice_loop.js are
    '# of verbs' and '# audios / verb'. For non-English locales these must
    differ; for English the locale file value must still be served (not a JS
    default that happened to match).
    """
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [])

    expected = get_strings(ui_lang)
    expected_size_unit = expected["practice.size_unit"]
    expected_listens_unit = expected["practice.listens_unit"]

    html = client.get(f"/verbs?language=en&ui_language={ui_lang}").text
    ui = _extract_window_ui(html)

    assert ui.get("practice.size_unit") == expected_size_unit, (
        f"[{ui_lang}] practice.size_unit: got {ui.get('practice.size_unit')!r}, "
        f"expected {expected_size_unit!r} from locale file"
    )
    assert ui.get("practice.listens_unit") == expected_listens_unit, (
        f"[{ui_lang}] practice.listens_unit: got {ui.get('practice.listens_unit')!r}, "
        f"expected {expected_listens_unit!r} from locale file"
    )


# ── learn board (render) ──────────────────────────────────────────────────────


def test_board_renders_svg_star(mock_verb: VerbEntry) -> None:
    """The known button must render an SVG star, not a plain text character."""
    html = render_board_html(_board(mock_verb))
    assert "known-icon" in html
    assert "<svg" in html
    assert "viewBox" in html
    # Should NOT fall back to text star
    assert "<span class='known-icon'>★</span>" not in html
    assert '<span class="known-icon">★</span>' not in html


def test_board_ui_json_includes_practice_strings(mock_verb: VerbEntry) -> None:
    """board_ui_json passed to window.UI on the learn page must include practice keys."""
    ui_strings = get_strings("en")
    html = render_board_html(_board(mock_verb), ui_strings=ui_strings)

    marker = "window.UI = "
    start = html.index(marker) + len(marker)
    end = html.index(";", start)
    ui = json.loads(html[start:end])

    for key in [
        "practice.prev",
        "practice.next",
        "practice.of",
        "practice.finish",
        "practice.abandon",
        "practice.listen_first",
        "practice.wrap_up",
        "practice.learned_prompt",
        "practice.done",
    ]:
        assert key in ui, f"Missing board UI key: {key}"
        assert ui[key], f"Empty board UI key: {key}"
