from __future__ import annotations

import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from core.i18n import get_strings, resolve_ui_language
from core.registry import all_plugins
from core.verb_loader import load_entries_for_language

RECENT_VERBS_LIMIT = 8
MAX_SYNTHETIC_RANK = 999999

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

    ui_lang = resolve_ui_language(request)
    ui = get_strings(ui_lang)
    html_dir = "rtl" if ui_lang == "he" else "ltr"

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

    # Last 8 entries with a real rank = most recently added (proxy: highest rank number)
    recent_ids: list[str] = []

    for verb_row in reversed(verbs_js):
        rank = verb_row.get("rank")
        verb_id = verb_row.get("id")

        if not isinstance(rank, int):
            continue
        if not isinstance(verb_id, str):
            continue
        if rank >= MAX_SYNTHETIC_RANK:
            continue

        recent_ids.append(verb_id)

        if len(recent_ids) >= RECENT_VERBS_LIMIT:
            break

    recent_ids.reverse()

    verbs_json = json.dumps(verbs_js, ensure_ascii=False)
    recent_json = json.dumps(recent_ids, ensure_ascii=False)
    lang_json = json.dumps(selected_language)
    ui_json = json.dumps(
        {
            "verbs.count_one": ui["verbs.count_one"],
            "verbs.count_other": ui["verbs.count_other"],
            "verbs.empty_state": ui["verbs.empty_state"],
            "verbs.filter_recent": ui["verbs.filter_recent"],
        },
        ensure_ascii=False,
    )

    html = f"""<!doctype html>
    <html lang="{ui_lang}" dir="{html_dir}">
    <head>
      <meta charset="utf-8"/>
      <meta name="viewport" content="width=device-width, initial-scale=1"/>
      <title>{ui['verbs.title']}</title>
      <link rel="stylesheet" href="/static/common.css"/>
      <link rel="stylesheet" href="/static/verbs.css"/>
    </head>
    <body>
  <div class="vb-page">

    <div class="vb-header">
      <a href="/?language={selected_language}" class="vb-back">{ui['verbs.back_home']}</a>
      <h1 class="vb-title">{ui['verbs.heading']}</h1>
    </div>

    <div class="vb-feedback-row">
      <a
        href="/feedback?page=verbs&language={selected_language}&return_to=/verbs?language={selected_language}"
        class="feedback-link"
        title="{ui['verbs.feedback_title']}"
      >
        {ui['verbs.feedback_link']}
      </a>
    </div>

    <form action="/search_verb" method="get" class="vb-toolbar">
      <input type="hidden" name="language" value="{selected_language}" />

      <input
        id="vb-search"
        name="q"
        class="vb-search"
        type="text"
        placeholder="{ui['verbs.search_placeholder']}"
        autocomplete="off"
      />

      <button type="submit" class="vb-search-submit">
        {ui['verbs.find_button']}
      </button>

      <div class="vb-filter-toggle" id="vb-filter-toggle">
        <button type="button" class="vb-ftbtn active" data-filter="new">{ui['verbs.filter_new']}</button>
        <button type="button" class="vb-ftbtn" data-filter="seen">{ui['verbs.filter_seen']}</button>
        <button type="button" class="vb-ftbtn" data-filter="all">{ui['verbs.filter_all']}</button>
        <button type="button" class="vb-ftbtn" data-filter="known">{ui['verbs.filter_known']}</button>
      </div>
    </form>

    <div class="vb-toolbar vb-toolbar-meta">
      <select id="vb-sort" class="vb-sort-select">
        <option value="rank">{ui['verbs.sort_frequency']}</option>
        <option value="alpha">{ui['verbs.sort_az']}</option>
      </select>
      <div id="vb-count" class="vb-count"></div>
    </div>

    <div id="vb-list" class="vb-list"></div>

  </div>

  <script>
    window.VB_LANGUAGE = {lang_json};
    window.VB_VERBS = {verbs_json};
    window.VB_RECENT_IDS = {recent_json};
    window.UI = {ui_json};
  </script>
  <script src="/static/verbs.js"></script>
</body>
</html>"""

    response = HTMLResponse(html)
    response.set_cookie("language", selected_language, httponly=False, samesite="lax")
    response.set_cookie("ui_language", ui_lang, httponly=False, samesite="lax")
    return response
