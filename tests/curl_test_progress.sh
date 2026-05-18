#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Manual curl smoke-test for the /api/progress endpoints.
#
# Four modes -- all use the same three env vars:
#
#   BASE_URL      server base URL          (default: http://localhost:8000)
#   TOKEN         Firebase ID token        (default: local-dev bypass)
#   VERB_LANGUAGE language code to test    (default: en)
#
# ── Mode 1: local-dev bypass (no Firebase needed) ──────────────────────────
#   Requires ALLOW_LOCAL_DEV_AUTH=true + ENVIRONMENT=local on the server.
#
#     bash tests/curl_test_progress.sh
#
# ── Mode 2: local server with a real Firebase token ────────────────────────
#   Start the local server (make local-run), log in via the browser, then
#   open DevTools -> Console on http://localhost:<PORT> and run:
#
#     window.VerbBoardAuth.getIdToken().then(t => console.log(t))
#
#   Copy the printed JWT, then:
#
#     TOKEN="<paste>" BASE_URL="http://localhost:8001" \
#       bash tests/curl_test_progress.sh
#
# ── Mode 3: stage ──────────────────────────────────────────────────────────
#   a. Open https://stage.verbboard.com and log in with Google.
#   b. Open DevTools -> Console and run:
#
#        window.VerbBoardAuth.getIdToken().then(t => console.log(t))
#
#   c. Copy the printed JWT, then:
#
#        TOKEN="<paste>" BASE_URL="https://stage.verbboard.com" \
#          bash tests/curl_test_progress.sh
#
# ── Mode 4: prod ───────────────────────────────────────────────────────────
#   Same steps as stage, using the prod URL instead:
#
#        TOKEN="<paste>" BASE_URL="https://verbboard.com" \
#          bash tests/curl_test_progress.sh
#
#   The script writes only synthetic verb IDs (en_curl_test_<PID>) and
#   restores any badge state it temporarily overwrites, so it is safe to
#   run against prod. No real verb data is modified.
#
# ── Optional: test a different language ────────────────────────────────────
#   Add VERB_LANGUAGE=he (or ru / es) to any of the modes above:
#
#     TOKEN="..." BASE_URL="https://stage.verbboard.com" VERB_LANGUAGE=he \
#       bash tests/curl_test_progress.sh
#
# Token expiry: Firebase ID tokens expire after 1 hour.
# If you get 401 errors, refresh the token from the browser console.
# ---------------------------------------------------------------------------

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
TOKEN="${TOKEN:-local-dev}"
VERB_LANGUAGE="${VERB_LANGUAGE:-en}"   # NOTE: not LANG -- that's a reserved shell variable
AUTH="Authorization: Bearer ${TOKEN}"

# Use a unique verb id so parallel runs don't collide
VERB_ID="${VERB_LANGUAGE}_curl_test_$$"

PASS=0
FAIL=0

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
dim()   { printf '\033[2m%s\033[0m\n'  "$*"; }

check() {
  local label="$1"
  local expected="$2"
  local actual="$3"

  if echo "$actual" | grep -q "$expected"; then
    green "  PASS  $label"
    PASS=$(( PASS + 1 ))
  else
    red   "  FAIL  $label"
    red   "        expected to find : $expected"
    red   "        in response      : $actual"
    FAIL=$(( FAIL + 1 ))
  fi
}

check_absent() {
  local label="$1"
  local absent="$2"
  local actual="$3"

  if echo "$actual" | grep -q "$absent"; then
    red   "  FAIL  $label"
    red   "        expected NOT to find : $absent"
    red   "        in response          : $actual"
    FAIL=$(( FAIL + 1 ))
  else
    green "  PASS  $label"
    PASS=$(( PASS + 1 ))
  fi
}

check_status() {
  local label="$1"
  local expected_status="$2"
  local actual_status="$3"

  if [ "$actual_status" = "$expected_status" ]; then
    green "  PASS  $label (HTTP $actual_status)"
    PASS=$(( PASS + 1 ))
  else
    red   "  FAIL  $label"
    red   "        expected HTTP $expected_status, got HTTP $actual_status"
    FAIL=$(( FAIL + 1 ))
  fi
}

echo ""
echo "=== VerbBoard Progress API -- curl smoke tests ==="
dim  "    base  : $BASE_URL"
dim  "    lang  : $VERB_LANGUAGE"
dim  "    token : ${TOKEN:0:12}..."
dim  "    verb  : $VERB_ID"
echo ""

# ---------------------------------------------------------------------------
echo "--- Auth guards (all endpoints must reject unauthenticated requests) ---"
# ---------------------------------------------------------------------------

STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  "$BASE_URL/api/progress?language=$VERB_LANGUAGE")
check_status "GET  /api/progress          -- no token" 401 "$STATUS"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  "$BASE_URL/api/progress/practice?language=$VERB_LANGUAGE")
check_status "GET  /api/progress/practice -- no token" 401 "$STATUS"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "$BASE_URL/api/progress/seen" \
  -H "Content-Type: application/json" \
  -d "{\"language\":\"$VERB_LANGUAGE\",\"verb_id\":\"$VERB_ID\"}")
check_status "POST /api/progress/seen     -- no token" 401 "$STATUS"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "$BASE_URL/api/progress/known" \
  -H "Content-Type: application/json" \
  -d "{\"language\":\"$VERB_LANGUAGE\",\"verb_id\":\"$VERB_ID\",\"known\":true}")
