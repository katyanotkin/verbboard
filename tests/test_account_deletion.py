"""
Unit tests for core/account_deletion.py -- the self-serve account deletion
orchestrator.

This is the "cheap insurance against a future refactor silently dropping a
step" test the code review asked for: `delete_account` is uniquely
irreversible (data gone, auth account gone), so the order and completeness
of its four sub-calls is pinned here rather than only covered indirectly via
the route test.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from firebase_admin.auth import UserNotFoundError

from core import account_deletion

# ---------------------------------------------------------------------------
# delete_account -- all four steps called, in order: data first, auth last
# ---------------------------------------------------------------------------


def test_delete_account_calls_all_four_steps_exactly_once() -> None:
    with (
        patch.object(account_deletion, "delete_all_progress_data") as mock_progress,
        patch.object(account_deletion, "delete_entitlement") as mock_entitlement,
        patch.object(account_deletion, "delete_sessions_for_uid") as mock_sessions,
        patch.object(account_deletion, "_delete_auth_user") as mock_auth,
    ):
        account_deletion.delete_account("u1")

    mock_progress.assert_called_once_with("u1")
    mock_entitlement.assert_called_once_with("u1")
    mock_sessions.assert_called_once_with("u1")
    mock_auth.assert_called_once_with("u1")


def test_delete_account_order_is_data_deletions_then_auth_account_last() -> None:
    """Pins the exact order: progress -> entitlement -> sessions -> auth.

    A future refactor that reorders these (e.g. deleting the auth account
    before Firestore cleanup finishes) would strand a uid's data with no way
    for the user to sign back in and retry -- this is the specific
    "silently dropping/reordering a step" risk the code review flagged.
    """
    order: list[str] = []

    with (
        patch.object(account_deletion, "delete_all_progress_data", side_effect=lambda uid: order.append("progress")),
        patch.object(account_deletion, "delete_entitlement", side_effect=lambda uid: order.append("entitlement")),
        patch.object(account_deletion, "delete_sessions_for_uid", side_effect=lambda uid: order.append("sessions")),
        patch.object(account_deletion, "_delete_auth_user", side_effect=lambda uid: order.append("auth")),
    ):
        account_deletion.delete_account("u1")

    assert order == ["progress", "entitlement", "sessions", "auth"]


def test_delete_account_propagates_a_failed_step_and_stops_the_pipeline() -> None:
    """If a data-deletion step raises, later steps (including the
    irreversible auth-account delete) must not run."""
    with (
        patch.object(account_deletion, "delete_all_progress_data", side_effect=RuntimeError("firestore down")),
        patch.object(account_deletion, "delete_entitlement") as mock_entitlement,
        patch.object(account_deletion, "delete_sessions_for_uid") as mock_sessions,
        patch.object(account_deletion, "_delete_auth_user") as mock_auth,
    ):
        with pytest.raises(RuntimeError):
            account_deletion.delete_account("u1")

    mock_entitlement.assert_not_called()
    mock_sessions.assert_not_called()
    mock_auth.assert_not_called()


# ---------------------------------------------------------------------------
# _delete_auth_user
# ---------------------------------------------------------------------------


def test_delete_auth_user_calls_firebase_delete_user() -> None:
    with (
        patch("core.auth.firebase_auth.initialize_firebase_admin"),
        patch("firebase_admin.auth.delete_user") as mock_delete_user,
    ):
        account_deletion._delete_auth_user("u1")

    mock_delete_user.assert_called_once_with("u1")


def test_delete_auth_user_swallows_user_not_found() -> None:
    """Dev-bypass uids and already-removed Firebase accounts must not raise --
    the data deletion already ran, there's nothing left to clean up."""
    with (
        patch("core.auth.firebase_auth.initialize_firebase_admin"),
        patch("firebase_admin.auth.delete_user", side_effect=UserNotFoundError("no such user")),
    ):
        account_deletion._delete_auth_user("local-dev-user")  # must not raise


def test_delete_auth_user_does_not_swallow_other_errors() -> None:
    """Only UserNotFoundError is expected/benign; any other Firebase Auth
    failure must propagate rather than being silently absorbed."""
    with (
        patch("core.auth.firebase_auth.initialize_firebase_admin"),
        patch("firebase_admin.auth.delete_user", side_effect=RuntimeError("boom")),
    ):
        with pytest.raises(RuntimeError):
            account_deletion._delete_auth_user("u1")
