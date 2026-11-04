"""
Replace the example list of existing verbs with a reviewed set.

Input: a JSON map `{"<verb_id>": [ {"keep": <existing index>} | {"dst": "...", "form": "<tense.person>",
"tr": {"<ui lang>": "..."}, "untagged": true (optional, skips tagging)} , ... ]}`. `keep` entries are copied unchanged (so their audio, translations
and target survive); new entries are tagged with `core.example_targets` against the verb's own forms and must
resolve to the requested `form`. Every new entry needs a translation into every UI language except the verb's
own (see the translations-match-content skill). Dry run by default; `--execute` writes with an update-time
precondition. Stage and prod share Firestore, so --execute is live.

    python -m tools.apply_example_sets --language ru --sets ru_fix_all.json
    python -m tools.apply_example_sets --language ru --sets ru_fix_all.json --execute
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=True)

from google.api_core.exceptions import FailedPrecondition  # noqa: E402

from core.example_targets import tag_from_hint, tag_sentence  # noqa: E402
from core.languages.config import UI_LANGUAGES  # noqa: E402
from core.storage.firestore_db import get_db  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

STRESS_MARK = "́"
MIN_WORDS, MAX_WORDS = 4, 16
MAX_EXAMPLES = 12
_COMPOUND_FUTURE = re.compile(r"\bбуд(у|ешь|ет|ем|ете|ут)\s+\w+(ть|ться|ти|чь)\b", re.IGNORECASE)


def _path(target: dict[str, Any]) -> str:
    return f"{target['tense']}.{target['person']}" if target.get("person") else str(target["tense"])


def build_examples(
    language: str, doc: dict[str, Any], entries: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (new example list, problems). A non-empty problem list means the verb must not be written."""
    problems: list[str] = []
    existing = doc.get("examples") or []
    forms = doc.get("forms") or {}
    needed_translations = [lang for lang in UI_LANGUAGES if lang != language]
    result: list[dict[str, Any]] = []
    for position, entry in enumerate(entries):
        if "keep" in entry:
            index = entry["keep"]
            if not isinstance(index, int) or not 0 <= index < len(existing):
                problems.append(f"#{position}: keep {index!r} is not an existing example")
                continue
            result.append(dict(existing[index]))
            continue
        dst = str(entry.get("dst") or "").strip()
        form = str(entry.get("form") or "")
        translations = entry.get("tr") or {}
        words = len(dst.split())
        if not dst or not MIN_WORDS <= words <= MAX_WORDS:
            problems.append(f"#{position}: sentence length {words} words")
            continue
        if STRESS_MARK in dst:
            problems.append(f"#{position}: stress mark in sentence")
            continue
        if language == "ru" and _COMPOUND_FUTURE.search(dst):
            problems.append(f"#{position}: compound future")
            continue
        missing = [lang for lang in needed_translations if not str(translations.get(lang) or "").strip()]
        if missing:
            problems.append(f"#{position}: missing translations {missing}")
            continue
        if entry.get("untagged"):
            # Explicit opt-out for a cell no tagger can resolve (e.g. Russian "есть": one form for all six persons).
            result.append({"dst": dst, "translations": {lang: str(translations[lang]) for lang in needed_translations}})
            continue
        target = tag_sentence(language, dst, forms)
        if target is None:
            problems.append(f"#{position}: could not tag {dst!r} for {form}")
            continue
        if _path(target) != form:
            if form in (target.get("also") or []):
                target = tag_from_hint(language, dst, forms, form, target["answer"])
            else:
                target = None
        if target is None:
            problems.append(f"#{position}: sentence does not resolve to {form}: {dst!r}")
            continue
        result.append(
            {
                "dst": dst,
                "translations": {lang: str(translations[lang]) for lang in needed_translations},
                "target": target,
            }
        )
    if not 1 <= len(result) <= MAX_EXAMPLES:
        problems.append(f"{len(result)} examples")
    return result, problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--language", required=True)
    parser.add_argument("--sets", required=True, help="JSON map verb_id -> example entries")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    sets: dict[str, list[dict[str, Any]]] = json.loads(Path(args.sets).read_text(encoding="utf-8"))
    db = get_db()
    counts: Counter[str] = Counter()
    seen: set[str] = set()
    for snapshot in db.collection("verbs").where("language", "==", args.language).stream():
        doc = snapshot.to_dict() or {}
        entries = sets.get(doc.get("verb_id", ""))
        if entries is None:
            continue
        seen.add(doc["verb_id"])
        examples, problems = build_examples(args.language, doc, entries)
        if problems:
            counts["rejected"] += 1
            logger.warning("%s rejected: %s", doc["verb_id"], "; ".join(problems))
            continue
        counts["ok"] += 1
        counts["new_examples"] += sum(1 for e in entries if "keep" not in e)
        if args.execute:
            try:
                db.collection("verbs").document(snapshot.id).update(
                    {"examples": examples, "updated_at": datetime.now(UTC).isoformat()},
                    option=db.write_option(last_update_time=snapshot.update_time),
                )
                counts["written"] += 1
            except FailedPrecondition:
                counts["conflicts"] += 1
                logger.warning("conflict, skipped (changed since read): %s", snapshot.id)
    for missing_verb in sorted(set(sets) - seen):
        counts["unknown_verb"] += 1
        logger.warning("%s: not found for language %s", missing_verb, args.language)
    logger.info("%s %s", args.language, dict(counts))


if __name__ == "__main__":
    main()
