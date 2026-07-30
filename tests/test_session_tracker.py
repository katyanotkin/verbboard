"""Tests for session tracking helpers.

Covers:
- get_fingerprint_sid: deterministic SHA256(ip|ua|date)[:32]; stable across
  calls, varies by IP / UA / date; uses X-Forwarded-For when present
- delete_sessions_for_uid: query-and-delete-by-uid, used by account deletion
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from starlette.requests import Request

from core.analytics import session_tracker
from core.analytics.session_tracker import get_fingerprint_sid

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
