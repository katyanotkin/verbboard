"""Learn board render unit tests.

These tests call render_board_html() directly (no HTTP client needed) to verify
that the rendered board HTML contains correct feedback links and URL encoding.
"""

from __future__ import annotations

import re

import pytest

from core.models import Board, VerbEntry


def _make_board(verb: VerbEntry, *, row_key: str = "present_3sg", language: str = "en") -> Board:
    return Board(
        language=language,
        verb=verb,
        voice_key="female",
        voice_label="Female",
        sections=[
            {
                "title": "Present",
                "rows": [
                    {
                        "key": row_key,
                        "label": "Base",
                        "text": verb.forms.get(row_key, ""),
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


def test_jump_to_example_button_hidden_for_lemma_row(mock_verb: VerbEntry) -> None:
    """The bare dictionary-form row (key "lemma"/"base"/"infinitive" depending on
    language plugin) never has a matching example sentence, so it must never get
    a jump-to-example button even though the verb has examples (issue #11)."""
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb, row_key="base"), return_to="/?language=en")
    assert "jump-example-btn" not in html
    # The row's audio button must be unaffected -- only the magnifier is suppressed.
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


# ---------------------------------------------------------------------------
# pronoun reference block (issue #32)
# ---------------------------------------------------------------------------


def test_pronoun_block_renders_for_language_with_pronoun_data(mock_verb: VerbEntry) -> None:
    """mock_verb is English (board.language='en'), which has PRONOUNS data --
    the block must render with all six persons, in fixed PRONOUN_PERSONS order."""
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), return_to="/?language=en", ui_lang="ru")
    assert "pronoun-block" in html
    assert "pronoun-table" in html
    # English pronoun words, in 1sg/2sg/3sg/1pl/2pl/3pl order. Word cells get
    # a leading &nbsp; (issue #32 follow-up, 2026-09-15) for breathing room
    # from the cell edge, alongside the side-by-side translation column.
    i_index = html.index(">&nbsp;I<")
    you_index = html.index(">&nbsp;you<")
    he_index = html.index("he / she / it")
    we_index = html.index(">&nbsp;we<")
    they_index = html.index(">&nbsp;they<")
    assert i_index < you_index < he_index < we_index < they_index


def test_pronoun_block_absent_for_language_without_pronoun_data(
    mock_verb: VerbEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A future language plugin without PRONOUNS data must not error -- the
    block is silently skipped."""
    from core.render import render_board_html

    monkeypatch.setattr("core.render.PRONOUNS", {})
    html = render_board_html(_make_board(mock_verb), return_to="/?language=en", ui_lang="ru")
    assert "pronoun-block" not in html


def test_pronoun_block_translation_cell_empty_when_ui_lang_matches_verb_lang(
    mock_verb: VerbEntry,
) -> None:
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), return_to="/?language=en", ui_lang="en")
    assert "pronoun-block" in html
    # No Russian glosses should leak in when ui_lang == board.language.
    assert "я" not in html


def test_translation_toggle_independent_of_pronoun_data(mock_verb: VerbEntry) -> None:
    """Reveal decoupling (2026-09-16): pronoun translations no longer gate on
    #toggle-translations at all (they reveal on unwrapping .pronoun-block
    itself, via CSS [open], not this button) -- so having pronoun data for
    the language pair must NOT make the toggle appear on its own. mock_verb
    has zero example translations and zero lemma_translations for ui_lang;
    en/ru both have PRONOUNS data (would have triggered the old clause)."""
    from core.render import render_board_html

    assert not mock_verb.examples[0].translations
    assert not mock_verb.lemma_translations

    html = render_board_html(_make_board(mock_verb), return_to="/?language=en", ui_lang="ru")
    assert "toggle-translations" not in html


def test_pronoun_translation_independent_of_toggle_state(mock_verb: VerbEntry) -> None:
    """The pronoun translation cell must be revealable purely by the
    .pronoun-block[open] CSS selector, with no dependency on
    #learn-page.translations-visible -- confirm the old selector is gone
    and the new one is present in the stylesheet-driving markup contract
    (the reveal itself is a CSS rule in learn.css, not server-rendered
    state, so this pins the HTML side of the contract: the cell always
    renders with real content, never conditionally omitted based on
    whether the example-translation toggle would be shown)."""
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), return_to="/?language=en", ui_lang="ru")
    assert "toggle-translations" not in html  # no example/lemma translations for this mock
    assert "class='pronoun-translation'" in html
    assert ">я<" in html  # translation text always rendered, regardless of toggle absence


def test_pronoun_block_word_column_rtl_for_hebrew_study_language(mock_verb: VerbEntry) -> None:
    """Hebrew study language + non-Hebrew UI: pronoun-word cells (study-language
    script) need explicit dir="rtl" per the label_dir convention (same rule
    used for conj-label cells); the translation column stays ltr since
    ui_lang ("en") is not Hebrew."""
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb, language="he"), return_to="/?language=he", ui_lang="en")
    assert "pronoun-block" in html
    assert "class='pronoun-word' dir=\"rtl\"" in html
    assert "class='pronoun-translation' dir='ltr'" in html


def test_pronoun_block_translation_column_rtl_for_hebrew_ui_language(mock_verb: VerbEntry) -> None:
    """Non-Hebrew study language + Hebrew UI: the translation column (Hebrew
    glosses) must be dir="rtl"; the word column has no dir override since
    label_dir only fires when board.language itself is "he"."""
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb, language="en"), return_to="/?language=en", ui_lang="he")
    assert "pronoun-block" in html
    assert "class='pronoun-translation' dir='rtl'" in html
    assert "class='pronoun-word'>" in html  # no dir attribute injected


def test_pronoun_block_absent_for_real_unsupported_study_language(mock_verb: VerbEntry) -> None:
    """A study language genuinely absent from PRONOUNS (not monkeypatched --
    e.g. a mistyped/legacy language code) must not crash render_board_html()
    and must simply omit the block."""
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb, language="de"), return_to="/?language=de", ui_lang="ru")
    assert "pronoun-block" not in html


def test_pronoun_block_survives_unsupported_ui_language(mock_verb: VerbEntry) -> None:
    """A mistyped/unsupported ui_lang (not in PRONOUNS at all, distinct from
    the already-covered board.language == ui_lang case) must not crash and
    must leave the translation column empty rather than KeyError."""
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb, language="en"), return_to="/?language=en", ui_lang="xx")
    assert "pronoun-block" in html
    assert "class='pronoun-translation' dir='ltr'></td>" in html


# ---------------------------------------------------------------------------
# topbar Back vs bottom-nav Back href parity (bug fix, uncommitted at time of
# writing: board.html previously hardcoded bnav_back_href to
# /verbs?language=...&ui_language=..., ignoring return_to entirely, so the
# two Back controls could point to different places for the same page load).
# ---------------------------------------------------------------------------

_TOPBAR_BACK_RE = re.compile(r'<a href="([^"]*)" class="nav-btn nav-btn--ghost">')
_BNAV_BACK_RE = re.compile(r'<a href="([^"]*)" class="bnav-tab bnav-back"')


def _topbar_back_href(html: str) -> str:
    match = _TOPBAR_BACK_RE.search(html)
    assert match, "topbar Back link not found in rendered board HTML"
    return match.group(1)


def _bnav_back_href(html: str) -> str:
    match = _BNAV_BACK_RE.search(html)
    assert match, "bottom-nav Back link not found in rendered board HTML"
    return match.group(1)


def test_topbar_and_bnav_back_hrefs_match_for_valid_return_to(mock_verb: VerbEntry) -> None:
    """A valid return_to must produce identical Back hrefs for the topbar Back
    button and the bottom-nav Back tab -- both derive from the same validated
    return_to, so the two controls must never diverge for real navigation."""
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), return_to="/verbs?language=en")
    assert _topbar_back_href(html) == _bnav_back_href(html) == "/verbs?language=en"


def test_topbar_and_bnav_back_hrefs_diverge_intentionally_when_return_to_missing(
    mock_verb: VerbEntry,
) -> None:
    """Missing return_to falls back differently per control by design: topbar
    Back falls back to home, bottom-nav Back falls back to the verbs list --
    matching each control's own pre-existing standalone fallback."""
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), return_to=None)
    assert _topbar_back_href(html) == "/?language=en&amp;ui_language=en"
    assert _bnav_back_href(html) == "/verbs?language=en&amp;ui_language=en"


@pytest.mark.parametrize(
    "malicious_return_to",
    [
        "https://evil.example",
        "//evil.example",
        "/\\evil.example",
    ],
)
def test_malicious_return_to_rejected_falls_back_like_missing(mock_verb: VerbEntry, malicious_return_to: str) -> None:
    """An invalid/open-redirect return_to must be rejected by safe_return_to()
    and fall back exactly like a missing return_to for both controls, with no
    trace of the malicious value anywhere in the rendered page."""
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), return_to=malicious_return_to)
    assert "evil.example" not in html
    assert _topbar_back_href(html) == "/?language=en&amp;ui_language=en"
    assert _bnav_back_href(html) == "/verbs?language=en&amp;ui_language=en"
