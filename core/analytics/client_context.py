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


def detect_os(user_agent: str | None) -> str:
    text = (user_agent or "").casefold()

    if not text:
        return "unknown"

    if "iphone" in text or "ipad" in text:
        return "ios"
    if "android" in text:
        return "android"
    if "windows" in text:
        return "windows"
    if "mac os" in text or "macos" in text or "macintosh" in text:
        return "mac"
    if "linux" in text:
        return "linux"

    return "unknown"
