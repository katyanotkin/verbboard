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
## NOTES 2026-04-20
## Upcoming
- Verb picker UX for growing verb sets
- Optional user personalization (TBD)
