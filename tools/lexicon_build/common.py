from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NoReturn


def fail(message: str) -> NoReturn:
    raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"invalid JSON in {path}: {error}")

    if not isinstance(payload, dict):
        fail(f"{path}: expected top-level object")

    return payload


def load_optional_json_map(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"invalid JSON in {path}: {error}")

    if not isinstance(payload, dict):
        fail(f"{path}: expected top-level object")

    normalized_payload: dict[str, list[str]] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not key.strip():
            fail(f"{path}: example-map keys must be non-empty strings")
        if not isinstance(value, list):
            fail(f"{path}: value for '{key}' must be a list")

        normalized_sentences: list[str] = []
        for index, sentence in enumerate(value, start=1):
            if not isinstance(sentence, str) or not sentence.strip():
                fail(
                    f"{path}: sentence #{index} for '{key}' must be a non-empty string"
                )
            normalized_sentences.append(sentence)

        normalized_payload[key] = normalized_sentences

    return normalized_payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_top_level(
    payload: dict[str, Any],
    expected_language: str,
    source_path: Path,
) -> list[dict[str, Any]]:
    if payload.get("language") != expected_language:
        fail(
            f"{source_path}: expected language='{expected_language}', "
            f"got '{payload.get('language')}'"
        )

    verbs_object = payload.get("verbs")
    if not isinstance(verbs_object, list):
        fail(f"{source_path}: top-level 'verbs' must be a list")

    if not verbs_object:
        fail(f"{source_path}: source catalog contains no verbs")

    verbs: list[dict[str, Any]] = []
    for index, entry in enumerate(verbs_object, start=1):
        if not isinstance(entry, dict):
            fail(f"{source_path}: verb #{index} must be an object")
        verbs.append(entry)

    return verbs


def validate_required_keys(
    entry: dict[str, Any],
    required_keys: list[str],
    context: str,
) -> None:
    for key in required_keys:
        if key not in entry:
            fail(f"{context}: missing key '{key}'")
