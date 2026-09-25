from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.admin_auth import get_session_uid
from core.admin_logging import log_missing_verb_search
from core.analytics.search_hits import record_search_hit
from core.editions import picker_study_plugins, resolve_study_language, study_language_picker_label
from core.entitlements import can_study
from core.i18n import get_strings, resolve_ui_language
from core.languages.config import LANGUAGE
from core.safe_return import safe_return_to
from core.search_utils import find_best_entry, tokenize_text
from core.settings import load_settings
from core.storage.verb_repository import find_verb_by_search_extract, list_verbs_recent
from core.task_tracking import track
from core.translation_service import translate_search_query
from core.verb_autogen import (
    AUTOGEN_LANGUAGES,
    autogen_rate_limited,
    autogenerate_missing_verb,
    check_verb_rejected,
    is_plausible_verb_query,
)
from core.verb_loader import get_verb_of_the_day, load_entries_for_language

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_NON_LATIN_LANGUAGES = {"ru", "he"}


def _entitlement_redirect(
    language: str,
    ui_language: str,
    return_to: str | None,
) -> RedirectResponse:
    """Bounce a search request for a Plus-only language before any
    translation/autogeneration LLM spend happens -- both search endpoints
    otherwise end in a redirect to /learn, which is already gated, but not
    before burning a Vertex Gemini call (and, for autogen-eligible
    languages, a Claude generation + TTS prewarm) first."""
    # Anonymous callers get the same notice as signed-in ones: signing in would
    # not unlock a Plus-only language, so /auth/signin is never the answer here.
    _ui_suffix = f"&ui_language={ui_language}" if ui_language else ""
    base = safe_return_to(return_to or "", fallback="") or f"/verbs?language={language}{_ui_suffix}"
    sep = "&" if "?" in base else "?"
    return RedirectResponse(url=f"{base}{sep}plus_required=1")


def _client_ip(request: Request) -> str:
    """Best-effort per-instance rate-limit key -- NOT a hard security boundary.

    Deliberately takes the LAST X-Forwarded-For hop, not the first: unlike
    core.analytics.session_tracker's fingerprint (best-effort analytics, first
    hop is fine), this key gates a paid-LLM-call rate limit, where the first
    hop is whatever the client itself sent and trivially spoofable. The last
    hop is appended by the infra closest to Cloud Run and is the one a client
    can't directly control. If this deployment's proxy chain doesn't append in
    that order, this key stops being a meaningful rate-limit boundary -- worth
    confirming against the actual Fastly/GFE config in front of Cloud Run.
    """
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
        if hops:
            return hops[-1]
    return (request.client.host if request.client else "") or "unknown"


def _looks_english(query: str) -> bool:
    """Return True if the query contains only ASCII letters/spaces -- likely English input."""
    stripped = query.strip()
    return bool(stripped) and all(c.isascii() and (c.isalpha() or c.isspace()) for c in stripped)


@dataclass
class _HomeVerb:
    id: str
    lemma: Any  # str or dict for Russian


def _doc_to_home_verb(d: dict) -> _HomeVerb:
    lemma = d.get("display_lemma") or d.get("lemma") or ""
    return _HomeVerb(id=d.get("verb_id", ""), lemma=lemma)


def _entry_label(entry: _HomeVerb) -> str:
    if isinstance(entry.lemma, dict):
        return entry.lemma.get("imperfective", "") + " / " + entry.lemma.get("perfective", "")
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

    session_uid = get_session_uid(request)
    if not can_study(language, session_uid):
        return _entitlement_redirect(language, ui_language, return_to)

    translated = await asyncio.to_thread(
        translate_search_query,
        query,
        source_lang,
        language,
    )

    logger.debug("search_verb_by_lang q=%r translated=%r lang=%s", query, translated, language)

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
            record_search_hit(language=language, verb_id=matched_verb_id, source="search_by_lang")
            _rt_suffix = f"&return_to={quote(return_to, safe='/')}" if return_to else ""
            return RedirectResponse(
                url=(
                    f"/learn?language={language}&verb_id={matched_verb_id}"
                    f"&translated_from={quote(query, safe='')}&source_lang={source_lang}"
                    f"{_ui_suffix}{_rt_suffix}"
                )
            )

    base = safe_return_to(return_to or "", fallback="") or f"/?language={language}{_ui_suffix}"
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
    if language in AUTOGEN_LANGUAGES:
        autogen_query = translated
        if not is_plausible_verb_query(autogen_query, language):
            # translate_search_query() can return an aspect pair for Russian
            # (e.g. "бегать/бежать") -- "/" fails the plausibility gate even
            # though the first token alone is a perfectly good query. Retry
            # before giving up; the displayed `search=` stays the full string.
            tokens = tokenize_text(translated)
            if tokens and is_plausible_verb_query(tokens[0], language):
                autogen_query = tokens[0]
        if is_plausible_verb_query(autogen_query, language):
            if await asyncio.to_thread(check_verb_rejected, language, autogen_query):
                return RedirectResponse(
                    url=f"{base}{sep}not_available=1&search={quote(translated, safe='')}&search_mode=native&not_a_verb=1"
                )
            if autogen_rate_limited(_client_ip(request)):
                logger.warning("autogen rate-limited client for %s/%s", language, autogen_query)
                return RedirectResponse(
                    url=f"{base}{sep}not_available=1&search={quote(translated, safe='')}&search_mode=native"
                )
            track(
                asyncio.create_task(
                    autogenerate_missing_verb(
                        language=language,
                        query=autogen_query,
                        audio_backend=request.app.state.audio_backend,
                    )
                )
            )
            return RedirectResponse(
                url=f"{base}{sep}not_available=1&search={quote(translated, safe='')}&search_mode=native&generating=1"
            )
        return RedirectResponse(
            url=f"{base}{sep}not_available=1&search={quote(translated, safe='')}&search_mode=native&garbage=1"
        )
    return RedirectResponse(url=f"{base}{sep}not_available=1&search={quote(translated, safe='')}&search_mode=native")


