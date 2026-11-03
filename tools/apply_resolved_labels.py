"""
Apply reviewed single labels to examples whose tag shares its surface form with other cells.

Input: a JSON map `{"<verb_id>#<example index>": "<tense.person>" | "ambiguous"}` produced by a
linguist pass over the multi-label rows (`target.also`). Each chosen label must be one of the
row's current candidates; the target is rebuilt with `core.example_targets.tag_from_hint`
(validated against the sentence, `source: "generated"`, no `also`). "ambiguous" rows are left
as they are. Dry run by default; `--execute` writes, guarded by the snapshot's update time.

Stage and prod share Firestore, so --execute is live. A later `backfill_example_targets --retag`
recomputes tags from the rules and would undo these choices.

    python -m tools.apply_resolved_labels --language en --resolved resolved_en.json
    python -m tools.apply_resolved_labels --language en --resolved resolved_en.json --execute
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

from google.api_core.exceptions import FailedPrecondition  # noqa: E402

from core.example_targets import native_sentence, tag_from_hint  # noqa: E402
from core.storage.firestore_db import get_db  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--language", required=True)
    parser.add_argument("--resolved", required=True, help="JSON map key -> label | ambiguous")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    resolved: dict[str, str] = json.loads(Path(args.resolved).read_text(encoding="utf-8"))
    by_verb: dict[str, dict[int, str]] = defaultdict(dict)
    for key, label in resolved.items():
        verb_id, _, index_text = key.rpartition("#")
        by_verb[verb_id][int(index_text)] = label

    db = get_db()
    counts: Counter[str] = Counter()
    for snapshot in db.collection("verbs").where("language", "==", args.language).stream():
        data = snapshot.to_dict() or {}
        wanted = by_verb.get(data.get("verb_id", ""))
        if not wanted:
            continue
        examples = [dict(ex) for ex in data.get("examples", [])]
        changed = False
        for index, label in wanted.items():
            if label == "ambiguous":
                counts["ambiguous_kept"] += 1
                continue
            if index >= len(examples) or not isinstance(examples[index].get("target"), dict):
                counts["missing"] += 1
                continue
            current = examples[index]["target"]
            current_path = f"{current['tense']}.{current['person']}" if current.get("person") else current["tense"]
            if label not in [current_path, *(current.get("also") or [])]:
                counts["not_a_candidate"] += 1
                logger.warning("%s#%d: %s is not a candidate", data.get("verb_id"), index, label)
                continue
            rebuilt = tag_from_hint(
                args.language, native_sentence(examples[index]), data.get("forms") or {}, label, current["answer"]
            )
            if rebuilt is None:
                counts["rebuild_failed"] += 1
                logger.warning("%s#%d: could not rebuild %s", data.get("verb_id"), index, label)
                continue
            examples[index]["target"] = rebuilt
            counts["resolved"] += 1
            changed = True
        if changed and args.execute:
            try:
                db.collection("verbs").document(snapshot.id).update(
                    {"examples": examples, "updated_at": datetime.now(UTC).isoformat()},
                    option=db.write_option(last_update_time=snapshot.update_time),
                )
                counts["verbs_written"] += 1
            except FailedPrecondition:
                counts["conflicts"] += 1
                logger.warning("conflict, skipped (changed since read): %s", snapshot.id)
    logger.info("%s %s", args.language, dict(counts))


if __name__ == "__main__":
    main()
