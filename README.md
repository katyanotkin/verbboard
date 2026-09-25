# VerbBoard

Verb-focused language learning app: conjugation tables, TTS audio, guided practice, and AI-assisted content expansion. Which study languages each tier includes is defined in one place, `core/languages/config.py` (`FREE_STUDY_LANGUAGES`, `PLUS_EXTRA_STUDY_LANGUAGES`); the UI is offered in a smaller set (`UI_LANGUAGES`, same file), so some study languages are study-only with no UI translation.

For the languages in `AUTOGEN_LANGUAGES` (`core/verb_autogen.py`), missing verbs are generated on the spot via AI. For the others, unknown searches become demand signals that drive future verb coverage through a human-reviewed pipeline.

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
- spaced repetition built into the practice loop, not a separate review mode
- multilingual conjugation-first UX
- PWA — installable on Android from the home page
- real-world usage feedback loops
- fast iteration and operational simplicity

---

## Current behavior

### Home page
- Select language (`en`, `ru`, `he`, `es`, `it` free; `fr` Plus-only, listed but shows a request-access notice without entitlement)
- Verb of the day: one featured verb per language, deep-linked to the learn page — same pick all day, changes daily
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
- Pronoun reference: a collapsible "Pronouns" panel shows I/you/he-she-it/we/you/they in the verb's language, with translations revealed by the same toggle used for example sentences

### Verbs page
- Browse with filters: new / seen / known / recent
- Practice session entry point
- Export known verbs as a CSV (Anki-importable) — appears once you've learned at least one verb in that language
- Login nudge: a dismissible sign-in prompt appears for anonymous users who browse and star verbs but never start a practice session

---

## Search and demand signals

- Search across infinitives, conjugated forms, and partial matches
- Cross-language: type an English word, select English — Gemini translates and finds the matching verb in your studied language
- For the languages in `AUTOGEN_LANGUAGES` (`core/verb_autogen.py`): missing verbs are generated automatically (Gemini via VertexAI; Claude for Russian), no admin review, added directly to the live verb set within ~30 seconds
- For languages outside `AUTOGEN_LANGUAGES`: unknown searches are logged as demand signals for human-reviewed AI generation
- Human-reviewed workflow: admin reviews signals, Claude + Gemini generate candidate, human promotes to live verbs

---

## Guided learning experience

- Practice sessions of 3, 6, or 9 verbs; configurable audio listens per verb (3 / 5 / All)
- Verbs you've seen but haven't marked as learned keep coming back: up to a third of each practice session is reserved for them, longest-waiting first, so a verb you're stuck on can't go many sessions without resurfacing
- Audio listening required before advancing to the next verb
- Skip & mark as learned — for verbs you already know
- A free Google sign-in is required to start a practice session (browsing verbs, audio, search and the Verb of the Day stay open without an account); a session already in progress can always be finished
- Complete a session to earn a badge
- Anonymous users earning a badge see a one-tap sign-in prompt in the completion screen, so progress isn't lost if the device changes
- Learning badges and persistent progress tracking
- Cross-device sync for authenticated users
- Spaced repetition on the free tier: marking a verb known (star or "Skip & mark as learned") enters it into a Leitner box ladder (1 / 3 / 7 / 16 / 35 day intervals). Due verbs are quietly mixed back into a normal practice session -- capped at roughly a third of the session -- and resurface with a simple "Knew it" / "Show me again" self-report. There is no separate review screen, no notifications, and no streak pressure to drive it.

---

### Login and cross-device sync
- Google sign-in via Firebase Auth
- By default, progress stays on the current device only
- Sign in to sync seen verbs, known verbs, practice badges, and spaced-repetition state across devices
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
- **Firestore** — primary verb store, user progress, entitlements, and candidate pipeline
- **GCS** — audio cache (on-demand TTS → persistent storage)
- **Cloud Run** — stateless deployment/runtime layer
- **Firebase Auth** — Google sign-in and identity management
- **Anthropic Claude + GCP Vertex AI Gemini** — AI-assisted conjugation, example generation, translation, and cross-language search

> **GCP requirement:** Cloud Run service account needs `roles/aiplatform.user` to call Vertex AI for cross-language search translation.

