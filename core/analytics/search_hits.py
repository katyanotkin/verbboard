"""Per-verb counter of searches that resolved to an existing verb.

demand_signal only records searches that MISSED. Once a verb exists (whether
hand-curated or generated on the spot by core.verb_autogen), a later search
for it lands directly on /learn and leaves no trace, so "do people search for
the verbs we generate again?" was unanswerable. One doc per (language,
verb_id) with an atomically incremented counter answers it without a
per-search write-amplified log; join against `verb_candidates` docs with
`source == "autogen"` to isolate generated verbs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from core.task_tracking import track

logger = logging.getLogger(__name__)

COLLECTION = "verb_search_hits"


def _record_search_hit(language: str, verb_id: str, source: str) -> None:
    from google.cloud import firestore

    from core.storage.firestore_db import get_db

    try:
        get_db().collection(COLLECTION).document(f"{language}_{verb_id}").set(
            {
                "language": language,
                "verb_id": verb_id,
                "hits": firestore.Increment(1),
                f"hits_{source}": firestore.Increment(1),
                "last_hit_at": datetime.now(UTC),
            },
            merge=True,
        )
    except Exception:
        logger.exception("Failed to record search hit for %s/%s", language, verb_id)


def record_search_hit(*, language: str, verb_id: str | None, source: str) -> None:
    """Fire-and-forget: count one search that resolved to `verb_id`.

    `source` is "search" (same-language search) or "search_by_lang"
    (English-to-target cross-language search). Never raises, never blocks the
    redirect the caller is about to return. Counts are best-effort and
    bot-inflatable (the search routes are public and unthrottled on the hit
    path), so read them as approximate popularity, not exact user counts.
    """
    if not language or not verb_id or source not in {"search", "search_by_lang"}:
        return
    track(asyncio.create_task(asyncio.to_thread(_record_search_hit, language, verb_id, source)))
