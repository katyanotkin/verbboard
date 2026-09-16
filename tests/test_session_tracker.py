"""Tests for session tracking helpers.

Covers:
- get_fingerprint_sid: deterministic SHA256(ip|ua|date)[:32]; stable across
  calls, varies by IP / UA / date; uses X-Forwarded-For when present
- delete_sessions_for_uid: query-and-delete-by-uid, used by account deletion
- _create_session: referrer captured on create, truncated at 500 chars, and
  never touched by the AlreadyExists enrich path (set-once, like device_type)
- _record_sign_in_tap: valid-branch allowlist, set-once-per-day behavior
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from unittest.mock import MagicMock, patch

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


# ── delete_sessions_for_uid ─────────────────────────────────────────────────────
#
# Sessions are keyed by (ip, ua, date) fingerprint, not uid, so this is a
# query -- unlike every other uid-keyed deletion in this codebase (part of
# account_deletion.delete_account()).


def test_delete_sessions_for_uid_queries_by_uid_and_deletes_matches() -> None:
    doc1 = MagicMock()
    doc2 = MagicMock()
    db = MagicMock()
    db.collection.return_value.where.return_value.stream.return_value = iter([doc1, doc2])

    with patch("core.storage.firestore_db.get_db", return_value=db):
        session_tracker.delete_sessions_for_uid("u1")

    db.collection.assert_called_with(session_tracker.COLLECTION)
    db.collection.return_value.where.assert_called_with("uid", "==", "u1")
    doc1.reference.delete.assert_called_once()
    doc2.reference.delete.assert_called_once()


def test_delete_sessions_for_uid_no_matches_is_a_noop() -> None:
    db = MagicMock()
    db.collection.return_value.where.return_value.stream.return_value = iter([])

    with patch("core.storage.firestore_db.get_db", return_value=db):
        session_tracker.delete_sessions_for_uid("u1")  # must not raise


# ── _create_session: referrer capture ───────────────────────────────────────
#
# referrer is set-once at session creation, mirroring device_type: it
# identifies the traffic source of the *first* hit that opened the session,
# so a later request for the same (ip, ua, day) fingerprint must never
# overwrite it.


def test_create_session_writes_referrer_on_create() -> None:
    db = MagicMock()

    with patch("core.storage.firestore_db.get_db", return_value=db):
        session_tracker._create_session("fp1", "2026-09-16", "mobile", "es", "en", False, "https://google.com/search")

    doc_ref = db.collection.return_value.document.return_value
    doc_ref.create.assert_called_once()
    written = doc_ref.create.call_args.args[0]
    assert written["referrer"] == "https://google.com/search"


def test_create_session_truncates_long_referrer() -> None:
    db = MagicMock()
    long_referrer = "https://example.com/?q=" + ("a" * 600)

    with patch("core.storage.firestore_db.get_db", return_value=db):
        session_tracker._create_session("fp1", "2026-09-16", "mobile", "es", "en", False, long_referrer)

    doc_ref = db.collection.return_value.document.return_value
    written = doc_ref.create.call_args.args[0]
    assert len(written["referrer"]) == session_tracker._MAX_REFERRER_LEN
    assert written["referrer"] == long_referrer[: session_tracker._MAX_REFERRER_LEN]


def test_create_session_blank_referrer_stored_as_empty_string() -> None:
    db = MagicMock()

    with patch("core.storage.firestore_db.get_db", return_value=db):
        session_tracker._create_session("fp1", "2026-09-16", "mobile", "es", "en", False, "")

    doc_ref = db.collection.return_value.document.return_value
    written = doc_ref.create.call_args.args[0]
    assert written["referrer"] == ""


def test_create_session_already_exists_does_not_write_referrer() -> None:
    """Second call for the same fingerprint/day (AlreadyExists) enriches
    language/ui_lang/verb_viewed only -- referrer must never appear in the
    enrich payload, regardless of what referrer the second call carried, so
    the originally captured value can never be clobbered."""
    from google.api_core.exceptions import AlreadyExists

    db = MagicMock()
    doc_ref = db.collection.return_value.document.return_value
    doc_ref.create.side_effect = AlreadyExists("already exists")

    with patch("core.storage.firestore_db.get_db", return_value=db):
        session_tracker._create_session(
            "fp1", "2026-09-16", "mobile", "es", "en", True, "https://second-referrer.example.com"
        )

    doc_ref.set.assert_called_once()
    update_payload = doc_ref.set.call_args.args[0]
    assert "referrer" not in update_payload
    assert update_payload["language"] == "es"
    assert update_payload["ui_lang"] == "en"
    assert update_payload["verb_viewed"] is True


# ── _record_sign_in_tap / record_sign_in_tap ────────────────────────────────


def test_record_sign_in_tap_writes_valid_branch() -> None:
    db = MagicMock()
    doc_ref = db.collection.return_value.document.return_value
    doc_ref.get.return_value.exists = False

    with patch("core.storage.firestore_db.get_db", return_value=db):
        session_tracker._record_sign_in_tap("fp1", "2026-09-16", "mobile")

    doc_ref.set.assert_called_once()
    payload = doc_ref.set.call_args.args[0]
    assert payload["sign_in_tapped_branch"] == "mobile"
    assert "sign_in_tapped_at" in payload


def test_record_sign_in_tap_rejects_invalid_branch() -> None:
    db = MagicMock()

    with patch("core.storage.firestore_db.get_db", return_value=db):
        session_tracker._record_sign_in_tap("fp1", "2026-09-16", "tablet")

    db.collection.assert_not_called()


def test_record_sign_in_tap_is_set_once_per_day() -> None:
    """A second tap (e.g. after dismissing the account chooser) must not
    overwrite the branch recorded by the first tap of the day."""
    db = MagicMock()
    doc_ref = db.collection.return_value.document.return_value
    doc_ref.get.return_value.exists = True
    doc_ref.get.return_value.to_dict.return_value = {"sign_in_tapped_branch": "mobile"}

    with patch("core.storage.firestore_db.get_db", return_value=db):
        session_tracker._record_sign_in_tap("fp1", "2026-09-16", "desktop")

    doc_ref.set.assert_not_called()


def test_record_sign_in_tap_async_wrapper_schedules_and_awaits() -> None:
    """record_sign_in_tap() is the fire-and-forget async wrapper the route
    handler calls; confirm it actually runs the sync helper (not just
    schedules a task that's never awaited by the test)."""
    db = MagicMock()
    doc_ref = db.collection.return_value.document.return_value
    doc_ref.get.return_value.exists = False

    async def _scenario() -> None:
        await session_tracker.record_sign_in_tap("fp1", "2026-09-16", "standalone")
        # Wait for the fire-and-forget task to actually finish running.
        for task in list(session_tracker._pending):
            await task

    with patch("core.storage.firestore_db.get_db", return_value=db):
        _run_async(_scenario())

    doc_ref.set.assert_called_once()
    payload = doc_ref.set.call_args.args[0]
    assert payload["sign_in_tapped_branch"] == "standalone"
