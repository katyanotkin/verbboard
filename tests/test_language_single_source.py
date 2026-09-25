"""Study/UI language lists have one source of truth (core/languages/config.py).

Hand-kept copies drifted before: analytics blanked the language of every
Italian and French session because its own list stopped at four languages.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.analytics.daily_counters import _clean_lang, _clean_ui_lang
from core.editions import active_study_plugins, study_language_label
from core.i18n import get_strings
from core.languages.config import ALL_STUDY_LANGUAGES, UI_LANGUAGES


@pytest.mark.parametrize("code", sorted(set(ALL_STUDY_LANGUAGES) | set(UI_LANGUAGES)))
def test_analytics_keeps_every_configured_language(code: str) -> None:
    assert _clean_lang(code) == code


def test_analytics_still_rejects_unknown_language_codes() -> None:
    assert _clean_lang("xx") == ""
    assert _clean_lang("") == ""


@pytest.mark.parametrize("ui_lang", list(UI_LANGUAGES))
def test_about_page_lists_the_active_study_languages(client: TestClient, ui_lang: str) -> None:
    ui = get_strings(ui_lang)
    plugins = active_study_plugins()
    assert plugins, "edition must expose at least one study language"

    html = client.get(f"/about?ui_language={ui_lang}").text

    for code in plugins:
        assert study_language_label(code, plugins, ui) in html


@pytest.mark.parametrize("code", list(UI_LANGUAGES))
def test_ui_language_allowlist_keeps_only_interface_languages(code: str) -> None:
    assert _clean_ui_lang(code) == code


def test_ui_language_allowlist_rejects_study_only_languages() -> None:
    study_only = set(ALL_STUDY_LANGUAGES) - set(UI_LANGUAGES)
    assert study_only, "expected at least one study-only language"
    for code in study_only:
        assert _clean_ui_lang(code) == ""
