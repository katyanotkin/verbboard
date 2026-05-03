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

# Product Notes — 2026-05-03

## Product evolution

- Demand-driven loop now fully operational and editable:
  search → signal → generation → preview → promotion
- Direct live verb regeneration in production (no pipeline friction)
- Admin evolved into a content control layer, not just a moderation UI
- Feedback, demand signals, and analytics now form a closed product loop

## Language system _(major milestone)_

Language configuration fully centralized into a single source of truth.

Eliminated duplication across: routes, plugins, UI labels, language selectors.

The system now guarantees:
- consistent display (names, native forms, RTL)
- no drift between UI and backend
- adding a new language is config-driven, not code-scattered

> **Product implication:** scaling beyond 4 languages is now operationally trivial.

## UX / behavior

- Full UI localization stabilized (EN / RU / HE / ES)
- Introduced consistent learning markers: ✓ seen · ★ known — standardized across the product
- Added visual legend + unified icon system
- UI components standardized (buttons, badges, feedback flows)

## AI / generation

- AI is now part of live content operations, not just batch generation
- Regeneration allows: correcting bad verbs instantly, iterating on prompts without pipeline delay
- RU generation quality improved: correct aspect/tense mapping, expanded grammatical coverage (edge cases enforced)

## Data & modeling

- Firestore fully established as runtime source of truth
- Lexicon JSON downgraded to: local dev, import/backfill only
- Demand + feedback now include contextual metadata (device, page, source)

## Testing & release discipline

- E2E tests + navigation smoke tests are now hard deployment gates
- Stage → prod promotion is blocked on real user flows
- Test suite covers: navigation integrity, feedback loop correctness, state retention & security edge cases

---

## System direction

The product has shifted from a **static learning tool** to a **self-evolving system** driven by real user demand, with live-editable content and scalable language support.

**Upcoming:**
- Guided practice sets (first real retention layer)
- Personalization (only if it preserves simplicity)
- Expand language coverage (now unblocked by architecture)

---

_The system is no longer just generating content — it can now adapt, correct, and scale itself in real time._
