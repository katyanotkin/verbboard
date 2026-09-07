"""One-off script: apply two minor fixes a linguist-agent review found in the
40-verb Italian batch added by tools/seed_it_verbs_batch2.py.

1. it_conoscere's 5th example ("Conosci qualcuno che possa aiutarmi?") was a
   presente-indicativo question -- the same mood/tense as example 0, and a
   needless duplicate. conoscere's imperativo is actually fine in natural
   Italian ("Conosci te stesso"), so this replaces it with a genuine
   imperativo example instead of the substituted-form workaround used for
   verbs (sembrare, diventare) whose imperativo really is unnatural.

2. it_sembrare's futuro example translated "sembrerà" as Russian imperfective
   "будет казаться" where perfective "покажется" is the more idiomatic
   Russian future for this context -- not wrong, just less natural.

Usage:
    .venv/bin/python -m tools.fix_it_batch2_linguist_notes
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.storage.firestore_db import get_db  # noqa: E402

FIXES: dict[str, dict[str, Any]] = {
    "it_conoscere": {
        "index": 4,
        "new_example": {
            "dst": "Conosci le persone prima di giudicarle.",
            "translations": {
                "en": "Get to know people before you judge them.",
                "es": "Conoce a las personas antes de juzgarlas.",
                "he": "הכר את האנשים לפני שתשפוט אותם.",
                "ru": "Узнай людей, прежде чем судить их.",
            },
        },
    },
    "it_sembrare": {
        "index": 3,
        "translation_only": {"ru": "Завтра всё покажется проще, вот увидишь."},
    },
}


def main() -> None:
    db = get_db()
    for verb_id, fix in FIXES.items():
        doc_ref = db.collection("verbs").document(verb_id)
        doc = doc_ref.get()
        if not doc.exists:
            print(f"{verb_id} -- NOT FOUND")
            continue

        existing = doc.to_dict()
        examples = list(existing.get("examples") or [])
        index = fix["index"]
        if index >= len(examples):
            print(f"  {verb_id}: SKIPPED -- expected an example at index {index}, found {len(examples)}")
            continue

        if "new_example" in fix:
            before = examples[index].get("dst")
            examples[index] = fix["new_example"]
            print(f"  {verb_id}[{index}]: {before!r} -> {fix['new_example']['dst']!r}")
        else:
            before = examples[index]["translations"]["ru"]
            examples[index]["translations"]["ru"] = fix["translation_only"]["ru"]
            print(f"  {verb_id}[{index}].translations.ru: {before!r} -> {fix['translation_only']['ru']!r}")

        doc_ref.update({"examples": examples, "updated_at": datetime.now(UTC).isoformat()})
        print(f"  {verb_id}: OK -- updated")


if __name__ == "__main__":
    main()
