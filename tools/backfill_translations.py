"""
Backfill example translations for all verbs in Firestore.

Translates example sentences into all supported UI languages except the verb's
own language. Only fills missing translation keys — safe to re-run at any time.

Usage (run from project root, needs GCP auth + ANTHROPIC_API_KEY in .env):

    python -m tools.backfill_translations --language ru
    python -m tools.backfill_translations --language all --dry-run
    python -m tools.backfill_translations --language en --target-lang ru
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from google.cloud import firestore

from core.translation_service import SUPPORTED_LANGUAGES, translate_examples

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VERBS_COLLECTION = os.getenv("VERBS_COLLECTION", "verbs")


def _needs_translation(examples: list[dict], target_langs: list[str]) -> bool:
    return any(
        lang not in ex.get("translations", {})
        for ex in examples
        for lang in target_langs
        if isinstance(ex, dict) and isinstance(ex.get("dst"), str)
    )


def _strip_translations(examples: list[dict], target_langs: list[str]) -> list[dict]:
    stripped = []
    for ex in examples:
        if not isinstance(ex, dict):
            stripped.append(ex)
            continue
        existing = ex.get("translations", {})
        if isinstance(existing, dict):
            remaining = {k: v for k, v in existing.items() if k not in target_langs}
            stripped.append({**ex, "translations": remaining})
        else:
            stripped.append(ex)
    return stripped


def process_verb(
    doc_ref: firestore.DocumentReference,
    data: dict,
    target_langs: list[str] | None,
    project: str,
    api_key: str,
    dry_run: bool,
    force: bool = False,
) -> bool:
    verb_lang = data.get("language", "")
    lemma = data.get("lemma", "") or data.get("verb_id", "")
    if isinstance(lemma, dict):
        lemma = lemma.get("imperfective") or lemma.get("perfective") or str(lemma)

    examples: list[dict] = [
        ex for ex in data.get("examples", []) if isinstance(ex, dict) and isinstance(ex.get("dst"), str)
    ]
    if not examples:
        return False

    effective_targets = target_langs or [lang for lang in SUPPORTED_LANGUAGES if lang != verb_lang]

    if force:
        examples = _strip_translations(examples, effective_targets)
    elif not _needs_translation(examples, effective_targets):
        return False

    logger.info("  translating %d examples → %s", len(examples), effective_targets)
    if dry_run:
        return True

    translated = translate_examples(
        verb_lang=verb_lang,
        lemma=lemma,
        examples=examples,
        target_langs=effective_targets,
        project=project,
        api_key=api_key,
    )

    if translated is not examples:
        doc_ref.update(
            {
                "examples": translated,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )

    return True


def run(
    language: str,
    target_langs: list[str] | None,
    project: str,
    api_key: str,
    dry_run: bool,
    force: bool = False,
) -> None:
    db = firestore.Client(project=project)
    verb_langs = list(SUPPORTED_LANGUAGES) if language == "all" else [language]

    for verb_lang in verb_langs:
        logger.info("Processing language: %s", verb_lang)
        docs = db.collection(VERBS_COLLECTION).where("language", "==", verb_lang).stream()
        updated = skipped = 0
        for doc in docs:
            data = doc.to_dict()
            logger.info("  %s", data.get("verb_id", doc.id))
            if process_verb(doc.reference, data, target_langs, project, api_key, dry_run, force):
                updated += 1
            else:
                skipped += 1
        logger.info("  %s: %d updated, %d already complete", verb_lang, updated, skipped)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill example translations.")
    parser.add_argument(
        "--language",
        default="all",
        help="Verb language to process (en/ru/he/es/all). Default: all",
    )
    parser.add_argument(
        "--target-lang",
        dest="target_lang",
        help="Only fill translations into this UI language (optional filter).",
    )
    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        help="GCP project ID.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing to Firestore.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-translate even if translations already exist.",
    )
    args = parser.parse_args()

    if not args.project:
        logger.error("--project or GOOGLE_CLOUD_PROJECT is required")
        sys.exit(1)

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY is not set")
        sys.exit(1)

    if args.dry_run:
        logger.info("DRY RUN — no writes will be made")
    if args.force:
        logger.info("FORCE — existing translations will be overwritten")

    run(
        language=args.language,
        target_langs=[args.target_lang] if args.target_lang else None,
        project=args.project,
        api_key=api_key,
        dry_run=args.dry_run,
        force=args.force,
    )


if __name__ == "__main__":
    main()
