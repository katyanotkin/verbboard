# /perf — VerbBoard Performance Audit

Measure and report performance of stage or prod, then identify bottlenecks and improvements.

## What to measure

For each key page (home, verbs per language, learn per language, about):
- TTFB and total time via `curl -s -o /dev/null -w "..."` — 3 passes to see variance
- Response size
- HTTP caching headers (`Cache-Control`, `ETag`, `Last-Modified`, `content-encoding`)
- Static asset headers (CSS, JS served by Starlette StaticFiles)

For learn page specifically:
- Cold prewarm (first hit on a rarely-accessed verb) vs warm
- Whether `asyncio.gather(*tasks)` blocks the HTML response

For navigation flows:
- Check for `<link rel="prefetch">` hints in HTML/JS
- Check verbs.js for hover-prefetch logic
- Check if Firestore queries are cached in-process

## Baselines (2026-05-09, verbboard.com prod)

| Page | TTFB warm | Notes |
|------|-----------|-------|
| Home | 0.10-0.19s | |
| Verbs | ~0.17s | Firestore scan every request |
| Learn warm | 0.10-0.15s | prewarm cache hit |
| Learn cold | 0.5-0.7s | first visit, GCS list_blobs |

## Baselines (2026-05-10, stage.verbboard.com)

| Page | TTFB warm | Notes |
|------|-----------|-------|
| Home | 0.15-0.19s | |
| Verbs (en) | 0.19-0.20s | Firestore scan every request |
| Verbs (ru/he/es) | 0.15-0.21s | same |
| Learn warm (en_go) | 0.16-0.25s | prewarm cache hit |
| Learn cold (en_work, en_call) | 0.54-0.67s | GCS list_blobs cold |
| About | 0.13s | |

## Known issues found

1. **Static assets: no Cache-Control max-age** — only ETag. Browser must revalidate on every navigation (3 conditional GET round trips). Fix: add `Cache-Control: max-age=86400` via custom StaticFiles subclass.
2. **Verbs page: Firestore query on every request** — no in-process cache. 150-200ms overhead per hit. Fix: in-process TTL cache (60s).
3. **Learn page: HTML blocked by audio tasks** — `asyncio.gather(*tasks)` awaits all ensure_audio before returning HTML. New-verb cold load can be slow if TTS needed. Fix: fire tasks in background after response.
4. **No prefetch hints** — navigating Home -> Verbs or Verbs -> Learn is always a cold navigation. Fix: `<link rel="prefetch">` for verbs page in home, hover-prefetch in verbs.js.
5. **No gzip/brotli** on HTML or static assets.

## Workflow

1. `curl` measurements (3 passes) for all pages
2. Check cache headers with `curl -s -D - <url> -o /dev/null`
3. Read `app/routes/verbs.py`, `app/routes/learn.py`, `core/verb_loader.py`, `app/main.py`
4. Read relevant JS files in `app/static/`
5. Report with table + numbered issue list
