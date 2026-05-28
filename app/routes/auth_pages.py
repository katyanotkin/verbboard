from __future__ import annotations

import json
import re

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from core.settings import load_settings

router = APIRouter()

_SAFE_RETURN_RE = re.compile(r"^/[^/\\]")


def _safe_return_to(url: str) -> str:
    """Allow only relative paths starting with a single slash."""
    if url == "/":
        return "/"
    if url and _SAFE_RETURN_RE.match(url):
        return url
    return ""


@router.get("/auth/signin", response_class=HTMLResponse, include_in_schema=False)
def auth_signin_page(return_to: str = "") -> str:
    settings = load_settings()
    # Re-serialize through json.loads/dumps to guarantee well-formed JSON with no
    # </script> injection risk, even if the raw secret value is malformed.
    try:
        firebase_cfg = json.dumps(
            json.loads(settings.firebase_web_config_json or "null")
        )
    except (TypeError, ValueError):
        firebase_cfg = "null"

    safe_return = json.dumps(_safe_return_to(return_to))

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Sign in to VerbBoard</title>
  <style>
    body {{
      font-family: system-ui, sans-serif;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; margin: 0; background: #f8fafc; color: #374151;
    }}
    .msg {{ text-align: center; padding: 24px; }}
    .msg p {{ margin: 8px 0; font-size: 1rem; }}
    .msg small {{ display: block; color: #6b7280; font-size: 0.85rem; margin-top: 8px; }}
    #signin-btn {{
      margin-top: 16px; padding: 12px 24px; font-size: 1rem; font-weight: 600;
      background: #2d6a4f; color: white; border: none; border-radius: 999px;
      cursor: pointer;
    }}
    #signin-btn:disabled {{ opacity: 0.6; cursor: default; }}
  </style>
</head>
<body>
  <div class="msg">
    <p id="status">Tap the button to sign in to VerbBoard.</p>
    <button id="signin-btn" onclick="doSignIn()">Sign in with Google</button>
    <small id="hint"></small>
  </div>
  <script>window.FIREBASE_WEB_CONFIG = {firebase_cfg};</script>
  <script src="https://www.gstatic.com/firebasejs/11.9.1/firebase-app-compat.js"></script>
  <script src="https://www.gstatic.com/firebasejs/11.9.1/firebase-auth-compat.js"></script>
  <script>
    const cfg = window.FIREBASE_WEB_CONFIG;
    const returnTo = {safe_return};
    const status = document.getElementById('status');
    const hint = document.getElementById('hint');
    const btn = document.getElementById('signin-btn');
    if (!cfg || !cfg.apiKey) {{
      status.textContent = 'Auth not configured.';
      btn.hidden = true;
    }} else {{
      firebase.initializeApp(cfg);
    }}
    async function doSignIn() {{
      btn.disabled = true;
      status.textContent = 'Signing in…';
      try {{
        const provider = new firebase.auth.GoogleAuthProvider();
        provider.setCustomParameters({{ prompt: 'select_account' }});
        await firebase.auth().signInWithPopup(provider);
        status.textContent = 'Signed in!';
        if (returnTo) {{
          window.location.href = returnTo;
        }} else {{
          hint.textContent = 'You can close this tab and return to VerbBoard.';
          btn.hidden = true;
          window.close();
        }}
      }} catch (err) {{
        status.textContent = 'Sign-in failed.';
        hint.textContent = err.message || String(err);
        btn.disabled = false;
      }}
    }}
  </script>
</body>
</html>"""
