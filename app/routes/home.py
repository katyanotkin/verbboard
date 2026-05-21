from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.admin_logging import log_missing_verb_search
from core.i18n import get_strings, resolve_ui_language
from core.languages.config import LANGUAGE
from core.registry import all_plugins
from core.search_utils import find_best_entry
from core.settings import load_settings
from core.storage.verb_repository import find_verb_by_search_extract, list_verbs_recent
from core.verb_loader import load_entries_for_language

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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
def set_language(language: str):
    entries = _load_entries(language)
    default_verb_id = entries[0].id if entries else ""

    response = RedirectResponse(url=f"/?language={language}&verb_id={default_verb_id}")
    response.set_cookie("language", language, httponly=False, samesite="lax")
    if default_verb_id:
        response.set_cookie("verb_id", default_verb_id, httponly=False, samesite="lax")
    return response


@router.get("/search_verb", response_model=None)
def search_verb(
    request: Request,
    language: str,
    q: str = "",
):
    query = (q or "").strip()
    if not query:
        return RedirectResponse(url=f"/?language={language}")

    doc = find_verb_by_search_extract(language, query)

    if doc:
        matched_verb_id = doc.get("verb_id")

        response = RedirectResponse(
            url=f"/learn?language={language}&verb_id={matched_verb_id}"
        )
        response.set_cookie("language", language, httponly=False, samesite="lax")
        response.set_cookie("verb_id", matched_verb_id, httponly=False, samesite="lax")
        return response

    entries = _load_entries(language)
    matched_entry = find_best_entry(entries, query)

    if matched_entry:
        matched_verb_id = matched_entry.id

        response = RedirectResponse(
            url=f"/learn?language={language}&verb_id={matched_verb_id}"
        )
        response.set_cookie("language", language, httponly=False, samesite="lax")
        response.set_cookie("verb_id", matched_verb_id, httponly=False, samesite="lax")
        return response

    log_missing_verb_search(
        language=language,
        query=query,
        page="home",
        source="search",
    )

    response = RedirectResponse(
        url=f"/?language={language}&search={query}&not_available=1"
    )
    response.set_cookie("language", language, httponly=False, samesite="lax")
    return response


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    language: str | None = Query(None),
    verb_id: str | None = Query(None),
    search: str | None = Query(None),
    not_available: int | None = Query(None),
) -> HTMLResponse:
    plugins = all_plugins()

    settings = load_settings()

    ui_lang = resolve_ui_language(request)
    ui = get_strings(ui_lang)
    html_dir = "rtl" if LANGUAGE.get(ui_lang, LANGUAGE["en"]).rtl else "ltr"

    cookie_language = request.cookies.get("language")
    cookie_verb_id = request.cookies.get("verb_id")

    selected_language = language or cookie_language or "he"
    if selected_language not in plugins:
        selected_language = "he"

    entries = _load_entries(selected_language)
    total_verbs = len(load_entries_for_language(language=selected_language))

    selected_verb_id = verb_id or cookie_verb_id
    if entries:
        valid_verb_ids = {entry.id for entry in entries}
        if selected_verb_id not in valid_verb_ids:
            selected_verb_id = entries[0].id
    else:
        selected_verb_id = ""

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

    verb_options = [
        (entry.id, _entry_label(entry), entry.id == selected_verb_id)
        for entry in entries[:20]
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
            "verb_options": verb_options,
            "search_value": search_value,
            "notice_text": notice_text,
            "total_verbs": total_verbs,
            "firebase_web_config_json": settings.firebase_web_config_json,
        },
    )
    response.set_cookie("language", selected_language, httponly=False, samesite="lax")
    response.set_cookie("ui_language", ui_lang, httponly=False, samesite="lax")
    if selected_verb_id:
        response.set_cookie("verb_id", selected_verb_id, httponly=False, samesite="lax")
    return response
