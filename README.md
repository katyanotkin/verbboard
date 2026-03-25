# VerbBoard

Minimal verb learning app (FastAPI + server-rendered UI).
Focused on fast iteration and simple learning flow:
get a verb → see it → hear it → move on.

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
- Select:
  - language (`en`, `ru`, `he`, `es`)
  - verb
  - voice (`female`, `male`)
- Click **Learn** to open the learning view
Or search for a verb (see below)
Visual indicators:
✓ seen verbs
★ known verbs
Progress bar shows known verbs count

#### Search
Search accepts:
-- infinitives
-- conjugated forms
-- partial matches
Behavior:
-- first matching verb is opened directly
-- no results list (fast resolution)
-- If no match:
--- shows: "No match in the current set"
--- logs query for future expansion

### Learn page
- Displays:
  - conjugation board
  - examples with audio
- Controls
  - voice toggle (female / male; female set as default)
  - * mark verb as known
  - back to verb list
- Behavior:
  - known updates progress
  - Preserves:
    - language
    - voice
    - verb (when navigating back to Home)



#### Direct verb access
Open a specific verb:
http://127.0.0.1:8000/learn?language=es&verb_id=es_tener&voice=female


## State persistence

- Language and voice persist via cookies
- Returning to Home keeps last selected values
- Learn page maintains current context



## Development

### Pre-commit linting

```bash
pip install pre-commit
pre-commit --version
pre-commit install
pre-commit run --all-files
```

Hook installed at:

```
.git/hooks/pre-commit
```

---

## Notes
### 2026-03-25

- Stateless architecture (no DB; browser `localStorage` for progress)
- Audio generated on demand and cached via backend
- Search supports conjugated forms (intent-based match, first hit wins)
- Missing searches logged for future verb expansion
- Learning loop introduced:
  - `seen` (✓)
  - `known` (★)
- No backend personalization

### Upcoming

- Database-backed lexicon
- Ingestion pipeline for adding new verbs
