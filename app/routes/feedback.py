from __future__ import annotations

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from core.analytics.client_context import detect_device_type
from core.feedback_spam import is_spam_submission
from core.feedback_store import save_feedback
from core.i18n import get_strings, resolve_ui_language
from core.plus_request_service import is_requestable_language
from core.polls import (
    ACTIVE_POLL_ID,
    get_poll_options,
    get_poll_question,
    get_poll_valid_answers,
)
from core.rate_limit import SlidingWindowRateLimiter, client_ip
from core.safe_return import safe_return_to
from core.settings import load_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Public unauthenticated write (issue #77): cap size and rate per client.
_MAX_COMMENT_LENGTH = 4000
_MAX_FIELD_LENGTH = 200
_FEEDBACK_RATE_LIMITER = SlidingWindowRateLimiter(max_calls=10, window_seconds=600)

# Pages whose feedback needs a reply address: policy questions.
_CONTACT_REQUIRED_PAGES = {"privacy", "terms"}
templates = Jinja2Templates(directory="app/templates")


def _feedback_redirect(*, page: str, language: str, verb_id: str, return_to: str, ui_language: str, **extra: str):
    params = {
        "page": page,
        "language": language,
        "verb_id": verb_id,
        "return_to": return_to,
        "ui_language": ui_language,
        **extra,
    }
    return RedirectResponse(url=f"/feedback?{urlencode(params)}", status_code=303)


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

    # Visitors arriving via the "Contact us" link on /privacy or /terms are
    # here specifically to reach the owner -- an unreachable submission
    # defeats the purpose, so the email is required on that path only.
    # General feedback (from every other page's 💬 link) stays anonymous-first.
    contact_email_required = page in _CONTACT_REQUIRED_PAGES
    plus_mode = page == "plus" and is_requestable_language(language)
    if page == "plus" and not plus_mode:
        page = ""
        contact_email_required = False
    language_label = ui.get(f"lang.{language}", language) if plus_mode else ""

    return templates.TemplateResponse(
        request,
        "feedback.html",
        {
            "lang": ui_lang,
            "html_dir": "rtl" if ui_lang == "he" else "ltr",
            "firebase_web_config_json": settings.firebase_web_config_json,
            "title": ui["feedback.title"],
            "heading": ui["plus.request_btn"] if plus_mode else ui["feedback.heading"],
            "back_label": ui["feedback.back"],
            "comment_placeholder": ui["feedback.comment_placeholder"],
            "contact_email_required": contact_email_required,
            "contact_email_label": ui.get(
                "feedback.contact_email_label_required" if contact_email_required else "feedback.contact_email_label",
                "Reply to:" if contact_email_required else "Reply to (optional):",
            ),
            "contact_email_placeholder": ui.get("feedback.contact_email_placeholder", "you@example.com"),
            "submit_label": ui["feedback.submit_button"],
            "auth_login": ui.get("auth.login", "Login"),
            "auth_logout": ui.get("auth.logout", "Logout"),
            "page": page,
            "language": language,
            "verb_id": verb_id,
            "return_to": return_to,
            "success": success == "1",
            "success_msg": ui["feedback.success"],
            "plus_mode": plus_mode,
            "rate_line": ui["feedback.rate_line"],
            "rate_label": ui["rate.link_label"],
            "plus_btn_label": ui["plus.request_btn"],
            "plus_account_tpl": ui["plus.req_account"],
            "plus_lang_label": ui["plus.req_lang"].format(language=language_label),
            "plus_strings": {
                "done": ui["plus.request_done"],
                "already": ui["plus.request_already"],
                "error": ui["plus.request_error"],
                "signin_prompt": ui["plus.signin_prompt"],
                "signin_btn": ui["plus.signin_btn"],
            },
            "error_empty": error == "empty",
            "error_empty_msg": ui["feedback.error_empty"],
            "error_email_required": error == "email_required",
            "error_email_required_msg": ui.get(
                "feedback.error_email_required", "Please provide an email so we can reply."
            ),
            "poll_question": get_poll_question(ACTIVE_POLL_ID, ui_lang) if ACTIVE_POLL_ID and not plus_mode else "",
            "poll_options": get_poll_options(ACTIVE_POLL_ID, ui_lang) if ACTIVE_POLL_ID and not plus_mode else [],
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
    contact_email: str = Form(""),
    hp_url: str = Form(""),
):
    return_to = safe_return_to(return_to, fallback="/")
    if is_spam_submission(honeypot=hp_url, contact_email=contact_email):
        # Pretend success so a bot gets no signal; nothing is saved.
        return _feedback_redirect(
            page=page, language=language, verb_id=verb_id, return_to=return_to, ui_language=ui_language, success="1"
        )
    if not _FEEDBACK_RATE_LIMITER.allow(client_ip(request)):
        return RedirectResponse(url=return_to, status_code=303)
    clean_comment = comment.strip()[:_MAX_COMMENT_LENGTH]
    clean_contact_email = contact_email.strip()[:_MAX_FIELD_LENGTH]
    page = page[:_MAX_FIELD_LENGTH]
    language = language[:_MAX_FIELD_LENGTH]
    verb_id = verb_id[:_MAX_FIELD_LENGTH]

    if page in _CONTACT_REQUIRED_PAGES and not clean_contact_email:
        params = urlencode(
            {
                "page": page,
                "language": language,
                "verb_id": verb_id,
                "return_to": return_to,
                "error": "email_required",
                "ui_language": ui_language,
            }
        )
        return RedirectResponse(url=f"/feedback?{params}", status_code=303)

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
            contact_email=clean_contact_email or None,
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

    return _feedback_redirect(
        page=page, language=language, verb_id=verb_id, return_to=return_to, ui_language=ui_language, success="1"
    )
