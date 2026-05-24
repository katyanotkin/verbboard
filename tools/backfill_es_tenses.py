"""
Backfill missing tenses (imperfect, future, imperative) for existing Spanish verbs.

Reads all Spanish verbs from Firestore, identifies those missing one or more of
the target tenses, submits a single Anthropic Message Batch for all of them, then
merges ONLY the new forms into each Firestore document (existing present/preterite
are never touched).

Usage (from project root, needs GCP auth + ANTHROPIC_API_KEY in .env):

    python -m tools.backfill_es_tenses
    python -m tools.backfill_es_tenses --dry-run
    python -m tools.backfill_es_tenses --collection verb_candidates  # for stage
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from datetime import UTC, datetime
from typing import Any

import anthropic
from dotenv import load_dotenv
from google.cloud import firestore

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TARGET_TENSES = ("imperfect", "future", "imperative")
POLL_INTERVAL = 30

_BACKFILL_SYSTEM_TEXT = """\
You are a Spanish conjugation generator.
Return raw valid JSON only — no markdown fences, no prose. Begin with `{`.

Schema:
{
  "imperfect":  { "yo": "...", "tu": "...", "el": "...", "nos": "...", "ellos": "..." },
  "future":     { "yo": "...", "tu": "...", "el": "...", "nos": "...", "ellos": "..." },
  "imperative": { "tu": "...", "vosotros": "...", "usted": "...", "ustedes": "..." }
}

Always return all three tense objects with all their slots filled."""

# Wrap in a cache_control block so all 43 batch requests share the cached prompt.
_BACKFILL_SYSTEM = [
    {
        "type": "text",
        "text": _BACKFILL_SYSTEM_TEXT,
        "cache_control": {"type": "ephemeral"},
    }
]


def _parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    return json.loads(text)


def _needs_backfill(forms: dict[str, Any]) -> bool:
    return any(not forms.get(t) for t in TARGET_TENSES)


def run(collection: str, project: str, api_key: str, dry_run: bool) -> None:
    db = firestore.Client(project=project)

    docs = list(db.collection(collection).where("language", "==", "es").stream())
    logger.info("Fetched %d Spanish verbs from '%s'", len(docs), collection)

    to_backfill = [d for d in docs if _needs_backfill(d.to_dict().get("forms", {}))]
    logger.info(
        "%d need backfill  |  %d already complete",
        len(to_backfill),
        len(docs) - len(to_backfill),
    )

    if not to_backfill:
        logger.info("Nothing to do.")
        return

    for doc in to_backfill:
        d = doc.to_dict()
        missing = [t for t in TARGET_TENSES if not d.get("forms", {}).get(t)]
        logger.info("  %-20s  missing: %s", d.get("verb_id", doc.id), missing)

    if dry_run:
        logger.info("DRY RUN -- no API calls or Firestore writes.")
        return

    client = anthropic.Anthropic(api_key=api_key)

    id_to_doc: dict[str, Any] = {}
    requests = []
    for idx, doc in enumerate(to_backfill):
        d = doc.to_dict()
        lemma = d.get("lemma") or doc.id
        custom_id = f"es_backfill_{idx}"
        id_to_doc[custom_id] = doc
        requests.append(
            {
                "custom_id": custom_id,
                "params": {
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1024,
                    "system": _BACKFILL_SYSTEM,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Spanish verb (infinitive): {lemma}",
                        }
                    ],
                },
            }
        )

    batch = client.messages.batches.create(requests=requests)
    logger.info("Batch submitted: %s  (%d requests)", batch.id, len(requests))

    while True:
        batch = client.messages.batches.retrieve(batch.id)
        c = batch.request_counts
        logger.info(
            "  status=%-10s  processing=%d  succeeded=%d  errored=%d",
            batch.processing_status,
            c.processing,
            c.succeeded,
            c.errored,
        )
        if batch.processing_status == "ended":
            break
        time.sleep(POLL_INTERVAL)

    saved = errored = 0
    now = datetime.now(UTC).isoformat()

    for result in client.messages.batches.results(batch.id):
        doc = id_to_doc.get(result.custom_id)
        if doc is None:
            logger.warning("Unknown custom_id: %s", result.custom_id)
            continue

        verb_id = doc.to_dict().get("verb_id", doc.id)

        if result.result.type != "succeeded":
            logger.warning("FAIL  %-20s  type=%s", verb_id, result.result.type)
            errored += 1
            continue

        try:
            generated = _parse_json(result.result.message.content[0].text)
        except (json.JSONDecodeError, IndexError) as exc:
            logger.warning("PARSE %-20s  %s", verb_id, exc)
            errored += 1
            continue

        existing_forms = doc.to_dict().get("forms", {})
        update_payload: dict[str, Any] = {"updated_at": now}

        for tense in TARGET_TENSES:
            if not existing_forms.get(tense) and generated.get(tense):
                update_payload[f"forms.{tense}"] = generated[tense]
                logger.info("  +%-12s  %s", tense, verb_id)

        if len(update_payload) > 1:
            db.collection(collection).document(doc.id).update(update_payload)
            logger.info(
                "SAVED %-20s  (%d tenses added)", verb_id, len(update_payload) - 1
            )
            saved += 1
        else:
            logger.info("SKIP  %-20s  (nothing new in generated output)", verb_id)

    logger.info(
        "Done: %d saved  |  %d errored  |  batch=%s",
        saved,
        errored,
        batch.id,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill imperfect/future/imperative for existing Spanish verbs."
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("VERBS_COLLECTION", "verbs"),
        help="Firestore collection name (default: verbs)",
    )
    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        help="GCP project ID (or set GOOGLE_CLOUD_PROJECT)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be backfilled without making any API or Firestore calls.",
    )
    args = parser.parse_args()

    if not args.project:
        logger.error("--project or GOOGLE_CLOUD_PROJECT env var is required")
        return

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key and not args.dry_run:
        logger.error("ANTHROPIC_API_KEY is not set")
        return

    run(
        collection=args.collection,
        project=args.project,
        api_key=api_key,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
