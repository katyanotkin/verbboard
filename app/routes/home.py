from __future__ import annotations

from html import escape

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from dataclasses import dataclass
from typing import Any

from core.admin_logging import log_missing_verb_search
from core.i18n import get_strings, resolve_ui_language
from core.lexicon import load_lexicon
from core.paths import DATA_DIR
from core.registry import all_plugins
from core.search_utils import find_best_entry
from core.storage.verb_repository import find_verb_by_search_extract
from core.settings import load_settings
from core.storage.verb_repository import list_verbs_recent

_SETTINGS = load_settings()

LANGUAGE_HOME_LABELS = {
    "en": "English",
    "ru": "Russian / Русский",
    "he": "Hebrew / עברית",
    "es": "Spanish / Español",
}

_UI_LANG_FLAGS = [
    ("en", "🇺🇸"),
    ("ru", "🇷🇺"),
    ("he", "🇮🇱"),
    ("es", "🇪🇸"),
]

router = APIRouter()


@dataclass
class _HomeVerb:
    id: str
    lemma: Any  # str or dict for Russian


def _doc_to_home_verb(d: dict) -> _HomeVerb:
    lemma = d.get("display_lemma") or d.get("lemma") or ""
    return _HomeVerb(id=d.get("verb_id", ""), lemma=lemma)


def _load_entries(language: str):
    if _SETTINGS.verb_data_source == "firestore":
        docs = list_verbs_recent(language, limit=20)
        return [_doc_to_home_verb(d) for d in docs]
    lex_path = DATA_DIR / language / "lexicon.json"
    return load_lexicon(lex_path) if lex_path.exists() else []


def _build_ui_lang_selector(ui_lang: str, learning_lang: str, label: str) -> str:
    btns = "".join(
        f'<a href="/?ui_language={code}&language={escape(learning_lang)}"'
        f' class="ui-lang-btn{" active" if code == ui_lang else ""}"'
        f' aria-label="{code}">{flag}<span class="ui-lang-code">{code}</span></a>'
        for code, flag in _UI_LANG_FLAGS
    )
    return (
        f'<div class="ui-lang-row">'
        f'<span class="ui-lang-label">{escape(label)}</span>'
        f'<div class="ui-lang-selector">{btns}</div>'
        f"</div>"
    )


@router.get("/set_language", response_model=None)
def set_language(language: str):
    entries = _load_entries(language)
    default_verb_id = entries[0].id if entries else ""

    response = RedirectResponse(url=f"/?language={language}&verb_id={default_verb_id}")
    response.set_cookie("language", language, httponly=False, samesite="lax")
    if default_verb_id:
        response.set_cookie("verb_id", default_verb_id, httponly=False, samesite="lax")
    return response


