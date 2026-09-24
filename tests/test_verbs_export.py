"""Tests for the Anki/CSV known-verbs export feature (GitHub issue #22).

Covers: the /api/verbs opt-in `translation` field the export flow relies on,
and the export button/script markup on the /verbs page.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import seed_spanish_verb


def test_api_verbs_omits_translation_by_default(client: TestClient, fake_db) -> None:
    seed_spanish_verb(fake_db)
    data = client.get("/api/verbs?language=es&offset=0&limit=5").json()
    assert data["verbs"]
    assert all("translation" not in v for v in data["verbs"])


def test_api_verbs_includes_translation_when_requested(client: TestClient, fake_db) -> None:
    seed_spanish_verb(fake_db)
    data = client.get("/api/verbs?language=es&offset=0&limit=5&include_translations=1&ui_language=en").json()
    assert data["verbs"]
    assert all("translation" in v for v in data["verbs"])
    assert any(v["translation"] for v in data["verbs"])


def test_verbs_page_has_hidden_export_button_and_script(client: TestClient) -> None:
    html = client.get("/verbs?language=es&ui_language=en").text
    assert 'id="vb-export-btn"' in html
    # The button's wrapper div (not the button itself) is hidden by default --
    # it now also wraps a help-hint, and JS toggles the wrapper's `hidden`
    # attribute (see verbs_export.js's updateVisibility()).
    assert 'id="vb-export-wrap" hidden' in html
    assert "verbs_export.js" in html


def test_verbs_page_embedded_verb_blob_has_no_translation_field(client: TestClient) -> None:
    # The export flow re-fetches everything via /api/verbs, so the initial
    # page's embedded VB_VERBS blob shouldn't carry the extra field for
    # every visitor -- only opt-in pagination calls should.
    html = client.get("/verbs?language=es&ui_language=en").text
    start = html.index("window.VB_VERBS = ")
    end = html.index(";\n", start)
    assert '"translation"' not in html[start:end]
