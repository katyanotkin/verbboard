# CLAUDE.md — VerbBoard Project Context

This file is read automatically by Claude Code at the start of every session.
Update it as the project evolves.

---

## What is VerbBoard?

VerbBoard is a language learning product built around one core idea:
**verbs are the fastest path to usable language.**

Instead of vocabulary lists, VerbBoard teaches how verbs actually work in
context — through conjugation tables, real usage examples, audio, and repetition.

---

## Core Features

1. **Conjugation-first learning**
   - Full verb forms across tenses and moods
   - Verbs ordered by frequency (highest value first, lowest rank number)
   - Focus on usage, not rote memorization

2. **Search by real usage**
   - Supports inflected forms, not just lemmas ("went", "был")
   - Search matches against `search_extract` array field in Firestore
   - Unknown/missing queries are captured as demand signals for content expansion

3. **Audio-first experience**
   - TTS audio for every verb form and example sentence
   - Audio backend is pluggable: `local` (dev) or `gcs` (prod/stage)
   - Russian audio library replacement is a separate planned task — do not touch

4. **Stateless, frictionless UX**
   - No login required
   - Progress tracked client-side (localStorage: seen / known)
   - Instant access, zero onboarding friction

5. **Demand-driven content pipeline**
   - Unknown verbs → captured as demand signals → reviewed → AI-generated via Claude → promoted to live
   - `core/verb_service.py` handles AI generation + Firestore promotion
   - Admin flow ensures quality before release

6. **Multi-language support**
   - Current languages: English (`en`), Russian (`ru`), Hebrew (`he`), Spanish (`es`)
   - Each language is a plugin: `core/languages/{lang}/plugin.py`
   - Plugins self-register on import in `app/main.py`
   - `core/registry.py` holds the plugin registry (`all_plugins()`)

---

## Tech Stack

- **Backend:** Python 3.12 + FastAPI
- **Frontend:** Vanilla JS + CSS (no framework — do not introduce one)
- **Data:** GCP Firestore (single source of truth in all environments)
- **Audio:** Pluggable backend — `local` for dev, `gcs` (Google Cloud Storage) for prod/stage
- **AI generation:** Anthropic Claude (`claude-sonnet-4-6`) via `core/verb_service.py`
- **Secrets:** GCP Secret Manager (prod/stage) or `.env` (local)
- **Infrastructure:** GCP (Cloud Run + Firestore + GCS)
- **App entry point:** `app.main:app`

---

## Running Locally

```bash
# Full local run (loads .env, starts uvicorn with hot reload):
set -a && . $(PWD)/.env && set +a && $(PYTHON) -m uvicorn app.main:app --reload --port $(HOST_PORT)

# Or via Makefile:
make local-run
```

- Port is defined in `.env` as `HOST_PORT` (check `.env` & Makefile for actual value)
- Local base URL: `http://localhost:${HOST_PORT}`
- In local environment: `VERB_DATA_SOURCE=local` (need verification), `AUDIO_BACKEND=local`
- In stage/prod: `VERB_DATA_SOURCE=firestore`, `AUDIO_BACKEND=gcs`

---

## Project Structure

```
app/
  main.py                  # FastAPI app, mounts routers, plugin imports, startup hook
  routes/
    home.py                # Home / search entry point
    verbs.py               # /verbs — browse verbs page (HTML, verb list from Firestore)
    learn.py               # /learn — conjugation board for a single verb
    audio.py               # /audio — TTS audio endpoint
    feedback.py            # /feedback — user feedback capture
    health.py              # /health — health check
    about.py               # /about
    admin.py               # Admin dashboard
    admin_auth.py          # Admin authentication
    admin_candidates.py    # Candidate verb management
    admin_feedback.py      # Feedback review
    admin_signals.py       # Demand signal review
    admin_utils.py         # Admin utilities
  static/                  # Vanilla JS + CSS (served at /static)
  templates/               # Jinja2 HTML templates (admin views)

core/
  models.py                # Core dataclasses: VerbEntry, Board, Example
  settings.py              # Settings dataclass + loader (env vars + GCP Secret Manager)
  registry.py              # Language plugin registry (all_plugins())
  verb_service.py          # AI verb generation via Claude + Firestore promotion
  verb_loader.py           # Loads verb entries (local or Firestore)
  audio_service.py         # Audio orchestration
  audio_backend/
    base.py                # Abstract audio backend
    factory.py             # Creates local or gcs backend from settings
    local.py               # Local filesystem audio backend
    gcs.py                 # GCS audio backend
  demand/
    query_resolution.py    # Resolves search queries to verbs or signals
    candidate_aggregation.py
    gcs_events.py
    recommendation.py
  languages/
    en/plugin.py           # English language plugin (self-registers)
    ru/plugin.py           # Russian language plugin
    he/plugin.py           # Hebrew language plugin
    es/plugin.py           # Spanish language plugin
  storage/
    firestore_db.py        # get_db() — Firestore client singleton
    verb_repository.py     # All Firestore CRUD: get_verb, list_verbs, upsert_verb,
                           #   find_verb_by_search_extract, find_verb_by_lemma,
                           #   list_verbs_recent, get_candidate
    verb_document.py       # Document builders + ID generation + search_extract builder
  search_utils.py          # flatten_values, normalize_text
  render.py                # Board rendering logic
  cache.py                 # Caching layer
  tts.py                   # TTS integration
  supported_languages.py   # Language config
  paths.py                 # Path helpers
  polls.py                 # Polling utilities
  lexicon.py               # LEGACY — prototype only, do not use
  lexicon_loader.py        # LEGACY — prototype only, do not use

tests/                     # Test suite (to be scaffolded)
tools/                     # Dev/admin tooling scripts
scripts/                   # Deployment / ops scripts
data_src/                  # Source data (used for seeding)
runtime/                   # Local runtime artifacts (audio cache etc.)
Makefile                   # Dev task shortcuts
pytest.ini                 # Pytest config (read before adding test config)
```

