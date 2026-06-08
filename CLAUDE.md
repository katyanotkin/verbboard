# CLAUDE.md — VerbBoard Project Context

VerbBoard is a verb-focused language learning app: conjugation tables, real usage examples, audio, and practice loops. Unknown searches become demand signals that drive future verb coverage. FastAPI + server-rendered UI, GCP backend.

---

## Tech Stack

- **Backend:** Python 3.12 + FastAPI
- **Frontend:** Vanilla JS + CSS (no framework -- do not introduce one)
- **Data:** GCP Firestore (single source of truth in all environments)
- **Audio:** GCS-only (`AUDIO_BUCKET`); pluggable backend abstraction in `core/audio_backend/`
- **AI generation:** Anthropic Claude -- Haiku (`claude-haiku-4-5-20251001`) for English, Sonnet (`claude-sonnet-4-6`) for all others; GCP Gemini for translation workflows
- **Auth:** Firebase Auth (Google sign-in); server validates ID tokens on `/api/progress/*`
- **Secrets:** GCP Secret Manager (prod/stage) or `.env` (local)
- **Infrastructure:** GCP -- Cloud Run + Firestore + GCS
- **Cross-language search:** Vertex AI Gemini (`gemini-2.5-flash-lite`) translates EN query to target language lemma; `translate_search_query()` in `core/translation_service.py`
- **App entry point:** `app.main:app`

---

## Running Locally

```bash
make local-run
```

Local base URL: `http://localhost:${HOST_PORT}` (set in `.env`)

Pre-commit linting: `pip install pre-commit && pre-commit install`

---

## Project Structure

```
app/
  main.py          # FastAPI app, routers, plugin imports, startup
  routes/          # home, verbs, learn, audio, feedback, health, about, admin*
                   # api_progress.py  -- /api/progress/* endpoints
                   # auth_pages.py    -- /auth/signin page (three-branch sign-in flow)
                   # well_known.py    -- /.well-known/assetlinks.json (TWA Digital Asset Links)
  static/          # Vanilla JS + CSS
                   # auth.js          -- Firebase auth, hydrateProgress, vb:* events
                   # progress.js      -- VerbBoardProgress (localStorage known/seen)
                   # storage.js       -- VerbBoardStorage (readSet/writeSet/readJson/writeJson)
                   # practice_loop.js -- practice session + badge sync
                   # verbs_filters.js -- verb list filter/sort/render
                   # verbs_page.js    -- wires filters + practice loop + auth events
                   # learn.js         -- known button, audio tracking, practice bar
                   # pwa.js           -- install prompt (beforeinstallprompt), deferred
                   # sw.js            -- service worker, cache version vb-v18
                   # manifest.json    -- PWA manifest (icons, display, scope)
                   # icons/           -- PNG icons for PWA (48/72/96/144/192/512px + maskable)
  templates/       # Jinja2 templates
                   # _bottom_nav.html -- shared 5-tab bottom nav (Back/Search/List/Practice/Login)
                   # signin.html      -- /auth/signin page
                   # feedback.html    -- feedback page (converted from f-string to Jinja2)
                   # privacy.html     -- /privacy page (required for Google Play OAuth consent)

core/
  models.py             # VerbEntry, Board, Example dataclasses
  settings.py           # load_settings() -- frozen Settings dataclass; secrets loading
  settings_ai.py        # AI generation: prompts (split by lang), model/token config, async client, get_cached_system()
  registry.py           # language plugin registry (all_plugins())
  verb_loader.py        # loads verbs from Firestore (60s TTL cache)
  audio_service.py      # ensure_audio(), build_hashed_audio_key()
  audio_backend/        # base, factory, local, gcs
  languages/            # en, ru, he, es -- each plugin self-registers
  storage/              # firestore_db, verb_repository, verb_document
  progress/             # models.py, progress_repository.py, progress_service.py
  tts.py                # VOICES dict, TTS integration
  translation_service.py # translate_search_query() + translate_examples(); Gemini for non-HE, Claude for HE
  safe_return.py        # safe_return_to() -- validates redirect URLs to prevent open redirect

tests/             # pytest suite
```

Use the **Explore** agent for detailed file navigation.

---

## Key Architectural Patterns

**Language plugins:** `core/languages/{lang}/plugin.py` self-registers on import (triggered in `app/main.py`). Each implements `build_board(verb, voice_key, voice_label) -> Board`.

**Firestore data model:**
- Verb collections: `verbs`, `verb_candidates`, `demand_signal`, `demand_signal_labels`
- Doc ID: `{language}_{transliterated_lemma}` (e.g. `en_go`, `ru_idti`) -- Cyrillic/Hebrew transliterated to ASCII
- Key fields: `language`, `verb_id`, `lemma`, `rank`, `forms`, `examples`, `search_extract` (array), `morph`, `display_lemma`, `display_forms`
- Search: `find_verb_by_search_extract()` uses `array_contains` on normalized query
- User progress: `user_progress/{uid}/languages/{lang}/verbs/{verb_id}` -- `seen`, `known`, timestamps
- User practice: `user_practice/{uid}/languages/{lang}` -- `badges` (list of ints), `started_at`, `updated_at`
- Legacy fallback: old data at `user_progress/{uid}/verbs/{verb_id}` is read if new path is empty

