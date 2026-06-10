# VerbBoard Architecture & Consistency TODO

---

## Overview

VerbBoard is a verb-focused language learning app: conjugation tables, audio, real examples, and a practice loop. Unknown searches become demand signals that drive future verb coverage.

### Request lifecycle

```
Browser
  |
  | HTTP
  v
Firebase Hosting (Fastly CDN)
  - serves static assets directly from /public
  - forwards /api/*, /admin/*, /learn, /verbs, etc. to Cloud Run
  - strips all cookies except __session before forwarding
  |
  v
Cloud Run  (Docker container, app.main:app)
  FastAPI app
    routes/         HTTP handlers -- one file per feature area
    core/           business logic, no HTTP
    templates/      Jinja2 .html files
    static/         vanilla JS + CSS (no framework)
  |
  +-- Firestore       verb data, user progress, demand signals
  +-- GCS             audio files (mp3)
  +-- Secret Manager  env secrets (prod/stage)
  +-- Vertex AI       cross-language search translation (Gemini)
  +-- Anthropic API   verb generation + Hebrew translation (Claude)
```

### Backend

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | |
| Web framework | FastAPI | async, type-annotated handlers |
| Templates | Jinja2 (via `fastapi.templating`) | all HTML responses use `TemplateResponse` |
| Config | `core/settings.py` `load_settings()` | frozen dataclass; reads from Secret Manager or `.env` |
| Database | Firestore | single source of truth; no second DB |
| Audio storage | GCS | `core/audio_backend/gcs.py`; factory enforces GCS-only |
| AI generation | Anthropic Claude | Haiku (`claude-haiku-4-5-20251001`) for EN, Sonnet (`claude-sonnet-4-6`) for others |
| Translation | Vertex AI Gemini | `gemini-2.5-flash-lite` via `core/translation_service.py` |
| Auth (users) | Firebase Auth | ID token validated on `/api/progress/*` |
| Auth (admin) | HMAC session token | `__session` cookie; only cookie CDN forwards to Cloud Run |

### Frontend

| Concern | Approach |
|---|---|
| Framework | None -- vanilla JS only (no React, Vue, etc.) |
| CSS | Per-page files + `common.css`; custom properties for theming; no inline `<style>` blocks |
| Auth | `auth.js` -- Firebase JS SDK (deferred); `authReadyPromise` resolves once per page load |
| Progress | `progress.js` -- `VerbBoardProgress`; localStorage + server sync on login |
| Practice | `practice_loop.js` -- session state in localStorage; badge sync on `vb:progress-hydrated` |
| PWA | `sw.js` (cache `vb-v18`), `manifest.json`, `pwa.js` install prompt |
| i18n | 4 locales (EN/RU/HE/ES); all 4 locale files must be updated together |

### Language plugins

Each language (`en`, `ru`, `he`, `es`) lives in `core/languages/{lang}/plugin.py` and self-registers on import. All plugins implement the same interface:

```python
build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board
```

Plugins are imported in `app/main.py` at startup. The registry is in `core/registry.py`.

### Key data flows

**Verb page load:** `GET /learn?verb={id}&language={lang}` -> `verb_loader.py` (Firestore, 60s TTL cache) -> language plugin `build_board()` -> `core/render.py` builds HTML -> `TemplateResponse("board.html")`

**Audio on demand:** `GET /audio/{language}/{verb_id}/{voice}/{form_key}.mp3` -> `audio_service.ensure_audio()` -> GCS fetch or TTS generate + GCS store

**Cross-language search:** `GET /search_verb_by_lang?q={query}&source_lang=en&language={lang}` -> `translate_search_query()` (Vertex AI) -> Firestore lookup -> redirect to `/learn` or log demand signal

**Demand pipeline:** Admin reviews signals -> triggers Claude generation (`admin_candidates.py`) -> candidate stored in Firestore -> preview on `/learn` -> promote to `verbs` collection

**User progress:** Firebase ID token -> `POST /api/progress/sync` -> `progress_service.py` -> `user_progress/{uid}/languages/{lang}/verbs/{verb_id}`

