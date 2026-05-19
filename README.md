# VerbBoard

Verb-focused language learning system built around fast iteration, demand-driven expansion, and lightweight practice loops.
Unknown searches become demand signals that drive future verb coverage.

---

## Run locally

```bash
make local-run
```

Open in browser:
```
http://127.0.0.1:8000
```

---

## Current behavior

### Home page
- Select language (`en`, `ru`, `he`, `es`), verb, voice (`female`, `male`)
- Browse available verbs
- Search works across conjugated forms
- Click **Learn** to open the learning view, or search for a verb

Visual indicators: star known verbs, progress bar shows known count (visited inidicated by tint)

#### Search
- Accepts infinitives, conjugated forms, partial matches
- First matching verb opens directly (no results list)
- No match: shows notice and logs query for future expansion

### Learning experience
- Conjugation board with TTS audio for every form and example sentence
- Voice toggle (female / male)
- Star to mark verb as known
- Back to verb list
- Inline example translations when UI language differs from verb language

### Browse verbs page
- Filter by seen / known / recent
- Sort options

### Practice loop
- start a session of 3, 6, or 9 verbs; requires listening to audio before advancing
- completion earns a badge; practice badges displayed inline; compact grouped badge display for larger collections
- Persistent practice progress per language

### Login and cross-device sync
- Google sign-in via Firebase Auth
- On login: server progress (seen, known, badges) is merged into localStorage and the page re-renders
- On sign-out: localStorage progress for that language is cleared and the page re-renders
- Badges are synced to Firestore on session completion and fetched on login

## State persistence
- Language and voice persist via cookies
- Seen / known / practice state stored in localStorage per language
- Authenticated users: state synced to Firestore (`user_progress`, `user_practice` collections)

---

## Architecture

- **FastAPI + server-rendered UI** — application layer
- **Firestore** -- primary verb store, user progress, and candidate pipeline
- **GCS** -- audio cache (on-demand TTS -> persistent storage)
- **Cloud Run** -- stateless deployment/runtime layer
- **Firebase Auth** -- Google sign-in; server validates ID tokens on `/api/progress/*`
- **Anthropic Claude + GCP Gemini** — generation and translation workflows

## Demand-driven generation pipeline

Unknown verb searches are logged as demand signals. Admin flow:
1. Signals reviewed and classified
2. Structured verb data generated via AI workflows -- conjugation, examples, morphology, translation generated via Claude API and Gemini
3. Admin previews candidate on live learn page with inline Promote / Needs Fix / Regen
4. Promoted candidates move to live verb set

---

## Development

### Pre-commit linting
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---
#### Lexicon
As of 2026-04-30, Lexicon JSON is retained for local development and Firestore import/backfill only.
Runtime stage/prod reads from Firestore.