**Demand-driven generation pipeline:** Unknown searches are logged as demand signals. Admin flow: review signals -> generate structured verb data via Claude + Gemini -> preview candidate on live `/learn` page -> promote to `verbs`. Admin triggers `_call_claude(language, query)` in `admin_candidates.py` (async) -> strict JSON -> stored as candidate. All AI config lives in `core/settings_ai.py`. Per-language system prompt via `get_cached_system(language)` with `cache_control: ephemeral`. Hebrew gets `max_tokens=4096`, others 2048.

**Audio:**
- URL: `/audio/{language}/{verb_id}/{voice}/{form_key}.mp3`
- `form_key` = `build_hashed_audio_key(base_key, text)` = `{base_key}_{sha1(text)[:10]}` -- content-addressed
- On-demand: endpoint loads verb, walks board rows/examples to find matching hash, calls `ensure_audio()`
- Pre-warm: `_warm_verb_audio()` in `admin_candidates.py` generates both voices on verb add/regenerate
- `_NO_AUDIO_ROW_KEYS = {"aspect", "pair", "binyan", "root"}` -- no audio button for these rows

**Auth and progress sync:**
- Firebase Auth via `auth.js` (deferred); `authReadyPromise` resolves once per page load
- On login: `hydrateProgress()` merges server state into localStorage, dispatches `vb:progress-hydrated`
- On sign-out: dispatches `vb:auth-signed-out` -- only when transitioning from logged-in to null
- Badge merge: keep whichever list (local vs server) is longer; `syncPracticeBadgesFromServer()` called inside `vb:progress-hydrated` handler

**Practice loop:**
- Session: `localStorage` key `practice_session:{lang}` -- `{ids, lemmas, size}`; sizes 3/6/9
- Requires 5 audio plays before Next/Finish; completion earns a badge
- `BADGE_COMPACT_THRESHOLD` (from `VB_BADGE_COMPACT_THRESHOLD`) switches to compact grouped badge display
- Wrap-up modal on return to verbs page (`practice_wrapup:{lang}`)

**PWA / Mobile:**
- Manifest at `/manifest.json`, service worker at `/sw.js` (cache `vb-v18`), icons in `app/static/icons/`
- Install prompt: `pwa.js` listens for `beforeinstallprompt` (must not be deferred); shows install button; on mobile tap shows hint, second tap triggers prompt
- 5-tab bottom nav (`_bottom_nav.html`): Back / Search / List / Practice / Login; min-height 56px; uses `env(safe-area-inset-bottom)` padding; included on all pages
- Sign-in flow (`auth_pages.py` + `signin.html`): standalone PWA uses `window.open('/auth/signin', '_blank')`; mobile browser navigates to `/auth/signin?return_to=...`; desktop uses `signInWithPopup`
- Digital Asset Links at `/.well-known/assetlinks.json` (`well_known.py`) -- SHA-256 fingerprint needed for TWA (currently PLACEHOLDER)
- Per-environment Firebase secrets: `verbboard-firebase-web-config-stage` (stage), `verbboard-firebase-web-config` (prod)
- TWA / Google Play: target is ~50KB Android shell via PWABuilder; requires assetlinks fingerprint + OAuth consent screen verification

**Cross-language search:**
- Endpoint: `GET /search_verb_by_lang?language={lang}&q={query}&source_lang=en`
- Calls `translate_search_query(query, source_lang, target_lang, project)` in `core/translation_service.py` via Vertex AI Gemini (`gemini-2.5-flash-lite`)
- Token fallback: Gemini may return "correr." with punctuation; each token is tried against `find_verb_by_search_extract`
- Fuzzy fallback: if Firestore misses, `load_entries_for_language` + `find_best_entry` scans cached verbs
- On success: redirects to `/learn` with `translated_from={original}&source_lang=en`; UI shows "Найдено через Английский: {original}"
- On translation failure: redirects with `not_available=1&search={original}&search_mode=en`
- On translation success but verb absent: logs demand signal with translated word; `search_mode=native`
- **GCP requirement:** Cloud Run service account needs `roles/aiplatform.user` to call Vertex AI

**Inline translations:** `Example.translations` dict; Claude/Gemini routing per language; shown when UI language differs from verb language.

**Localization:** UI in EN / RU / HE / ES. Language + voice persist via cookies. Hebrew RTL supported.

**Lexicon JSON:** As of 2026-04-30, retained for local development and Firestore import/backfill only. Runtime (stage/prod) reads exclusively from Firestore.

---

## Conventions & Constraints

- No frontend frameworks -- vanilla JS only
- No second database -- Firestore is the single source of truth
- Do not commit `.env` or secrets
- When adding a feature: does it conflict with the stateless/frictionless UX principle?
- Always read `Makefile` and `pytest.ini` before touching test config

---

## Testing

```bash
pytest       # run all tests
make test    # check Makefile first
```

- `pytest.ini` is present -- read before adding pytest config
- Tests live in `tests/`
- Use the **qa-engineer** agent for writing and maintaining tests
- Playwright e2e tests leave a running asyncio loop -- run async test coroutines in a `ThreadPoolExecutor` worker thread (see `tests/test_audio.py` for the pattern)
