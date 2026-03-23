# VerbBoard

Minimal verb learning app (FastAPI + server-rendered UI).

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

### Learn page
- Defaults to `female` voice if not specified
- Preserves:
  - language
  - voice
  - verb (when navigating back to Home)
- Shows:
  - conjugation board
  - examples with audio
- Voice selector available on page (updates instantly)

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
```

Hook installed at:

```
.git/hooks/pre-commit
```

---

## Notes
### 2026-03-23
- No database yet (stateless + local storage direction)
- Audio generated on demand and cached via backend
- Designed for fast iteration, not completeness
#### Upcoming (next step)
- Verb search from Home:
  - direct lookup by lemma
  - fallback: "not available yet"
  - logging missing verbs for admin
