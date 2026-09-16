"""Post-generation sanity checks for cold (search-miss) Russian verb generation.

Pair-completion (`core.verb_service.generate_and_promote_verb`) always has an
anchor: the aspect is implied by the verb it's completing, so Claude only has
to produce a correct partner. A cold search-miss has no such anchor -- Claude
must independently determine aspect classification *and* produce consistent
forms, with no admin review before the result goes live. This module is the
extra bar that gap requires; it is not needed by the pair-completion path.
"""

from __future__ import annotations

import re
from typing import Any

_CYRILLIC_TOKEN = re.compile(r"^[а-яё]+$", re.IGNORECASE)

_ASPECT_FORM_KEYS: dict[str, tuple[str, ...]] = {
    "imperfective": ("present",),
    "perfective": ("future",),
    "biaspectual": ("present", "future"),
}
_ASPECT_ABSENT_KEYS: dict[str, tuple[str, ...]] = {
    "imperfective": ("future",),
    "perfective": ("present",),
    "biaspectual": (),
}


def validate_ru_payload(lemma: str, morph: Any, forms: dict[str, Any]) -> str | None:
    """Return a failure reason string, or None if the payload is safe to publish live."""
    if not isinstance(morph, dict):
        return "morph is not an object"

    aspect = morph.get("aspect")
    if aspect not in _ASPECT_FORM_KEYS:
        return f"invalid aspect: {aspect!r}"

    for required_key in _ASPECT_FORM_KEYS[aspect]:
        if not isinstance(forms.get(required_key), dict) or not forms[required_key]:
            return f"aspect={aspect} requires non-empty forms.{required_key}"
    for absent_key in _ASPECT_ABSENT_KEYS[aspect]:
        if forms.get(absent_key):
            return f"aspect={aspect} should not have forms.{absent_key}"

    if not isinstance(forms.get("past"), dict) or not forms["past"]:
        return "forms.past is required for every aspect"
    if not isinstance(forms.get("imperative"), dict) or not forms["imperative"]:
        return "forms.imperative is required for every aspect"

    pair = morph.get("pair", "")
    if not isinstance(pair, str):
        return "morph.pair is not a string"
    if aspect == "biaspectual" and pair:
        return "biaspectual verbs must have an empty morph.pair"
    if pair:
        if pair.strip().lower() == lemma.strip().lower():
            return "morph.pair must not equal the lemma"
        if not _CYRILLIC_TOKEN.match(pair.strip()):
            return f"morph.pair is not a single Cyrillic token: {pair!r}"

    return None
