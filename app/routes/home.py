from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from core.lexicon import load_lexicon
from core.paths import DATA_DIR
from core.registry import all_plugins

router = APIRouter()


@router.get("/set_language", response_model=None)
def set_language(language: str, voice: str = "female"):
    lex_path = DATA_DIR / language / "lexicon.json"
    entries = load_lexicon(lex_path) if lex_path.exists() else []
    default_verb_id = entries[0].id if entries else ""
    return RedirectResponse(
        url=f"/?language={language}&voice={voice}&verb_id={default_verb_id}"
    )


@router.get("/", response_class=HTMLResponse)
def home(
    language: str = Query("he"),
    voice: str = Query("female"),
    verb_id: str | None = Query(None),
) -> str:
    plugins = all_plugins()
    if language not in plugins:
        language = "he"

    lex_path = DATA_DIR / language / "lexicon.json"
    entries = load_lexicon(lex_path)

    if verb_id is None and entries:
        verb_id = entries[0].id

    lang_options = "\n".join(
        f"<option value='{key}' {'selected' if key == language else ''}>{plugin.display_name}</option>"
        for key, plugin in plugins.items()
    )
    verb_options = "\n".join(
        f"<option value='{entry.id}' {'selected' if entry.id == verb_id else ''}>"
        f"{entry.rank}. "
        f"{entry.lemma if not isinstance(entry.lemma, dict) else (entry.lemma.get('imperfective', '') + ' / ' + entry.lemma.get('perfective', ''))}"
        f"</option>"
        for entry in entries
    )
    voice_options = "\n".join(
        f"<option value='{voice_key}' {'selected' if voice_key == voice else ''}>{voice_key.title()}</option>"
        for voice_key in ("female", "male")
    )

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Verb Board (MVP0)</title>
  <style>
    :root {{
      color-scheme: light;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      font-family: system-ui, sans-serif;
      margin: 24px auto;
      max-width: 820px;
      padding: 0 16px;
      background: #f7f8fb;
      color: #1f2937;
    }}

    h1 {{
      margin: 0 0 20px 0;
      font-size: 32px;
      line-height: 1.15;
    }}

    form.controls {{
      max-width: 360px;
      margin: 0 auto;
      padding: 24px;
      background: #ffffff;
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
    }}

    .row {{
      margin: 14px 0;
    }}

    .row.center {{
      text-align: center;
      margin-top: 20px;
    }}

    label {{
      display: inline-block;
      margin-bottom: 6px;
      font-size: 14px;
      font-weight: 700;
      color: #374151;
    }}

    select {{
      width: 100%;
      font-size: 16px;
      padding: 11px 12px;
      border: 1px solid #d1d5db;
      border-radius: 10px;
      background: #fff;
      color: #111827;
      outline: none;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }}

    select:focus {{
      border-color: #2563eb;
      box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
    }}

    .learn-btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      min-width: 170px;
      padding: 12px 20px;
      border: none;
      border-radius: 999px;
      background: linear-gradient(135deg, #2563eb, #1d4ed8);
      color: #ffffff;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.02em;
      cursor: pointer;
      box-shadow: 0 10px 22px rgba(37, 99, 235, 0.28);
      transition:
        transform 0.12s ease,
        box-shadow 0.12s ease,
        filter 0.12s ease;
    }}

    .learn-btn:hover {{
      transform: translateY(-1px);
      box-shadow: 0 14px 26px rgba(37, 99, 235, 0.34);
      filter: brightness(1.03);
    }}

    .learn-btn:active {{
      transform: translateY(0);
      box-shadow: 0 8px 16px rgba(37, 99, 235, 0.24);
    }}

    .learn-icon {{
      font-size: 16px;
      line-height: 1;
    }}

    .learn-btn:disabled {{
      cursor: wait;
      opacity: 0.85;
    }}

    .learn-btn.loading {{
      filter: saturate(0.9);
    }}
  </style>
</head>
<body>
  <h1>Verb Board (MVP0)</h1>

  <form
      action="/learn"
      method="get"
      class="controls"
      onsubmit="
        const btn = this.querySelector('.learn-btn');
        btn.disabled = true;
        btn.classList.add('loading');
        btn.querySelector('.learn-label').textContent = 'Loading…';
        btn.querySelector('.learn-icon').textContent = '⏳';
      "
    >
    <div class="row">
      <label><b>Language</b></label><br/>
      <select
        name="language"
        onchange="window.location='/set_language?language=' + this.value + '&voice=' + document.querySelector('select[name=voice]').value;"
      >
        {lang_options}
      </select>
    </div>

    <div class="row">
      <label><b>Verb</b></label><br/>
      <select name="verb_id">
        {verb_options}
      </select>
    </div>

    <div class="row">
      <label><b>Voice</b></label><br/>
      <select name="voice">
        {voice_options}
      </select>
    </div>

    <div class="row center">
      <button type="submit" class="learn-btn" title="Learn">
        <span class="learn-label">Learn</span>
        <span class="learn-icon">▶</span>
      </button>
    </div>
  </form>
</body>
</html>
"""
