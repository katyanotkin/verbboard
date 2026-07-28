"""Learn board render unit tests.

These tests call render_board_html() directly (no HTTP client needed) to verify
that the rendered board HTML contains correct feedback links and URL encoding.
"""

from __future__ import annotations

from core.models import Board, VerbEntry


def _make_board(verb: VerbEntry) -> Board:
    return Board(
        language="en",
        verb=verb,
        voice_key="female",
        voice_label="Female",
        sections=[
            {
                "title": "Present",
                "rows": [
                    {
                        "key": "base",
                        "label": "Base",
                        "text": verb.forms.get("base", ""),
                        "href": "",
                    },
                ],
            }
        ],
    )


def test_learn_board_has_feedback_link(mock_verb: VerbEntry) -> None:
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), return_to="/?language=en")
    assert "/feedback?" in html
    assert "page=learn" in html
    assert "en_go" in html


def test_jump_to_example_button_renders_by_default(mock_verb: VerbEntry) -> None:
    """Default (no explicit flag passed) must match today's shipped behavior --
    the kill switch defaults on, so this is a no-op guard, not a new gate."""
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), return_to="/?language=en")
    assert "jump-example-btn" in html


def test_jump_to_example_button_hidden_when_disabled(mock_verb: VerbEntry) -> None:
    from core.render import render_board_html

    html = render_board_html(
        _make_board(mock_verb),
        return_to="/?language=en",
        jump_to_example_enabled=False,
    )
    assert "jump-example-btn" not in html
    # Play button and everything else must be unaffected -- only the jump
    # button itself is gated, not audio or the rest of the row.
    assert "audio" in html.lower()


def test_learn_board_feedback_link_url_encodes_learn_href(mock_verb: VerbEntry) -> None:
    """Feedback href must encode the learn page URL (not the back-button destination).

    The feedback link's return_to is always the learn page itself, so it always
    contains both ? (%3F) and & (%26) regardless of what return_to is passed.
    """
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), return_to="/?language=en")
    assert "%3F" in html  # ? in /learn?language=en is encoded
    assert "%26" in html  # & in &verb_id=en_go is encoded


def test_learn_board_feedback_return_to_is_learn_page_not_back_destination(
    mock_verb: VerbEntry,
) -> None:
    """Feedback return_to must point to learn page, independent of back-button destination."""
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), return_to="/verbs?language=en")
    assert "/learn" in html
    assert "%3F" in html
    assert "%26" in html
