from __future__ import annotations

import argparse

from core.storage.firestore_db import get_db
from core.storage.verb_document import (
    _strip_combining_marks,
    build_storage_verb_id,
)

COLLECTION = "verbs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply Firestore document ID migrations",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    db = get_db()

    docs = db.collection(COLLECTION).where("language", "==", "he").stream()

    rows: list[dict[str, str]] = []

    for doc in docs:
        payload = doc.to_dict() or {}

        existing_id = doc.id
        lemma = str(payload.get("lemma") or "")
        canonical = _strip_combining_marks(lemma)

        generated_id = build_storage_verb_id(
            language="he",
            lemma=lemma,
        )

        rows.append(
            {
                "existing_id": existing_id,
                "generated_id": generated_id,
                "canonical": canonical,
                "lemma": lemma,
            }
        )

    rows.sort(key=lambda row: (row["generated_id"], row["existing_id"]))

    print()

    print(
        f"{'EXISTING ID':<24}" f"{'GENERATED ID':<24}" f"{'CANONICAL':<24}" f"{'LEMMA'}"
    )

    print("-" * 120)

    migrated = 0
    skipped = 0
    collisions = 0

    for row in rows:
        existing_id = row["existing_id"]
        generated_id = row["generated_id"]
        canonical = row["canonical"]
        lemma = row["lemma"]

        marker = ""

        if existing_id != generated_id:
            marker = "  <-- MIGRATE"

        print(
            f"{existing_id:<24}"
            f"{generated_id:<24}"
            f"{canonical:<24}"
            f"{lemma}"
            f"{marker}"
        )

        if not args.execute:
            continue

        if existing_id == generated_id:
            skipped += 1
            continue

        old_ref = db.collection(COLLECTION).document(existing_id)
        new_ref = db.collection(COLLECTION).document(generated_id)

        if new_ref.get().exists:
            print()
            print(f"COLLISION: {existing_id} -> {generated_id} " f"({lemma})")
            print("Destination document already exists")
            print()

            collisions += 1
            continue

        payload = old_ref.get().to_dict() or {}

        payload["verb_id"] = generated_id

        print(f"EXECUTE: {existing_id} -> {generated_id}")

        new_ref.set(payload)

        old_ref.delete()

        migrated += 1

    print()

    if args.execute:
        print(f"Migrated: {migrated}")
        print(f"Skipped: {skipped}")
        print(f"Collisions: {collisions}")

    print()


if __name__ == "__main__":
    main()
