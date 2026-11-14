"""robots.txt and sitemap.xml generation (issue #103). Pure logic; routes live in app/routes/seo.py."""

from __future__ import annotations

import logging
import os
from urllib.parse import quote
from xml.sax.saxutils import escape

from core.editions import active_study_plugins
from core.entitlements import requires_entitlement
from core.settings import _resolve_environment
from core.verb_loader import load_entries_for_language

logger = logging.getLogger(__name__)

# No public-base-URL setting exists; the canonical prod host is fixed. Overridable
# via PUBLIC_BASE_URL (never derived from the request: stage must not emit it).
_DEFAULT_PROD_BASE_URL = "https://verbboard.com"
MAX_SITEMAP_URLS = 50_000
_DISALLOWED_PREFIXES = ("/admin", "/audio", "/api", "/auth", "/feedback", "/__/")


def public_base_url() -> str:
    return (os.getenv("PUBLIC_BASE_URL", "").strip() or _DEFAULT_PROD_BASE_URL).rstrip("/")


def canonical_learn_url(language: str, verb_id: str) -> str:
    """The single canonical /learn URL for a verb (issue #102); shared by the sitemap and <link rel=canonical>."""
    return f"{public_base_url()}/learn?language={quote(language, safe='')}&verb_id={quote(verb_id, safe='')}&ui_language=en"


def canonical_verbs_url(language: str) -> str:
    """The single canonical /verbs URL for a study language (issue #119); shared by the sitemap and the page head."""
    return f"{public_base_url()}/verbs?language={quote(language, safe='')}&ui_language=en"


def canonical_home_url() -> str:
    return f"{public_base_url()}/"


def canonical_about_url() -> str:
    return f"{public_base_url()}/about"


def build_robots_txt() -> str:
    if _resolve_environment() != "prod":
        return "User-agent: *\nDisallow: /\n"
    lines = ["User-agent: *", *(f"Disallow: {prefix}" for prefix in _DISALLOWED_PREFIXES)]
    lines.append("")
    lines.append(f"Sitemap: {public_base_url()}/sitemap.xml")
    return "\n".join(lines) + "\n"


def free_sitemap_languages() -> list[str]:
    return [code for code in active_study_plugins() if not requires_entitlement(code)]


def build_sitemap_xml() -> str:
    """Raises on loader failure (caller turns it into a 503)."""
    base = public_base_url()
    locs: list[str] = [f"{base}/"]
    for language in free_sitemap_languages():
        locs.append(canonical_verbs_url(language))
        for entry in load_entries_for_language(language=language):
            locs.append(canonical_learn_url(language, entry.id))
    if len(locs) > MAX_SITEMAP_URLS:
        logger.error("SITEMAP_TRUNCATED urls=%d limit=%d", len(locs), MAX_SITEMAP_URLS)
        locs = locs[:MAX_SITEMAP_URLS]
    body = "".join(f"<url><loc>{escape(loc)}</loc></url>" for loc in locs)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n'
    )
