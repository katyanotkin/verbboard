"""Tests for the verbs_page_limit feature.

Covers:
- Default verbs_page_limit=20 is present on the Settings dataclass
- When verbs_page_limit=3 and 5 verbs exist, only 3 appear in window.VB_VERBS
- When verbs_page_limit=0, all verbs appear (unlimited mode)
- Entries are sorted by rank ascending before slicing -- top-ranked entries survive
"""

from __future__ import annotations

import dataclasses
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.models import VerbEntry
from core.settings import load_settings as _real_load_settings

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_entries(specs: list[tuple[str, int]]) -> list[VerbEntry]:
    """Build VerbEntry objects from (verb_id_suffix, rank) tuples."""
    return [
        VerbEntry(id=f"en_{suffix}", rank=rank, lemma=suffix, forms={}, examples=[])
        for suffix, rank in specs
    ]


def _settings_with_limit(limit: int, batch: int = 20):
    """Return a Settings instance with verbs_page_limit overridden."""
    return dataclasses.replace(
        _real_load_settings(), verbs_page_limit=limit, verbs_display_batch=batch
    )


def _extract_vb_verbs(html: str) -> list[dict]:
    """Parse window.VB_VERBS from rendered HTML and return the list."""
    marker = "window.VB_VERBS = "
    start = html.index(marker) + len(marker)
    end = html.index(";", start)
    return json.loads(html[start:end])


def _extract_vb_verbs_total(html: str) -> int:
    """Parse window.VB_VERBS_TOTAL from rendered HTML."""
    marker = "window.VB_VERBS_TOTAL = "
    start = html.index(marker) + len(marker)
    end = html.index(";", start)
    return int(html[start:end])


def _extract_progress_total_text(html: str) -> str:
    """Extract the text content of the server-rendered progress-total span."""
    marker = 'class="progress-total">'
    start = html.index(marker) + len(marker)
    end = html.index("</span>", start)
    return html[start:end]


# ── unit: Settings default ────────────────────────────────────────────────────


def test_settings_verbs_page_limit_default() -> None:
    """verbs_page_limit must default to 300 when VERBS_PAGE_LIMIT env var is absent."""
    settings = _real_load_settings()
    assert settings.verbs_page_limit == 300


def test_settings_verbs_display_batch_default() -> None:
    """verbs_display_batch must default to 20 when VERBS_DISPLAY_BATCH env var is absent."""
    settings = _real_load_settings()
    assert settings.verbs_display_batch == 20


def test_settings_page_limit_must_exceed_display_batch() -> None:
    """verbs_page_limit > verbs_display_batch must hold when page limit is non-zero."""
    import pytest

    from core.settings import _validate

    bad = dataclasses.replace(
        _real_load_settings(), verbs_page_limit=20, verbs_display_batch=20
    )
    with pytest.raises(ValueError, match="VERBS_PAGE_LIMIT"):
        _validate(bad)


# ── integration: limit applied ────────────────────────────────────────────────


def test_verbs_page_limit_slices_to_n(client: TestClient) -> None:
    """When verbs_page_limit=3 and 5 verbs are available, only 3 appear in VB_VERBS."""
    entries = _make_entries(
        [("alpha", 1), ("beta", 2), ("gamma", 3), ("delta", 4), ("epsilon", 5)]
    )
    with (
        patch("app.routes.verbs.load_entries_for_language", return_value=entries),
        patch(
            "app.routes.verbs.load_settings",
            return_value=_settings_with_limit(3, batch=1),
        ),
    ):
        resp = client.get("/verbs?language=en")

    assert resp.status_code == 200
    verbs = _extract_vb_verbs(resp.text)
    assert len(verbs) == 3


def test_verbs_page_limit_zero_returns_all(client: TestClient) -> None:
    """When verbs_page_limit=0, all verbs must appear in VB_VERBS (unlimited)."""
    entries = _make_entries(
        [("alpha", 1), ("beta", 2), ("gamma", 3), ("delta", 4), ("epsilon", 5)]
    )
    with (
        patch("app.routes.verbs.load_entries_for_language", return_value=entries),
        patch(
            "app.routes.verbs.load_settings",
            return_value=_settings_with_limit(0),
        ),
    ):
        resp = client.get("/verbs?language=en")

    assert resp.status_code == 200
    verbs = _extract_vb_verbs(resp.text)
    assert len(verbs) == 5


def test_verbs_page_limit_keeps_top_ranked_entries(client: TestClient) -> None:
    """With limit=3, the 3 lowest-rank (highest priority) entries must survive the cut.

    Entries are intentionally given out-of-order rank values to verify sorting
    happens before slicing.
    """
    # rank=5 is worst; ranks 1/2/3 should survive
    entries = _make_entries(
        [("worst", 5), ("second", 2), ("best", 1), ("third", 3), ("fourth", 4)]
    )
    with (
        patch("app.routes.verbs.load_entries_for_language", return_value=entries),
        patch(
            "app.routes.verbs.load_settings",
            return_value=_settings_with_limit(3, batch=1),
        ),
    ):
        resp = client.get("/verbs?language=en")

    assert resp.status_code == 200
    verbs = _extract_vb_verbs(resp.text)
    assert len(verbs) == 3

    surviving_ids = {v["id"] for v in verbs}
    assert "en_best" in surviving_ids
    assert "en_second" in surviving_ids
    assert "en_third" in surviving_ids
    assert "en_worst" not in surviving_ids
    assert "en_fourth" not in surviving_ids


# ── progress bar: total reflects full Firestore count, not loaded count ───────


def test_progress_total_shows_full_firestore_count(client: TestClient) -> None:
    """VB_VERBS_TOTAL and the progress-total span must equal the full Firestore
    count even when verbs_page_limit slices VB_VERBS to a smaller set."""
    entries = _make_entries([("a", 1), ("b", 2), ("c", 3), ("d", 4), ("e", 5)])
    with (
        patch("app.routes.verbs.load_entries_for_language", return_value=entries),
        patch(
            "app.routes.verbs.load_settings",
            return_value=_settings_with_limit(3, batch=1),
        ),
    ):
        resp = client.get("/verbs?language=en")

    assert resp.status_code == 200
    verbs = _extract_vb_verbs(resp.text)
    assert len(verbs) == 3, "only 3 verbs loaded into VB_VERBS"

    total = _extract_vb_verbs_total(resp.text)
    assert total == 5, f"VB_VERBS_TOTAL should be full Firestore count (5), got {total}"

    span_text = _extract_progress_total_text(resp.text)
    assert (
        "5" in span_text
    ), f"progress-total span should show full count 5, got {span_text!r}"
