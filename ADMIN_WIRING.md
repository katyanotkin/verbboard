# ── Add to app/main.py ────────────────────────────────────────────────────
#
# 1. Import the router (alongside your existing route imports):
#
#    from app.routes.admin import router as admin_router
#
# 2. Include it (no prefix here — the router carries its own secret prefix):
#
#    app.include_router(admin_router)
#
# That's it.  The page is served at:
#   https://yourdomain.com/<ADMIN_SECRET>/
#
# ── Add to .env (and .env.sample) ─────────────────────────────────────────
#
#   ADMIN_SECRET=pick-something-hard-to-guess
#
# Do NOT commit a real secret to .env.sample — keep the placeholder:
#   ADMIN_SECRET=
#
# ── Security note ─────────────────────────────────────────────────────────
# The secret path is "security through obscurity" — fine for an internal
# MVP tool, but not a substitute for proper auth if the app is public-facing.
# Upgrade to GCP IAP or a session cookie if/when needed.
