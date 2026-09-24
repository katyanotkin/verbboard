from __future__ import annotations

import re

# Crude, deliberately broad self-identification check: crawlers, SEO/backlink
# scanners, and scripted HTTP clients. Undeclared bots that spoof a browser
# user agent are not caught. Only used to keep them out of usage stats.
_BOT_PATTERN = re.compile(
    r"bot[/;)]|\bbot\b|crawl|spider|slurp|scan|curl|wget|python|go-http|headless|monitor|uptime|facebookexternalhit|httpclient",
    re.IGNORECASE,
)


def detect_device_type(user_agent: str | None) -> str:
    text = (user_agent or "").casefold()

    if not text:
        return "unknown"

    if _BOT_PATTERN.search(text):
        return "bot"

    if "ipad" in text or "tablet" in text:
        return "tablet"

    if "mobile" in text or "iphone" in text or "android" in text:
        return "mobile"

    return "desktop"
