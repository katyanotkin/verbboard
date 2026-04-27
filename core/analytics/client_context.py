from __future__ import annotations


def detect_device_type(user_agent: str | None) -> str:
    text = (user_agent or "").casefold()

    if not text:
        return "unknown"

    if "ipad" in text or "tablet" in text:
        return "tablet"

    if "mobile" in text or "iphone" in text or "android" in text:
        return "mobile"

    return "desktop"
