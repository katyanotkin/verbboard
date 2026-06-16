"""Tests for verbs page display batch configuration.

Covers:
- window.VB_DISPLAY_BATCH is correctly embedded from Settings
- The show-more wrapper element is always present in server HTML (JS controls visibility)
- Batch defaults match expected values
- VB_VERBS slice and VB_VERBS_TOTAL behave correctly together with display batch
"""

from __future__ import annotations

import dataclasses
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.models import VerbEntry
from core.settings import load_settings as _real_load_settings


def _make_entries(n: int) -> list[VerbEntry]:
    return [VerbEntry(id=f"en_v{i}", rank=i, lemma=f"verb{i}", forms={}, examples=[]) for i in range(1, n + 1)]


def _settings_with(limit: int = 0, batch: int = 20):
    return dataclasses.replace(_real_load_settings(), verbs_page_limit=limit, verbs_display_batch=batch)


def _extract(html: str, marker: str) -> str:
    start = html.index(marker) + len(marker)
    end = html.index(";", start)
    return html[start:end].strip()


# ── VB_DISPLAY_BATCH embedding ────────────────────────────────────────────────


def test_vb_display_batch_embedded_in_html(client: TestClient) -> None:
    """window.VB_DISPLAY_BATCH must reflect the Settings value, not a hardcoded default."""
    with (
        patch("app.routes.verbs.load_entries_for_language", return_value=_make_entries(5)),
        patch("app.routes.verbs.load_settings", return_value=_settings_with(batch=7)),
    ):
        resp = client.get("/verbs?language=en")

    assert resp.status_code == 200
    raw = _extract(resp.text, "window.VB_DISPLAY_BATCH = ")
    assert int(raw) == 7, f"Expected VB_DISPLAY_BATCH=7, got {raw!r}"


def test_vb_display_batch_default_value(client: TestClient) -> None:
    """When no override, VB_DISPLAY_BATCH must equal the Settings default (20)."""
    settings = _real_load_settings()
    with patch("app.routes.verbs.load_entries_for_language", return_value=_make_entries(3)):
        resp = client.get("/verbs?language=en")

    assert resp.status_code == 200
    raw = _extract(resp.text, "window.VB_DISPLAY_BATCH = ")
    assert int(raw) == settings.verbs_display_batch


def test_vb_display_batch_changes_with_settings(client: TestClient) -> None:
    """Different batch values produce different VB_DISPLAY_BATCH in the response."""
    entries = _make_entries(50)
    for expected_batch in (5, 10, 25):
        with (
            patch("app.routes.verbs.load_entries_for_language", return_value=entries),
            patch(
                "app.routes.verbs.load_settings",
                return_value=_settings_with(batch=expected_batch),
            ),
        ):
            resp = client.get("/verbs?language=en")

        raw = _extract(resp.text, "window.VB_DISPLAY_BATCH = ")
        assert int(raw) == expected_batch, (
            f"Batch={expected_batch}: expected VB_DISPLAY_BATCH={expected_batch}, got {raw!r}"
        )


# ── Show-more wrapper always present ─────────────────────────────────────────


def test_show_more_wrapper_always_in_html(client: TestClient) -> None:
    """The show-more wrapper must be present in server HTML regardless of verb count.
    JS controls its visibility; the element must always exist as an anchor point.
    """
    with patch("app.routes.verbs.load_entries_for_language", return_value=_make_entries(3)):
        resp = client.get("/verbs?language=en")

    assert 'id="vb-load-more-wrap"' in resp.text


def test_show_more_button_always_in_html(client: TestClient) -> None:
    """The show-more button must be in server HTML; its display is toggled by JS."""
    with patch("app.routes.verbs.load_entries_for_language", return_value=_make_entries(1)):
        resp = client.get("/verbs?language=en")

    assert 'id="vb-load-more"' in resp.text


# ── VB_VERBS_TOTAL vs VB_DISPLAY_BATCH independence ──────────────────────────


def test_vb_verbs_total_independent_of_display_batch(client: TestClient) -> None:
    """VB_VERBS_TOTAL reflects total Firestore count; VB_DISPLAY_BATCH is the JS display unit.
    Regression guard: a misconfigured batch must not corrupt the total count.
    """
    entries = _make_entries(40)
    with (
        patch("app.routes.verbs.load_entries_for_language", return_value=entries),
        patch("app.routes.verbs.load_settings", return_value=_settings_with(batch=10)),
    ):
        resp = client.get("/verbs?language=en")

    assert resp.status_code == 200
    total = int(_extract(resp.text, "window.VB_VERBS_TOTAL = "))
    batch = int(_extract(resp.text, "window.VB_DISPLAY_BATCH = "))
    verbs_json = json.loads(_extract(resp.text, "window.VB_VERBS = ").rstrip(";"))

    assert total == 40, f"VB_VERBS_TOTAL should be 40, got {total}"
    assert batch == 10, f"VB_DISPLAY_BATCH should be 10, got {batch}"
    assert len(verbs_json) == 40, "VB_VERBS should contain all entries when page limit=0"


def test_two_batch_scenario_metadata_correct(client: TestClient) -> None:
    """With 25 verbs and batch=20: VB_VERBS has 25 entries, VB_DISPLAY_BATCH=20, total=25.

    This mirrors the 'two-batch' case: first 20 shown, show-more loads the remaining 5.
    The metadata must reflect this so JS can decide when to show the show-more button.
    """
    entries = _make_entries(25)
    with (
        patch("app.routes.verbs.load_entries_for_language", return_value=entries),
        patch("app.routes.verbs.load_settings", return_value=_settings_with(batch=20)),
    ):
        resp = client.get("/verbs?language=en")

    assert resp.status_code == 200
    total = int(_extract(resp.text, "window.VB_VERBS_TOTAL = "))
    batch = int(_extract(resp.text, "window.VB_DISPLAY_BATCH = "))
    verbs_json = json.loads(_extract(resp.text, "window.VB_VERBS = ").rstrip(";"))

    assert len(verbs_json) == 25, "VB_VERBS must have all 25 verbs"
    assert batch == 20, "VB_DISPLAY_BATCH must be 20"
    assert total == 25, "VB_VERBS_TOTAL must be 25"
    assert len(verbs_json) > batch, "VB_VERBS count exceeds VB_DISPLAY_BATCH -- show-more button should appear"
