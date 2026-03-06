from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


VALID_HE_BINYANIM = {
    "פעל",
    "פיעל",
    "התפעל",
    "הפעיל",
    "נפעל",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def require_keys(obj: dict[str, Any], keys: list[str], context: str) -> None:
    for key in keys:
        if key not in obj:
            fail(f"{context}: missing key '{key}'")


def require_nonempty_string(value: Any, context: str) -> None:
    if not isinstance(value, str) or not value.strip():
        fail(f"{context}: expected non-empty string")


def check_examples(examples: list[Any], context: str) -> None:
    if not isinstance(examples, list):
        fail(f"{context}: examples must be a list")
    if len(examples) < 5:
        fail(f"{context}: expected at least 5 examples, got {len(examples)}")
    for index, example in enumerate(examples, start=1):
        if not isinstance(example, dict):
            fail(f"{context}: example #{index} must be an object")
        require_keys(example, ["dst"], f"{context} example #{index}")
        require_nonempty_string(example["dst"], f"{context} example #{index} dst")


def check_hebrew_entry(entry: dict[str, Any], index: int) -> None:
    context = f"verb #{index} ({entry.get('id', '<missing id>')})"
    require_keys(entry, ["id", "rank", "lemma", "morph", "forms", "examples"], context)

    require_nonempty_string(entry["id"], f"{context} id")
    require_nonempty_string(entry["lemma"], f"{context} lemma")

    if not isinstance(entry["rank"], int):
        fail(f"{context}: rank must be int")

    morph = entry["morph"]
    if not isinstance(morph, dict):
        fail(f"{context}: morph must be object")
    require_keys(morph, ["binyan", "root"], f"{context} morph")
    require_nonempty_string(morph["binyan"], f"{context} morph.binyan")
    require_nonempty_string(morph["root"], f"{context} morph.root")

    if morph["binyan"] not in VALID_HE_BINYANIM:
        fail(
            f"{context}: invalid binyan '{morph['binyan']}', "
            f"expected one of {sorted(VALID_HE_BINYANIM)}"
        )

    forms = entry["forms"]
    if not isinstance(forms, dict):
        fail(f"{context}: forms must be object")

    require_keys(forms, ["present", "past", "future"], f"{context} forms")

    present = forms["present"]
    past = forms["past"]
    future = forms["future"]

    if not isinstance(present, dict):
        fail(f"{context}: forms.present must be object")
    if not isinstance(past, dict):
        fail(f"{context}: forms.past must be object")
    if not isinstance(future, dict):
        fail(f"{context}: forms.future must be object")

    for key in ["m_sg", "f_sg", "m_pl", "f_pl"]:
        require_nonempty_string(present.get(key), f"{context} forms.present.{key}")

    for key in ["1sg", "2msg", "2fsg", "3msg", "3fsg", "1pl", "2mpl", "2fpl", "3pl"]:
        require_nonempty_string(past.get(key), f"{context} forms.past.{key}")

    for key in ["1sg", "2msg", "2fsg", "3msg", "3fsg", "1pl", "2mpl", "2fpl", "3pl"]:
        require_nonempty_string(future.get(key), f"{context} forms.future.{key}")

    check_examples(entry["examples"], context)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: python tools/check_lexicon.py data/he/lexicon.json")

    path = Path(sys.argv[1])
    if not path.exists():
        fail(f"file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))

    require_keys(payload, ["language", "version", "verbs"], "top-level")

    if payload["language"] != "he":
        fail(f"top-level: expected language='he', got '{payload['language']}'")

    if not isinstance(payload["version"], int):
        fail("top-level: version must be int")

    verbs = payload["verbs"]
    if not isinstance(verbs, list):
        fail("top-level: verbs must be list")

    seen_ids: set[str] = set()
    seen_lemmas: set[str] = set()
    seen_ranks: set[int] = set()

    for index, entry in enumerate(verbs, start=1):
        if not isinstance(entry, dict):
            fail(f"verb #{index}: must be object")
        check_hebrew_entry(entry, index)

        verb_id = entry["id"]
        lemma = entry["lemma"]
        rank = entry["rank"]

        if verb_id in seen_ids:
            fail(f"duplicate id: {verb_id}")
        if lemma in seen_lemmas:
            fail(f"duplicate lemma: {lemma}")
        if rank in seen_ranks:
            fail(f"duplicate rank: {rank}")

        seen_ids.add(verb_id)
        seen_lemmas.add(lemma)
        seen_ranks.add(rank)

    print(f"OK: {path} ({len(verbs)} verbs)")


if __name__ == "__main__":
    main()
