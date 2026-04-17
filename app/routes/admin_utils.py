from __future__ import annotations

import logging
from pathlib import Path

from core.settings import load_settings

logger = logging.getLogger(__name__)

_SETTINGS = load_settings()
ADMIN_PREFIX = f"/{_SETTINGS.admin_secret}"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

VERBS_COLLECTION = "verbs"
CANDIDATES_COLLECTION = "verb_candidates"

CANDIDATE_STATUSES = {
    "needs_generation",
    "pending",
    "to_be_fixed",
    "duplicate",
    "promoted",
}


def signal_collections() -> tuple[str, str]:
    """Return (signals_collection, labels_collection)."""
    return _SETTINGS.verb_signals_collection, _SETTINGS.verb_signal_labels_collection
