from __future__ import annotations

import sys
from collections import defaultdict

from core.storage.firestore_db import get_db
from core.storage.verb_document import (
    _strip_combining_marks,
    build_storage_verb_id,
)

COLLECTION = "verbs"


def canonicalize(text: str) -> str:
    return _strip_combining_marks(text).strip().lower()


def main() -> None:
    db = get_db()

    docs = db.collection(COLLECTION).stream()

    by_generated_id: dict[str, list[dict]] = defaultdict(list)
    by_canonical_lemma: dict[str, list[dict]] = defaultdict(list)

    total = 0

    for doc in docs:
        payload = doc.to_dict() or {}

        language = str(payload.get("language") or "")
        lemma = str(payload.get("lemma") or "")
        verb_id = str(payload.get("verb_id") or doc.id)

        if not language or not lemma:
            continue

        generated_id = build_storage_verb_id(
            language=language,
            lemma=lemma,
        )

        canonical_lemma = canonicalize(lemma)

        row = {
            "verb_id": verb_id,
            "lemma": lemma,
            "doc_id": doc.id,
        }

        by_generated_id[generated_id].append(row)
        by_canonical_lemma[f"{language}:{canonical_lemma}"].append(row)

        total += 1

    print()
    print(f"Audited {total} verbs")
    print()

    print("=== GENERATED ID COLLISIONS ===")
    generated_collisions = 0

    for generated_id, rows in sorted(by_generated_id.items()):
        unique_doc_ids = {r["doc_id"] for r in rows}

        if len(unique_doc_ids) <= 1:
            continue

        generated_collisions += 1

        print()
        print(f"[COLLISION] {generated_id}")

        for row in rows:
            print(
                f"  lemma={row['lemma']} "
                f"verb_id={row['verb_id']} "
                f"doc_id={row['doc_id']}"
            )

    if generated_collisions == 0:
        print("No generated-id collisions found")

    print()
    print("=== CANONICAL LEMMA COLLISIONS ===")

    canonical_collisions = 0

    for key, rows in sorted(by_canonical_lemma.items()):
        unique_doc_ids = {r["doc_id"] for r in rows}

        if len(unique_doc_ids) <= 1:
            continue

        canonical_collisions += 1

        print()
        print(f"[CANONICAL COLLISION] {key}")

        for row in rows:
            print(
                f"  lemma={row['lemma']} "
                f"verb_id={row['verb_id']} "
                f"doc_id={row['doc_id']}"
            )

    if canonical_collisions == 0:
        print("No canonical lemma collisions found")

    print()

    total_collisions = generated_collisions + canonical_collisions

    if total_collisions > 0:
        print(f"FAILED: detected {total_collisions} collision groups")
        sys.exit(1)


if __name__ == "__main__":
    main()
