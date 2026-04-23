#!/usr/bin/env python3
"""
Migration: convert morph.pair from latin verb_id (e.g. 'ru_smotret')
to Cyrillic lemma (e.g. 'смотреть') for all Russian verbs.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.storage.firestore_db import get_db

COLLECTION = "verbs"
LANGUAGE = "ru"
DRY_RUN = "--apply" not in sys.argv


def is_latin_verb_id(pair: str) -> bool:
    """True if pair looks like 'ru_smotret' rather than 'смотреть'."""
    return bool(pair and pair.startswith("ru_"))


def main() -> None:
    db = get_db()
    docs = db.collection(COLLECTION).where("language", "==", LANGUAGE).stream()

    # Build verb_id -> lemma index first
    all_docs = [doc.to_dict() for doc in docs]
    id_to_lemma = {d["verb_id"]: d.get("lemma", "") for d in all_docs}

    to_fix = []
    for doc in all_docs:
        morph = doc.get("morph") or {}
        pair = morph.get("pair", "")
        if is_latin_verb_id(pair):
            resolved_lemma = id_to_lemma.get(pair, "")
            to_fix.append((doc["verb_id"], pair, resolved_lemma))

    print(f"Found {len(to_fix)} verbs with latin verb_id in pair field:\n")
    for verb_id, old_pair, new_pair in to_fix:
        status = "✓" if new_pair else "✗ NOT FOUND"
        print(f"  {verb_id}: '{old_pair}' → '{new_pair}' {status}")

    if not to_fix:
        print("Nothing to do.")
        return

    if DRY_RUN:
        print("\nDry run — pass --apply to write changes.")
        return

    print("\nApplying...")
    updated = 0
    skipped = 0
    for verb_id, old_pair, new_pair in to_fix:
        if not new_pair:
            print(f"  SKIP {verb_id}: pair '{old_pair}' not found in Firestore")
            skipped += 1
            continue

        doc_ref = db.collection(COLLECTION).document(verb_id)
        doc_data = doc_ref.get().to_dict()
        morph = dict(doc_data.get("morph") or {})
        morph["pair"] = new_pair
        doc_ref.update({"morph": morph})
        print(f"  UPDATED {verb_id}: pair '{old_pair}' → '{new_pair}'")
        updated += 1

    print(f"\nDone. Updated: {updated}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
