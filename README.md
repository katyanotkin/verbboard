# VerbBoard

Minimal verb learning app (FastAPI + server-rendered UI).
Focused on fast iteration and simple learning flow: get a verb → see it → hear it → move on.

---

## Run locally

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open in browser:
```
http://127.0.0.1:8000
```

---

## Current behavior

### Home page
- Select language (`en`, `ru`, `he`, `es`), verb, voice (`female`, `male`)
- Click **Learn** to open the learning view, or search for a verb

Visual indicators: ✓ seen verbs · ★ known verbs · progress bar shows known count

#### Search
- Accepts infinitives, conjugated forms, partial matches
- First matching verb opens directly (no results list)
- No match: shows notice and logs query for future expansion

### Learn page
- Conjugation board with TTS audio for every form and example sentence
- Voice toggle (female / male)
- ★ mark verb as known
- Back to verb list

## State persistence
- Language and voice persist via cookies
- Returning to Home keeps last selected values

---

## Architecture

- **Firestore** — primary verb store and candidate pipeline
- **GCS** — audio cache (on-demand TTS → persistent storage)
- **Cloud Run** — stateless application layer

## Candidate pipeline

Unknown verb searches are logged as demand signals. Admin flow:
1. Signals reviewed and classified
2. Candidates generated via Claude API — conjugation, examples, morph
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
## NOTES 2026-04-26

### Product evolution
- Demand-driven verb expansion: unknown searches captured as signals
- Built end-to-end candidate pipeline (signal → generation → preview → promotion)
- Admin preview uses real learn page (no separate admin UI abstraction)
- Feedback loop integrated across product (💬 + verb demand via search)

### Data & modeling decisions
- Output schema aligned with render layer
- Aspect pairs stored as lemma strings (resolved at render time) → improved data resilience
- Audio keys hashed by text → eliminates stale cache mismatches

### AI / generation
- Verb generation powered via Anthropic API
- Switching from Opus → Sonnet reduced generation cost ~5x with no quality loss
- Prompt design optimized for structured output

### UX / behavior
- Search over conjugated forms (not just lemmas)
- Stateless UX with local progress tracking (seen / known)
- Verbs browsing page with filtering and sorting

#### Lexicon
As of 2026-04-30, Lexicon JSON is retained for local development and Firestore import/backfill only.
Runtime stage/prod reads from Firestore.

---

## Upcoming
- Centralize UI language configuration
- Introduce guided verb practice sets with progress trackin
- Optional user personalization (TBD)
