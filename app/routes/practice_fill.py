from __future__ import annotations

import asyncio
from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.admin_auth import get_session_uid
from core.fill_practice_service import (
    ACCESS_NOT_FOUND,
    ACCESS_OK,
    ACCESS_PLUS_FEATURE,
    build_fill_page_data,
    check_fill_access,
    page_data_to_json,
)
from core.i18n import get_strings, resolve_ui_language
from core.settings import load_settings

templates = Jinja2Templates(directory="app/templates")

router = APIRouter()


@router.get("/practice/fill", response_class=HTMLResponse)
async def practice_fill(
    request: Request,
    language: str = Query(...),
    verb_id: str | None = Query(None, max_length=80),
):
    settings = load_settings()
    ui_lang = resolve_ui_language(request)
    quoted_language = quote(language, safe="")
    quoted_ui = quote(ui_lang, safe="")

    access = await asyncio.to_thread(check_fill_access, language, get_session_uid(request), settings)
    if access == ACCESS_NOT_FOUND:
        return HTMLResponse("Not found", status_code=404)
    if access == ACCESS_PLUS_FEATURE:
        return RedirectResponse(
            url=f"/feedback?page=plus&language={quoted_language}&ui_language={quoted_ui}", status_code=303
        )
    if access != ACCESS_OK:
        # Plus-only study language without entitlement: same notice redirect as /learn.
        return RedirectResponse(
            url=f"/verbs?language={quoted_language}&plus_required=1&ui_language={quoted_ui}", status_code=303
        )

    page_data = await asyncio.to_thread(build_fill_page_data, language, ui_lang, verb_id or None)
    if verb_id:
        back_href = f"/learn?language={quoted_language}&verb_id={quote(verb_id, safe='')}&ui_language={quoted_ui}"
    else:
        back_href = f"/verbs?language={quoted_language}&ui_language={quoted_ui}"

    return templates.TemplateResponse(
        request,
        "practice_fill.html",
        context={
            "request": request,
            "ui": get_strings(ui_lang),
            "ui_lang": ui_lang,
            "ui_language": ui_lang,
            "language": language,
            "verb_id": verb_id or "",
            "html_dir": "rtl" if ui_lang == "he" else "ltr",
            "study_dir": page_data["studyDir"],
            "back_href": back_href,
            "empty": not page_data["items"],
            "page_data_json": page_data_to_json(page_data),
            "firebase_web_config_json": settings.firebase_web_config_json,
        },
    )
