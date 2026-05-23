from __future__ import annotations

import json
import os

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.i18n import get_strings, resolve_ui_language
from core.registry import all_plugins
from core.settings import load_settings
from core.verb_loader import load_entries_for_language

RECENT_VERBS_LIMIT = 8
MAX_SYNTHETIC_RANK = 999999

PRACTICE_LOOP_ENABLED = os.getenv(
    "PRACTICE_LOOP_ENABLED",
    "false",
).lower() in (
    "true",
    "1",
    "yes",
)

templates = Jinja2Templates(directory="app/templates")

router = APIRouter()


@router.get("/verbs", response_class=HTMLResponse)
def verb_browser(
    request: Request,
    language: str | None = Query(None),
    not_available: int | None = Query(None),
    search: str | None = Query(None),
    search_mode: str | None = Query(None),
) -> HTMLResponse:
    settings = load_settings()

    cookie_language = request.cookies.get("language")
    plugins = all_plugins()

    selected_language = language or cookie_language or "he"

    if selected_language not in plugins:
        selected_language = "he"

    ui_lang = resolve_ui_language(request)
    ui = get_strings(ui_lang)

    html_dir = "rtl" if ui_lang == "he" else "ltr"

    sort_az_label = get_strings(selected_language).get(
        "verbs.sort_az",
        "A → Z",
    )

    entries = load_entries_for_language(language=selected_language)

    verbs_js: list[dict[str, object]] = []

    for entry in entries:
        lemma = entry.display_lemma or entry.lemma

        if isinstance(lemma, dict):
            lemma = lemma.get("imperfective") or lemma.get("perfective") or ""

        verbs_js.append(
            {
                "id": entry.id,
                "lemma": str(lemma),
                "rank": entry.rank or MAX_SYNTHETIC_RANK,
            }
        )

    recent_ids: list[str] = []

    for verb_row in reversed(verbs_js):
        rank = verb_row.get("rank")
        verb_id = verb_row.get("id")

        if not isinstance(rank, int):
            continue

        if not isinstance(verb_id, str):
            continue

        if rank >= MAX_SYNTHETIC_RANK:
            continue

        recent_ids.append(verb_id)

        if len(recent_ids) >= RECENT_VERBS_LIMIT:
            break

    recent_ids.reverse()

    ui_strings: dict[str, str] = {
        "verbs.count_one": ui["verbs.count_one"],
        "verbs.count_other": ui["verbs.count_other"],
        "verbs.empty_state": ui["verbs.empty_state"],
        "verbs.filter_recent": ui["verbs.filter_recent"],
        # Auth button labels -- always included so auth.js can localize the
        # Login/Logout button regardless of whether the practice loop is on.
        "auth.login": ui["auth.login"],
        "auth.logout": ui["auth.logout"],
    }

    if "verbs.count_few" in ui:
        ui_strings["verbs.count_few"] = ui["verbs.count_few"]

    if PRACTICE_LOOP_ENABLED:
        ui_strings.update(
            {
                "practice.label": ui["practice.label"],
                "practice.start": ui["practice.start"],
                "practice.start_mixed": ui["practice.start_mixed"],
                "practice.in_progress": ui["practice.in_progress"],
                "practice.continue": ui["practice.continue"],
                "practice.abandon": ui["practice.abandon"],
                "practice.wrap_up": ui["practice.wrap_up"],
                "practice.learned_prompt": ui["practice.learned_prompt"],
                "practice.done": ui["practice.done"],
            }
        )

    raw_search = (search or "").strip()
    notice_text = raw_search if str(not_available) == "1" else None
    search_value = raw_search if str(not_available) == "1" else ""

    response = templates.TemplateResponse(
        request,
        "verbs.html",
        context={
            "request": request,
            "ui": ui,
            "ui_json": json.dumps(ui_strings, ensure_ascii=False),
            "ui_lang": ui_lang,
            "html_dir": html_dir,
            "selected_language": selected_language,
            "sort_az_label": sort_az_label,
            "verbs_json": json.dumps(verbs_js, ensure_ascii=False),
            "recent_json": json.dumps(recent_ids, ensure_ascii=False),
            "lang_json": json.dumps(selected_language),
            "notice_text": notice_text,
            "search_value": search_value,
            "search_mode": search_mode or "native",
            "practice_loop_enabled": PRACTICE_LOOP_ENABLED,
            "badge_compact_threshold": settings.badge_compact_threshold,
            "firebase_web_config_json": (settings.firebase_web_config_json),
        },
    )

    response.set_cookie(
        "language",
        selected_language,
        httponly=False,
        samesite="lax",
    )

    response.set_cookie(
        "ui_language",
        ui_lang,
        httponly=False,
        samesite="lax",
    )

    return response
