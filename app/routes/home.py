from __future__ import annotations
from fastapi.responses import HTMLResponse, RedirectResponse

from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from core.lexicon import load_lexicon
from core.registry import all_plugins

router = APIRouter()

@router.get("/set_language", response_model=None)
def set_language(language: str, voice: str = "female"):
    lex_path = Path("data") / language / "lexicon.json"
    entries = load_lexicon(lex_path) if lex_path.exists() else []
    default_verb_id = entries[0].id if entries else ""
    return RedirectResponse(url=f"/?language={language}&voice={voice}&verb_id={default_verb_id}")

@router.get("/", response_class=HTMLResponse)
def home(
    language: str = Query("he"),
    voice: str = Query("female"),
    verb_id: str | None = Query(None),
) -> str:
    plugins = all_plugins()
    if language not in plugins:
        language = "he"

    lex_path = Path("data") / language / "lexicon.json"
    entries = load_lexicon(lex_path)

    if verb_id is None and entries:
        verb_id = entries[0].id

    lang_options = "\n".join(
        f"<option value='{k}' {'selected' if k == language else ''}>{p.display_name}</option>"
        for k, p in plugins.items()
    )
    verb_options = "\n".join(
        f"<option value='{e.id}' {'selected' if e.id == verb_id else ''}>{e.rank}. {e.lemma if not isinstance(e.lemma, dict) else (e.lemma.get('imperfective','') + ' / ' + e.lemma.get('perfective',''))}</option>"
        for e in entries
    )
    voice_options = "\n".join(
        f"<option value='{k}' {'selected' if k == voice else ''}>{k.title()}</option>"
        for k in ("female", "male")
    )

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Verb Board (MVP0)</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; max-width: 820px; }}
    select, button {{ font-size: 16px; padding: 10px; width:100%; }}
    .row {{ margin: 12px 0; }}
  </style>
</head>
<body>
  <h1>Verb Board (MVP0)</h1>

  <form action="/learn" method="get">
  <div class="row">
    <label><b>Language</b></label><br/>
    <select name="language"
          onchange="window.location='/set_language?language=' + this.value + '&voice=' + document.querySelector('select[name=voice]').value;">
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

    <div class="row">
      <button type="submit">Learn</button>
    </div>
  </form>
</body>
</html>
"""
