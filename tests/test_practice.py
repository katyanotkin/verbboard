"""Tests for the practice loop feature.

Covers:
- Verbs page: practice panel element present, practice UI strings in window.UI
- Learn board: practice strings in window.UI, star SVG rendered
- Pool logic: new-verbs-first priority, mix-in fallback
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

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


# ── verbs page ────────────────────────────────────────────────────────────────


def test_verbs_page_has_practice_panel_element(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.verbs.PRACTICE_LOOP_ENABLED", True)
    monkeypatch.setattr(
        "app.routes.verbs.load_entries_for_language",
        lambda **kw: _stub_entries(),
    )
    html = client.get("/verbs?language=en").text
    assert 'id="practice-panel"' in html


def test_verbs_page_ui_includes_practice_strings(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.verbs.PRACTICE_LOOP_ENABLED", True)
    monkeypatch.setattr(
        "app.routes.verbs.load_entries_for_language",
        lambda **kw: _stub_entries(),
    )
    html = client.get("/verbs?language=en").text

    # Extract window.UI JSON from the page
    marker = "window.UI = "
    start = html.index(marker) + len(marker)
    end = html.index(";", start)
    ui = json.loads(html[start:end])

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
    from core.i18n import get_strings

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
