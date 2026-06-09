from __future__ import annotations

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from core.admin_auth import (
    ADMIN_SESSION_COOKIE,
    ADMIN_SESSION_MAX_AGE_SECONDS,
    create_admin_session_token,
    verify_admin_password,
)
from core.settings import load_settings

router = APIRouter()
settings = load_settings()
ADMIN_PREFIX = "/admin"


@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(error: str = "") -> str:
    error_html = ""
    if error == "1":
        error_html = """
        <div style="margin-bottom:16px;padding:12px 14px;background:#fcecea;border:1px solid #f5b7b1;border-radius:12px;color:#c0291a;">
          Invalid admin password.
        </div>
        """

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Admin login</title>
  <style>
    body {{
      font-family: system-ui, sans-serif;
      margin: 40px auto;
      max-width: 420px;
      padding: 0 16px;
      background: #f8fafc;
      color: #1f2937;
    }}

    .card {{
      background: white;
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 24px;
      box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
    }}

    h1 {{
      margin: 0 0 12px 0;
    }}

    p {{
      color: #4b5563;
      margin: 0 0 18px 0;
    }}

    input[type="password"] {{
      width: 100%;
      box-sizing: border-box;
      padding: 12px;
      border: 1px solid #d1d5db;
      border-radius: 12px;
      font: inherit;
      margin-bottom: 14px;
    }}

    button {{
      border: none;
      background: #2563eb;
      color: white;
      cursor: pointer;
      padding: 10px 16px;
      border-radius: 999px;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Admin login</h1>
    <p>Enter admin password.</p>
    {error_html}
    <form method="post" action="{ADMIN_PREFIX}/login">
      <input type="password" name="password" placeholder="Password" required autofocus />
      <button type="submit">Log in</button>
    </form>
  </div>
</body>
</html>
"""


@router.post("/login")
async def admin_login(password: str = Form(...)) -> RedirectResponse:
    if not verify_admin_password(password):
        return RedirectResponse(url=f"{ADMIN_PREFIX}/login?error=1", status_code=303)

    token = create_admin_session_token()
    response = RedirectResponse(url=ADMIN_PREFIX, status_code=303)
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.environment in {"stage", "prod"},
        max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        path="/",
    )
    return response


@router.post("/logout")
async def admin_logout() -> RedirectResponse:
    response = RedirectResponse(url=f"{ADMIN_PREFIX}/login", status_code=303)
    response.delete_cookie(key=ADMIN_SESSION_COOKIE, path="/")
    return response
