from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, NoReturn

from core.paths import DATA_DIR, DATA_SRC_DIR


SUPPORTED_LANGUAGES = {"en", "ru", "he"}


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


def derive_en_present_3sg(lemma: str) -> str:
    if lemma.endswith(("s", "sh", "ch", "x", "z", "o")):
        return f"{lemma}es"
    if len(lemma) > 1 and lemma.endswith("y") and lemma[-2] not in "aeiou":
        return f"{lemma[:-1]}ies"
    return f"{lemma}s"


def derive_en_gerund(lemma: str) -> str:
    if lemma.endswith("ie"):
        return f"{lemma[:-2]}ying"
    if lemma.endswith("e") and lemma not in {"be", "see"}:
        return f"{lemma[:-1]}ing"
    if (
        len(lemma) >= 3
        and lemma[-1] not in "aeiouwxy"
        and lemma[-2] in "aeiou"
        and lemma[-3] not in "aeiou"
        and len(lemma) <= 4
    ):
        return f"{lemma}{lemma[-1]}ing"
    return f"{lemma}ing"


def derive_en_regular_past(lemma: str) -> str:
    if len(lemma) > 1 and lemma.endswith("y") and lemma[-2] not in "aeiou":
        return f"{lemma[:-1]}ied"
    if lemma.endswith("e"):
        return f"{lemma}d"
    if (
        len(lemma) >= 3
        and lemma[-1] not in "aeiouwxy"
        and lemma[-2] in "aeiou"
        and lemma[-3] not in "aeiou"
        and len(lemma) <= 4
    ):
        return f"{lemma}{lemma[-1]}ed"
    return f"{lemma}ed"


def build_en_examples(
    lemma: str,
    present_3sg: str,
    past: str,
    past_participle: str,
    gerund: str,
    built_in_examples: dict[str, list[str]],
) -> list[dict[str, str]]:
    custom_examples = built_in_examples.get(lemma)
    if custom_examples:
        return [{"dst": sentence} for sentence in custom_examples]

    return [
        {"dst": f"I {lemma} my work every day."},
        {"dst": f"She {present_3sg} a new task at work."},
        {"dst": f"They {past} the job yesterday."},
        {"dst": f"He has {past_participle} the report already."},
        {"dst": f"We are {gerund} the project now."},
    ]


def expand_english_entry(
    seed_entry: dict[str, Any],
    rank: int,
    built_in_examples: dict[str, list[str]],
) -> dict[str, Any]:
    context = f"English seed #{rank}"

    validate_required_keys(seed_entry, ["id", "lemma"], context)

    seed_id = seed_entry["id"]
    lemma = seed_entry["lemma"]
    irregular_object = seed_entry.get("irregular", {})
    examples_object = seed_entry.get("examples")

    if not isinstance(seed_id, str) or not seed_id.strip():
        fail(f"{context}: id must be a non-empty string")
    if not isinstance(lemma, str) or not lemma.strip():
        fail(f"{context}: lemma must be a non-empty string")
    if irregular_object is not None and not isinstance(irregular_object, dict):
        fail(f"{context}: irregular must be an object if present")
    if examples_object is not None and not isinstance(examples_object, list):
        fail(f"{context}: examples must be a list if present")

    irregular: dict[str, Any] = (
        irregular_object if isinstance(irregular_object, dict) else {}
    )

    base = lemma
    past = str(irregular.get("past") or derive_en_regular_past(lemma))
    past_participle = str(irregular.get("past_participle") or past)
    present_3sg = str(irregular.get("present_3sg") or derive_en_present_3sg(lemma))
    gerund = str(irregular.get("gerund") or derive_en_gerund(lemma))

    runtime_examples: list[dict[str, str]]
    if examples_object:
        runtime_examples = []
        for index, example in enumerate(examples_object, start=1):
            if not isinstance(example, dict):
                fail(f"{context}: example #{index} must be an object")
            sentence = example.get("dst")
            if not isinstance(sentence, str) or not sentence.strip():
                fail(f"{context}: example #{index} must contain non-empty 'dst'")
            runtime_examples.append({"dst": sentence})
    else:
        runtime_examples = build_en_examples(
            lemma=lemma,
            present_3sg=present_3sg,
            past=past,
            past_participle=past_participle,
            gerund=gerund,
            built_in_examples=built_in_examples,
        )

    return {
        "id": seed_id,
        "rank": rank,
        "lemma": lemma,
        "forms": {
            "base": base,
            "past": past,
            "past_participle": past_participle,
            "present_3sg": present_3sg,
            "gerund": gerund,
        },
        "examples": runtime_examples,
    }


def expand_hebrew_entry(seed_entry: dict[str, Any], rank: int) -> dict[str, Any]:
    context = f"Hebrew seed #{rank}"
    validate_required_keys(
        seed_entry,
        ["id", "lemma", "morph", "forms", "examples"],
        context,
    )
    runtime_entry = dict(seed_entry)
    runtime_entry["rank"] = rank
    return runtime_entry


def build_ru_examples(
    sem: str,
    aspect: str,
    present: dict[str, str],
    past: dict[str, str],
    imperative: dict[str, str],
) -> list[dict[str, str]]:
    return [
        {"dst": f"Я {present.get('1sg', '')}."},
        {"dst": f"Он {present.get('3sg', '')}."},
        {"dst": f"Мы {past.get('pl', '')} вчера."},
        {"dst": f"{imperative.get('sg', '')} внимательно."},
        {"dst": f"Радио {past.get('n', '')} всю ночь."},
    ]


