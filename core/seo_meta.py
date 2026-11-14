"""Page title / meta description / canonical / Open Graph values (issues #102, #104). Pure logic.

Templates receive these as plain strings and Jinja autoescape handles the HTML escaping.

No hreflang on purpose: the ui_language variants of a page are the same URL with a query param
(resolved from localStorage / Accept-Language), not real localized pages, so alternates would be wrong.
"""

from __future__ import annotations

from core.sitemap_service import canonical_learn_url, public_base_url

TITLE_MAX = 60
DESCRIPTION_MAX = 155
SITE_NAME = "VerbBoard"

_DEFAULTS = {
    "seo.learn_title": "Conjugation of {lemma}: all tenses with audio | VerbBoard",
    "seo.learn_title_short": "{lemma}: conjugation and audio | VerbBoard",
    "seo.learn_title_min": "{lemma} | VerbBoard",
    "seo.learn_desc": "{lemma} ({translation}): {language} verb conjugation in all tenses, with example sentences and audio.",
    "seo.learn_desc_plain": "{lemma}: {language} verb conjugation in all tenses, with example sentences and audio.",
    "seo.learn_desc_short": "{lemma}: {language} verb conjugation with audio.",
}


def truncate_at_word(text: str, limit: int) -> str:
    """Cut to at most `limit` characters at a word boundary, adding an ellipsis when something was removed."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut and text[limit - 1] != " ":
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:/-") + "…"


def lemma_text(lemma: object) -> str:
    """Plain lemma string; a Russian aspect pair dict becomes 'imperfective / perfective'."""
    if isinstance(lemma, dict):
        return f"{lemma.get('imperfective', '')} / {lemma.get('perfective', '')}"
    return str(lemma)


def _t(ui: dict[str, str], key: str) -> str:
    return ui.get(key) or _DEFAULTS[key]


def learn_title(ui: dict[str, str], lemma: str) -> str:
    for key in ("seo.learn_title", "seo.learn_title_short", "seo.learn_title_min"):
        candidate = _t(ui, key).format(lemma=lemma)
        if len(candidate) <= TITLE_MAX:
            return candidate
    template = _t(ui, "seo.learn_title_min")
    overhead = len(template.format(lemma=""))
    return template.format(lemma=truncate_at_word(lemma, max(TITLE_MAX - overhead, 4)))


def learn_description(ui: dict[str, str], lemma: str, translation: str, language_name: str) -> str:
    keys = (["seo.learn_desc"] if translation else []) + ["seo.learn_desc_plain", "seo.learn_desc_short"]
    for key in keys:
        candidate = _t(ui, key).format(lemma=lemma, translation=translation, language=language_name)
        if len(candidate) <= DESCRIPTION_MAX:
            return candidate
    fallback = _t(ui, "seo.learn_desc_short")
    overhead = len(fallback.format(lemma="", language=language_name))
    return fallback.format(lemma=truncate_at_word(lemma, max(DESCRIPTION_MAX - overhead, 4)), language=language_name)


def learn_meta(
    ui: dict[str, str],
    *,
    language: str,
    verb_id: str,
    lemma: str,
    translation: str,
    language_name: str,
    is_candidate: bool,
) -> dict[str, object]:
    """Template variables for the /learn head. Candidate previews are noindex and carry no canonical/og:url."""
    title = learn_title(ui, lemma)
    description = learn_description(ui, lemma, translation, language_name)
    canonical = "" if is_candidate else canonical_learn_url(language, verb_id)
    return {
        "meta_title": title,
        "meta_description": description,
        "canonical_url": canonical,
        "og_url": canonical,
        "noindex": is_candidate,
    }


def static_page_meta(
    ui: dict[str, str], key_prefix: str, path: str, *, noindex: bool = False, default_title: str = SITE_NAME
) -> dict[str, object]:
    """Home / verbs / about: title and description from `{key_prefix}_title` / `{key_prefix}_desc` i18n keys."""
    return {
        "meta_title": ui.get(f"{key_prefix}_title") or default_title,
        "meta_description": ui.get(f"{key_prefix}_desc", ""),
        "canonical_url": "",
        "og_url": f"{public_base_url()}{path}",
        "noindex": noindex,
    }


# Search-miss / error signal params: a home or /verbs page rendered for one of these is a transient state.
NOINDEX_STATE_PARAMS = frozenset({"not_available", "generating", "not_a_verb", "garbage", "queued", "plus_required"})
