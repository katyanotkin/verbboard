"""Tests for session tracking helpers.

Covers:
- get_fingerprint_sid: deterministic SHA256(ip|ua|date)[:32]; stable across
  calls, varies by IP / UA / date; uses X-Forwarded-For when present
- Everything below the fingerprint tests asserts on final Firestore state via
  the shared `fake_db` fixture (issue #8), not on call counts:
  - delete_sessions_for_uid: removes only the given uid's docs
  - _create_session: referrer captured on create, truncated, never touched by
    the AlreadyExists enrich path (set-once, like device_type); flags only
    flip false -> true
  - _enrich_lang / _attach_uid: merge semantics leave other fields alone
  - _record_sign_in_tap / _record_practice_* / _record_votd_clicked:
    validation and set-once-per-day behavior
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from unittest.mock import patch

from starlette.requests import Request

from core.analytics import session_tracker
from core.analytics.session_tracker import get_fingerprint_sid


def _run_async(coro):
    """Run an async coroutine in a fresh worker-thread event loop.

    Matches the pattern in tests/test_audio.py / tests/test_task_tracking.py:
    Playwright e2e tests can leave a running asyncio loop in the main thread,
    so asyncio.run() there would fail; a fresh thread has no loop.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


# ── request helper ─────────────────────────────────────────────────────────────


