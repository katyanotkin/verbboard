---
name: verify
description: How to launch and drive VerbBoard locally for runtime verification of changes.
---

# Verifying VerbBoard changes at runtime

## Launch

`make local-run` fails in agent shells (`python: not found` — Makefile uses bare `python`). Use the venv directly:

```bash
set -a && . ./.env && set +a && ./.venv/bin/python -m uvicorn app.main:app --port 8001 > /tmp/server.log 2>&1 &
curl -s http://localhost:8001/health   # 200 when up (~8s)
```

`HOST_PORT` in `.env` is the usual port; any free port works when passed explicitly.

## API surface

`.env` has `ALLOW_LOCAL_DEV_AUTH=true`, so authenticated `/api/progress/*` endpoints accept `Authorization: Bearer local-dev` — no Firebase token needed locally.

## Browser surface

Playwright (sync API) from the venv works headless. Effective pattern for progress/practice features: `goto` the page once, seed localStorage via `page.evaluate` (keys like `practice_streak:{lang}`, `practice_wrapup:{lang}`, `known:{lang}`), then `goto` again and assert on rendered DOM / screenshot. Use viewport 375x700 for the mobile check (project memory requires it), and `?language=he&ui_language=he` for the RTL pass.

Real Firestore is hit locally (no emulator) — use throwaway language codes or far-future dates for seeded server state to stay deterministic.

## Gotchas

- Server logs → whatever file you redirected to; Firestore latency makes `networkidle` flaky, prefer `domcontentloaded` + short `wait_for_timeout`.
- Practice completion (`_finishPractice`) requires N real audio plays per verb — driving it live is slow/flaky; verify its pieces at the API (POST merge) and seeded-localStorage (display) surfaces instead.