### Testing

Four layers; see `TESTING.md` for full commands and principles.

| Layer | Location | Tool | Runs against |
|---|---|---|---|
| Unit | `tests/*.py` | pytest | stubs (in-memory FakeDB, no-op audio) |
| E2E | `tests/e2e/` | pytest + Playwright (Chromium) | live FastAPI server on a free port; real Firestore |
| Integration | `tests/integration/` | pytest | real Firestore (requires ADC credentials) |
| Smoke | `scripts/smoke*.py` | plain HTTP | running service (local / stage / prod) |

**Playwright** controls a real Chromium browser. The `live_server_url` session fixture starts the FastAPI app in a background thread on a random port; each test gets a fresh page. E2E tests skip gracefully when Firestore is empty, so they are safe without credentials.

**Parallelization** via `pytest-xdist`:
- Unit tests: `-n auto` (each worker is an isolated process with its own stubs)
- E2E tests: `-n 2` (each worker starts its own server on a different port with its own browser)
- Integration tests: sequential only (shared Firestore state)

Pre-commit hook runs the full unit suite on every commit (`pytest` without `-n`).

---

Generated from lead-architect audit (2026-06-10). Tracks divergences from intended architecture.

---

## Critical

- [x] **`admin_auth.py`: replace f-string login page with Jinja2 template**
  - Created `app/templates/admin_login.html` + `app/static/admin_login.css`
  - Minimal redirect scripts (login-callback, logout) left inline (3-liners, acceptable)

- [ ] **Cookie persistence on Firebase Hosting (decision needed)**
  - Firebase Hosting / Fastly CDN strips all cookies except `__session` before forwarding to Cloud Run
  - Affected cookies set via `Set-Cookie`: `language`, `ui_language`, `verb_id`, `vb_sid`, `vb_seen`
  - On prod/stage, Cloud Run never sees these on subsequent requests -- preferences silently reset
  - Options: move preferences to `localStorage` + pass as query params on first load; or accept degradation
  - Files: `app/routes/home.py`, `app/routes/verbs.py`, `app/routes/about.py`, `app/main.py`

## Medium

- [x] **`admin.py`: use `TemplateResponse` instead of `read_text` + `str.replace`**
  - Replaced `__ADMIN_ROOT__` placeholders in `admin.html` with `{{ admin_prefix }}` Jinja2 variables
  - Removed `TEMPLATES_DIR` and unused `Path` import from `admin_utils.py`

- [ ] **Inline `<style>` blocks in templates**
  - `app/templates/signin.html` lines 7-24 -- flexbox layout, button styles
  - `app/templates/feedback.html` -- card layout, form styles, alert boxes
  - `app/templates/privacy.html` -- page layout styles
  - `app/templates/about.html` -- page layout styles
  - Fix: extract each into `app/static/{page}.css`, link via `<link rel="stylesheet">`

- [ ] **Inline `style=` attributes in Python-generated HTML**
  - `core/render.py` lines 87, 172: `style="font-size:..."` and `style="text-align:..."` baked into f-strings
  - Fix: use CSS classes instead of inline styles

## Low / Architectural Debt

- [ ] **`core/render.py`: ~280 lines of Python-side HTML generation**
  - Builds conjugation table rows, audio buttons, example rows, banners as f-strings, passes via `| safe`
  - Technically uses Jinja2 at the end but inverts separation of concerns
  - Not urgent -- acceptable given conjugation table complexity, but a future refactor target
  - Consider: Jinja2 macros for row/button/example fragments when next touching render logic

---

## Passing (no action needed)

- Language plugins (`en/ru/he/es`): all implement `build_board`, all self-register -- consistent
- Audio backend: GCS-only enforced via factory -- no local backend exposed at runtime
- AI model routing: Haiku for EN, Sonnet for others -- correctly applied in `settings_ai.py` and `admin_candidates.py`
- Firestore-only at runtime: no JSON lexicon reads in production paths
- Route organization: all routes in `app/routes/`, nothing leaked into `main.py`
- Admin cookie: `__session` used correctly in `admin_auth.py`
