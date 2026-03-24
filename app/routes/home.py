from __future__ import annotations

from html import escape

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from core.admin_logging import log_missing_verb_search
from core.lexicon import load_lexicon
from core.paths import DATA_DIR
from core.registry import all_plugins

router = APIRouter()

LANGUAGE_HOME_LABELS = {
    "en": "English",
    "ru": "Russian / Русский",
    "he": "Hebrew / עברית",
    "es": "Spanish / Español",
}


def _load_entries(language: str):
    lex_path = DATA_DIR / language / "lexicon.json"
    return load_lexicon(lex_path) if lex_path.exists() else []


def _normalize_text(value: str) -> str:
    return value.strip().casefold()


def _entry_search_candidates(entry) -> list[str]:
    candidates: list[str] = [entry.id]

    lemma = entry.lemma
    if isinstance(lemma, dict):
        candidates.extend(str(value) for value in lemma.values() if value)
    elif lemma:
        candidates.append(str(lemma))

    display_lemma = getattr(entry, "display_lemma", None)
    if isinstance(display_lemma, dict):
        candidates.extend(str(value) for value in display_lemma.values() if value)
    elif display_lemma:
        candidates.append(str(display_lemma))

    return candidates


def _find_verb_id(entries, query: str) -> str | None:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return None

    for entry in entries:
        for candidate in _entry_search_candidates(entry):
            if _normalize_text(candidate) == normalized_query:
                return entry.id

    for entry in entries:
        for candidate in _entry_search_candidates(entry):
            if normalized_query in _normalize_text(candidate):
                return entry.id

    return None


@router.get("/set_language", response_model=None)
def set_language(language: str, voice: str = "female"):
    entries = _load_entries(language)
    default_verb_id = entries[0].id if entries else ""

    response = RedirectResponse(
        url=f"/?language={language}&voice={voice}&verb_id={default_verb_id}"
    )
    response.set_cookie("language", language, httponly=False, samesite="lax")
    response.set_cookie("voice", voice, httponly=False, samesite="lax")
    if default_verb_id:
        response.set_cookie("verb_id", default_verb_id, httponly=False, samesite="lax")
    return response


