from __future__ import annotations

import re
from urllib.parse import unquote

_SAFE_RE = re.compile(r"^/[^/\\]")
# Whitespace and control characters (browsers strip tab/CR/LF inside URLs, so
# "/\t/evil.com" would become "//evil.com").
_UNSAFE_CHARS_RE = re.compile(r"[^\S ]|[\x00-\x1f\x7f]")  # a plain space is legitimate once decoded (%20)


def safe_return_to(url: str, fallback: str = "/") -> str:
    """Validate a redirect target; return fallback for any unsafe input.

    Rules:
    - Must be a relative path starting with a single slash
    - Double-slash (protocol-relative) and backslash are rejected
    - URL-encoded input is decoded before validation (and re-checked after a
      second decode); any whitespace or control character rejects the URL
    """
    raw = url or ""
    decoded = unquote(raw)
    # Guard double-encoding (%252f -> %2f -> /): validate every decode layer.
    twice = unquote(decoded)
    for candidate in (raw, decoded, twice):
        if _UNSAFE_CHARS_RE.search(candidate):
            return fallback
        if candidate.startswith("//") or candidate.startswith("/\\"):
            return fallback
    if decoded == "/":
        return "/"
    if _SAFE_RE.match(decoded) and _SAFE_RE.match(twice or "/"):
        return decoded
    return fallback
