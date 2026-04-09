from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from core.feedback_store import save_feedback

router = APIRouter()


@router.get("/feedback", response_class=HTMLResponse)
def feedback_form(
    request: Request,
    page: str = "",
    language: str = "",
    verb_id: str = "",
    return_to: str = "/",
    success: str = "",
) -> str:
    success_html = ""
    if success == "1":
        success_html = """
        <div style="margin-bottom:16px;padding:12px 14px;background:#ecfdf5;border:1px solid #86efac;border-radius:12px;color:#166534;">
          Thanks — feedback received.
        </div>
        """

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>VerbBoard feedback</title>
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

    h1 {{
      margin-top: 0;
      margin-bottom: 8px;
    }}

    p {{
      color: #4b5563;
      margin-top: 0;
    }}

    textarea {{
      width: 100%;
      min-height: 180px;
      padding: 12px;
      border: 1px solid #d1d5db;
      border-radius: 12px;
      box-sizing: border-box;
      font: inherit;
      resize: vertical;
    }}

    .actions {{
      margin-top: 16px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}

    .primary-btn,
    .secondary-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 10px 16px;
      border-radius: 999px;
      text-decoration: none;
      font-weight: 700;
      transition: all 0.12s ease;
    }}

    .primary-btn {{
      border: none;
      background: #2563eb;
      color: white;
      cursor: pointer;
    }}

    .primary-btn:hover {{
      transform: translateY(-1px);
      filter: brightness(1.05);
    }}

    .secondary-link {{
      border: 1px solid #d1d5db;
      background: white;
      color: #374151;
    }}

    .secondary-link:hover {{
      background: #f8fafc;
    }}

    .meta {{
      margin-top: 12px;
      font-size: 12px;
      color: #6b7280;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Feedback</h1>
    <p>What felt confusing, wrong, or missing? Any other comment is welcome.</p>

    {success_html}

    <form method="post" action="/feedback">
      <input type="hidden" name="page" value="{page}">
      <input type="hidden" name="language" value="{language}">
      <input type="hidden" name="verb_id" value="{verb_id}">
      <input type="hidden" name="return_to" value="{return_to}">

      <textarea
        name="comment"
        placeholder="What felt confusing, wrong, or missing?"
        required
      ></textarea>

      <div class="actions">
        <button type="submit" class="primary-btn">Send feedback</button>
        <a href="{return_to}" class="secondary-link">Back</a>
      </div>

      <div class="meta">
        page={page or "-"} · language={language or "-"} · verb_id={verb_id or "-"}
      </div>
    </form>
  </div>
</body>
</html>
"""


@router.post("/feedback", response_model=None)
def submit_feedback(
    request: Request,
    comment: str = Form(...),
    page: str = Form(""),
    language: str = Form(""),
    verb_id: str = Form(""),
    return_to: str = Form("/"),
):
    save_feedback(
        comment=comment,
        page=page or "unknown",
        language=language or None,
        verb_id=verb_id or None,
        path=str(request.url.path),
        user_agent=request.headers.get("user-agent"),
    )

    return RedirectResponse(url=return_to or "/", status_code=303)
