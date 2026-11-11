"""Brazilian Portuguese payload cleanup for freshly generated verbs.

The board reads imperative slots `voce`/`nos`/`voces` (ASCII, like every other stored slot key), but
Gemini sometimes keys them with the accented pronouns ("você", "nós", "vocês"), which silently
drops those rows from the board (seen on pt_dormir and pt_precisar). Rewrite the keys, and the
same person names inside an example's `form` hint, before anything is stored. For the finite tenses
"você/ela" mean the stored `ele` slot and "vocês/elas" the `eles` slot; an explicit canonical key wins
over an alias.
"""

from __future__ import annotations

from typing import Any

# Stored slots: eu/ele/nos/eles for every tense, voce/nos/voces for the imperative.
_FINITE_ALIASES = {"você": "ele", "ela": "ele", "vocês": "eles", "elas": "eles", "nós": "nos"}
_IMPERATIVE_ALIASES = {"você": "voce", "vocês": "voces", "nós": "nos"}


def _rename_keys(tense: Any, aliases: dict[str, str]) -> Any:
    if not isinstance(tense, dict):
        return tense
    renamed: dict[str, Any] = {
        k: v for k, v in tense.items() if not (isinstance(k, str) and k.strip().lower() in aliases)
    }
    for slot, value in tense.items():
        if isinstance(slot, str) and slot.strip().lower() in aliases:
            renamed.setdefault(aliases[slot.strip().lower()], value)
    return renamed


def _aliases_for(tense_name: str) -> dict[str, str]:
    return _IMPERATIVE_ALIASES if tense_name == "imperative" else _FINITE_ALIASES


def _normalize_hint(path: Any) -> Any:
    if not isinstance(path, str) or "." not in path:
        return path
    tense, person = path.split(".", 1)
    return f"{tense}.{_aliases_for(tense).get(person.strip().lower(), person)}"


def normalize_pt_payload(generated: Any) -> Any:
    """Rewrite slot keys in place (the payload is freshly parsed JSON) and return it."""
    if not isinstance(generated, dict):
        return generated
    forms = generated.get("forms")
    if isinstance(forms, dict):
        for name, tense in list(forms.items()):
            if isinstance(tense, dict):
                forms[name] = _rename_keys(tense, _aliases_for(name))
    examples = generated.get("examples")
    if isinstance(examples, list):
        for example in examples:
            if isinstance(example, dict) and "form" in example:
                example["form"] = _normalize_hint(example["form"])
    return generated
