"""
Backfill example and/or lemma translations for all verbs in Firestore.

Translates example sentences and/or verb infinitives into all supported UI
languages except the verb's own language. Only fills missing translation
keys — safe to re-run at any time.

Usage (run from project root, needs GCP auth + ANTHROPIC_API_KEY in .env):

    python -m tools.backfill_translations --language ru
    python -m tools.backfill_translations --language all --dry-run
    python -m tools.backfill_translations --language en --target-lang ru
    python -m tools.backfill_translations --language fr --field lemma
    python -m tools.backfill_translations --language it --field examples --force

--field defaults to "both" (examples + lemma) -- the two were previously
separate scripts (backfill_translations.py / backfill_lemma_translations.py)
with near-identical boilerplate, which made it easy to run one and forget
the other, leaving a verb with (e.g.) a translated lemma but untranslated
examples. Merged 2026-09-15; also replaces the one-off, non-resumable
backfill_fr_translations.py / backfill_it_translations.py (this script's
--language flag already accepts any verb-source language, not just
SUPPORTED_LANGUAGES).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from google.cloud import firestore

from core.languages.config import ALL_STUDY_LANGUAGES
from core.translation_service import SUPPORTED_LANGUAGES, translate_examples, translate_lemma

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VERBS_COLLECTION = os.getenv("VERBS_COLLECTION", "verbs")

FIELD_CHOICES = ("both", "examples", "lemma")


def _lemma_as_str(lemma: object) -> str:
    if isinstance(lemma, dict):
        return lemma.get("imperfective") or lemma.get("perfective") or str(lemma)
    return str(lemma or "")


def _needs_example_translation(examples: list[dict], target_langs: list[str]) -> bool:
    return any(
        lang not in ex.get("translations", {})
        for ex in examples
        for lang in target_langs
        if isinstance(ex, dict) and isinstance(ex.get("dst"), str)
    )


def _strip_example_translations(examples: list[dict], target_langs: list[str]) -> list[dict]:
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


def _process_examples(
    doc_ref: firestore.DocumentReference,
    data: dict,
    verb_lang: str,
    lemma: str,
    target_langs: list[str] | None,
    project: str,
    api_key: str,
    dry_run: bool,
    force: bool,
) -> bool:
    examples: list[dict] = [
        ex for ex in data.get("examples", []) if isinstance(ex, dict) and isinstance(ex.get("dst"), str)
    ]
    if not examples:
        return False

    effective_targets = target_langs or [lang for lang in SUPPORTED_LANGUAGES if lang != verb_lang]

    if force:
        examples = _strip_example_translations(examples, effective_targets)
    elif not _needs_example_translation(examples, effective_targets):
        return False

    logger.info("  examples: translating %d → %s", len(examples), effective_targets)
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
        doc_ref.update({"examples": translated, "updated_at": firestore.SERVER_TIMESTAMP})

    return True


def _process_lemma(
    doc_ref: firestore.DocumentReference,
    data: dict,
    verb_lang: str,
    lemma: str,
    target_langs: list[str] | None,
    project: str,
    api_key: str,
    dry_run: bool,
    force: bool,
) -> bool:
    if not lemma:
        return False

    effective_targets = target_langs or [lang for lang in SUPPORTED_LANGUAGES if lang != verb_lang]
    existing = {} if force else (data.get("lemma_translations") or {})

    if not force and all(t in existing for t in effective_targets):
        return False

    logger.info("  lemma: translating %r → %s", lemma, effective_targets)
    if dry_run:
        return True

    translated = translate_lemma(
        verb_lang=verb_lang,
        lemma=lemma,
        existing_translations=existing,
        target_langs=effective_targets,
        project=project,
        api_key=api_key,
    )

    if translated and translated != existing:
        doc_ref.update({"lemma_translations": translated, "updated_at": firestore.SERVER_TIMESTAMP})

    return True


def process_verb(
    doc_ref: firestore.DocumentReference,
    data: dict,
    field: str,
    target_langs: list[str] | None,
    project: str,
    api_key: str,
    dry_run: bool,
    force: bool = False,
) -> bool:
    verb_lang = data.get("language", "")
    lemma = _lemma_as_str(data.get("lemma") or data.get("verb_id", ""))

    updated = False
    if field in ("both", "examples"):
        updated = (
            _process_examples(doc_ref, data, verb_lang, lemma, target_langs, project, api_key, dry_run, force)
            or updated
        )
    if field in ("both", "lemma"):
        updated = (
            _process_lemma(doc_ref, data, verb_lang, lemma, target_langs, project, api_key, dry_run, force) or updated
        )
    return updated


def source_languages(language: str) -> list[str]:
    """Verb (source) languages to process. "all" means every study language,
    not just the UI languages that SUPPORTED_LANGUAGES holds: Italian and French
    verbs are translated INTO the UI languages too (issue #59)."""
    return list(ALL_STUDY_LANGUAGES) if language == "all" else [language]


def run(
    language: str,
    field: str,
    target_langs: list[str] | None,
    project: str,
    api_key: str,
    dry_run: bool,
    force: bool = False,
) -> None:
    db = firestore.Client(project=project)
    verb_langs = source_languages(language)

    for verb_lang in verb_langs:
        logger.info("Processing language: %s", verb_lang)
        docs = db.collection(VERBS_COLLECTION).where("language", "==", verb_lang).stream()
        updated_count = skipped = 0
        for doc in docs:
            data = doc.to_dict()
            logger.info("  %s", data.get("verb_id", doc.id))
            if process_verb(doc.reference, data, field, target_langs, project, api_key, dry_run, force):
                updated_count += 1
            else:
                skipped += 1
        logger.info("  %s: %d updated, %d already complete", verb_lang, updated_count, skipped)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill example and/or lemma translations.")
    parser.add_argument(
        "--language",
        default="all",
        help="Verb language to process (any source language, or 'all' for every study language). Default: all",
    )
    parser.add_argument(
        "--field",
        choices=FIELD_CHOICES,
        default="both",
        help="Which field(s) to backfill. Default: both",
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
        field=args.field,
        target_langs=[args.target_lang] if args.target_lang else None,
        project=args.project,
        api_key=api_key,
        dry_run=args.dry_run,
        force=args.force,
    )


if __name__ == "__main__":
    main()
