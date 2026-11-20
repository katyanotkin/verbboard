"""Share a study language with a friend (issue #128).

Pure helpers: the link a sender shares and the preview image a chat app shows for it.
The host always comes from `PUBLIC_BASE_URL` (never the request), and the link carries no
`ui_language`, so the recipient's Accept-Language picks their UI language.
"""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import quote

from core.languages.config import FREE_STUDY_LANGUAGES
from core.sitemap_service import public_base_url

SHARE_UTM_SOURCE = "share"

# Cards in app/static/og/, one per language, made by tools/make_share_cards.py.
OG_IMAGE_WIDTH = 1200
OG_IMAGE_HEIGHT = 630


def is_shareable_language(language: str) -> bool:
    """Plus-only languages are not shared: the recipient would only meet the Plus notice."""
    return language in FREE_STUDY_LANGUAGES


def share_verbs_url(language: str) -> str:
    if not is_shareable_language(language):
        return ""
    return f"{public_base_url()}/verbs?language={quote(language, safe='')}&utm_source={SHARE_UTM_SOURCE}"


def share_og_image_url(language: str) -> str:
    if not is_shareable_language(language):
        return ""
    return f"{public_base_url()}/static/og/verbs-{quote(language, safe='')}.png"


def is_share_landing(query_params: Mapping[str, str]) -> bool:
    return query_params.get("utm_source", "") == SHARE_UTM_SOURCE
