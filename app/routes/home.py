from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.admin_logging import log_missing_verb_search
from core.i18n import get_strings, resolve_ui_language
from core.languages.config import LANGUAGE
from core.registry import all_plugins
from core.safe_return import safe_return_to
from core.search_utils import find_best_entry, tokenize_text
from core.settings import load_settings
from core.storage.verb_repository import find_verb_by_search_extract, list_verbs_recent
from core.translation_service import translate_search_query
from core.verb_loader import load_entries_for_language

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_NON_LATIN_LANGUAGES = {"ru", "he"}


def _looks_english(query: str) -> bool:
    """Return True if the query contains only ASCII letters/spaces -- likely English input."""
    stripped = query.strip()
    return bool(stripped) and all(
        c.isascii() and (c.isalpha() or c.isspace()) for c in stripped
    )


@dataclass
class _HomeVerb:
    id: str
    lemma: Any  # str or dict for Russian


def _doc_to_home_verb(d: dict) -> _HomeVerb:
    lemma = d.get("display_lemma") or d.get("lemma") or ""
    return _HomeVerb(id=d.get("verb_id", ""), lemma=lemma)


def _entry_label(entry: _HomeVerb) -> str:
    if isinstance(entry.lemma, dict):
        return (
            entry.lemma.get("imperfective", "")
            + " / "
            + entry.lemma.get("perfective", "")
        )
    return str(entry.lemma)


def _load_entries(language: str) -> list[_HomeVerb]:
    docs = list_verbs_recent(language, limit=20)
    return [_doc_to_home_verb(d) for d in docs]


@router.get("/set_language", response_model=None)
def set_language(language: str, ui_language: str = ""):
    url = f"/?language={language}"
    if ui_language:
        url += f"&ui_language={ui_language}"
    return RedirectResponse(url=url)


@router.get("/search_verb_by_lang", response_model=None)
async def search_verb_by_lang(
    request: Request,
    language: str,
    q: str = "",
    source_lang: str = "en",
    return_to: str | None = None,
    ui_language: str = "",
):
    query = (q or "").strip()
    _ui_suffix = f"&ui_language={ui_language}" if ui_language else ""
    if not query:
        return RedirectResponse(url=f"/?language={language}{_ui_suffix}")

    settings = load_settings()
    translated = await asyncio.to_thread(
        translate_search_query,
        query,
        source_lang,
        language,
        settings.google_cloud_project,
    )

    logger.debug(
        "search_verb_by_lang q=%r translated=%r lang=%s", query, translated, language
    )

    if translated:
        doc = find_verb_by_search_extract(language, translated)

        if not doc:
            # Gemini may return multi-word output despite the single-word prompt;
            # try each token so "бегать/бежать" or "correr." still resolves.
            for token in tokenize_text(translated):
                doc = find_verb_by_search_extract(language, token)
                if doc:
                    break

        if not doc:
            # Fuzzy fallback against all cached verbs (60 s TTL).
            all_entries = load_entries_for_language(language=language)
            matched = find_best_entry(all_entries, translated)
            if matched:
                doc = {"verb_id": matched.id}

        if doc:
            matched_verb_id = doc.get("verb_id")
            return RedirectResponse(
                url=(
                    f"/learn?language={language}&verb_id={matched_verb_id}"
                    f"&translated_from={quote(query, safe='')}&source_lang={source_lang}"
                    f"{_ui_suffix}"
                )
            )

    base = (
        safe_return_to(return_to or "", fallback="")
        or f"/?language={language}{_ui_suffix}"
    )
    sep = "&" if "?" in base else "?"

    if not translated:
        # Gemini failed to translate -- show original query so user can retry
        logger.warning(
            "search_verb_by_lang translation failed q=%r %s->%s",
            query,
            source_lang,
            language,
        )
        return RedirectResponse(
            url=f"{base}{sep}not_available=1&search={quote(query, safe='')}&search_mode={source_lang}"
        )
    # Translation succeeded but verb not in DB -- show translated word
    # so user sees what was actually searched in the target language.
    log_missing_verb_search(
        language=language,
        query=translated,
        page="home",
        source="search_by_lang",
    )
    return RedirectResponse(
        url=f"{base}{sep}not_available=1&search={quote(translated, safe='')}&search_mode=native"
    )


@router.get("/search_verb", response_model=None)
def search_verb(
    request: Request,
    language: str,
    q: str = "",
    ui_language: str = "",
    return_to: str | None = None,
):
    query = (q or "").strip()
    _ui_suffix = f"&ui_language={ui_language}" if ui_language else ""
    if not query:
        return RedirectResponse(url=f"/?language={language}{_ui_suffix}")

    if language in _NON_LATIN_LANGUAGES and _looks_english(query):
        _rt = f"&return_to={quote(return_to, safe='')}" if return_to else ""
        return RedirectResponse(
            url=f"/search_verb_by_lang?language={language}&q={quote(query, safe='')}&source_lang=en{_ui_suffix}{_rt}"
        )

    doc = find_verb_by_search_extract(language, query)

    if doc:
        matched_verb_id = doc.get("verb_id")
        return RedirectResponse(
            url=f"/learn?language={language}&verb_id={matched_verb_id}{_ui_suffix}"
        )

    entries = _load_entries(language)
    matched_entry = find_best_entry(entries, query)

    if matched_entry:
        return RedirectResponse(
            url=f"/learn?language={language}&verb_id={matched_entry.id}{_ui_suffix}"
        )

    log_missing_verb_search(
        language=language,
        query=query,
        page="home",
        source="search",
    )

    base = (
        safe_return_to(return_to or "", fallback="")
        or f"/?language={language}{_ui_suffix}"
    )
    sep = "&" if "?" in base else "?"
    return RedirectResponse(
        url=f"{base}{sep}not_available=1&search={quote(query, safe='')}"
    )


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    language: str | None = Query(None),
    search: str | None = Query(None),
    not_available: int | None = Query(None),
    search_mode: str | None = Query(None),
) -> HTMLResponse:
    plugins = all_plugins()

    settings = load_settings()

    ui_lang = resolve_ui_language(request)
    ui = get_strings(ui_lang)
    html_dir = "rtl" if LANGUAGE.get(ui_lang, LANGUAGE["en"]).rtl else "ltr"

    selected_language = language or "he"
    if selected_language not in plugins:
        selected_language = "he"

    raw_search_value = search or ""
    search_value = "" if str(not_available) == "1" else raw_search_value

    def _lang_label(key: str) -> str:
        if key not in LANGUAGE:
            return plugins[key].display_name
        return ui.get(f"lang.{key}", LANGUAGE[key].display)

    lang_options = [
        (key, _lang_label(key), key == selected_language)
        for key, plugin in plugins.items()
    ]

    notice_text = raw_search_value.strip() if str(not_available) == "1" else None

    response = templates.TemplateResponse(
        request,
        "home.html",
        {
            "lang": ui_lang,
            "html_dir": html_dir,
            "ui": ui,
            "ui_lang_codes": list(LANGUAGE.keys()),
            "ui_lang_native": {code: cfg.native for code, cfg in LANGUAGE.items()},
            "ui_lang_labels": {
                code: get_strings(code).get("home.ui_language_label", code.upper())
                for code in LANGUAGE
            },
            "learning_lang": selected_language,
            "lang_options": lang_options,
            "search_value": search_value,
            "notice_text": notice_text,
            "search_mode": search_mode or "native",
            "firebase_web_config_json": settings.firebase_web_config_json,
        },
    )
    return response
