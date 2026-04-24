from __future__ import annotations

import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from core.registry import all_plugins
from core.verb_loader import load_entries_for_language

router = APIRouter()


@router.get("/verbs", response_class=HTMLResponse)
def verb_browser(
    request: Request,
    language: str | None = Query(None),
) -> HTMLResponse:
    settings = request.app.state.settings
    cookie_language = request.cookies.get("language")
    plugins = all_plugins()

    selected_language = language or cookie_language or "he"
    if selected_language not in plugins:
        selected_language = "he"

    entries = load_entries_for_language(
        language=selected_language,
        source=settings.verb_data_source,
    )
    entries_sorted = sorted(entries, key=lambda entry: entry.rank or 999999)

    verbs_js = []
    for entry in entries_sorted:
        lemma = entry.display_lemma or entry.lemma
        if isinstance(lemma, dict):
            lemma = lemma.get("imperfective") or lemma.get("perfective") or ""

        verbs_js.append(
            {
                "id": entry.id,
                "lemma": str(lemma),
                "rank": entry.rank or 999999,
            }
        )

    verbs_json = json.dumps(verbs_js, ensure_ascii=False)
    lang_json = json.dumps(selected_language)

    lang_options = "\n".join(
        f'<option value="{key}" {"selected" if key == selected_language else ""}>'
        f"{plugin.display_name}</option>"
        for key, plugin in plugins.items()
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>VerbBoard — Browse verbs</title>
  <link rel="stylesheet" href="/static/common.css"/>
  <link rel="stylesheet" href="/static/verbs.css"/>
</head>
<body>
  <div class="vb-page">

    <div class="vb-header">
      <a href="/?language={selected_language}" class="vb-back">⟵ Home</a>
      <h1 class="vb-title">Browse verbs</h1>
      <select class="vb-lang-select"
        onchange="window.location='/verbs?language='+this.value">
        {lang_options}
      </select>
    </div>

    <div class="vb-toolbar">
      <input id="vb-search" class="vb-search" type="text"
             placeholder="Search…" autocomplete="off"/>
      <div class="vb-filter-toggle" id="vb-filter-toggle">
        <button class="vb-ftbtn active" data-filter="unknown">Unknown</button>
        <button class="vb-ftbtn" data-filter="all">All</button>
        <button class="vb-ftbtn" data-filter="known">Known</button>
      </div>
    </div>

    <div class="vb-toolbar vb-toolbar-meta">
      <select id="vb-sort" class="vb-sort-select">
        <option value="rank">By frequency</option>
        <option value="alpha">A → Z</option>
      </select>
      <div id="vb-count" class="vb-count"></div>
    </div>

    <div id="vb-list" class="vb-list"></div>

  </div>

  <script>
    window.VB_LANGUAGE = {lang_json};
    window.VB_VERBS = {verbs_json};
  </script>
  <script src="/static/verbs.js"></script>
</body>
</html>"""

    response = HTMLResponse(html)
    response.set_cookie("language", selected_language, httponly=False, samesite="lax")
    return response
