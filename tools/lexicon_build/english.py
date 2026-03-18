from __future__ import annotations

from typing import Any

from tools.lexicon_build.common import fail, validate_required_keys


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
    gerund: str,
    strategy: str,
    built_in_examples: dict[str, list[str]],
) -> list[dict[str, str]]:
    custom_examples = built_in_examples.get(lemma)
    if custom_examples:
        return [{"dst": sentence} for sentence in custom_examples]

    if strategy == "become_state":
        return [
            {"dst": "I become tired in the evening."},
            {"dst": f"She {present_3sg} more confident every year."},
            {"dst": f"They {past} friends quickly."},
            {"dst": f"He is {gerund} stronger."},
            {"dst": "Become stronger every day."},
        ]

    if strategy == "meet_person_or_meet_with_group":
        return [
            {"dst": "I meet my tutor every Friday."},
            {"dst": f"She {present_3sg} the client today."},
            {"dst": f"They {past} at the station."},
            {"dst": f"We are {gerund} with the team now."},
            {"dst": "Meet me at the entrance."},
        ]

    return [
        {"dst": f"I {lemma} my work every day."},
        {"dst": f"She {present_3sg} a new task at work."},
        {"dst": f"They {past} the job yesterday."},
        {"dst": f"We are {gerund} the project now."},
        {"dst": f"{lemma.capitalize()} carefully."},
    ]


def expand_english_entry(
    seed_entry: dict[str, Any],
    rank: int,
    built_in_examples: dict[str, list[str]],
) -> dict[str, Any]:
    context = f"English seed #{rank}"
    strategy = seed_entry.get("example_strategy", "generic")

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
    if not isinstance(strategy, str) or not strategy.strip():
        fail(f"{context}: example_strategy must be a non-empty string if present")

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
            gerund=gerund,
            strategy=strategy,
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
