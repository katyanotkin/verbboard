from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from core.i18n import get_strings, resolve_ui_language
from core.registry import all_plugins
from core.settings import load_settings
from core.storage.firestore_db import get_db
from core.storage.verb_repository import list_verbs_recent
from core.verb_loader import load_entries_for_language

log = logging.getLogger(__name__)

RECENT_VERBS_LIMIT = 8

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
    generating: int | None = Query(None),
    garbage: int | None = Query(None),
) -> HTMLResponse:
    settings = load_settings()

    plugins = all_plugins()

    selected_language = language or "he"

    if selected_language not in plugins:
        selected_language = "he"

    ui_lang = resolve_ui_language(request)
    ui = get_strings(ui_lang)

    html_dir = "rtl" if ui_lang == "he" else "ltr"

    sort_az_label = get_strings(selected_language).get(
        "verbs.sort_az",
        "A → Z",
    )

    all_entries = load_entries_for_language(language=selected_language)
    total_verb_count = len(all_entries)

    if settings.verbs_page_limit > 0:
        entries = sorted(all_entries, key=lambda e: e.rank)[: settings.verbs_page_limit]
    else:
        entries = all_entries

    verbs_js = [_build_verb_item(e) for e in entries]

    recent_docs = list_verbs_recent(language=selected_language, limit=RECENT_VERBS_LIMIT)
    known_ids = {v["id"] for v in verbs_js}
    recent_ids = [d["verb_id"] for d in recent_docs if d.get("verb_id") in known_ids]

    ui_strings: dict[str, str] = {
        "verbs.count_one": ui["verbs.count_one"],
        "verbs.count_other": ui["verbs.count_other"],
        "verbs.empty_state": ui["verbs.empty_state"],
        "verbs.filter_recent": ui["verbs.filter_recent"],
        "verbs.load_more": ui["verbs.load_more"],
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
    generating_verb = notice_text if (notice_text and generating == 1) else None
    garbage_query = notice_text if (notice_text and garbage == 1 and not generating_verb) else None

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
            "generating_verb": generating_verb,
            "garbage_query": garbage_query,
            "search_mode": search_mode or "native",
            "practice_loop_enabled": PRACTICE_LOOP_ENABLED,
            "badge_compact_threshold": settings.badge_compact_threshold,
            "total_verb_count": total_verb_count,
            "verbs_display_batch": settings.verbs_display_batch,
            "firebase_web_config_json": (settings.firebase_web_config_json),
            "verbs_return_to": quote(f"/verbs?language={selected_language}&ui_language={ui_lang}", safe="/"),
        },
    )

    return response


def _build_verb_item(entry: object) -> dict[str, object]:
    lemma = getattr(entry, "display_lemma", None) or getattr(entry, "lemma", "")
    if isinstance(lemma, dict):
        lemma = lemma.get("imperfective") or lemma.get("perfective") or ""
    morph = getattr(entry, "morph", None) or {}
    item: dict[str, object] = {
        "id": entry.id,  # type: ignore[attr-defined]
        "lemma": str(lemma),
        "created_at": entry.created_at,  # type: ignore[attr-defined]
    }
    if morph.get("root"):
        item["root"] = str(morph["root"])
    return item


@router.get("/api/verbs", response_class=JSONResponse)
def api_verbs(
    language: str = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> JSONResponse:
    all_entries = load_entries_for_language(language=language)
    total = len(all_entries)
    sorted_entries = sorted(all_entries, key=lambda e: e.rank)
    page = sorted_entries[offset : offset + limit]
    verbs = [_build_verb_item(e) for e in page]

    try:
        get_db().collection("verb_paging_events").add(
            {
                "language": language,
                "offset": offset,
                "limit": limit,
                "timestamp": datetime.now(timezone.utc),
            }
        )
    except Exception:
        log.warning("verb_paging_events write failed", exc_info=True)

    return JSONResponse(
        {
            "verbs": verbs,
            "total": total,
            "has_more": offset + limit < total,
        }
    )
