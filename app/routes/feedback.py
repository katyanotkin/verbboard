from __future__ import annotations

import json
from html import escape
from urllib.parse import unquote, urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from core.analytics.client_context import detect_device_type
from core.feedback_store import save_feedback
from core.i18n import get_strings, resolve_ui_language
from core.polls import (
    ACTIVE_POLL_ID,
    get_poll_options,
    get_poll_question,
    get_poll_valid_answers,
)
from core.settings import load_settings

router = APIRouter()


def _safe_return_to(return_to: str) -> str:
    decoded = unquote(return_to or "/")
    if not decoded.startswith("/"):
        return "/"
    if decoded.startswith("//"):
        return "/"
    return decoded


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
    return_to = _safe_return_to(return_to)

    ui_lang = resolve_ui_language(request)
    ui = get_strings(ui_lang)
    html_dir = "rtl" if ui_lang == "he" else "ltr"
    settings = load_settings()
    firebase_cfg = settings.firebase_web_config_json or "null"

    poll_question = get_poll_question(ACTIVE_POLL_ID, ui_lang) if ACTIVE_POLL_ID else ""
    poll_options = get_poll_options(ACTIVE_POLL_ID, ui_lang) if ACTIVE_POLL_ID else []

    success_html = ""
    if success == "1":
        success_html = f"""
        <div style="margin-bottom:16px;padding:12px 14px;background:#ecfdf5;border:1px solid #86efac;border-radius:12px;color:#166534;">
          {escape(ui["feedback.success"])}
        </div>
        """

    error_html = ""
    if error == "empty":
        error_html = f"""
        <div style="margin-bottom:16px;padding:12px 14px;background:#fef2f2;border:1px solid #fca5a5;border-radius:12px;color:#991b1b;">
          {escape(ui["feedback.error_empty"])}
        </div>
        """

    poll_block = ""
    if poll_question and poll_options:
        options_html = "".join(
            f"""
            <label class="choice-label">
              <input type="radio" name="poll_answer" value="{escape(value)}"> {escape(label)}
            </label>"""
            for value, label in poll_options
        )
        poll_block = f"""
        <div class="question-block">
          <div class="question-title">{escape(poll_question)}</div>
          <div class="choice-row">{options_html}
          </div>
        </div>
        """

    bnav_lang = escape(language)
    return f"""<!doctype html>
<html lang="{ui_lang}" dir="{html_dir}">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta name="theme-color" content="#2d6a4f"/>
  <meta name="mobile-web-app-capable" content="yes"/>
  <link rel="manifest" href="/static/manifest.json"/>
  <title>{escape(ui["feedback.title"])}</title>
  <link rel="stylesheet" href="/static/common.css"/>
  <script>window.UI ={json.dumps({"auth.login": ui.get("auth.login", "Login"), "auth.logout": ui.get("auth.logout", "Logout")})};</script>
  <script>window.FIREBASE_WEB_CONFIG = {firebase_cfg};</script>
  <script src="https://www.gstatic.com/firebasejs/11.9.1/firebase-app-compat.js"></script>
  <script src="https://www.gstatic.com/firebasejs/11.9.1/firebase-auth-compat.js"></script>
  <script defer src="/static/auth.js"></script>
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

    .card-nav {{
      margin-bottom: 16px;
    }}

    .card-nav h1 {{
      margin: 0;
      font-size: 22px;
    }}

    .actions {{
      margin-top: 16px;
      display: flex;
      justify-content: center;
    }}

    @media (max-width: 639px) {{
      body {{
        margin-top: 12px;
        padding-bottom: calc(56px + env(safe-area-inset-bottom) + 16px);
      }}
    }}

  </style>
</head>
<body>
  <div class="card">
    <div class="topbar-nav card-nav">
      <h1>{escape(ui["feedback.heading"])}</h1>
      <div class="topbar-nav-right">
        <a href="{escape(return_to)}" class="feedback-link">{escape(ui["feedback.back"])}</a>
        <div id="auth-slot" style="display:contents"></div>
      </div>
    </div>

    {success_html}
    {error_html}

    <form method="post" action="/feedback">
      <input type="hidden" name="page" value="{escape(page)}">
      <input type="hidden" name="language" value="{escape(language)}">
      <input type="hidden" name="verb_id" value="{escape(verb_id)}">
      <input type="hidden" name="return_to" value="{escape(return_to)}">
      <input type="hidden" name="ui_language" value="{ui_lang}">

      {poll_block}

      <textarea name="comment" placeholder="{escape(ui["feedback.comment_placeholder"])}"></textarea>

      <div class="actions">
        <button type="submit" class="feedback-link">💬 {escape(ui["feedback.submit_button"])}</button>
      </div>
    </form>
  </div>
<nav class="bottom-nav" aria-label="Main navigation">
  <a href="/?language={bnav_lang}" class="bnav-tab" aria-current="false">
    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"
         fill="none" stroke="currentColor" stroke-width="2"
         stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
    <span>Search</span>
  </a>
  <a href="/verbs?language={bnav_lang}" class="bnav-tab" aria-current="false">
    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"
         fill="none" stroke="currentColor" stroke-width="2"
         stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <line x1="8" y1="6" x2="21" y2="6"/>
      <line x1="8" y1="12" x2="21" y2="12"/>
      <line x1="8" y1="18" x2="21" y2="18"/>
      <line x1="3" y1="6" x2="3.01" y2="6"/>
      <line x1="3" y1="12" x2="3.01" y2="12"/>
      <line x1="3" y1="18" x2="3.01" y2="18"/>
    </svg>
    <span>Browse</span>
  </a>
  <button class="bnav-tab" onclick="document.querySelector('#auth-slot button')?.click()" aria-label="Profile">
    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"
         fill="none" stroke="currentColor" stroke-width="2"
         stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
      <circle cx="12" cy="7" r="4"/>
    </svg>
    <span>Profile</span>
  </button>
</nav>
<script defer src="/static/pwa.js"></script>
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
    return_to = _safe_return_to(return_to)
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
