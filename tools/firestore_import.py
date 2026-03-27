from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from core.storage.firestore_db import get_db
from core.storage.verb_document import build_verb_document_from_lexicon_entry
from core.storage.verb_repository import upsert_verb
from core.supported_languages import supported_languages_list

VERBS_COLLECTION = "verbs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete all existing verbs before import",
    )
    parser.add_argument(
        "--limit-per-language",
        type=int,
        default=None,
        help="Import only the first N verbs per language",
    )
    return parser.parse_args()


def clear_verbs_collection() -> None:
    db = get_db()
    docs = db.collection(VERBS_COLLECTION).stream()

    deleted_count = 0
    for document in docs:
        document.reference.delete()
        deleted_count += 1

    print(f"Deleted {deleted_count} docs from '{VERBS_COLLECTION}'")


def load_lexicon(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def lexicon_path_for_language(language: str) -> Path:
    return Path("runtime") / "data" / language / "lexicon.json"


def run(*, clear: bool, limit_per_language: int | None) -> None:
    if clear:
        clear_verbs_collection()

    total_verbs_imported = 0

    for language in supported_languages_list():
        lexicon_path = lexicon_path_for_language(language)
        print(f"Loading {language} from {lexicon_path}")

        if not lexicon_path.exists():
            print(f"Skipping {language}: missing {lexicon_path}")
            continue

        lexicon = load_lexicon(lexicon_path)
        verbs = lexicon.get("verbs", [])
        print(f"{language}: {len(verbs)} verbs available")

        imported_for_language = 0

        for verb in verbs:
            payload = build_verb_document_from_lexicon_entry(
                language=language,
                entry=verb,
            )

            upsert_verb(
                verb_id=payload["verb_id"],
                payload=payload,
            )

            imported_for_language += 1
            total_verbs_imported += 1

            print(
                f"Imported {language}/{payload['verb_id']} "
                f"({imported_for_language})"
            )

            if (
                limit_per_language is not None
                and imported_for_language >= limit_per_language
            ):
                break

    print(f"Import done. Total verbs: {total_verbs_imported}")


if __name__ == "__main__":
    args = parse_args()
    run(
        clear=args.clear,
        limit_per_language=args.limit_per_language,
    )
