"""Rate-nudge state of a signed-in user: users/{uid}.rate_nudge.

Every field only moves forward (max for counts and last_at, OR for tapped), and clients send
absolute values, so retries and out-of-order syncs from several devices are harmless.
The user doc's own updated_at / last_seen_at are never touched (admin Reports reads them).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from core.storage.firestore_db import get_db

logger = logging.getLogger(__name__)

USERS_COLLECTION = "users"
MAX_COUNT = 10000
COUNT_FIELDS = ("votd_opens", "votd_opens_at_last_ask", "completed", "asks")
STATE_FIELDS = (*COUNT_FIELDS, "last_at", "tapped")


def _as_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0
    return max(0, int(value))


def normalize_rate_nudge(raw: Any) -> dict[str, Any]:
    """Coerce a stored or incoming map into the full field set (missing/garbage -> 0/False)."""
    raw = raw if isinstance(raw, dict) else {}
    state: dict[str, Any] = {name: _as_int(raw.get(name)) for name in (*COUNT_FIELDS, "last_at")}
    state["tapped"] = raw.get("tapped") is True
    return state


def merge_rate_nudge(stored: Any, incoming: Any, *, now_ms: int) -> dict[str, Any]:
    """Pure monotonic merge. last_at is clamped to now_ms (a future value would block asks forever)."""
    left = normalize_rate_nudge(stored)
    right = normalize_rate_nudge(incoming)
    merged: dict[str, Any] = {name: max(left[name], right[name]) for name in (*COUNT_FIELDS, "last_at")}
    merged["last_at"] = min(merged["last_at"], max(0, now_ms))
    merged["tapped"] = left["tapped"] or right["tapped"]
    return merged


def sync_rate_nudge(uid: str, incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge the client's absolute state into the stored one and return the merged state.

    Read-merge-write (not transactional: the merge is monotonic, so the worst race is one
    device's newer value being written a moment later by the next sync). Writes nothing
    when the merge changes nothing.
    """
    doc = get_db().collection(USERS_COLLECTION).document(uid)
    snapshot: Any = doc.get()
    stored = ((snapshot.to_dict() or {}).get("rate_nudge") if snapshot.exists else None) or {}
    now = datetime.now(UTC)
    merged = merge_rate_nudge(stored, incoming, now_ms=int(now.timestamp() * 1000))
    stored_state = {name: stored.get(name) for name in STATE_FIELDS} if isinstance(stored, dict) else {}
    if merged != stored_state:
        doc.set({"rate_nudge": {**merged, "updated_at": now}}, merge=True)
    return merged
