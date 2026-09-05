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
  +-- entitlement gate  core/entitlements.py -- can_study() checked on
  |                     /learn, /verbs, /audio, both search endpoints,
  |                     /api/preferences before any of the below runs
  |
  +-- Firestore       verb data, user progress, entitlements, demand signals
  +-- GCS             audio files (mp3)
  +-- Secret Manager  env secrets (prod/stage)
  +-- Vertex AI       cross-language search translation + EN/ES autogen (Gemini)
  +-- Anthropic API   verb generation + Hebrew translation (Claude)
```

### Backend

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | |
| Web framework | FastAPI | async, type-annotated handlers |
| Templates | Jinja2 (via `fastapi.templating`) | all HTML responses use `TemplateResponse` |
| Config | `core/settings.py` `load_settings()` | frozen dataclass; reads from Secret Manager or `.env`; carries `edition` and `study_languages` |
| Editions | `core/editions.py` | filters the plugin registry to the active edition's allowed study languages; no-op with zero env vars set |
| Entitlements | `core/entitlements.py` | `can_study(language, uid)` gates Plus-only study languages; `user_entitlements/{uid}` in Firestore; 60s TTL cache, fails open on Firestore error |
| Database | Firestore | single source of truth; no second DB |
| Audio storage | GCS | `core/audio_backend/gcs.py`; factory enforces GCS-only |
| AI generation | Anthropic Claude | Haiku (`claude-haiku-4-5-20251001`) for EN, Sonnet (`claude-sonnet-4-6`) for others |
| Translation | Vertex AI Gemini | `gemini-2.5-flash-lite` via `core/translation_service.py` |
| EN/ES autogen | Vertex AI Gemini | `gemini-2.5-flash` via `core/verb_autogen.py`; inline generation on search miss, no admin review |
| Auth (users) | Firebase Auth | ID token validated on `/api/progress/*` |
| Auth (admin) | HMAC session token | `__session` cookie; only cookie CDN forwards to Cloud Run |

### Frontend

| Concern | Approach |
|---|---|
| Framework | None -- vanilla JS only (no React, Vue, etc.) |
| CSS | Per-page files + `common.css`; custom properties for theming; no inline `<style>` blocks |
| Auth | `auth.js` -- Firebase JS SDK (deferred); `authReadyPromise` resolves once per page load |
| Progress | `progress.js` -- `VerbBoardProgress`; localStorage + server sync on login |
| Practice | `practice_loop.js` -- session state in localStorage; badge sync on `vb:progress-hydrated`; mixes due spaced-repetition verbs into the session |
| Spaced repetition | `srs.js` -- `nextBox()` (Leitner box-transition rule, mirrors `leitner_next_box()` in `core/progress/models.py`), `getDueVerbIds()`, `mergeFromServer()` (last-write-wins, not union-merge) |
| PWA | `sw.js` (cache version -- check the `CACHE` constant at the top of the file directly; it changes on every deploy that touches a precached asset, so a number recorded here would just go stale), `manifest.json`, `pwa.js` install prompt |
| i18n | 4 locales (EN/RU/HE/ES); all 4 locale files must be updated together; Italian/French are study-only and have no UI locale of their own |

### Language plugins

Each language lives in `core/languages/{lang}/plugin.py` and self-registers on import. All plugins implement the same interface:

```python
build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board
```

Six plugins exist today: `en`, `es`, `fr`, `he`, `it`, `ru` -- all six are imported unconditionally in `app/main.py` at startup, so the registry (`core/registry.py`) always contains all six regardless of edition. What varies by edition is not which plugins *register*, but which ones are *reachable*:

- `core/editions.py`'s `active_study_plugins()` filters the registry down to `Settings.study_languages` for language-picker purposes
- `core/entitlements.py`'s `can_study()` is the actual enforcement layer, checked per-request on `/learn`, `/verbs`, `/audio`, both search endpoints, and `/api/preferences`

`en`/`ru`/`he`/`es` are free-tier (`FREE_STUDY_LANGUAGES` in `core/languages/config.py`, also the fixed 4-language UI locale set). `it`/`fr` (`PLUS_EXTRA_STUDY_LANGUAGES`) are Plus-only and study-only -- no UI translation exists for them, they only ever appear as the *studied* language, never the *UI* language.

### Editions

`core/editions.py` + `Settings.edition` (`EDITION` env var, `free` default). One Docker image, one deployment shape -- edition is config, not a fork or a second Cloud Run service. Stage runs `EDITION=plus` to exercise both code paths in one environment; prod runs `EDITION=free` explicitly.

`Settings.study_languages` defaults per edition via `default_study_languages(edition)` (`core/languages/config.py`): free gets exactly `FREE_STUDY_LANGUAGES`, Plus gets that plus `PLUS_EXTRA_STUDY_LANGUAGES`. Can be overridden directly via the `STUDY_LANGUAGES` CSV env var. `Settings._validate()` refuses to boot a free-edition instance that has a Plus-only language in its study list.

Other edition-scoped config: `APP_NAME`/`APP_SHORT_NAME`, `ANDROID_PACKAGE_NAME`/`ANDROID_CERT_FINGERPRINTS` (so a future Plus Android listing can carry its own package/signing identity from the same image), `ON_DEMAND_EXAMPLES_ENABLED` (defaults to `edition == "plus"`, independently overridable as a cost kill switch; on-demand example generation itself is not yet built).

### Entitlements

`core/entitlements.py`. `requires_entitlement(language)` is true for any language outside `FREE_STUDY_LANGUAGES` (today: `it`, `fr`). `has_plus_entitlement(uid)` reads `user_entitlements/{uid}` in Firestore, true iff `status == "active"` and not expired; 60-second TTL cache (plain dict, not `lru_cache`, because TTL eviction matters -- a revoked grant must not stay cached indefinitely). Fails open on a Firestore read error (a few minutes of free content during a GCP incident is cheaper than locking out a paying user); fails closed only on a definitive negative (no doc, or inactive status). `can_study(language, uid)` is the single call site every route uses: `not requires_entitlement(language) or (uid is not None and has_plus_entitlement(uid))`.

No billing integration exists yet -- grants are manual via `/admin/entitlements` (`app/routes/admin_entitlements.py`, `set_entitlement()`/`get_entitlement()`/`list_entitlements()`/`lookup_uid_by_email()`). The record schema reserves billing-only fields (`product_id`, `purchase_token`, `order_id`, `expires_at`) seeded to `None` on first write so a future billing-sourced value has somewhere to land without a migration.

### Spaced repetition

`core/progress/models.py` (`LEITNER_INTERVAL_DAYS = (1, 3, 7, 16, 35)`, `LEITNER_MAX_BOX`, `leitner_next_box()`) + `app/static/srs.js` (`nextBox()`, kept in lockstep with the Python version -- `tests/test_srs_merge.py` runs both through a Node-subprocess parity harness).

A verb enters the box ladder the moment it's marked `known` (star toggle or "Skip & mark as learned") -- `known` doubles as "entered the review ladder"; there's no separate opt-in. The only recall signal is binary ("Knew it" / "Show me again") on resurfaced verbs inside a normal practice session -- no SM-2/ease-factor math, no separate review screen. State (`srs_box`, `srs_due_at`, `srs_reviewed_at`) lives on the existing `user_progress/{uid}/languages/{lang}/verbs/{verb_id}` document, no new collection. `POST /api/progress/review` advances the box server-side; `GET /api/progress` includes the fields when `srs_box > 0`.

Due-ness is computed client-side (`srs.js`'s `getDueVerbIds()`) from data `hydrateProgress()` already fetched -- no server-side due query, no Cloud Scheduler, no background job. `practice_loop.js`'s `startPractice()` mixes due-and-known verbs into a session (capped around 1/3 of session size) via `dueReviewCandidates()`, tagging each verb's mode (`'review'` vs `'new'`) in the session's `modes` map; `learn_practice.js`'s practice bar shows the recall buttons only for `mode === 'review'` verbs.

Sync model deliberately differs from seen/known: SRS state can move in either direction across devices (a box can go up or down), so `srs.js`'s `mergeFromServer()` is last-write-wins by `srs_reviewed_at`, not the union-merge-never-delete rule the rest of progress sync uses. Do not fold SRS fields into the existing union-merge loop.

### Cookie constraint

Firebase Hosting (Fastly CDN) strips **all** cookies from requests and responses except `__session`. Rules that follow from this:

- `__session` -- admin HMAC token only; set/read by `admin_auth.py` and `admin_utils.py`
- All other preferences (`language`, `ui_language`) travel as **URL query params**, never as cookies
- Analytics sessions use a **server-side IP+UA fingerprint** (see Analytics below)
- Never add a new `set_cookie()` call for a non-`__session` name in server code

### Client-side state propagation

State that must survive navigation: `language` (studied language) and `ui_language` (UI locale).

**`language`** -- persisted in `localStorage` as `vb_language` by `home.js`. On bare `/?` loads with no `?language=` param, home.js reads localStorage and redirects before the page renders. All server-rendered navigation links include `?language=` explicitly.

**`ui_language`** -- two-layer defence:
1. **Explicit param propagation**: every server-rendered link (`_bottom_nav.html`, verbs.html, board.html back/feedback links, render.py `resolved_return_to`/`learn_href`) and every JS navigation (`home.js openVerb()`, `verbs_filters.js renderItem()`) must include `&ui_language=`. `core/render.py` computes `ui_suffix` from the `ui_lang` parameter and applies it to all generated URLs. `core/render.py` also sanitizes `return_to` via `safe_return_to()` before embedding in any href (XSS guard -- prevents `javascript:` URIs in the Back button).
2. **localStorage safety net**: `app/templates/_persist_ui_lang.html` is included in every page template (home, verbs, board, about, privacy, feedback). The inline early-load script saves `ui_language` to `localStorage('vb_ui_language')` when the param is present; if the param is absent and localStorage has a value, it redirects before the page is painted. This catches any link that accidentally drops the param.

**`window.VB_UI_LANG`** -- JS-side source of truth for UI language. Set in every page template (`window.VB_UI_LANG = {{ ui_lang | tojson }}` or equivalent). All JS modules (`verbs_filters.js`, `practice_loop.js`, `learn.js`) read from this single global -- no per-module URL parsing.

**`_bottom_nav.html` `bnav_ui_lang`** -- falls back to the page-level `lang` variable if `bnav_ui_lang` is not explicitly set by the including template. Individual templates only need to set `bnav_ui_lang` when it differs from `lang` (e.g. `board.html` where the verb language differs from the UI language).

**Voice form (board.html)** -- `voice_source_input` in `core/render.py` carries all form-round-trip state: `source=candidate` (if applicable), `translated_from`, and `source_lang`. Adding new per-request state to the voice form means adding it to `voice_source_input` in `render.py`, not to `board.html`.

**Auditing rule**: any change that adds a new navigation path (link, form, `RedirectResponse`, `window.location`) must carry both `language` and `ui_language`. Any removal of a state-carrying mechanism (cookie, localStorage key) requires a full path audit of every link, form, JS navigation, and redirect before committing.

### Verbs page paging

- **Server pre-load**: both platforms receive up to `VERBS_PAGE_LIMIT` verbs in the initial render. `VB_VERBS_TOTAL` is always the full count.
- **Desktop** (`pointer: fine`): `VERBS_DISPLAY_BATCH` items shown at a time; "Show more" button pages through pre-loaded set, then fetches from Firestore.
- **Mobile** (`pointer: coarse`): `filters.showAll()` called on **fresh page loads** only -- sets `displayCount = Infinity` so the full pre-loaded list is scrollable with no button tap. Back-nav and return-from-learn/feedback skip `showAll()` so `sessionStorage` restores the previous scroll position (same `navType === 'back_forward' || fromInternal` guard used throughout `verbs_page.js`).
- **Filter change**: `applyFilter(filter, init=false)` resets `displayCount` to `batch` on both viewports -- intentional, a filter switch is a new context.

### Analytics

Middleware: `_PageViewMiddleware` in `app/main.py` intercepts GET requests to tracked pages (`/`, `/verbs`, `/learn`, `/feedback`).

**Session tracking** (`core/analytics/session_tracker.py`):
- Session ID = `SHA256(forwarded_ip | user_agent | date)[:32]` -- deterministic, no cookie needed
- One Firestore doc per `(IP, UA, day)` in `analytics_sessions`; `create()` is a no-op for returning visitors
- UID attached to session doc on user login via `POST /api/analytics/session` (auth.js fires this after Firebase sign-in; server derives fingerprint from the same request headers)

**Page view counting:** `analytics_daily` was dropped 2026-06-14 -- nothing writes to it anymore. `core/analytics/daily_counters.py` now holds only `_clean_lang()`, a language-code sanitizer reused by `session_tracker.py` and `api_analytics.py`. Usage stats are derived entirely from `analytics_sessions` via `get_device_mix()` in `core/admin_feedback_service.py`.

### Key data flows

**Verb page load:** `GET /learn?verb={id}&language={lang}` -> `can_study(language, uid)` entitlement gate (`core/entitlements.py`) -> `verb_loader.py` (Firestore, 5-minute TTL cache) -> language plugin `build_board()` -> `core/render.py` builds HTML -> `TemplateResponse("board.html")`

**Audio on demand:** `GET /audio/{language}/{verb_id}/{voice}/{form_key}.mp3` -> `can_study(language, uid)` entitlement gate -> `audio_service.ensure_audio()` -> GCS fetch or TTS generate + GCS store

**Cross-language search:** `GET /search_verb_by_lang?q={query}&source_lang=en&language={lang}` -> entitlement gate -> `translate_search_query()` (Vertex AI) -> Firestore lookup -> redirect to `/learn` or log demand signal

**EN/ES autogen (search miss, free-tier languages only):** search miss on `en`/`es` -> `is_plausible_verb_query()` gate (`core/verb_autogen.py`) -> fire-and-forget asyncio task -> Gemini (`gemini-2.5-flash`) generates structured verb data -> pydantic validation -> dual-write to `verb_candidates` (as already-promoted) and live `verbs` -> cache bust -> audio pre-warm. No Anthropic call, no admin review, live within ~30 seconds.

**Demand pipeline (HE/RU/IT/FR, human-reviewed):** Admin reviews signals -> triggers Claude generation (`admin_candidates.py`) -> candidate stored in Firestore -> preview on `/learn` -> promote to `verbs` collection

**User progress:** Firebase ID token -> `POST /api/progress/sync` -> `progress_service.py` -> `user_progress/{uid}/languages/{lang}/verbs/{verb_id}`

**Spaced repetition review:** practice session surfaces a due verb (`srs.js` `getDueVerbIds()`, client-computed) -> user self-reports recall -> `POST /api/progress/review` -> `leitner_next_box()` advances `srs_box`/`srs_due_at` server-side on the same progress document

### Testing

See **`TESTING.md`** for layers, commands, parallelization, and principles.

Pre-commit hook runs the full test suite (unit + e2e) on every commit (`pytest tests/` without `-n`). E2E tests connect to real Firestore and can be slow -- run them separately with `-n 2` against stage if the hook times out.

---

Generated from lead-architect audit (2026-06-10). Tracks divergences from intended architecture.

**Note (2026-09-03):** the checklist below predates editions, entitlements, and spaced repetition, and has not been re-audited against them. Treat it as a historical record of the pre-Plus codebase rather than a current-state check; a fresh audit covering those three systems is separate, larger work.

---

## Critical

- [x] **`admin_auth.py`: replace f-string login page with Jinja2 template**
  - Created `app/templates/admin_login.html` + `app/static/admin_login.css`
  - Minimal redirect scripts (login-callback, logout) left inline (3-liners, acceptable)

- [x] **Cookie persistence on Firebase Hosting**
  - Firebase Hosting / Fastly CDN strips all cookies except `__session`
  - `language`, `ui_language`, `verb_id` preference cookies removed from all routes; `ui_language` now travels exclusively as URL query param
  - `vb_sid`/`vb_seen` analytics cookies replaced by server-side IP+UA fingerprint (see Analytics section below)
  - `_persist_ui_lang.html` localStorage safety net added to all page templates
  - `render.py` `resolved_return_to` / `learn_href`, board.html feedback link, `home.js openVerb()` all carry `ui_language`
  - Mobile verbs `showAll()` restored with back-nav guard (fresh-load only)

## Medium

- [x] **`admin.py`: use `TemplateResponse` instead of `read_text` + `str.replace`**
  - Replaced `__ADMIN_ROOT__` placeholders in `admin.html` with `{{ admin_prefix }}` Jinja2 variables
  - Removed `TEMPLATES_DIR` and unused `Path` import from `admin_utils.py`

- [x] **Inline `<style>` blocks in templates**
  - Extracted `signin.css`, `feedback.css`, `privacy.css`, `about.css` from inline blocks
  - Alert divs in `feedback.html` replaced with `.alert .alert-success/.alert-error` classes
  - `admin_login.css` also extracted (admin login page)

- [ ] **Inline `style=` attributes in Python-generated HTML**
  - `core/render.py` lines 87, 172: `style="font-size:..."` and `style="text-align:..."` baked into f-strings
  - Fix: use CSS classes instead of inline styles

- [x] **`_firebase_auth.html`: apply `_html_safe_json()` to `firebase_web_config_json` in all routes**
  - Fixed by `_safe_firebase_config()` in `core/settings.py` -- called once in `load_settings()`, pre-escapes `<`, `>`, `&` so all routes are safe without per-route encoding

- [ ] **`practice_loop.js`: replace biased shuffle with Fisher-Yates**
  - `startPractice()` line 313 uses `sort(() => Math.random() - 0.5)` -- not uniformly random (V8 TimSort bias)
  - Users see the same verbs disproportionately

- [ ] **`admin_feedback.js`: `answerLabel` called with one argument**
  - Lines 221, 227: `answerLabel(row.poll_answer)` omits `pollMeta`; poll option labels are never shown
  - Fix: pass the correct `pollMeta` argument

## Low / Architectural Debt

- [ ] **`home.js`: dead code and minor hygiene**
  - `updatePrimaryAction()` is an empty stub called twice -- remove
  - `window.location = ...` should be `window.location.href = ...` (line 105)

- [ ] **`verbs_filters.js`: `esc()` does not escape single quotes**
  - Safe today (only used in double-quoted attributes), but diverges from `admin_shared.js` -- latent gap if ever used in single-quoted context

- [ ] **`admin.html`/`admin_feedback.html`/`admin_login.html`**: minor hardening
  - `window.ADMIN_ROOT` in `admin.html` should use `| tojson` not bare string interpolation
  - Add `lang="en"` to `<html>` on all admin pages (WCAG 3.1.1)
  - Add `autocomplete="current-password"` to admin login password field

- [ ] **`core/render.py`: ~280 lines of Python-side HTML generation**
  - Builds conjugation table rows, audio buttons, example rows, banners as f-strings, passes via `| safe`
  - Technically uses Jinja2 at the end but inverts separation of concerns
  - Not urgent -- acceptable given conjugation table complexity, but a future refactor target
  - Consider: Jinja2 macros for row/button/example fragments when next touching render logic

---

## Passing (no action needed)

- Language plugins (`en/es/fr/he/it/ru`): all implement `build_board`, all self-register -- consistent
- Audio backend: GCS-only enforced via factory -- no local backend exposed at runtime
- AI model routing: Haiku for EN, Sonnet for others -- correctly applied in `settings_ai.py` and `admin_candidates.py`
- Firestore-only at runtime: no JSON lexicon reads in production paths
- Route organization: all routes in `app/routes/`, nothing leaked into `main.py`
- Admin cookie: `__session` used correctly in `admin_auth.py`
