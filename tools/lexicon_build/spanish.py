from __future__ import annotations

from typing import Any

from tools.lexicon_build.common import fail, validate_required_keys


def build_es_examples(
    lemma: str,
    present: dict[str, str],
    preterite: dict[str, str],
    gerund: str,
    strategy: str,
    imperative: dict[str, str],
) -> list[dict[str, str]]:
    if strategy == "be_identity_or_quality":
        imperative_tu = imperative.get("tu", "")
        return [
            {"dst": f"Yo {present.get('yo', '')} estudiante."},
            {"dst": f"Ella {present.get('el', '')} muy amable."},
            {"dst": f"Nosotros {preterite.get('nos', '')} amigos por años."},
            {"dst": f"{imperative_tu.capitalize()} amable con todos."}
            if imperative_tu
            else {"dst": "Sé amable con todos."},
        ]

    if strategy == "be_state_or_location":
        imperative_tu = imperative.get("tu", "")
        return [
            {"dst": f"Yo {present.get('yo', '')} en casa."},
            {"dst": f"Él {present.get('el', '')} cansado hoy."},
            {"dst": f"Ayer {preterite.get('el', '')} aquí."},
            {"dst": f"{imperative_tu.capitalize()} tranquilo ahora."}
            if imperative_tu
            else {"dst": "Está tranquilo ahora."},
        ]

    return [
        {"dst": f"Yo {present.get('yo', '')} cada día."},
        {"dst": f"Él {present.get('el', '')} ahora."},
        {"dst": f"Ayer nosotros {preterite.get('nos', '')} juntos."},
        {"dst": f"Estamos {gerund} hoy."},
    ]


def expand_spanish_entry(
    seed_entry: dict[str, Any],
    rank: int,
    built_in_examples: dict[str, list[str]],
) -> dict[str, Any]:
    del built_in_examples

    context = f"Spanish seed #{rank}"
    validate_required_keys(
        seed_entry,
        ["id", "lemma", "seed_forms"],
        context,
    )

    seed_id = seed_entry["id"]
    lemma = seed_entry["lemma"]
    strategy = seed_entry.get("example_strategy", "generic")
    seed_forms_object = seed_entry["seed_forms"]
    examples_object = seed_entry.get("examples")

    if not isinstance(seed_id, str) or not seed_id.strip():
        fail(f"{context}: id must be a non-empty string")
    if not isinstance(lemma, str) or not lemma.strip():
        fail(f"{context}: lemma must be a non-empty string")
    if not isinstance(strategy, str) or not strategy.strip():
        fail(f"{context}: example_strategy must be a non-empty string if present")
    if not isinstance(seed_forms_object, dict):
        fail(f"{context}: seed_forms must be an object")

    validate_required_keys(
        seed_forms_object,
        ["present", "preterite", "gerund", "participle"],
        f"{context} seed_forms",
    )

    present_object = seed_forms_object["present"]
    preterite_object = seed_forms_object["preterite"]
    gerund = seed_forms_object["gerund"]
    participle = seed_forms_object["participle"]
    imperative_object = seed_forms_object.get("imperative", {})

    if not isinstance(present_object, dict):
        fail(f"{context}: seed_forms.present must be an object")
    if not isinstance(preterite_object, dict):
        fail(f"{context}: seed_forms.preterite must be an object")
    if not isinstance(gerund, str) or not gerund.strip():
        fail(f"{context}: seed_forms.gerund must be a non-empty string")
    if not isinstance(participle, str) or not participle.strip():
        fail(f"{context}: seed_forms.participle must be a non-empty string")
    if imperative_object is not None and not isinstance(imperative_object, dict):
        fail(f"{context}: seed_forms.imperative must be an object if present")

    present: dict[str, str] = {}
    for key in ["yo", "tu", "el", "nos", "ellos"]:
        value = present_object.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(f"{context}: missing or empty seed_forms.present.{key}")
        present[key] = value

    preterite: dict[str, str] = {}
    for key in ["yo", "tu", "el", "nos", "ellos"]:
        value = preterite_object.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(f"{context}: missing or empty seed_forms.preterite.{key}")
        preterite[key] = value

    imperative: dict[str, str] = {}
    if isinstance(imperative_object, dict):
        for key, value in imperative_object.items():
            if not isinstance(key, str) or not key.strip():
                fail(f"{context}: imperative keys must be non-empty strings")
            if not isinstance(value, str) or not value.strip():
                fail(
                    f"{context}: imperative value for '{key}' must be a non-empty string"
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
    else:
        runtime_examples = build_es_examples(
            lemma=lemma,
            present=present,
            preterite=preterite,
            gerund=gerund,
            strategy=strategy,
            imperative=imperative,
        )

    forms: dict[str, Any] = {
        "present": present,
        "preterite": preterite,
        "gerund": gerund,
        "participle": participle,
    }

    if imperative:
        forms["imperative"] = imperative

    return {
        "id": seed_id,
        "rank": rank,
        "lemma": lemma,
        "forms": forms,
        "examples": runtime_examples,
    }
