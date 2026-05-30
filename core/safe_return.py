from __future__ import annotations

import re
from urllib.parse import unquote

_SAFE_RE = re.compile(r"^/[^/\\]")


def safe_return_to(url: str, fallback: str = "/") -> str:
    """Validate a redirect target; return fallback for any unsafe input.

    Rules:
    - Must be a relative path starting with a single slash
    - Double-slash (protocol-relative) and backslash are rejected
    - URL-encoded input is decoded before validation
    """
    decoded = unquote(url or "")
    if decoded == "/":
        return "/"
    if _SAFE_RE.match(decoded):
        return decoded
    return fallback