def expand_russian_entry(
    seed_entry: dict[str, Any],
    rank: int,
    built_in_examples: dict[str, list[str]],
) -> dict[str, Any]:
    context = f"Russian seed #{rank}"

    validate_required_keys(
        seed_entry,
        ["id", "lemma", "aspect", "seed_forms"],
        context,
    )

    seed_id = seed_entry["id"]
    lemma = seed_entry["lemma"]
    aspect = seed_entry["aspect"]
    pair = seed_entry.get("pair")
    sem = seed_entry.get("sem", "action")
    seed_forms_object = seed_entry["seed_forms"]
    examples_object = seed_entry.get("examples")
    custom_examples = built_in_examples.get(seed_id)

    if not isinstance(seed_id, str) or not seed_id.strip():
        fail(f"{context}: id must be a non-empty string")
    if not isinstance(lemma, str) or not lemma.strip():
        fail(f"{context}: lemma must be a non-empty string")
    if aspect not in {"imperfective", "perfective"}:
        fail(f"{context}: aspect must be 'imperfective' or 'perfective'")
    if pair is not None and (not isinstance(pair, str) or not pair.strip()):
        fail(f"{context}: pair must be a non-empty string if present")
    if not isinstance(sem, str) or not sem.strip():
        fail(f"{context}: sem must be a non-empty string if present")
    if not isinstance(seed_forms_object, dict):
        fail(f"{context}: seed_forms must be an object")

    validate_required_keys(
        seed_forms_object,
        ["present", "past", "imperative"],
        f"{context} seed_forms",
    )

    present_object = seed_forms_object["present"]
    past_object = seed_forms_object["past"]
    imperative_object = seed_forms_object["imperative"]

    if not isinstance(present_object, dict):
        fail(f"{context}: seed_forms.present must be an object")
    if not isinstance(past_object, dict):
        fail(f"{context}: seed_forms.past must be an object")
    if not isinstance(imperative_object, dict):
        fail(f"{context}: seed_forms.imperative must be an object")

    present: dict[str, str] = {}
    for key in ["1sg", "2sg", "3sg", "1pl", "2pl", "3pl"]:
        value = present_object.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(f"{context}: missing or empty seed_forms.present.{key}")
        present[key] = value

    past: dict[str, str] = {}
    for key in ["m", "f", "n", "pl"]:
        value = past_object.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(f"{context}: missing or empty seed_forms.past.{key}")
        past[key] = value

    imperative: dict[str, str] = {}
    for key in ["sg", "pl"]:
        value = imperative_object.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(f"{context}: missing or empty seed_forms.imperative.{key}")
        imperative[key] = value

    runtime_examples: list[dict[str, str]]
    if examples_object:
        if not isinstance(examples_object, list):
            fail(f"{context}: examples must be a list if present")
        runtime_examples = []
        for index, example in enumerate(examples_object, start=1):
            if not isinstance(example, dict):
                fail(f"{context}: example #{index} must be an object")
            sentence = example.get("dst")
            if not isinstance(sentence, str) or not sentence.strip():
                fail(f"{context}: example #{index} must contain non-empty 'dst'")
            runtime_examples.append({"dst": sentence})
    elif custom_examples:
        runtime_examples = [{"dst": sentence} for sentence in custom_examples]
    else:
        runtime_examples = build_ru_examples(
            sem=sem,
            aspect=aspect,
            present=present,
            past=past,
            imperative=imperative,
        )

    return {
        "id": seed_id,
        "rank": rank,
        "lemma": lemma,
        "morph": {
            "aspect": aspect,
            "pair": pair,
            "sem": sem,
        },
        "forms": {
            "present": present,
            "past": past,
            "imperative": imperative,
        },
        "examples": runtime_examples,
    }


EXPANDERS: dict[str, Callable[[dict[str, Any], int], dict[str, Any]]] = {
    "he": expand_hebrew_entry,
}


def build_runtime_payload(
    language: str,
    source_payload: dict[str, Any],
    source_path: Path,
    built_in_examples: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    source_verbs = validate_top_level(
        payload=source_payload,
        expected_language=language,
        source_path=source_path,
    )

    runtime_verbs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for rank, seed_entry in enumerate(source_verbs, start=1):
        if language == "en":
            runtime_entry = expand_english_entry(
                seed_entry,
                rank,
                built_in_examples or {},
            )
        elif language == "ru":
            runtime_entry = expand_russian_entry(
                seed_entry,
                rank,
                built_in_examples or {},
            )
        else:
            expander = EXPANDERS.get(language)
            if expander is None:
                fail(f"no expander configured for language '{language}'")
            runtime_entry = expander(seed_entry, rank)

        runtime_id_object = runtime_entry.get("id")
        if not isinstance(runtime_id_object, str) or not runtime_id_object.strip():
            fail(f"{source_path}: runtime verb #{rank} has invalid id")

        if runtime_id_object in seen_ids:
            fail(f"{source_path}: duplicate id '{runtime_id_object}'")
        seen_ids.add(runtime_id_object)

        runtime_verbs.append(runtime_entry)

    return {
        "language": language,
        "version": int(source_payload.get("version", 1)),
        "verbs": runtime_verbs,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate runtime lexicon.json from source catalog"
    )
    parser.add_argument(
        "--language",
        required=True,
        choices=sorted(SUPPORTED_LANGUAGES),
        help="Language code: en, ru, he",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    language = arguments.language

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
