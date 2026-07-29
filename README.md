# VerbBoard

Verb-focused language learning app: conjugation tables, TTS audio, guided practice, and AI-assisted content expansion. Supports English, Spanish, Hebrew, and Russian.

For English and Spanish, missing verbs are generated on the spot via AI. For Hebrew and Russian, unknown searches become demand signals that drive future verb coverage.

---

## Run locally

```bash
make local-run
```

Open in browser:

```text
http://127.0.0.1:8000
```

---

## Product direction

VerbBoard is evolving from a verb reference tool into a guided learning system driven by real usage signals, persistent progress, and iterative AI-assisted content expansion. Targeting Google Play via TWA (Trusted Web Activity) as a ~50KB Android shell.

The product focuses on:
- guided learning flows with audio-first practice sessions
- multilingual conjugation-first UX
- PWA — installable on Android from the home page
- real-world usage feedback loops
- fast iteration and operational simplicity

---

## Current behavior

### Home page
- Select language (`en`, `ru`, `he`, `es`)
- Search verbs: studied language selected by default; select English to cross-search in your studied language (translated via Gemini)
- Voice selection (`female`, `male`)
- Install button on Android to add to home screen

Visual indicators:
- ★ learned verbs
- tinted background = previously visited

### Learn page
- Conjugation table with TTS audio for every form and example sentence
- Switch between female and male voices
- Inline translations when UI language differs from the verb's language
- Focus filter: hide conjugation rows by gender (masculine / feminine) and number (singular / plural) — Hebrew, Russian, Spanish

### Verbs page
- Browse with filters: new / seen / known / recent
- Practice session entry point

---

## Search and demand signals

- Search across infinitives, conjugated forms, and partial matches
- Cross-language: type an English word, select English — Gemini translates and finds the matching verb in your studied language
- For English and Spanish: missing verbs are generated automatically via Gemini (VertexAI), no admin review, added directly to the live verb set within ~30 seconds
- For Hebrew and Russian: unknown searches are logged as demand signals for human-reviewed AI generation
- Human-reviewed workflow: admin reviews signals, Claude + Gemini generate candidate, human promotes to live verbs

---

## Guided learning experience

- Practice sessions of 3, 6, or 9 verbs; configurable audio listens per verb (3 / 5 / All)
- Audio listening required before advancing to the next verb
- Skip & mark as learned — for verbs you already know
- Complete a session to earn a badge
- Learning badges and persistent progress tracking
- Cross-device sync for authenticated users

---

### Login and cross-device sync
- Google sign-in via Firebase Auth
- By default, progress stays on the current device only
- Sign in to sync seen verbs, known verbs, and practice badges across devices
- Words learned and badges earned before signing in are preserved on first login

---

## PWA / Mobile

- PWA manifest, service worker, and icons in `app/static/`
- 4-tab icon-only bottom nav on mobile: Back / Verbs / Search / Login
- Install prompt on Android via `beforeinstallprompt`
- Three-branch sign-in: standalone PWA → new tab, mobile browser → `/auth/signin`, desktop → popup
- `/privacy` page for Google Play OAuth consent screen
- Digital Asset Links at `/.well-known/assetlinks.json` (TWA fingerprint required for Play)

---

## State persistence

- Language and UI language travel as URL query params (no cookies — Firebase Hosting CDN strips all except `__session`)
- Voice, seen / known / practice state stored in localStorage per language
- Authenticated users sync state to Firestore (`user_progress`, `user_practice`)

---

## Architecture

- **FastAPI + server-rendered UI** — application layer; Jinja2 templates, vanilla JS + CSS
- **Firestore** — primary verb store, user progress, analytics, and candidate pipeline
- **GCS** — audio cache (on-demand TTS → persistent storage)
- **Cloud Run** — stateless deployment/runtime layer
- **Firebase Auth** — Google sign-in and identity management
- **Anthropic Claude + GCP Vertex AI Gemini** — AI-assisted conjugation, example generation, translation, and cross-language search

> **GCP requirement:** Cloud Run service account needs `roles/aiplatform.user` to call Vertex AI for cross-language search translation.

---

## Editions

One Docker image, config-only difference between free and Plus -- no code fork, no second deployment stage. Stage runs `EDITION=plus` to exercise both code paths; prod runs `EDITION=free` explicitly.

- `EDITION` -- `free` (default) or `plus`
- `STUDY_LANGUAGES` -- CSV of language codes; defaults to today's four (`en,ru,he,es`) on free, adds Italian/French on Plus
- `APP_NAME` / `APP_SHORT_NAME` -- default `VerbBoard`
- `ANDROID_PACKAGE_NAME` / `ANDROID_CERT_FINGERPRINTS` -- drive `/.well-known/assetlinks.json`, so a future Plus Android listing can serve its own package + signing fingerprint from the same codebase
- `ON_DEMAND_EXAMPLES_ENABLED` -- defaults to `edition == "plus"`, independently overridable as a cost kill switch

`core/editions.py` filters the language-plugin registry (`core/registry.py`, unchanged, edition-agnostic) down to what the active edition allows via `active_study_plugins()` / `is_study_language()`. With zero env vars set, this is a no-op: free-edition behavior is unchanged.

No Plus features are live yet -- this is infrastructure only. Italian/French study languages and on-demand example generation need separate follow-up work, including a per-user entitlement check that doesn't exist yet.

---

## Demand-driven generation pipeline

Two tracks depending on language.

**EN/ES (automatic):** Search miss triggers Gemini (VertexAI) generation inline. Verb is promoted directly to the live set. Available within ~30 seconds. No Anthropic calls, no admin review.

**HE/RU (human-reviewed):**

1. Unknown search logged as a demand signal
2. Admin reviews and classifies signals
3. Claude + Gemini generate structured verb data: conjugation, examples, morphology, and translations
4. Candidate previewed directly inside the live learning UX
5. Human-reviewed candidate promoted into the live verb set

---

## Operational quality

- Stage → prod deployment promotion flow
- Smoke tests and Playwright E2E validation gates
- Audio cache audit tooling
- Deterministic verb ID validation and collision audits
- Production telemetry and usage analytics

---

## Development

### Linting

```bash
make lint        # ruff check + ruff format --check + mypy, no tests
```

### Pre-commit

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files   # also runs the full pytest suite
```

### Testing

```bash
make test        # all tests
make test-unit   # unit only (fast)
```

---

## Lexicon

As of 2026-04-30, Lexicon JSON is retained only for:
- local development
- Firestore import/backfill workflows

Runtime stage/prod environments read directly from Firestore.