@router.get("/search_verb", response_model=None)
async def search_verb(
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

    session_uid = get_session_uid(request)
    if not can_study(language, session_uid):
        return _entitlement_redirect(language, ui_language, return_to)

    if language in _NON_LATIN_LANGUAGES and _looks_english(query):
        _rt = f"&return_to={quote(return_to, safe='')}" if return_to else ""
        return RedirectResponse(
            url=f"/search_verb_by_lang?language={language}&q={quote(query, safe='')}&source_lang=en{_ui_suffix}{_rt}"
        )

    _rt_suffix = f"&return_to={quote(return_to, safe='/')}" if return_to else ""

    doc = find_verb_by_search_extract(language, query)

    if doc:
        matched_verb_id = doc.get("verb_id")
        record_search_hit(language=language, verb_id=matched_verb_id, source="search")
        return RedirectResponse(url=f"/learn?language={language}&verb_id={matched_verb_id}{_ui_suffix}{_rt_suffix}")

    entries = _load_entries(language)
    matched_entry = find_best_entry(entries, query)

    if matched_entry:
        record_search_hit(language=language, verb_id=matched_entry.id, source="search")
        return RedirectResponse(url=f"/learn?language={language}&verb_id={matched_entry.id}{_ui_suffix}{_rt_suffix}")

    log_missing_verb_search(
        language=language,
        query=query,
        page="home",
        source="search",
    )

    base = safe_return_to(return_to or "", fallback="") or f"/?language={language}{_ui_suffix}"
    sep = "&" if "?" in base else "?"
    if language in AUTOGEN_LANGUAGES:
        if is_plausible_verb_query(query, language):
            if await asyncio.to_thread(check_verb_rejected, language, query):
                return RedirectResponse(url=f"{base}{sep}not_available=1&search={quote(query, safe='')}&not_a_verb=1")
            if autogen_rate_limited(_client_ip(request)):
                logger.warning("autogen rate-limited client for %s/%s", language, query)
                return RedirectResponse(url=f"{base}{sep}not_available=1&search={quote(query, safe='')}")
            track(
                asyncio.create_task(
                    autogenerate_missing_verb(
                        language=language,
                        query=query,
                        audio_backend=request.app.state.audio_backend,
                    )
                )
            )
            return RedirectResponse(url=f"{base}{sep}not_available=1&search={quote(query, safe='')}&generating=1")
        return RedirectResponse(url=f"{base}{sep}not_available=1&search={quote(query, safe='')}&garbage=1")
    return RedirectResponse(url=f"{base}{sep}not_available=1&search={quote(query, safe='')}")


@router.get("/", response_class=HTMLResponse, response_model=None)
def home(
    request: Request,
    language: str | None = Query(None),
    search: str | None = Query(None),
    not_available: int | None = Query(None),
    search_mode: str | None = Query(None),
    generating: int | None = Query(None),
    garbage: int | None = Query(None),
    not_a_verb: int | None = Query(None),
) -> HTMLResponse | RedirectResponse:
    settings = load_settings()

    plugins = picker_study_plugins(settings)

    ui_lang = resolve_ui_language(request)
    ui = get_strings(ui_lang)
    html_dir = "rtl" if LANGUAGE.get(ui_lang, LANGUAGE["en"]).rtl else "ltr"

    selected_language = resolve_study_language(language, plugins)

    # Plus-only language without the entitlement: no home page / Verb of the Day
    # for it -- land on the /verbs notice (no sign-in; signing in wouldn't unlock it).
    if not can_study(selected_language, get_session_uid(request)):
        return RedirectResponse(url=f"/verbs?language={selected_language}&plus_required=1&ui_language={ui_lang}")

    raw_search_value = search or ""
    search_value = "" if str(not_available) == "1" else raw_search_value

    lang_options = [
        (key, study_language_picker_label(key, plugins, ui), key == selected_language)
        for key, plugin in plugins.items()
    ]

    notice_text = raw_search_value.strip() if str(not_available) == "1" else None
    generating_verb = notice_text if (notice_text and generating == 1) else None
    garbage_query = notice_text if (notice_text and garbage == 1 and not generating_verb) else None
    not_a_verb_query = notice_text if (notice_text and not_a_verb == 1 and not generating_verb) else None

    votd: dict[str, str] | None = None
    try:
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        votd_entry = get_verb_of_the_day(
            load_entries_for_language(language=selected_language),
            language=selected_language,
            date_str=date_str,
        )
        if votd_entry is not None:
            votd = {"id": votd_entry.id, "label": votd_entry.display_lemma or votd_entry.lemma}
    except Exception:
        logger.exception("Failed to compute verb of the day for %s", selected_language)

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
                code: get_strings(code).get("home.ui_language_label", code.upper()) for code in LANGUAGE
            },
            "learning_lang": selected_language,
            "lang_options": lang_options,
            "search_value": search_value,
            "notice_text": notice_text,
            "search_mode": search_mode or "native",
            "generating_verb": generating_verb,
            "garbage_query": garbage_query,
            "not_a_verb_query": not_a_verb_query,
            "firebase_web_config_json": settings.firebase_web_config_json,
            "votd": votd,
        },
    )
    return response
