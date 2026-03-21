from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from core.paths import DATA_DIR, DATA_SRC_DIR
from core.supported_languages import supported_languages_list

from tools.lexicon_build.common import (
    fail,
    load_json,
    load_optional_json_map,
    write_json,
    validate_top_level,
)

from tools.lexicon_build.english import expand_english_entry
from tools.lexicon_build.russian import expand_russian_entry
from tools.lexicon_build.spanish import expand_spanish_entry


EXPANDERS: dict[
    str,
    Callable[[dict[str, Any], int, dict[str, list[str]]], dict[str, Any]],
] = {
    "en": expand_english_entry,
    "ru": expand_russian_entry,
    "es": expand_spanish_entry,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate runtime lexicon.json from source catalog"
    )
    parser.add_argument(
        "--language",
        required=True,
        choices=supported_languages_list(),
    )
    return parser.parse_args()


def build_runtime_payload(
    language: str,
    source_payload: dict[str, Any],
    source_path: Path,
    built_in_examples: dict[str, list[str]],
) -> dict[str, Any]:
    source_verbs = validate_top_level(
        payload=source_payload,
        expected_language=language,
        source_path=source_path,
    )

    runtime_verbs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for rank, seed_entry in enumerate(source_verbs, start=1):
        if language == "he":
            # leave Hebrew untouched (your decision)
            runtime_entry = dict(seed_entry)
            runtime_entry["rank"] = rank
        else:
            expander = EXPANDERS.get(language)
            if expander is None:
                fail(f"no expander configured for language '{language}'")

            runtime_entry = expander(
                seed_entry,
                rank,
                built_in_examples,
            )

        verb_id = runtime_entry.get("id")
        if not isinstance(verb_id, str) or not verb_id.strip():
            fail(f"{source_path}: runtime verb #{rank} has invalid id")

        if verb_id in seen_ids:
            fail(f"{source_path}: duplicate id '{verb_id}'")

        seen_ids.add(verb_id)
        runtime_verbs.append(runtime_entry)

    return {
        "language": language,
        "version": int(source_payload.get("version", 1)),
        "verbs": runtime_verbs,
    }


def main() -> None:
    args = parse_args()
    language = args.language

    source_path = DATA_SRC_DIR / language / "catalog.json"
    output_path = DATA_DIR / language / "lexicon.json"

    source_payload = load_json(source_path)

    built_in_examples: dict[str, list[str]] = {}
    if language in {"en", "ru"}:
        built_in_examples = load_optional_json_map(
            DATA_DIR / language / "built_in_examples.json"
        )

    runtime_payload = build_runtime_payload(
        language=language,
        source_payload=source_payload,
        source_path=source_path,
        built_in_examples=built_in_examples,
    )

    write_json(output_path, runtime_payload)

    print(
        f"OK: generated {output_path} with "
        f"{len(runtime_payload['verbs'])} {language} verbs"
    )


if __name__ == "__main__":
    main()