@router.get("/search_verb", response_model=None)
def search_verb(
    language: str,
    voice: str = "female",
    q: str = "",
):
    entries = _load_entries(language)
    matched_verb_id = _find_verb_id(entries, q)

    if matched_verb_id:
        response = RedirectResponse(
            url=f"/learn?language={language}&verb_id={matched_verb_id}&voice={voice}"
        )
        response.set_cookie("language", language, httponly=False, samesite="lax")
        response.set_cookie("voice", voice, httponly=False, samesite="lax")
        response.set_cookie("verb_id", matched_verb_id, httponly=False, samesite="lax")
        return response

    log_missing_verb_search(language=language, query=q)

    response = RedirectResponse(
        url=f"/?language={language}&voice={voice}&search={q}&not_available=1"
    )
    response.set_cookie("language", language, httponly=False, samesite="lax")
    response.set_cookie("voice", voice, httponly=False, samesite="lax")
    return response


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    language: str | None = Query(None),
    voice: str | None = Query(None),
    verb_id: str | None = Query(None),
    search: str | None = Query(None),
    not_available: int | None = Query(None),
) -> HTMLResponse:
    plugins = all_plugins()

    cookie_language = request.cookies.get("language")
    cookie_voice = request.cookies.get("voice")
    cookie_verb_id = request.cookies.get("verb_id")

    selected_language = language or cookie_language or "he"
    if selected_language not in plugins:
        selected_language = "he"

    selected_voice = voice or cookie_voice or "female"
    if selected_voice not in ("female", "male"):
        selected_voice = "female"

    entries = _load_entries(selected_language)

    selected_verb_id = verb_id or cookie_verb_id
    if entries:
        valid_verb_ids = {entry.id for entry in entries}
        if selected_verb_id not in valid_verb_ids:
            selected_verb_id = entries[0].id
    else:
        selected_verb_id = ""

    raw_search_value = search or ""
    search_value = "" if str(not_available) == "1" else raw_search_value

    lang_options = "\n".join(
        f"<option value='{key}' {'selected' if key == selected_language else ''}>"
        f"{LANGUAGE_HOME_LABELS.get(key, plugin.display_name)}"
        f"</option>"
        for key, plugin in plugins.items()
    )

    verb_options = "\n".join(
        f"<option value='{entry.id}' {'selected' if entry.id == selected_verb_id else ''}>"
        f"{entry.lemma if not isinstance(entry.lemma, dict) else (entry.lemma.get('imperfective', '') + ' / ' + entry.lemma.get('perfective', ''))}"
        f"</option>"
        for entry in entries
    )

    voice_options = "\n".join(
        f"<option value='{voice_key}' {'selected' if voice_key == selected_voice else ''}>{voice_key.title()}</option>"
        for voice_key in ("female", "male")
    )

    notice_html = ""
    if str(not_available) == "1" and raw_search_value.strip():
        notice_html = (
            "<div style='max-width:360px;margin:0 auto 16px auto;padding:12px 14px;"
            "background:#fff7ed;border:1px solid #fdba74;border-radius:12px;color:#9a3412;'>"
            f"No match in the current set: <b>{escape(raw_search_value)}</b>"
            "</div>"
        )

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Verb Board (MVP0)</title>
  <style>
    .secondary-label {{
      font-weight: 600;
      color: #6b7280;
    }}

    .search-row {{
      margin-top: 18px;
      padding-top: 14px;
      border-top: 1px solid #e5e7eb;
    }}

    .search-hint {{
      margin-top: 6px;
      font-size: 12px;
      color: #6b7280;
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

    .row.dual-actions {{
      display: flex;
      gap: 10px;
      justify-content: center;
      flex-wrap: wrap;
    }}

    label {{
      display: block;
      margin-bottom: 6px;
      font-weight: 700;
    }}

    select,
    input[type="text"] {{
      width: 100%;
      padding: 10px;
      border-radius: 8px;
      border: 1px solid #d1d5db;
      box-sizing: border-box;
    }}

    .learn-btn,
    .search-btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 12px 20px;
      border-radius: 999px;
      border: none;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.12s ease;
      text-decoration: none;
      background: #e5e7eb;
      color: #111827;
    }}

    .learn-btn.is-primary,
    .search-btn.is-primary {{
      background: #2563eb;
      color: white;
    }}

    .learn-btn:hover,
    .search-btn:hover {{
      transform: translateY(-1px);
      filter: brightness(1.02);
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
  </style>
</head>

<body>
  <h1>Verb Board (MVP0)</h1>


  <form
    action="/learn"
    method="get"
    class="controls"
    onsubmit="
      if (event.submitter && event.submitter.name === 'search_submit') return true;
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
      <select name="verb_id" id="verb-select">
        {verb_options}
      </select>
    </div>

    <div class="row">
      <label>Voice</label>
      <select name="voice">
        {voice_options}
      </select>
    </div>

    <div class="row">
      <label class="secondary-label">Or find a verb</label>
      <input
        type="text"
        name="q"
        id="search-input"
        value="{escape(search_value)}"
        placeholder="Type a verb"
      />
    </div>
    {notice_html}

    <div class="row center dual-actions">
      <button
        type="submit"
        formaction="/search_verb"
        formmethod="get"
        class="search-btn"
        id="search-btn"
        name="search_submit"
        value="1"
      >
        Find
      </button>

      <button type="submit" class="learn-btn is-primary" id="learn-btn">
        <span class="learn-label">Learn</span>
        <span class="learn-icon">▶</span>
      </button>
    </div>

  </form>
<script src="/static/home.js"></script>
</body>
</html>
"""

    response = HTMLResponse(html)
    response.set_cookie("language", selected_language, httponly=False, samesite="lax")
    response.set_cookie("voice", selected_voice, httponly=False, samesite="lax")
    if selected_verb_id:
        response.set_cookie("verb_id", selected_verb_id, httponly=False, samesite="lax")
    return response
