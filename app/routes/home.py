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
    body {{
      font-family: system-ui, sans-serif;
      margin: 24px auto;
      max-width: 820px;
      padding: 0 16px;
      background: #f7f8fb;
      color: #1f2937;
    }}

    h1 {{
      margin-bottom: 20px;
    }}

    form.controls {{
      max-width: 360px;
      margin: 0 auto;
      padding: 24px;
      background: #fff;
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
      display: block;
      margin-bottom: 6px;
      font-weight: 700;
    }}

    select {{
      width: 100%;
      padding: 10px;
      border-radius: 8px;
      border: 1px solid #d1d5db;
    }}

    .learn-btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 12px 20px;
      border-radius: 999px;
      border: none;
      background: #2563eb;
      color: white;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.12s ease;
    }}

    .learn-btn:hover {{
      transform: translateY(-1px);
      filter: brightness(1.05);
    }}

    .learn-btn:disabled {{
      cursor: wait;
      pointer-events: none;
    }}

    .learn-btn.loading {{
      opacity: 0.7;
      filter: grayscale(0.4);
      transform: none;
    }}

    .learn-btn.loading .learn-label {{
      content: "Loading…";
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
      btn.querySelector('.learn-icon').textContent = '•••';
    "
  >

    <div class="row">
      <label>Language</label>
      <select
        name="language"
        onchange="window.location='/set_language?language=' + this.value + '&voice=' + document.querySelector('select[name=voice]').value;"
      >
        {lang_options}
      </select>
    </div>

    <div class="row">
      <label>Verb</label>
      <select name="verb_id">
        {verb_options}
      </select>
    </div>

    <div class="row">
      <label>Voice</label>
      <select name="voice">
        {voice_options}
      </select>
    </div>

    <div class="row center">
      <button type="submit" class="learn-btn">
        <span class="learn-label">Learn</span>
        <span class="learn-icon">▶</span>
      </button>
    </div>

  </form>
</body>
</html>
"""
