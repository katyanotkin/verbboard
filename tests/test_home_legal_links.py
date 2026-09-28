"""The home page must link to the privacy policy and terms (Google OAuth branding
verification requires the app homepage to link to its privacy policy)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.i18n import SUPPORTED_UI_LANGS


@pytest.mark.parametrize("ui_language", sorted(SUPPORTED_UI_LANGS))
def test_home_links_to_privacy_and_terms(client: TestClient, ui_language: str) -> None:
    html = client.get(f"/?language=es&ui_language={ui_language}").text
    assert f'href="/privacy?ui_language={ui_language}"' in html
    assert f'href="/terms?ui_language={ui_language}"' in html