def _build_request(
    *,
    forwarded_for: str = "",
    user_agent: str = "",
    client_host: str = "127.0.0.1",
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    if user_agent:
        headers.append((b"user-agent", user_agent.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": headers,
        "client": (client_host, 12345),
    }
    return Request(scope)


# ── get_fingerprint_sid ────────────────────────────────────────────────────────


def test_fingerprint_is_32_hex_chars() -> None:
    req = _build_request(forwarded_for="1.2.3.4", user_agent="Mozilla/5.0")
    sid = get_fingerprint_sid(req, "2026-06-10")
    assert len(sid) == 32
    assert all(c in "0123456789abcdef" for c in sid)


def test_fingerprint_is_deterministic() -> None:
    req = _build_request(forwarded_for="1.2.3.4", user_agent="Mozilla/5.0")
    sid1 = get_fingerprint_sid(req, "2026-06-10")
    sid2 = get_fingerprint_sid(req, "2026-06-10")
    assert sid1 == sid2


def test_fingerprint_varies_by_date() -> None:
    req = _build_request(forwarded_for="1.2.3.4", user_agent="Mozilla/5.0")
    assert get_fingerprint_sid(req, "2026-06-10") != get_fingerprint_sid(req, "2026-06-11")


def test_fingerprint_varies_by_ip() -> None:
    ua = "Mozilla/5.0"
    date = "2026-06-10"
    req1 = _build_request(forwarded_for="1.2.3.4", user_agent=ua)
    req2 = _build_request(forwarded_for="5.6.7.8", user_agent=ua)
    assert get_fingerprint_sid(req1, date) != get_fingerprint_sid(req2, date)


def test_fingerprint_varies_by_user_agent() -> None:
    ip = "1.2.3.4"
    date = "2026-06-10"
    req1 = _build_request(forwarded_for=ip, user_agent="Chrome/120")
    req2 = _build_request(forwarded_for=ip, user_agent="Firefox/121")
    assert get_fingerprint_sid(req1, date) != get_fingerprint_sid(req2, date)


def test_fingerprint_uses_x_forwarded_for() -> None:
    """X-Forwarded-For takes precedence over request.client.host."""
    req_forwarded = _build_request(forwarded_for="203.0.113.1", user_agent="UA", client_host="10.0.0.1")
    req_direct = _build_request(forwarded_for="", user_agent="UA", client_host="10.0.0.1")
    # Different IPs in hash source -> different fingerprints
    assert get_fingerprint_sid(req_forwarded, "2026-06-10") != get_fingerprint_sid(req_direct, "2026-06-10")


def test_fingerprint_uses_first_forwarded_ip() -> None:
    """Takes only the first IP from a comma-separated X-Forwarded-For header."""
    req_single = _build_request(forwarded_for="1.2.3.4", user_agent="UA")
    req_chain = _build_request(forwarded_for="1.2.3.4, 10.0.0.1, 172.16.0.1", user_agent="UA")
    assert get_fingerprint_sid(req_single, "2026-06-10") == get_fingerprint_sid(req_chain, "2026-06-10")


def test_fingerprint_falls_back_to_client_host() -> None:
    """When no X-Forwarded-For, uses request.client.host."""
    req = _build_request(forwarded_for="", user_agent="UA", client_host="192.168.1.1")
    sid = get_fingerprint_sid(req, "2026-06-10")
    assert len(sid) == 32


COLLECTION = session_tracker.COLLECTION
DATE = "2026-09-16"
DOC = f"{COLLECTION}/{DATE}_fp1"


def _seed(fake_db, fingerprint: str = "fp1", **fields) -> str:
    path = f"{COLLECTION}/{DATE}_{fingerprint}"
    fake_db._docs[path] = dict(fields)
    return path


# ── delete_sessions_for_uid ─────────────────────────────────────────────────────
#
# Sessions are keyed by (ip, ua, date) fingerprint, not uid, so this is a
# query -- unlike every other uid-keyed deletion in this codebase (part of
# account_deletion.delete_account()).


def test_delete_sessions_for_uid_removes_only_that_users_sessions(fake_db) -> None:
    a1 = _seed(fake_db, "a1", uid="A")
    a2 = _seed(fake_db, "a2", uid="A")
    b1 = _seed(fake_db, "b1", uid="B")
    anon = _seed(fake_db, "anon", uid=None)

    session_tracker.delete_sessions_for_uid("A")

    assert a1 not in fake_db._docs
    assert a2 not in fake_db._docs
    assert b1 in fake_db._docs
    assert anon in fake_db._docs


# ── _create_session ─────────────────────────────────────────────────────────
#
# referrer is set-once at session creation, mirroring device_type: it
# identifies the traffic source of the *first* hit that opened the session,
# so a later request for the same (ip, ua, day) fingerprint must never
# overwrite it.


def test_create_session_writes_initial_document(fake_db) -> None:
    session_tracker._create_session("fp1", DATE, "mobile", "es", "en", False, "https://google.com/search")

    doc = fake_db._docs[DOC]
    assert doc["referrer"] == "https://google.com/search"
    assert doc["device_type"] == "mobile"
    assert doc["uid"] is None
    assert doc["verb_viewed"] is False


def test_create_session_truncates_long_referrer(fake_db) -> None:
    long_referrer = "https://example.com/?q=" + ("a" * 600)

    session_tracker._create_session("fp1", DATE, "mobile", "es", "en", False, long_referrer)

    assert fake_db._docs[DOC]["referrer"] == long_referrer[: session_tracker._MAX_REFERRER_LEN]


def test_create_session_blank_referrer_stored_as_empty_string(fake_db) -> None:
    session_tracker._create_session("fp1", DATE, "mobile", "es", "en", False, "")

    assert fake_db._docs[DOC]["referrer"] == ""


def test_second_hit_enriches_but_never_overwrites_set_once_fields(fake_db) -> None:
    """A second hit for the same fingerprint/day enriches language/ui_lang and
    flips verb_viewed, but must not clobber referrer, device_type or uid."""
    session_tracker._create_session("fp1", DATE, "mobile", "", "", False, "https://first.example.com")
    fake_db._docs[DOC]["uid"] = "u1"

    session_tracker._create_session("fp1", DATE, "desktop", "es", "en", True, "https://second.example.com")

    doc = fake_db._docs[DOC]
    assert doc["referrer"] == "https://first.example.com"
    assert doc["device_type"] == "mobile"
    assert doc["uid"] == "u1"
    assert (doc["language"], doc["ui_lang"], doc["verb_viewed"]) == ("es", "en", True)


def test_verb_viewed_never_flips_back_to_false(fake_db) -> None:
    session_tracker._create_session("fp1", DATE, "mobile", "es", "en", True, "")

    session_tracker._create_session("fp1", DATE, "mobile", "es", "en", False, "")

    assert fake_db._docs[DOC]["verb_viewed"] is True


def test_second_hit_with_blank_language_keeps_existing_language(fake_db) -> None:
    session_tracker._create_session("fp1", DATE, "mobile", "es", "en", False, "")

    session_tracker._create_session("fp1", DATE, "mobile", "", "", False, "")

    assert (fake_db._docs[DOC]["language"], fake_db._docs[DOC]["ui_lang"]) == ("es", "en")


def test_create_session_swallows_firestore_errors() -> None:
    with patch("core.storage.firestore_db.get_db", side_effect=RuntimeError("boom")):
        session_tracker._create_session("fp1", DATE, "mobile", "es", "en")  # must not raise


# ── _enrich_lang / _attach_uid: merge semantics ─────────────────────────────


def test_enrich_lang_merges_without_dropping_other_fields(fake_db) -> None:
    _seed(fake_db, uid="u1", referrer="r", verb_viewed=True)

    session_tracker._enrich_lang("fp1", DATE, "he", "ru")

    doc = fake_db._docs[DOC]
    assert (doc["language"], doc["ui_lang"]) == ("he", "ru")
    assert (doc["uid"], doc["referrer"], doc["verb_viewed"]) == ("u1", "r", True)


def test_attach_uid_sets_uid_and_keeps_other_fields(fake_db) -> None:
    _seed(fake_db, uid=None, language="es", referrer="r")

    session_tracker._attach_uid("fp1", DATE, "u1")

    doc = fake_db._docs[DOC]
    assert doc["uid"] == "u1"
    assert (doc["language"], doc["referrer"]) == ("es", "r")


# ── _record_sign_in_tap ─────────────────────────────────────────────────────


def test_record_sign_in_tap_writes_valid_branch(fake_db) -> None:
    _seed(fake_db, device_type="mobile")

    session_tracker._record_sign_in_tap("fp1", DATE, "mobile")

    doc = fake_db._docs[DOC]
    assert doc["sign_in_tapped_branch"] == "mobile"
    assert "sign_in_tapped_at" in doc
    assert doc["device_type"] == "mobile"


def test_record_sign_in_tap_rejects_invalid_branch(fake_db) -> None:
    session_tracker._record_sign_in_tap("fp1", DATE, "tablet")

    assert fake_db._docs == {}


def test_record_sign_in_tap_is_set_once_per_day(fake_db) -> None:
    """A second tap (e.g. after dismissing the account chooser) must not
    overwrite the branch recorded by the first tap of the day."""
    session_tracker._record_sign_in_tap("fp1", DATE, "mobile")

    session_tracker._record_sign_in_tap("fp1", DATE, "desktop")

    assert fake_db._docs[DOC]["sign_in_tapped_branch"] == "mobile"


# ── _record_practice_started / _record_practice_completed (issue #48) ──────
#
# Auth-independent practice engagement signal on analytics_sessions. Both
# fields are set-once-per-day, mirroring _record_sign_in_tap, but unlike the
# sign-in-tap branch field there's no allowlist to validate (the route layer
# already restricts to _VALID_PRACTICE_EVENTS before calling these).


def test_record_practice_started_sets_flag_and_is_idempotent(fake_db) -> None:
    _seed(fake_db, device_type="mobile")

    session_tracker._record_practice_started("fp1", DATE)
    session_tracker._record_practice_started("fp1", DATE)

    assert fake_db._docs[DOC] == {"device_type": "mobile", "practice_started": True}


def test_record_practice_completed_sets_flag_and_is_idempotent(fake_db) -> None:
    _seed(fake_db, device_type="mobile")

    session_tracker._record_practice_completed("fp1", DATE)
    session_tracker._record_practice_completed("fp1", DATE)

    assert fake_db._docs[DOC] == {"device_type": "mobile", "practice_completed": True}


def test_record_practice_completed_does_not_require_practice_started(fake_db) -> None:
    """practice_completed is independently gated on its own field only --
    it must write fine even when practice_started was never set for this
    session-day (e.g. the started beacon was lost to a flaky network)."""
    _seed(fake_db)

    session_tracker._record_practice_completed("fp1", DATE)

    assert fake_db._docs[DOC] == {"practice_completed": True}


def test_practice_started_and_completed_do_not_affect_each_other(fake_db) -> None:
    _seed(fake_db, practice_completed=True)

    session_tracker._record_practice_started("fp1", DATE)

    assert fake_db._docs[DOC] == {"practice_completed": True, "practice_started": True}


# ── _record_votd_clicked ────────────────────────────────────────────────────


def test_record_votd_clicked_sets_flag_on_existing_session(fake_db) -> None:
    _seed(fake_db, home_viewed=True)

    session_tracker._record_votd_clicked("fp1", DATE)

    assert fake_db._docs[DOC] == {"home_viewed": True, "votd_clicked": True}


def test_record_votd_clicked_without_session_creates_no_stub_doc(fake_db) -> None:
    """A click landing after a UTC date rollover has no session doc; writing
    would create a stub without device_type/language that skews usage stats."""
    session_tracker._record_votd_clicked("fp1", DATE)

    assert fake_db._docs == {}


# ── async fire-and-forget wrappers ──────────────────────────────────────────


def test_async_wrappers_actually_run_their_sync_helpers(fake_db) -> None:
    """The route handlers call the async wrappers; confirm each schedules and
    completes its sync helper (a task never awaited would leave no state)."""
    _seed(fake_db, home_viewed=True)

    async def _scenario() -> None:
        await session_tracker.record_sign_in_tap("fp1", DATE, "standalone")
        await session_tracker.record_practice_started("fp1", DATE)
        await session_tracker.record_practice_completed("fp1", DATE)
        await session_tracker.record_votd_clicked("fp1", DATE)
        await session_tracker.enrich_lang("fp1", DATE, "es", "en")
        await session_tracker.attach_uid("fp1", DATE, "u1")
        for task in list(session_tracker._pending):
            await task

    _run_async(_scenario())

    doc = fake_db._docs[DOC]
    assert doc["sign_in_tapped_branch"] == "standalone"
    assert doc["practice_started"] is True
    assert doc["practice_completed"] is True
    assert doc["votd_clicked"] is True
    assert (doc["language"], doc["ui_lang"], doc["uid"]) == ("es", "en", "u1")
