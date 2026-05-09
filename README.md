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
#### Lexicon
As of 2026-04-30, Lexicon JSON is retained for local development and Firestore import/backfill only.
Runtime stage/prod reads from Firestore.
---

# Product Notes — 2026-05-09

## Features

- **Inline translations** — example sentences on the learn page show a translation button when the UI language differs from the verb language
- **Demand-driven content loop** — search → signal → AI generation → admin preview → promotion; live regeneration in production
- **Full localization** — UI in EN / RU / HE / ES; ✓ seen · ★ known markers across the product
- **Language system** — adding a new language is config-driven; one entry, no scattered code
- **Home page** — Browse and Choose a verb are co-equal starting points; search has its own row
- **Learn page** — examples above conjugation tables; English split into Infinitive / Present / Past sections
- **Hebrew** — infinitive row (שם פועל) with audio; Browse sort label follows the verb language
- **Audio** — on-demand generation on first play (no silent failures for uncached forms); both voices pre-generated when a verb is added or regenerated
- **E2E tests** — navigation and user flow tests are hard deployment gates; stage → prod blocked on real flows

## Coming next

- Practice loop with completion badges
- Login and cross-device progress sync
- Expand language coverage
