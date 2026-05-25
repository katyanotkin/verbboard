"""
Bulk verb generation via Anthropic Message Batches API.

Reads a list of verb queries (one per line), checks Firestore to skip any that
already exist in the live verbs or candidates collections, submits the rest as
a single Anthropic batch job, then stores results as candidates and runs
translations. All prompts are identical to the online admin flow.

Usage (run from project root, needs GCP auth + ANTHROPIC_API_KEY in .env):

    python -m tools.bulk_generate --language es --input es_verbs.txt
    python -m tools.bulk_generate --language ru --input ru_verbs.txt --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import UTC, datetime
from typing import Any

import anthropic
from dotenv import load_dotenv
from google.cloud import firestore

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VERBS_COLLECTION = os.getenv("VERBS_COLLECTION", "verbs")
CANDIDATES_COLLECTION = os.getenv("VERB_CANDIDATES_COLLECTION", "verb_candidates")
POLL_INTERVAL = 30  # seconds between status checks


# ---------------------------------------------------------------------------
# Firestore skip gate
# ---------------------------------------------------------------------------


def _verb_exists(db: firestore.Client, language: str, query: str) -> str | None:
    """Return a short reason string if the verb is already in Firestore, else None.

    Mirrors the two-step check in generate_candidate: first a point read by
    expected verb_id, then find_verb_by_search_extract which catches inflected
    forms whose lemma resolves to an existing document (e.g. "идёт" -> ru_idti).
    """
    from core.storage.verb_document import build_storage_verb_id
    from core.storage.verb_repository import find_verb_by_search_extract

    verb_id = build_storage_verb_id(language=language, lemma=query)
    if db.collection(VERBS_COLLECTION).document(verb_id).get().exists:
        return f"live:{verb_id}"
    if db.collection(CANDIDATES_COLLECTION).document(verb_id).get().exists:
        return f"candidate:{verb_id}"
    if find_verb_by_search_extract(language, query) is not None:
        return "live:search_extract match"
    return None


# ---------------------------------------------------------------------------
# Batch request builder
# ---------------------------------------------------------------------------


def _build_request(language: str, query: str, idx: int) -> dict[str, Any]:
    from core.settings_ai import (
        _MAX_TOKENS,
        _MAX_TOKENS_DEFAULT,
        _MODEL,
        _MODEL_DEFAULT,
        get_cached_system,
    )

    # custom_id must match ^[a-zA-Z0-9_-]{1,64}$ — use an index; query is
    # recovered via the id_to_query mapping built before batch submission.
    return {
        "custom_id": f"{language}_{idx}",
        "params": {
            "model": _MODEL.get(language, _MODEL_DEFAULT),
            "max_tokens": _MAX_TOKENS.get(language, _MAX_TOKENS_DEFAULT),
            "system": get_cached_system(language),
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"language: {language}\n"
                        f"raw query (may be any inflected form): {query}"
                    ),
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# Result parsing + Firestore write
# ---------------------------------------------------------------------------


def _parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    return json.loads(text)


def _get_max_rank(db: firestore.Client, language: str) -> int:
    docs = db.collection(VERBS_COLLECTION).where("language", "==", language).stream()
    max_rank = 0
    for doc in docs:
        rank = doc.to_dict().get("rank")
        if isinstance(rank, (int, float)) and rank > max_rank:
            max_rank = int(rank)
    return max_rank


def _save_candidate(
    db: firestore.Client,
    language: str,
    query: str,
    generated: dict[str, Any],
    rank: int,
) -> tuple[str, dict[str, Any]]:
    from core.storage.verb_document import (
        build_search_extract_from_entry,
        build_storage_verb_id,
    )

    lemma = generated.get("lemma") or query
    verb_id = build_storage_verb_id(language=language, lemma=lemma)
    now = datetime.now(UTC).isoformat()

    payload: dict[str, Any] = {
        "language": language,
        "query": query,
        "verb_id": verb_id,
        "lemma": lemma,
        "morph": generated.get("morph") or None,
        "rank": rank,
        "status": "pending",
        "forms": generated.get("forms", {}),
        "examples": generated.get("examples", []),
        "search_extract": build_search_extract_from_entry(
            language=language, entry=generated
        ),
        "created_at": now,
        "updated_at": now,
    }

    pronoun_forms = generated.get("pronoun_forms")
    if pronoun_forms:
        payload["pronoun_forms"] = pronoun_forms

    db.collection(CANDIDATES_COLLECTION).document(verb_id).set(payload)
    return verb_id, payload


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------


def run(
    language: str,
    queries: list[str],
    project: str,
    api_key: str,
    dry_run: bool,
) -> None:
    db = firestore.Client(project=project)

    # --- Gate: skip verbs already in Firestore (no AI needed) ---
    to_generate: list[str] = []
    for query in queries:
        reason = _verb_exists(db, language, query)
        if reason:
            logger.info("SKIP  %-30s  (%s)", query, reason)
        else:
            to_generate.append(query)

    skipped_pre = len(queries) - len(to_generate)
    logger.info(
        "%d total  |  %d to generate  |  %d skipped (already exist)",
        len(queries),
        len(to_generate),
        skipped_pre,
    )

    if not to_generate:
        logger.info("Nothing to generate.")
        return

    if dry_run:
        logger.info("DRY RUN -- would submit %d requests:", len(to_generate))
        for q in to_generate:
            logger.info("  %s", q)
        return

    # --- Submit batch ---
    client = anthropic.Anthropic(api_key=api_key)
    id_to_query = {f"{language}_{i}": q for i, q in enumerate(to_generate)}
    requests = [_build_request(language, q, i) for i, q in enumerate(to_generate)]
    batch = client.messages.batches.create(requests=requests)
    logger.info("Batch submitted: %s  (%d requests)", batch.id, len(requests))

    # --- Poll until ended ---
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

    # --- Process results ---
    from core.translation_service import translate_examples

    max_rank = _get_max_rank(db, language)
    saved = skipped_post = errored = 0

    for result in client.messages.batches.results(batch.id):
        query = id_to_query.get(result.custom_id, result.custom_id)

        if result.result.type != "succeeded":
            logger.warning("FAIL   %-30s  type=%s", query, result.result.type)
            errored += 1
            continue

        try:
            generated = _parse_json(result.result.message.content[0].text)
        except (json.JSONDecodeError, IndexError) as exc:
            logger.warning("PARSE  %-30s  %s", query, exc)
            errored += 1
            continue

        # Post-generation duplicate check on the model-resolved lemma -- mirrors
        # generate_candidate which checks by doc ID and by search_extract.
        from core.storage.verb_document import build_storage_verb_id
        from core.storage.verb_repository import find_verb_by_search_extract

        lemma = generated.get("lemma") or query
        resolved_id = build_storage_verb_id(language=language, lemma=lemma)
        if db.collection(VERBS_COLLECTION).document(resolved_id).get().exists:
            logger.info("SKIP   %-30s -> %-20s  (already live)", query, resolved_id)
            skipped_post += 1
            continue
        if db.collection(CANDIDATES_COLLECTION).document(resolved_id).get().exists:
            logger.info(
                "SKIP   %-30s -> %-20s  (already candidate)", query, resolved_id
            )
            skipped_post += 1
            continue
        if find_verb_by_search_extract(language, lemma) is not None:
            logger.info(
                "SKIP   %-30s -> %-20s  (search_extract match)", query, resolved_id
            )
            skipped_post += 1
            continue

        max_rank += 1
        verb_id, payload = _save_candidate(db, language, query, generated, max_rank)
        logger.info("SAVED  %-30s -> %s", query, verb_id)
        saved += 1

        # Translate examples (same logic as online admin flow)
        try:
            translated = translate_examples(
                verb_lang=language,
                lemma=lemma,
                examples=payload["examples"],
                project=project,
                api_key=api_key,
            )
            if translated is not payload["examples"]:
                db.collection(CANDIDATES_COLLECTION).document(verb_id).update(
                    {
                        "examples": translated,
                        "updated_at": datetime.now(UTC).isoformat(),
                    }
                )
        except Exception:
            logger.exception("Translation failed for %s/%s", language, verb_id)

    logger.info(
        "Done: %d saved  |  %d skipped post-gen  |  %d errored  |  batch=%s",
        saved,
        skipped_post,
        errored,
        batch.id,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk verb generation via Anthropic Batch API."
    )
    parser.add_argument(
        "--language", required=True, help="Verb language: en / ru / he / es"
    )
    parser.add_argument(
        "--input",
        help="File with one verb query per line (omit to read from stdin)",
    )
    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        help="GCP project ID (or set GOOGLE_CLOUD_PROJECT)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check Firestore skip gate and list what would be submitted, no API calls.",
    )
    args = parser.parse_args()

    if not args.project:
        logger.error("--project or GOOGLE_CLOUD_PROJECT env var is required")
        sys.exit(1)

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY is not set")
        sys.exit(1)

    if args.input:
        with open(args.input) as fh:
            raw_lines = fh.readlines()
    else:
        raw_lines = sys.stdin.readlines()

    queries = [
        line.strip() for line in raw_lines if line.strip() and not line.startswith("#")
    ]
    if not queries:
        logger.error("No queries found in input")
        sys.exit(1)

    logger.info("Language: %s  |  %d queries loaded", args.language, len(queries))
    if args.dry_run:
        logger.info("DRY RUN -- no API calls or Firestore writes")

    run(
        language=args.language,
        queries=queries,
        project=args.project,
        api_key=api_key,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
