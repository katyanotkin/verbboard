from __future__ import annotations

from datetime import datetime
from typing import Any


def json_safe(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types to safe equivalents.

    Handles Firestore DatetimeWithNanoseconds (subclass of datetime) and
    nested dicts/lists.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]
    return obj
