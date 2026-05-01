from __future__ import annotations

from typing import Any

from google.cloud.firestore_v1 import FieldFilter

from core.storage.firestore_db import get_db


VERBS_COLLECTION = "verbs"


def has_nonempty_slot(forms: dict[str, Any], slot: str) -> bool:
    value = forms.get(slot)

    if not value:
        return False

    if isinstance(value, dict):
        return any(bool(form) for form in value.values())

    if isinstance(value, list):
        return any(bool(form) for form in value)

    return bool(value)


def label(document_id: str, data: dict[str, Any]) -> str:
    lemma = data.get("lemma", "")
    verb_id = data.get("verb_id", document_id)
    return f"{verb_id} | {lemma}"


def main() -> None:
    db = get_db()

    docs = (
        db.collection(VERBS_COLLECTION)
        .where(filter=FieldFilter("language", "==", "ru"))
        .stream()
    )

    perfective_missing_future: list[str] = []
    perfective_with_future: list[str] = []
    perfective_with_present: list[str] = []

    imperfective_missing_present: list[str] = []
    imperfective_with_present: list[str] = []
    imperfective_with_future: list[str] = []

    unknown_aspect: list[str] = []

    for doc in docs:
        data = doc.to_dict() or {}

        aspect = (data.get("morph") or {}).get("aspect")
        forms = data.get("forms") or {}

        has_present = has_nonempty_slot(forms, "present")
        has_future = has_nonempty_slot(forms, "future")
        row = label(doc.id, data)

        if aspect == "perfective":
            if has_future:
                perfective_with_future.append(row)
            else:
                perfective_missing_future.append(row)

            if has_present:
                perfective_with_present.append(row)

        elif aspect == "imperfective":
            if has_present:
                imperfective_with_present.append(row)
            else:
                imperfective_missing_present.append(row)

            if has_future:
                imperfective_with_future.append(row)

        else:
            unknown_aspect.append(row)

    sections = [
        ("PERFECTIVE correct: has future", perfective_with_future),
        ("PERFECTIVE broken: missing future", perfective_missing_future),
        ("PERFECTIVE wrong: has present", perfective_with_present),
        ("IMPERFECTIVE correct: has present", imperfective_with_present),
        ("IMPERFECTIVE broken: missing present", imperfective_missing_present),
        ("IMPERFECTIVE wrong: has future", imperfective_with_future),
        ("UNKNOWN aspect", unknown_aspect),
    ]

    for title, rows in sections:
        print(f"\n## {title}: {len(rows)}")
        for row in sorted(rows):
            print(row)


if __name__ == "__main__":
    main()
