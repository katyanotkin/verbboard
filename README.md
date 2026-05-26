# VerbBoard

Verb-focused language learning system combining guided practice, persistent progress, on-demand audio, and AI-assisted content expansion.

Unknown searches become demand signals that drive future verb coverage.

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

VerbBoard is evolving from a verb reference tool into a guided learning system driven by real usage signals, persistent progress, and iterative AI-assisted content expansion.

The product focuses on:
- guided learning flows
- lightweight practice sessions
- multilingual conjugation-first UX
- real-world usage feedback loops
- fast iteration and operational simplicity

---

## Current behavior

### Home page
- Select language (`en`, `ru`, `he`, `es`)
- Search verbs across conjugated forms
- Guided learning entry point with practice-oriented navigation
- Voice selection (`female`, `male`)

Visual indicators:
- ★ known verbs
- progress bar for learning state
- visited verbs indicated by tint

## Search and demand signals

- Search across infinitives, conjugated forms, partial matches, and English meanings
- First matching verb opens directly
- Unknown searches become demand signals for future verb generation
- Human-reviewed AI workflows expand live verb coverage over time

## Guided learning experience

- Learn view organized as:
  infinitive → example usage → conjugation patterns
- UX with TTS audio for every form and example sentence
- Inline translations when UI language differs from the studied language
- Browse verbs with filters for seen / known / recent activity
- Guided practice sessions of 3, 6, or 9 verbs
- Audio listening required before advancing through practice sessions
- Learning badges and persistent progress tracking
- Cross-device sync for authenticated users



### Login and cross-device sync
- Google sign-in via Firebase Auth
- Seen verbs, known verbs, and practice badges sync across devices
- Local progress merges automatically with server state on login
- Practice badges persist across sessions

---

## State persistence

- Language and voice persist via cookies
- Seen / known / practice state stored in localStorage per language
- Authenticated users sync state to Firestore (`user_progress`, `user_practice`)

---

## Architecture

- **FastAPI + server-rendered UI** — application layer
- **Firestore** — primary verb store, user progress, analytics, and candidate pipeline
- **GCS** — audio cache (on-demand TTS → persistent storage)
- **Cloud Run** — stateless deployment/runtime layer
- **Firebase Auth** — Google sign-in and identity management
- **Anthropic Claude + GCP Gemini** — AI-assisted conjugation, example generation, and translation workflows

---

## Demand-driven generation pipeline

Unknown verb searches are logged as demand signals.

Admin workflow:

1. Signals reviewed and classified
2. AI workflows generate structured verb data:
   conjugation, examples, morphology, and translations
3. Candidates previewed directly inside the live learning UX
4. Human-reviewed candidates promoted into the live verb set

---

## Operational quality

- Stage → prod deployment promotion flow
- Smoke tests and Playwright E2E validation gates
- Audio cache audit tooling
- Deterministic verb ID validation and collision audits
- Production telemetry and usage analytics

---

## Development

### Pre-commit linting

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## Lexicon

As of 2026-04-30, Lexicon JSON is retained only for:
- local development
- Firestore import/backfill workflows

Runtime stage/prod environments read directly from Firestore.
