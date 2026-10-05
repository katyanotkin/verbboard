"""Replay search demand that could not be generated during an Anthropic outage.

Dry run by default; --apply generates the verbs (one at a time).

    python -m tools.replay_failed_demand                      # window = last outage in provider_status/anthropic
    python -m tools.replay_failed_demand --since 2026-10-05T00:00:00+00:00 --until 2026-10-06T00:00:00+00:00
    python -m tools.replay_failed_demand --apply --clear-pair-markers

Selects demand_signal docs (source search / search_by_lang) for Claude-generated
autogen languages, dedupes by query, skips verbs that now exist, rejected
queries and implausible queries.

The default window is the outage recorded in provider_status/anthropic
(opened_at..closed_at). Signals logged BEFORE opened_at (the failing requests
that discovered the outage) fall outside it: pass --since for those. At most
--max-items (default 50) queries are handled per run. Afterwards run
`python -m tools.backfill_translations --language all` to fill Hebrew gaps.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=True)

from core.provider_health import provider_unavailable_reason  # noqa: E402
from core.search_utils import tokenize_text  # noqa: E402
from core.settings import load_settings  # noqa: E402
from core.storage.firestore_db import get_db  # noqa: E402
from core.storage.verb_repository import find_verb_by_search_extract  # noqa: E402
from core.verb_autogen import (  # noqa: E402
    _CLAUDE_AUTOGEN_LANGUAGES,
    AUTOGEN_LANGUAGES,
    autogenerate_missing_verb,
    check_verb_rejected,
    is_plausible_verb_query,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_PAIR_ATTEMPTS_COLLECTION = "verb_pair_generation_attempts"
_SOURCES = {"search", "search_by_lang"}
_LANGUAGES = AUTOGEN_LANGUAGES & _CLAUDE_AUTOGEN_LANGUAGES


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _default_window(db: Any) -> tuple[datetime, datetime]:
    doc = db.collection("provider_status").document("anthropic").get()
    data = (doc.to_dict() or {}) if doc.exists else {}
    if not data.get("opened_at"):
        raise SystemExit("No provider_status/anthropic outage recorded; pass --since/--until.")
    if data.get("closed_at"):
        until = _parse_iso(data["closed_at"])
    else:
        until = _parse_iso(data["updated_at"]) if data.get("updated_at") else datetime.now(UTC)
        print(f"Note: outage has no closed_at; using {until.isoformat()} as the end of the window.")
    return _parse_iso(data["opened_at"]), until


def _as_aware(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return None


def select_queries(db: Any, since: datetime, until: datetime) -> list[tuple[str, str]]:
    """Distinct (language, query) pairs from demand signals inside the window."""
    col = load_settings().verb_signals_collection
    seen: dict[tuple[str, str], None] = {}
    # created_at is the timestamp field log_missing_verb_search writes.
    try:
        docs = list(db.collection(col).where("created_at", ">=", since).stream())
    except Exception:
        docs = list(db.collection(col).stream())
    for doc in docs:
        data = doc.to_dict() or {}
        created = _as_aware(data.get("created_at"))
        if created is None or not (since <= created <= until):
            continue
        if data.get("source") not in _SOURCES or data.get("language") not in _LANGUAGES:
            continue
        query = str(data.get("query", "")).strip().casefold()
        if query:
            seen.setdefault((data["language"], query), None)
    return list(seen)


def classify_query(language: str, query: str) -> tuple[str, str | None]:
    """Return (decision, query_to_generate); decision is 'generate' or a skip reason."""
    if find_verb_by_search_extract(language, query):
        return "exists", None
    candidate = query
    if not is_plausible_verb_query(candidate, language):
        tokens = tokenize_text(query)
        if tokens and is_plausible_verb_query(tokens[0], language):
            candidate = tokens[0]
        else:
            return "implausible", None
    if find_verb_by_search_extract(language, candidate):
        return "exists", None
    if check_verb_rejected(language, candidate):
        return "rejected", None
    return "generate", candidate


def clear_pair_markers(db: Any, since: datetime, until: datetime, apply: bool) -> int:
    count = 0
    for doc in db.collection(_PAIR_ATTEMPTS_COLLECTION).stream():
        data = doc.to_dict() or {}
        if data.get("reason") != "generation_failed":
            continue
        try:
            attempted = _parse_iso(data.get("attempted_at", ""))
        except ValueError:
            continue
        if since <= attempted <= until:
            count += 1
            print(f"{'DELETE' if apply else 'would delete'} pair marker {doc.id}")
            if apply:
                doc.reference.delete()
    return count


async def _run(args: argparse.Namespace) -> None:
    db = get_db()
    if args.since:
        since = _parse_iso(args.since)
        until = _parse_iso(args.until) if args.until else datetime.now(UTC)
    else:
        since, until = _default_window(db)
    print(f"Window: {since.isoformat()} .. {until.isoformat()}  ({'APPLY' if args.apply else 'dry run'})")

    audio_backend = None
    if args.apply:
        from core.audio_backend.factory import create_audio_backend

        audio_backend = create_audio_backend(load_settings())

    counts: dict[str, int] = {}
    selected = select_queries(db, since, until)
    if len(selected) > args.max_items:
        print(
            f"{len(selected) - args.max_items} queries left out by --max-items {args.max_items}; re-run for the rest."
        )
        selected = selected[: args.max_items]
    for language, query in selected:
        decision, target = classify_query(language, query)
        if decision != "generate" or target is None:
            counts[decision] = counts.get(decision, 0) + 1
            print(f"skip ({decision}): {language}/{query}")
            continue
        if not args.apply:
            counts["would_generate"] = counts.get("would_generate", 0) + 1
            print(f"would generate: {language}/{target}")
            continue
        await autogenerate_missing_verb(language=language, query=target, audio_backend=audio_backend)
        if provider_unavailable_reason():
            print(f"Claude still unavailable ({provider_unavailable_reason()}); stopping.")
            counts["aborted"] = 1
            break
        created = find_verb_by_search_extract(language, target) is not None
        key = "generated" if created else "no_verb_created"
        counts[key] = counts.get(key, 0) + 1
        print(f"{key}: {language}/{target}")

    if args.clear_pair_markers:
        counts["pair_markers"] = clear_pair_markers(db, since, until, args.apply)

    print("Summary:", counts or "nothing to do")
    if args.apply:
        print("Next: python -m tools.backfill_translations --language all")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", help="ISO start (default: last outage opened_at)")
    parser.add_argument("--until", help="ISO end (default: outage closed_at, or now)")
    parser.add_argument("--max-items", type=int, default=50, help="max distinct queries per run (default 50)")
    parser.add_argument("--apply", action="store_true", help="generate verbs / delete markers (default: dry run)")
    parser.add_argument(
        "--clear-pair-markers",
        action="store_true",
        help="delete verb_pair_generation_attempts markers with reason generation_failed in the window",
    )
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