See `ARCHITECTURE.md` for the full request lifecycle, data flows, and consistency audit.

---

## Editions

One Docker image, config-only difference between free and Plus -- no code fork, no second deployment stage. Stage runs `EDITION=plus` to exercise both code paths; prod runs `EDITION=free` explicitly.

- `EDITION` -- `free` (default) or `plus`
- `STUDY_LANGUAGES` -- CSV of language codes; defaults to `FREE_STUDY_LANGUAGES` on free and `ALL_STUDY_LANGUAGES` on Plus (both in `core/languages/config.py`)
- `APP_NAME` / `APP_SHORT_NAME` -- default `VerbBoard`
- `ANDROID_PACKAGE_NAME` / `ANDROID_CERT_FINGERPRINTS` -- drive `/.well-known/assetlinks.json`, so a future Plus Android listing can serve its own package + signing fingerprint from the same codebase
- `ON_DEMAND_EXAMPLES_ENABLED` -- defaults to `edition == "plus"`, independently overridable as a cost kill switch

`core/editions.py` filters the language-plugin registry (`core/registry.py`, unchanged, edition-agnostic) down to what the active edition allows via `active_study_plugins()` / `is_study_language()`. With zero env vars set, this is a no-op: free-edition behavior is unchanged.

Study languages outside `FREE_STUDY_LANGUAGES` (i.e. `PLUS_EXTRA_STUDY_LANGUAGES`) are gated Plus-only via `core/entitlements.py`: `can_study(language, uid)` checks `user_entitlements/{uid}` in Firestore and is enforced on `/learn`, `/verbs`, `/audio`, both search endpoints, and `/api/preferences`. Plus-only languages are still LISTED in the home language picker on every edition, labelled e.g. "French (Plus)" (`picker_study_plugins()` in `core/editions.py`); choosing one without the entitlement -- anonymous or signed in, never via the sign-in page -- lands on `/verbs?language=fr&plus_required=1` with a "Plus version only, request access via Feedback" notice linking to `/feedback?page=plus`. Entitlement grants are manual today -- an admin sets a record via `/admin/entitlements` (`user_entitlements/{uid}.status == "active"`, checked with a 60s TTL cache, fails open on a Firestore read error since this gates content, not sensitive data). No billing integration yet; the record schema reserves fields (`product_id`, `purchase_token`, `expires_at`) for when one exists.

---

## Spaced repetition

Anki-style, Leitner box ladder, built directly into the practice loop -- no separate review screen. A verb enters the ladder the first time it's marked known; recalling it correctly promotes it one box (`LEITNER_INTERVAL_DAYS = (1, 3, 7, 16, 35)` in `core/progress/models.py`), missing it resets it. The only signal is a binary self-report during a normal practice session, not graded recall quality. Due verbs are computed client-side from data already fetched on login -- no background job, no scheduler. Server state lives on the existing per-verb progress document (`srs_box` / `srs_due_at` / `srs_reviewed_at`), no new collection. Sync is last-write-wins by review timestamp, deliberately different from the union-merge-never-delete rule used for seen/known state, because SRS state can legitimately move backward across devices.

---

## Demand-driven generation pipeline

Two tracks depending on language.

**EN/ES (automatic):** Search miss triggers Gemini (VertexAI) generation inline. Verb is promoted directly to the live set. Available within ~30 seconds. No Anthropic calls, no admin review.

**HE/RU/IT/FR (human-reviewed):**

1. Unknown search logged as a demand signal
2. Admin reviews and classifies signals
3. Claude + Gemini generate structured verb data: conjugation, examples, morphology, and translations
4. Candidate previewed directly inside the live learning UX
5. Human-reviewed candidate promoted into the live verb set

AI model routing: Haiku (`claude-haiku-4-5-20251001`) for English, Sonnet (`claude-sonnet-4-6`) for every other language.

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

---

## Planned work

`PRODUCT_BACKLOG.md` and `PRODUCT_ROADMAP.md` are frozen historical records as of 2026-09-01. New work is tracked as GitHub Issues on the repo (labeled `free` / `plus` / `engineering` / `needs-scoping`), not in either file.
