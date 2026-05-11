# CLAUDE.md — VerbBoard Project Context

VerbBoard is a language learning app focused on verbs: conjugation tables, real usage examples, audio, and repetition. FastAPI + server-rendered UI, GCP backend.

---

## Tech Stack

- **Backend:** Python 3.12 + FastAPI
- **Frontend:** Vanilla JS + CSS (no framework -- do not introduce one)
- **Data:** GCP Firestore (single source of truth in all environments)
- **Audio:** GCS-only (`AUDIO_BUCKET`); pluggable backend abstraction in `core/audio_backend/`
- **AI generation:** Anthropic Claude -- Haiku (`claude-haiku-4-5-20251001`) for English, Sonnet (`claude-sonnet-4-6`) for all other languages
- **Secrets:** GCP Secret Manager (prod/stage) or `.env` (local)
- **Infrastructure:** GCP -- Cloud Run + Firestore + GCS
- **App entry point:** `app.main:app`

---

## Running Locally

```bash
make local-run
# or: set -a && . $(PWD)/.env && set +a && $(PYTHON) -m uvicorn app.main:app --reload --port $(HOST_PORT)
```

Local base URL: `http://localhost:${HOST_PORT}` (set in `.env`)

---

## Project Structure

```
app/
  main.py          # FastAPI app, routers, plugin imports, startup
  routes/          # home, verbs, learn, audio, feedback, health, about, admin*
  static/          # Vanilla JS + CSS
  templates/       # Jinja2 templates (home.html + admin views)

core/
  models.py        # VerbEntry, Board, Example dataclasses
  settings.py      # load_settings() -- frozen Settings dataclass; secrets loading
  settings_ai.py   # AI generation: prompts (split by lang), model/token config, async client, get_cached_system()
  registry.py      # language plugin registry (all_plugins())
  verb_loader.py   # loads verbs from Firestore (60s TTL cache)
  audio_service.py # ensure_audio(), build_hashed_audio_key()
  audio_backend/   # base, factory, local, gcs
  languages/       # en, ru, he, es -- each plugin self-registers
  storage/         # firestore_db, verb_repository, verb_document
  tts.py           # VOICES dict, TTS integration

tests/             # pytest suite
```

Use the **Explore** agent for detailed file navigation.

---

## Key Architectural Patterns

**Language plugins:** `core/languages/{lang}/plugin.py` self-registers on import (triggered in `app/main.py`). Each implements `build_board(verb, voice_key, voice_label) -> Board`.

**Firestore data model:**
- Collections: `verbs`, `verb_candidates`, `demand_signal`, `demand_signal_labels`
- Doc ID: `{language}_{transliterated_lemma}` (e.g. `en_go`, `ru_idti`) -- Cyrillic/Hebrew transliterated to ASCII
- Key fields: `language`, `verb_id`, `lemma`, `rank`, `forms`, `examples`, `search_extract` (array), `morph`, `display_lemma`, `display_forms`
- Search: `find_verb_by_search_extract()` uses `array_contains` on normalized query

**AI generation:** Admin triggers `_call_claude(language, query)` in `admin_candidates.py` (async, awaited) -> strict JSON -> stored as candidate -> previewable at `/learn` -> promoted to `verbs` via admin. All AI config (prompts, model, tokens, async client) lives in `core/settings_ai.py`. Per-language system prompt via `get_cached_system(language)` with `cache_control: ephemeral` for Anthropic prompt caching. English uses Haiku, others use Sonnet; Hebrew gets `max_tokens=4096`, others 2048.

**Audio:**
- URL: `/audio/{language}/{verb_id}/{voice}/{form_key}.mp3`
- `form_key` = `build_hashed_audio_key(base_key, text)` = `{base_key}_{sha1(text)[:10]}` -- content-addressed, text not recoverable from hash
- On-demand: endpoint loads verb, walks board rows/examples to find matching hash, calls `ensure_audio()`
- Pre-warm: `_warm_verb_audio()` in `admin_candidates.py` generates both voices on verb add/regenerate
- `_NO_AUDIO_ROW_KEYS = {"aspect", "pair", "binyan", "root"}` -- these rows get no audio button

**Localization:** UI in EN / RU / HE / ES. Language + voice persist via cookies. Hebrew RTL supported.

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

---

## What's Coming Next

- **Practice loop** on Browse Verbs page with completion badges
- **Login / server-side state** -- cross-device progress sync
- **Expand language coverage**
