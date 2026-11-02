"""
Rebuild `search_extract` for live verbs whose stored list is missing searchable forms.

Backfills that added tenses to `forms` (fr/es/it modes, he imperative) never refreshed
`search_extract`, so searching e.g. "comian" (es_comer's imperfect) missed the verb and
logged a demand signal. This adds every form `build_search_extract_from_entry` would
produce; existing entries (including admin-added aliases) are kept, nothing is removed.

Usage (project root, needs GCP auth):

    python -m tools.rebuild_search_extract --dry-run
    python -m tools.rebuild_search_extract [--language es]
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime

from dotenv import load_dotenv

load_dotenv(override=True)

from core.storage.firestore_db import get_db  # noqa: E402
from core.storage.verb_document import build_search_extract_from_entry  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--language", default="")
    args = parser.parse_args()

    db = get_db()
    query = db.collection("verbs")
    if args.language:
        query = query.where("language", "==", args.language)

    changed = 0
    for snapshot in query.stream():
        data = snapshot.to_dict() or {}
        current = list(data.get("search_extract") or [])
        wanted = build_search_extract_from_entry(language=data.get("language", ""), entry=data)
        additions = [value for value in wanted if value not in set(current)]
        if not additions:
            continue
        changed += 1
        logger.info("%s: +%d entries", snapshot.id, len(additions))
        if not args.dry_run:
            snapshot.reference.update(
                {"search_extract": current + additions, "updated_at": datetime.now(UTC).isoformat()}
            )
    logger.info("%s %d verb(s)", "would update" if args.dry_run else "updated", changed)


if __name__ == "__main__":
    main()
