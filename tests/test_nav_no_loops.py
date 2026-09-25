"""Navigation crawler: no redirect cycles, no server errors, and no link that
redirects straight back to the page it sits on (a dead-end Back/Home button).

Caught by hand once: on /verbs for a Plus-only language the Back link pointed
at /?language=fr, which home redirects to /verbs?language=fr again.

For every registered picker language, as an anonymous and as an entitled
visitor, each main page is fetched with redirects followed by hand; every
internal link in the rendered HTML is then resolved the same way. Links are
read from server-rendered HTML only; JS-built links and localStorage-driven
redirects (home.js) are outside what a TestClient can see.
"""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, urlsplit

import pytest

from core.editions import picker_study_plugins
from core.entitlements import requires_entitlement
from core.settings import load_settings
from tests.conftest import patch_everywhere, seed_spanish_verb

MAX_HOPS = 4
PAGES = ("/", "/verbs", "/learn?verb_id=es_hablar", "/about", "/feedback")
# Links that are not plain navigation (assets, APIs, auth, paid generation).
SKIPPED_PREFIXES = ("/static", "/audio", "/api", "/auth", "/admin", "/search_verb", "/set_language", "/manifest")
HREF_RE = re.compile(r'href="(/[^"#]*)')

LANGUAGES = sorted(picker_study_plugins(load_settings()))


def _signature(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.path, (parse_qs(parts.query).get("language") or [""])[0]


def _resolve(client, url: str) -> tuple[str, int, int, str]:
    """Follow redirects by hand. Returns (final_url, status, hops, body)."""
    seen = {url}
    hops = 0
    while True:
        resp = client.get(url, follow_redirects=False)
        if resp.status_code not in (301, 302, 303, 307, 308):
            return url, resp.status_code, hops, resp.text
        url = resp.headers["location"]
        hops += 1
        assert url not in seen, f"redirect cycle through {url}"
        assert hops <= MAX_HOPS, f"more than {MAX_HOPS} redirects starting from {url}"
        seen.add(url)


@pytest.mark.parametrize("entitled", [False, True], ids=["anonymous", "entitled"])
@pytest.mark.parametrize("language", LANGUAGES)
def test_no_loops_or_dead_end_links(client, fake_db, monkeypatch, language, entitled):
    seed_spanish_verb(fake_db)
    patch_everywhere(
        monkeypatch,
        "core.entitlements.can_study",
        lambda lang, uid, settings=None: entitled or not requires_entitlement(lang),
    )

    problems: list[str] = []
    for page in PAGES:
        joiner = "&" if "?" in page else "?"
        start = f"{page}{joiner}language={language}&ui_language=en"
        try:
            final_url, status, _, body = _resolve(client, start)
        except AssertionError as error:
            problems.append(f"{start}: {error}")
            continue
        if status >= 500:
            problems.append(f"{start}: {status}")
        if status != 200:
            continue

        page_signature = _signature(final_url)
        for href in sorted({html.unescape(match) for match in HREF_RE.findall(body)}):
            if href.startswith(SKIPPED_PREFIXES):
                continue
            try:
                target, target_status, hops, _ = _resolve(client, href)
            except AssertionError as error:
                problems.append(f"{final_url} links to {href}: {error}")
                continue
            if target_status >= 500:
                problems.append(f"{final_url} links to {href}: {target_status}")
            elif hops and _signature(target) == page_signature:
                problems.append(f"{final_url} links to {href}, which redirects back to {target}")

    assert not problems, "\n".join(problems)
