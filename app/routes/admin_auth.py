from __future__ import annotations

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from core.admin_auth import (
    ADMIN_SESSION_COOKIE,
    ADMIN_SESSION_MAX_AGE_SECONDS,
    create_admin_session_token,
    verify_admin_password,
    verify_admin_session_token,
)
from core.settings import load_settings

logger = logging.getLogger(__name__)

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
async def admin_login(password: str = Form(...)) -> HTMLResponse:
    if not verify_admin_password(password):
        return RedirectResponse(url=f"{ADMIN_PREFIX}/login?error=1", status_code=303)

    token = create_admin_session_token()
    print("[admin] login success, setting cookie", flush=True)
    # Firebase Hosting strips cookies whose names contain "session" from proxied requests.
    # Cookie is named vb_admin_tok (no "session") to avoid this.
    response = HTMLResponse(
        content=(
            "<!doctype html><html><head></head><body><script>"
            f"window.location.replace('{ADMIN_PREFIX}/login-callback');"
            "</script></body></html>"
        ),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        status_code=200,
    )
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        path="/",
    )
    return response


@router.get("/login-callback")
async def admin_login_callback(request: Request) -> HTMLResponse:
    print(f"[admin] ADMIN_SESSION_COOKIE={ADMIN_SESSION_COOKIE!r}", flush=True)
    print(
        f"[admin] login-callback cookie_header={request.headers.get('cookie')!r}",
        flush=True,
    )
    print(
        f"[admin] login-callback parsed_cookies={dict(request.cookies)!r}", flush=True
    )
    token = request.cookies.get(ADMIN_SESSION_COOKIE, "")
    print(f"[admin] login-callback token_present={bool(token)}", flush=True)
    return HTMLResponse(
        content=(
            "<!doctype html><html><head></head><body><script>"
            f"window.location.replace('{ADMIN_PREFIX}');"
            "</script></body></html>"
        ),
        headers={"Cache-Control": "no-store"},
        status_code=200,
    )


@router.get("/check-auth")
async def admin_check_auth(request: Request) -> Response:
    token = request.cookies.get(ADMIN_SESSION_COOKIE, "")
    print(f"[admin] cookie_header={request.headers.get('cookie')!r}", flush=True)
    print(f"[admin] cookies={dict(request.cookies)!r}", flush=True)
    if token and verify_admin_session_token(token):
        return Response(status_code=204)
    return Response(status_code=401)


@router.post("/logout")
async def admin_logout() -> HTMLResponse:
    response = HTMLResponse(
        content=(
            "<!doctype html><html><head></head><body><script>"
            f"window.location.replace('{ADMIN_PREFIX}/login');"
            "</script></body></html>"
        ),
        headers={"Cache-Control": "no-store"},
        status_code=200,
    )
    response.delete_cookie(
        key=ADMIN_SESSION_COOKIE, path="/", secure=True, samesite="lax"
    )
    return response
