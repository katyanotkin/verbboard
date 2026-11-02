from __future__ import annotations

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from core.analytics.client_context import detect_device_type
from core.auth.firebase_auth import get_bearer_token, verify_firebase_token
from core.feedback_store import save_feedback
from core.i18n import get_strings, resolve_ui_language
from core.plus_request_service import (
    MAX_NOTE_LENGTH,
    create_plus_request,
    is_requestable_language,
    is_valid_email,
    request_doc_id,
)
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

# Pages whose feedback needs a reply address: policy questions and Plus access requests.
_CONTACT_REQUIRED_PAGES = {"privacy", "terms", "plus"}
templates = Jinja2Templates(directory="app/templates")


def _verified_user(request: Request, id_token: str):
    """AuthUser from the verified Firebase ID token (form field or Bearer header), else None."""
    token = id_token.strip() or get_bearer_token(request)
    if not token:
        return None
    try:
        return verify_firebase_token(token)
    except Exception:
        return None


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
            "heading": ui["plus.req_title"] if plus_mode else ui["feedback.heading"],
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
            "success": success in ("1", "dup"),
            "success_msg": (
                ui["plus.req_dup"] if success == "dup" else ui["plus.req_done"] if plus_mode else ui["feedback.success"]
            ),
            "plus_mode": plus_mode,
            "plus_title": ui["plus.req_title"],
            "plus_lang_label": ui["plus.req_lang"].format(language=language_label),
            "plus_account_tpl": ui["plus.req_account"],
            "plus_signin_label": ui["plus.req_signin"],
            "plus_note_label": ui["plus.req_note"],
            "plus_submit_label": ui["plus.req_submit"],
            "plus_max_note": MAX_NOTE_LENGTH,
            "plus_error_signin_msg": ui["plus.req_error_signin"],
            "plus_error_msg": {
                "email_invalid": ui["plus.req_error_email"],
                "signin": ui["plus.req_error_signin"],
                "note": ui["plus.req_error_note"],
                "language": ui["plus.req_error_language"],
                "failed": ui["plus.req_error_failed"],
            }.get(error, ""),
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
    id_token: str = Form(""),
    website: str = Form(""),
):
    return_to = safe_return_to(return_to, fallback="/")
    if not _FEEDBACK_RATE_LIMITER.allow(client_ip(request)):
        return RedirectResponse(url=return_to, status_code=303)
    if page == "plus":
        return _submit_plus_request(
            request,
            comment=comment,
            language=language,
            return_to=return_to,
            ui_language=ui_language,
            contact_email=contact_email,
            id_token=id_token,
            website=website,
        )
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


def _submit_plus_request(
    request: Request,
    *,
    comment: str,
    language: str,
    return_to: str,
    ui_language: str,
    contact_email: str,
    id_token: str,
    website: str,
):
    language = language[:_MAX_FIELD_LENGTH]
    if not is_requestable_language(language):
        return _feedback_redirect(
            page="", language="", verb_id="", return_to=return_to, ui_language=ui_language, error="language"
        )
    ui_language = ui_language[:_MAX_FIELD_LENGTH]
    redirect_args = {
        "page": "plus",
        "language": language,
        "verb_id": "",
        "return_to": return_to,
        "ui_language": ui_language,
    }

    clean_contact_email = contact_email.strip()
    if website:  # honeypot: look successful, store nothing
        return _feedback_redirect(success="1", **redirect_args)

    user = _verified_user(request, id_token)
    if user is None or not user.email:
        return _feedback_redirect(error="signin", **redirect_args)

    note = comment.strip()
    if len(note) > MAX_NOTE_LENGTH:
        return _feedback_redirect(error="note", **redirect_args)
    if not is_valid_email(clean_contact_email):
        return _feedback_redirect(error="email_invalid", **redirect_args)

    try:
        created = create_plus_request(
            uid=user.uid,
            email=user.email,
            contact_email=clean_contact_email,
            language=language,
            note=note,
            ui_language=ui_language,
        )
    except Exception:
        logger.warning("plus request write failed", exc_info=True)
        return _feedback_redirect(error="failed", **redirect_args)
    if not created:
        return _feedback_redirect(success="dup", **redirect_args)

    # Also write the normal feedback entry so the admin feedback list shows it.
    try:
        user_agent = request.headers.get("user-agent", "")
        save_feedback(
            comment=note or "(no note)",
            page="plus",
            language=language,
            path=str(request.url.path),
            user_agent=user_agent,
            device_type=detect_device_type(user_agent),
            source="plus_request",
            contact_email=clean_contact_email,
            request_id=request_doc_id(user.uid, language),
        )
    except Exception:
        logger.warning("plus request feedback entry failed", exc_info=True)
    return _feedback_redirect(success="1", **redirect_args)
