"""
Tag existing live examples with the conjugated form they show (`examples[i].target`).

Deterministic only: an example is tagged when exactly one form cell matches at exactly one
place in the sentence (core/example_targets.py). Ambiguous or unmatched examples are left
untagged and listed in the report. Existing valid tags are kept (idempotent); `--retag`
recomputes all of them. Reads only `verbs`; writes only `examples` (+ `updated_at`) and
only with `--execute`. Each write is guarded by the snapshot's update time, so a
concurrent regen or translation backfill is never overwritten (the verb is skipped).

Stage and prod share Firestore, so --execute is live. The field is additive: nothing
reads it until the practice page ships.

Usage (project root, needs GCP auth):

    python -m tools.backfill_example_targets --language es --report /tmp/es_targets.csv
    python -m tools.backfill_example_targets --language es --execute
"""

from __future__ import annotations

import argparse
import csv
import logging
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=True)

from google.api_core.exceptions import FailedPrecondition  # noqa: E402

from core.example_targets import explain_untagged, native_sentence, tag_examples  # noqa: E402
from core.languages.config import ALL_STUDY_LANGUAGES  # noqa: E402
from core.storage.firestore_db import get_db  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def plan_verb(
    language: str, data: dict[str, Any], *, retag: bool = False
) -> tuple[list[Any], list[dict[str, str]], bool]:
    """Return (new_examples, report_rows, changed) for one verb document. Pure."""
    forms = data.get("forms")
    old_examples = data.get("examples") or []
    new_examples = tag_examples(language, forms, old_examples, retag=retag)
    rows: list[dict[str, str]] = []
    for index, (old, new) in enumerate(zip(old_examples, new_examples)):
        if not isinstance(new, dict):
            continue
        sentence = native_sentence(new)
        target = new.get("target")
        had_target = isinstance(old, dict) and old.get("target") is not None
        if target is None:
            status = "dropped_stale" if had_target else explain_untagged(language, sentence, forms)
        else:
            status = "kept" if had_target and old.get("target") == target else "tagged"
        rows.append(
            {
                "language": language,
                "verb_id": str(data.get("verb_id", "")),
                "index": str(index),
                "status": status,
                "form": ""
                if target is None
                else (target["tense"] + ("." + target["person"] if target["person"] else "")),
                "answer": "" if target is None else target["answer"],
                "match": "" if target is None else target["match"],
                "sentence": sentence,
            }
        )
    return new_examples, rows, new_examples != old_examples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", default="", help=f"one of {', '.join(ALL_STUDY_LANGUAGES)}; default all")
    parser.add_argument("--verb-id", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--retag", action="store_true", help="recompute tags that already validate")
    parser.add_argument("--report", default="", help="write a per-example CSV here")
    parser.add_argument("--execute", action="store_true", help="write to Firestore (default is a dry run)")
    args = parser.parse_args()

    db = get_db()
    query = db.collection("verbs")
    if args.language:
        query = query.where("language", "==", args.language)

    totals: Counter[str] = Counter()
    per_language: dict[str, Counter[str]] = {}
    report_rows: list[dict[str, str]] = []
    written = skipped_conflict = 0
    seen_verbs = 0

    for snapshot in query.stream():
        data = snapshot.to_dict() or {}
        language = data.get("language", "")
        if args.verb_id and data.get("verb_id") != args.verb_id:
            continue
        if args.limit and seen_verbs >= args.limit:
            break
        seen_verbs += 1
        new_examples, rows, changed = plan_verb(language, data, retag=args.retag)
        report_rows.extend(rows)
        counter = per_language.setdefault(language, Counter())
        for row in rows:
            counter[row["status"]] += 1
            totals[row["status"]] += 1
        if changed and args.execute:
            doc_ref = db.collection("verbs").document(snapshot.id)
            try:
                doc_ref.update(
                    {"examples": new_examples, "updated_at": datetime.now(UTC).isoformat()},
                    option=db.write_option(last_update_time=snapshot.update_time),
                )
                written += 1
            except FailedPrecondition:
                skipped_conflict += 1
                logger.warning("conflict, skipped (changed since read): %s", snapshot.id)

    for language, counter in sorted(per_language.items()):
        total = sum(counter.values())
        tagged = counter["tagged"] + counter["kept"]
        logger.info(
            "%s: %d/%d tagged (%.0f%%) %s", language, tagged, total, 100 * tagged / max(total, 1), dict(counter)
        )
    logger.info(
        "verbs seen=%d written=%d conflicts=%d mode=%s",
        seen_verbs,
        written,
        skipped_conflict,
        "EXECUTE" if args.execute else "dry-run",
    )

    if args.report:
        with open(args.report, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["language", "verb_id", "index", "status", "form", "answer", "match", "sentence"]
            )
            writer.writeheader()
            writer.writerows(report_rows)
        logger.info("report: %s (%d rows)", args.report, len(report_rows))


if __name__ == "__main__":
    main()