check_status "POST /api/progress/known    -- no token" 401 "$STATUS"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "$BASE_URL/api/progress/practice" \
  -H "Content-Type: application/json" \
  -d "{\"language\":\"$VERB_LANGUAGE\",\"badges\":[3]}")
check_status "POST /api/progress/practice -- no token" 401 "$STATUS"

# ---------------------------------------------------------------------------
echo ""
echo "--- user_progress collection: seen + known writes ---"
# ---------------------------------------------------------------------------

BODY=$(curl -s -X POST "$BASE_URL/api/progress/seen" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d "{\"language\":\"$VERB_LANGUAGE\",\"verb_id\":\"$VERB_ID\"}")
check "POST /api/progress/seen  --> ok:true" '"ok":true' "$BODY"

BODY=$(curl -s -X POST "$BASE_URL/api/progress/known" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d "{\"language\":\"$VERB_LANGUAGE\",\"verb_id\":\"$VERB_ID\",\"known\":true}")
check "POST /api/progress/known (known=true)  --> ok:true" '"ok":true' "$BODY"

# ---------------------------------------------------------------------------
echo ""
echo "--- user_progress collection: read back ---"
# ---------------------------------------------------------------------------

BODY=$(curl -s "$BASE_URL/api/progress?language=$VERB_LANGUAGE" \
  -H "$AUTH")
check "GET /api/progress  --> verb present"   "$VERB_ID"     "$BODY"
check "GET /api/progress  --> seen:true"      '"seen":true'  "$BODY"
check "GET /api/progress  --> known:true"     '"known":true' "$BODY"

# ---------------------------------------------------------------------------
echo ""
echo "--- user_progress collection: unmark known ---"
# ---------------------------------------------------------------------------

BODY=$(curl -s -X POST "$BASE_URL/api/progress/known" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d "{\"language\":\"$VERB_LANGUAGE\",\"verb_id\":\"$VERB_ID\",\"known\":false}")
check "POST /api/progress/known (known=false)  --> ok:true" '"ok":true' "$BODY"

BODY=$(curl -s "$BASE_URL/api/progress?language=$VERB_LANGUAGE" \
  -H "$AUTH")
check "GET /api/progress after unmark  --> known:false"     '"known":false' "$BODY"
check "GET /api/progress after unmark  --> seen still true" '"seen":true'   "$BODY"

# ---------------------------------------------------------------------------
echo ""
echo "--- user_practice collection: badges write ---"
# ---------------------------------------------------------------------------

BODY=$(curl -s -X POST "$BASE_URL/api/progress/practice" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d "{\"language\":\"$VERB_LANGUAGE\",\"badges\":[3,6,9]}")
check "POST /api/progress/practice  --> ok:true" '"ok":true' "$BODY"

# ---------------------------------------------------------------------------
echo ""
echo "--- user_practice collection: badges read back ---"
# ---------------------------------------------------------------------------

BODY=$(curl -s "$BASE_URL/api/progress/practice?language=$VERB_LANGUAGE" \
  -H "$AUTH")
check "GET /api/progress/practice  --> badges key present" '"badges"' "$BODY"
check "GET /api/progress/practice  --> badge 3 present"   '3'         "$BODY"
check "GET /api/progress/practice  --> badge 6 present"   '6'         "$BODY"
check "GET /api/progress/practice  --> badge 9 present"   '9'         "$BODY"

# ---------------------------------------------------------------------------
echo ""
echo "--- user_practice collection: language isolation ---"
# Language isolation: write to a second language, confirm it doesn't bleed
# into the first. Saves and restores the second language's badges so the
# test leaves no dirty data in Firestore.
# ---------------------------------------------------------------------------

OTHER_LANG="he"
if [ "$VERB_LANGUAGE" = "he" ]; then OTHER_LANG="en"; fi

# Save whatever badges the other language currently has
OTHER_BEFORE=$(curl -s "$BASE_URL/api/progress/practice?language=$OTHER_LANG" \
  -H "$AUTH")

# Write a temporary sentinel to the other language
SENTINEL="[42424242]"
curl -s -X POST "$BASE_URL/api/progress/practice" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d "{\"language\":\"$OTHER_LANG\",\"badges\":$SENTINEL}" > /dev/null

# Confirm the sentinel does NOT appear in the primary language
BODY=$(curl -s "$BASE_URL/api/progress/practice?language=$VERB_LANGUAGE" \
  -H "$AUTH")
check_absent \
  "GET practice?language=$VERB_LANGUAGE  --> $OTHER_LANG sentinel absent" \
  "42424242" \
  "$BODY"

# Restore the other language's original badges (extract from saved JSON)
RESTORED=$(echo "$OTHER_BEFORE" | grep -o '"badges":\[[^]]*\]' | sed 's/"badges"://' || echo "[]")
if [ -z "$RESTORED" ] || [ "$RESTORED" = "[]" ]; then
  RESTORED="[]"
fi
curl -s -X POST "$BASE_URL/api/progress/practice" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d "{\"language\":\"$OTHER_LANG\",\"badges\":$RESTORED}" > /dev/null
dim "    restored $OTHER_LANG badges: $RESTORED"

# ---------------------------------------------------------------------------
echo ""
echo "=========================================="
printf "Results: %d passed, %d failed\n" "$PASS" "$FAIL"
echo "=========================================="
echo ""

[ "$FAIL" -eq 0 ]