@router.get("/search_verb", response_model=None)
def search_verb(
    request: Request,
    language: str,
    q: str = "",
):
    query = (q or "").strip()
    if not query:
        return RedirectResponse(url=f"/?language={language}")

    doc = find_verb_by_search_extract(language, query)

    if doc:
        matched_verb_id = doc.get("verb_id")

        response = RedirectResponse(
            url=f"/learn?language={language}&verb_id={matched_verb_id}"
        )
        response.set_cookie("language", language, httponly=False, samesite="lax")
        response.set_cookie("verb_id", matched_verb_id, httponly=False, samesite="lax")
        return response

    entries = _load_entries(language)
    matched_entry = find_best_entry(entries, query)

    if matched_entry:
        matched_verb_id = matched_entry.id

        response = RedirectResponse(
            url=f"/learn?language={language}&verb_id={matched_verb_id}"
        )
        response.set_cookie("language", language, httponly=False, samesite="lax")
        response.set_cookie("verb_id", matched_verb_id, httponly=False, samesite="lax")
        return response

    log_missing_verb_search(
        language=language,
        query=query,
        page="home",
        source="search",
        user_agent=request.headers.get("user-agent", ""),
    )

    response = RedirectResponse(
        url=f"/?language={language}&search={query}&not_available=1"
    )
    response.set_cookie("language", language, httponly=False, samesite="lax")
    return response


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    language: str | None = Query(None),
    verb_id: str | None = Query(None),
    search: str | None = Query(None),
    not_available: int | None = Query(None),
) -> HTMLResponse:
    plugins = all_plugins()

    ui_lang = resolve_ui_language(request)
    ui = get_strings(ui_lang)
    html_dir = "rtl" if ui_lang == "he" else "ltr"

    cookie_language = request.cookies.get("language")
    cookie_verb_id = request.cookies.get("verb_id")

    selected_language = language or cookie_language or "he"
    if selected_language not in plugins:
        selected_language = "he"

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
        for entry in entries[:20]
    )

    notice_html = ""
    if str(not_available) == "1" and raw_search_value.strip():
        notice_html = (
            "<div class='notice'>"
            f"{escape(ui['home.no_match'])} <b>{escape(raw_search_value)}</b>"
            "</div>"
        )

    ui_lang_selector = _build_ui_lang_selector(
        ui_lang, selected_language, ui["home.ui_language_label"]
    )

    html = f"""<!doctype html>
<html lang="{ui_lang}" dir="{html_dir}">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>VerbBoard</title>
  <link rel="stylesheet" href="/static/common.css"/>
  <link rel="stylesheet" href="/static/home.css"/>
</head>

<body>
  <div class="page">
  <h1 class="page-title">VerbBoard <span class="copyright">©</span></h1>
  <div class="about-links">
    <a href="/about?lang={ui_lang}" class="about-inline">{escape(ui['home.about'])}</a>
    {ui_lang_selector}
  </div>

    <form
      action="/learn"
      method="get"
      class="controls"
      onsubmit="
        if (event.submitter && event.submitter.name === 'search_submit') return true;
        const btn = this.querySelector('.learn-btn');
        btn.disabled = true;
        btn.classList.add('loading');
        btn.querySelector('.learn-label').textContent = btn.dataset.loading;
        btn.querySelector('.learn-icon').textContent = '•••';
      "
    >
      <div class="intro-hint">
        {escape(ui['home.intro_hint'])}
      </div>

      <div class="row">
      <label><span class="label-icon">🌐</span> {escape(ui['home.language_label'])}</label>
        <select
          name="language"
          onchange="window.location='/set_language?language=' + this.value;"
        >
          {lang_options}
        </select>
      </div>

      <div class="row">
        <label><span class="label-icon">🧩</span> {escape(ui['home.verb_label'])}</label>
        <select name="verb_id" id="verb-select">
          {verb_options}
        </select>
      </div>

      <div class="row center">
        <a href="/verbs?language={escape(selected_language)}" class="browse-link">
            {escape(ui['home.browse_link'])}
        </a>
      </div>

      <div class="progress-row">
        <div class="progress-bar">
          <div class="progress-fill" style="width: 0%"></div>
        </div>
        <div class="progress-meta">
          <img src="/static/gold-star.svg" class="progress-star" alt="Known">
          <span class="progress-count">001</span>
        </div>
      </div>

      <div class="row search-row">
        <label class="secondary-label">{escape(ui['home.search_label'])}</label>
        <div class="search-input-wrap">
          <input
            type="text"
            name="q"
            id="search-input"
            value="{escape(search_value)}"
            placeholder="{escape(ui['home.search_placeholder'])}"
            autocomplete="off"
          />
          <div id="search-suggestions" class="search-suggestions" role="listbox" aria-label="Verb suggestions"></div>
        </div>
        <div class="field-help">
          {escape(ui['home.search_help'])}
        </div>
        {notice_html}
      </div>

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
          {escape(ui['home.find_button'])}
        </button>

        <button type="submit" class="learn-btn is-primary" id="learn-btn"
          data-loading="{escape(ui['home.loading'])}">
          <span class="learn-icon">▶</span>
          <span class="learn-label">{escape(ui['home.learn_button'])}</span>
        </button>
      </div>

        <div class="feedback-row">
            <a
                href="/feedback?page=home&language={escape(selected_language)}&return_to=/?language={escape(selected_language)}"
                class="feedback-link"
            >
            {escape(ui['home.feedback_link'])}
            </a>
        </div>
    </form>
  </div>

  <script src="/static/home.js"></script>
</body>
</html>
"""

    response = HTMLResponse(html)
    response.set_cookie("language", selected_language, httponly=False, samesite="lax")
    response.set_cookie("ui_language", ui_lang, httponly=False, samesite="lax")
    if selected_verb_id:
        response.set_cookie("verb_id", selected_verb_id, httponly=False, samesite="lax")
    return response
