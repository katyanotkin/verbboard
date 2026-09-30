"""Russian stress marks (combining acute, U+0301) must never reach stored verb data.

Edge TTS reads marked text worse than plain text (issue #46), and the generation
prompt's "plain text" rule is advisory, so every Claude response for Russian is
stripped here before it is parsed into a candidate or a live verb.
"""

from __future__ import annotations

import unicodedata
from typing import Any

STRESS_MARK = "́"


def strip_stress_marks(value: Any) -> Any:
    """Return value with U+0301 removed from every string, recursing into dicts and lists."""
    if isinstance(value, str):
        if STRESS_MARK not in value:
            return value
        decomposed = unicodedata.normalize("NFD", value)
        return unicodedata.normalize("NFC", decomposed.replace(STRESS_MARK, ""))
    if isinstance(value, dict):
        return {key: strip_stress_marks(item) for key, item in value.items()}
    if isinstance(value, list):
        return [strip_stress_marks(item) for item in value]
    return value