---

## Key Architectural Patterns

### Settings & Environment
- `core/settings.py` → `load_settings()` returns a frozen `Settings` dataclass
- Environment auto-detected from `ENVIRONMENT` env var or `K_SERVICE` (Cloud Run)
- `local` → uses local audio + either local or Firesore verb data source (defined by verb_data_source in .env)
- `stage` / `prod` → uses GCS audio + Firestore verb data
- Secrets: `ADMIN_SECRET` and `ANTHROPIC_API_KEY` from `.env` locally, GCP Secret Manager in cloud

### Language Plugins
- Each language registers itself via `core/languages/{lang}/plugin.py`
- Plugins are imported explicitly in `app/main.py` to trigger self-registration
- `core/registry.py` → `all_plugins()` returns all registered plugins

### Firestore Data Model
- **Collection:** `verbs` (configurable via `VERBS_COLLECTION` env var)
- **Document ID:** `{language}_{transliterated_lemma}` (e.g. `en_go`, `ru_idti`)
- **Key fields:** `language`, `verb_id`, `lemma`, `rank`, `forms`, `examples`,
  `search_extract` (array), `morph`, `display_lemma`, `display_forms`, `created_at`, `updated_at`
- **Search:** `find_verb_by_search_extract()` queries `search_extract array_contains normalized_query`
- **Collections:** `verbs`, `verb_candidates`, `demand_signal`, `demand_signal_labels`

### Verb ID Generation
- `build_storage_verb_id(language, lemma)` → transliterates lemma to ASCII → `{lang}_{ascii_lemma}`
- `build_verb_doc_id(verb_id)` → normalizes an existing verb_id for Firestore doc key
- Cyrillic and Hebrew are transliterated to Latin for stable ASCII doc IDs

### AI Generation Flow
- core/verb_service.py → generate_and_promote_verb(language, lemma)
- Calls Anthropic Claude (claude-sonnet-4-6) using system prompt defined in core/settings.py
- Flow:
1. Normalize input → resolve lemma
2. Invoke model → expect strict JSON (schema aligned with render layer)
3. Parse + validate response
4. Build Firestore document
5. Write to verb_candidates collection
---- skipped for auto-generated Russian aspect pairs
6. Candidate is previewable in real /learn UX
7. Promoted via admin → moved to verbs collection
- Idempotency:
---- Skip generation if verb already exists (by lemma / search_extract)

### Audio
- `app/routes/audio.py` serves audio
- `core/audio_backend/factory.py` creates backend from settings
- Local backend: reads from `runtime/audio_cache/`
- GCS backend: reads from configured GCS bucket
- **Russian audio replacement is out of scope for Claude Code sessions**

---

## Conventions & Constraints for Claude Code

- **Do not modify production source files** unless it will cause complicated code — prefer test helpers
- **Do not introduce a frontend framework** — vanilla JS only
- **Do not add a second database** — Firestore is the single source of truth
- **Do not use `core/lexicon.py` or `core/lexicon_loader.py`** — prototype legacy, not in use
- **Do not commit `.env` or any secrets**
- When adding a feature, ask: does this conflict with the stateless/frictionless UX principle?
- Russian audio replacement is a separate workstream — do not touch `core/tts.py` or audio backends
- Always read `Makefile` and `pytest.ini` before setting up any test commands

---

## Testing

```bash
pytest          # run all tests
make test       # if Makefile target exists (check first)
```

- `pytest.ini` is present — check it before adding new pytest settings
- Tests live in `tests/`
- Hitting real Firestore (dev/local project) is acceptable in tests
- See `TESTING.md` (to be created) for full documentation

---

## What's Coming Next

- **Practice loop** on Browse Verbs page with completion badges
- **Localization system** — user-selectable UI language (labels, RTL config)
- **Login / server-side state** — cross-device progress sync
- **Test suite** — unit, integration, and smoke tests (current priority)
- **Russian audio** — replacing TTS with dedicated higher-quality library (separate task)
