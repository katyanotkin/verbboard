"""French subjonctif forms are stored without the introducing "que".

The board's section title carries "que…", and the stored forms follow `present` (pronoun + elision).
The generation prompt says so, but Gemini still returns "que je reçoive" / "qu'il reçoive", which
would render as "que que je reçoive". Strip the particle from every generated response.
"""

from __future__ import annotations

import re
from typing import Any

_QUE_PREFIX = re.compile(r"^\s*qu(?:e\s+|')\s*", re.IGNORECASE)


def normalize_subjonctif(generated: Any) -> Any:
    """Return the payload with a leading "que "/"qu'" removed from each forms.subjonctif_present slot."""
    if not isinstance(generated, dict):
        return generated
    forms = generated.get("forms")
    if not isinstance(forms, dict):
        return generated
    tense = forms.get("subjonctif_present")
    if not isinstance(tense, dict):
        return generated
    forms["subjonctif_present"] = {
        slot: _QUE_PREFIX.sub("", text) if isinstance(text, str) else text for slot, text in tense.items()
    }
    return generated
    forms["subjonctif_present"] = {
        slot: _QUE_PREFIX.sub("", text) if isinstance(text, str) else text for slot, text in tense.items()
    }
    return generated
