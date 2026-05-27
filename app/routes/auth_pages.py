from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from core.settings import load_settings

router = APIRouter()


@router.get("/auth/signin", response_class=HTMLResponse, include_in_schema=False)
def auth_signin_page() -> str:
    settings = load_settings()
    firebase_cfg = settings.firebase_web_config_json or "null"
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
    .msg small {{ color: #6b7280; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <div class="msg">
    <p id="status">Signing in&hellip;</p>
    <small id="hint"></small>
  </div>
  <script>window.FIREBASE_WEB_CONFIG = {firebase_cfg};</script>
  <script src="https://www.gstatic.com/firebasejs/11.9.1/firebase-app-compat.js"></script>
  <script src="https://www.gstatic.com/firebasejs/11.9.1/firebase-auth-compat.js"></script>
  <script>
    const cfg = window.FIREBASE_WEB_CONFIG;
    const status = document.getElementById('status');
    const hint = document.getElementById('hint');
    if (!cfg || !cfg.apiKey) {{
      status.textContent = 'Auth not configured.';
    }} else {{
      firebase.initializeApp(cfg);
      const provider = new firebase.auth.GoogleAuthProvider();
      provider.setCustomParameters({{ prompt: 'select_account' }});
      firebase.auth().signInWithPopup(provider)
        .then(() => {{
          status.textContent = 'Signed in!';
          hint.textContent = 'You can close this tab and return to VerbBoard.';
          window.close();
        }})
        .catch(err => {{
          status.textContent = 'Sign-in failed.';
          hint.textContent = err.message || String(err);
        }});
    }}
  </script>
</body>
</html>"""
