from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from core.analytics.client_context import detect_device_type
from core.feedback_store import save_feedback
from core.i18n import get_strings, resolve_ui_language
from core.polls import (
    ACTIVE_POLL_ID,
    get_poll_options,
    get_poll_question,
    get_poll_valid_answers,
)
from core.safe_return import safe_return_to
from core.settings import load_settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/feedback")
def feedback_form(
    request: Request,
    page: str = "",
    language: str = "",
    verb_id: str = "",
    return_to: str = "/",
    success: str = "",
    error: str = "",
):
    return_to = safe_return_to(return_to, fallback="/")
    ui_lang = resolve_ui_language(request)
    ui = get_strings(ui_lang)
    settings = load_settings()

    return templates.TemplateResponse(
        request,
        "feedback.html",
        {
            "lang": ui_lang,
            "html_dir": "rtl" if ui_lang == "he" else "ltr",
            "firebase_web_config_json": settings.firebase_web_config_json,
            "title": ui["feedback.title"],
            "heading": ui["feedback.heading"],
            "back_label": ui["feedback.back"],
            "comment_placeholder": ui["feedback.comment_placeholder"],
            "submit_label": ui["feedback.submit_button"],
            "auth_login": ui.get("auth.login", "Login"),
            "auth_logout": ui.get("auth.logout", "Logout"),
            "page": page,
            "language": language,
            "verb_id": verb_id,
            "return_to": return_to,
            "success": success == "1",
            "success_msg": ui["feedback.success"],
            "error_empty": error == "empty",
            "error_empty_msg": ui["feedback.error_empty"],
            "poll_question": get_poll_question(ACTIVE_POLL_ID, ui_lang)
            if ACTIVE_POLL_ID
            else "",
            "poll_options": get_poll_options(ACTIVE_POLL_ID, ui_lang)
            if ACTIVE_POLL_ID
            else [],
        },
    )


@router.post("/feedback", response_model=None)
def submit_feedback(
    request: Request,
    comment: str = Form(""),
    poll_answer: str = Form(""),
    page: str = Form(""),
    language: str = Form(""),
    verb_id: str = Form(""),
    return_to: str = Form("/"),
    ui_language: str = Form(""),
):
    return_to = safe_return_to(return_to, fallback="/")
    clean_comment = comment.strip()

    if poll_answer not in get_poll_valid_answers(ACTIVE_POLL_ID or ""):
        poll_answer = ""

    poll_id = ACTIVE_POLL_ID if poll_answer else None
    poll_question = get_poll_question(poll_id, ui_language or "en") if poll_id else None

    try:
        user_agent = request.headers.get("user-agent", "")
        device_type = detect_device_type(user_agent)
        save_feedback(
            comment=clean_comment,
            poll_id=poll_id,
            poll_question=poll_question,
            poll_answer=poll_answer,
            page=page or "unknown",
            language=language or None,
            verb_id=verb_id or None,
            path=str(request.url.path),
            user_agent=user_agent,
            device_type=device_type,
            source="preview",
        )
    except ValueError:
        params = urlencode(
            {
                "page": page,
                "language": language,
                "verb_id": verb_id,
                "return_to": return_to,
                "error": "empty",
                "ui_language": ui_language,
            }
        )
        return RedirectResponse(url=f"/feedback?{params}", status_code=303)

    return RedirectResponse(url=return_to, status_code=303)
