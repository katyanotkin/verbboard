from __future__ import annotations

import argparse
from typing import Any

from google.cloud.firestore_v1 import FieldFilter

from core.storage.firestore_db import get_db


VERBS_COLLECTION = "verbs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def has_nonempty_slot(forms: dict[str, Any], slot: str) -> bool:
    value = forms.get(slot)

    if not value:
        return False

    if isinstance(value, dict):
        return any(bool(form) for form in value.values())

    if isinstance(value, list):
        return any(bool(form) for form in value)

    return bool(value)


def main() -> None:
    args = parse_args()
    db = get_db()

    docs = (
        db.collection(VERBS_COLLECTION)
        .where(filter=FieldFilter("language", "==", "ru"))
        .stream()
    )

    candidates = []

    for doc in docs:
        data = doc.to_dict() or {}
        aspect = (data.get("morph") or {}).get("aspect")
        forms = data.get("forms") or {}

        if aspect != "perfective":
            continue

        has_present = has_nonempty_slot(forms, "present")
        has_future = has_nonempty_slot(forms, "future")

        if has_present and not has_future:
            candidates.append((doc, data))

    print(f"Perfective verbs to migrate: {len(candidates)}")

    for doc, data in candidates:
        forms = data.get("forms") or {}
        lemma = data.get("lemma", "")
        verb_id = data.get("verb_id", doc.id)

        print(f"- {verb_id} | {lemma}")

        if args.apply:
            updated_forms = dict(forms)
            updated_forms["future"] = updated_forms["present"]
            del updated_forms["present"]

            doc.reference.update({"forms": updated_forms})

    if not args.apply:
        print("\nDry run only. Re-run with --apply to update Firestore.")


if __name__ == "__main__":
    main()
