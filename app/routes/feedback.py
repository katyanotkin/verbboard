from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from core.feedback_store import save_feedback
from core.i18n import get_strings, resolve_ui_language
from core.polls import ACTIVE_POLL_ID, get_poll_question
from core.analytics.client_context import detect_device_type

router = APIRouter()


@router.get("/feedback", response_class=HTMLResponse)
def feedback_form(
    request: Request,
    page: str = "",
    language: str = "",
    verb_id: str = "",
    return_to: str = "/",
    success: str = "",
    error: str = "",
) -> str:
    ui_lang = resolve_ui_language(request)
    ui = get_strings(ui_lang)
    html_dir = "rtl" if ui_lang == "he" else "ltr"

    poll_question = get_poll_question(ACTIVE_POLL_ID, ui_lang) if ACTIVE_POLL_ID else ""

    success_html = ""
    if success == "1":
        success_html = f"""
        <div style="margin-bottom:16px;padding:12px 14px;background:#ecfdf5;border:1px solid #86efac;border-radius:12px;color:#166534;">
          {escape(ui['feedback.success'])}
        </div>
        """

    error_html = ""
    if error == "empty":
        error_html = f"""
        <div style="margin-bottom:16px;padding:12px 14px;background:#fef2f2;border:1px solid #fca5a5;border-radius:12px;color:#991b1b;">
          {escape(ui['feedback.error_empty'])}
        </div>
        """

    poll_block = ""
    if poll_question:
        poll_block = f"""
        <div class="question-block">
          <div class="question-title">{escape(poll_question)}</div>
          <div class="choice-row">
            <label class="choice-label">
              <input type="radio" name="poll_answer" value="yes"> {escape(ui['feedback.poll_yes'])}
            </label>
            <label class="choice-label">
              <input type="radio" name="poll_answer" value="no"> {escape(ui['feedback.poll_no'])}
            </label>
            <label class="choice-label">
              <input type="radio" name="poll_answer" value="no_preference"> {escape(ui['feedback.poll_no_pref'])}
            </label>
          </div>
        </div>
        """

    return f"""<!doctype html>
<html lang="{ui_lang}" dir="{html_dir}">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{escape(ui['feedback.title'])}</title>
  <style>
    body {{
      font-family: system-ui, sans-serif;
      margin: 24px auto;
      max-width: 720px;
      padding: 0 16px;
      background: #f8fafc;
      color: #1f2937;
    }}

    .card {{
      background: white;
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 20px;
      box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
    }}

    textarea {{
      width: 100%;
      min-height: 150px;
      padding: 12px;
      border: 1px solid #d1d5db;
      border-radius: 12px;
      box-sizing: border-box;
      font: inherit;
      resize: vertical;
    }}

    .question-block {{
      margin: 16px 0;
      padding: 14px;
      border: 1px solid #e5e7eb;
      border-radius: 14px;
      background: #f8fafc;
    }}

    .choice-row {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}

    .choice-label {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 12px;
      border: 1px solid #d1d5db;
      border-radius: 999px;
      background: white;
      cursor: pointer;
      font-weight: 600;
      color: #374151;
    }}

    .actions {{
      margin-top: 16px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}

    .primary-btn {{
      border: none;
      background: #2563eb;
      color: white;
      cursor: pointer;
      padding: 10px 16px;
      border-radius: 999px;
      font-weight: 700;
    }}

    .secondary-link {{
      border: 1px solid #d1d5db;
      padding: 10px 16px;
      border-radius: 999px;
      text-decoration: none;
      color: #374151;
    }}

  </style>
</head>
<body>
  <div class="card">
    <h1>{escape(ui['feedback.heading'])}</h1>

    {success_html}
    {error_html}

    <form method="post" action="/feedback">
      <input type="hidden" name="page" value="{escape(page)}">
      <input type="hidden" name="language" value="{escape(language)}">
      <input type="hidden" name="verb_id" value="{escape(verb_id)}">
      <input type="hidden" name="return_to" value="{escape(return_to)}">
      <input type="hidden" name="ui_language" value="{ui_lang}">

      {poll_block}

      <textarea name="comment" placeholder="{escape(ui['feedback.comment_placeholder'])}"></textarea>

      <div class="actions">
        <button type="submit" class="primary-btn">{escape(ui['feedback.submit_button'])}</button>
        <a href="{escape(return_to)}" class="secondary-link">{escape(ui['feedback.back'])}</a>
      </div>
    </form>
  </div>
</body>
</html>
"""


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
    clean_comment = comment.strip()

    if poll_answer not in {"yes", "no", "no_preference"}:
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

    return RedirectResponse(url=return_to or "/", status_code=303)
