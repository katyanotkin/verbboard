from __future__ import annotations

from typing import Any

from tools.lexicon_build.common import fail, validate_required_keys


def build_ru_examples(
    sem: str,
    aspect: str,
    present: dict[str, str],
    past: dict[str, str],
    imperative: dict[str, str] | None,
) -> list[dict[str, str]]:
    finite_label = "буду" if aspect == "perfective" else present.get("1sg", "")
    finite_third = present.get("3sg", "")

    examples = [
        {
            "dst": f"Я {finite_label}."
            if aspect == "perfective"
            else f"Я {present.get('1sg', '')}."
        },
        {"dst": f"Он {finite_third}."},
        {"dst": f"Мы {past.get('pl', '')} вчера."},
        {"dst": f"Привидение {past.get('n', '')} всю ночь."},
    ]
    imperative_sg = (imperative or {}).get("sg", "").strip()
    if imperative_sg:
        examples.append({"dst": f"{imperative_sg} внимательно."})
    return examples


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
        ["present", "past"],
        f"{context} seed_forms",
    )

    present_object = seed_forms_object["present"]
    past_object = seed_forms_object["past"]

    if not isinstance(present_object, dict):
        fail(f"{context}: seed_forms.present must be an object")
    if not isinstance(past_object, dict):
        fail(f"{context}: seed_forms.past must be an object")

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

    imperative_object = seed_forms_object.get("imperative")
    imperative: dict[str, str] = {}
    if imperative_object is not None:
        if not isinstance(imperative_object, dict):
            fail(f"{context}: seed_forms.imperative must be an object if present")
        for key in ["sg", "pl"]:
            value = imperative_object.get(key)
            if value is None:
                continue
            if not isinstance(value, str) or not value.strip():
                fail(
                    f"{context}: seed_forms.imperative.{key} must be non-empty if present"
                )
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
