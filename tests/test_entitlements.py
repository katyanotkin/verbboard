"""Unit tests for core/entitlements.py -- the Plus entitlement gate.

Phase 1 uses a manually-set admin flag (user_entitlements/{uid}.status) as
the entitlement source. FREE_STUDY_LANGUAGES currently covers every
registered language (en/ru/he/es), so requires_entitlement() is False for
all of them today -- this file also pins that "zero behavioral effect in
production right now" invariant.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from core import entitlements
from core.languages.config import FREE_STUDY_LANGUAGES


@pytest.fixture(autouse=True)
def _clear_entitlement_cache():
    entitlements._entitlement_cache.clear()
    yield
    entitlements._entitlement_cache.clear()


def _mock_db_with_doc(exists: bool, data: dict | None = None) -> MagicMock:
    doc = MagicMock()
    doc.exists = exists
    doc.to_dict.return_value = data or {}

    doc_ref = MagicMock()
    doc_ref.get.return_value = doc

    collection = MagicMock()
    collection.document.return_value = doc_ref

    db = MagicMock()
    db.collection.return_value = collection
    return db


# ---------------------------------------------------------------------------
# requires_entitlement
# ---------------------------------------------------------------------------


def test_requires_entitlement_false_for_all_current_free_languages() -> None:
    """Pins today's zero-behavioral-effect invariant: every registered
    language (en/ru/he/es) is in FREE_STUDY_LANGUAGES."""
    assert set(FREE_STUDY_LANGUAGES) == {"en", "ru", "he", "es"}
    for lang in FREE_STUDY_LANGUAGES:
        assert entitlements.requires_entitlement(lang) is False


def test_requires_entitlement_true_for_unregistered_plus_language() -> None:
    assert entitlements.requires_entitlement("it") is True
    assert entitlements.requires_entitlement("fr") is True


# ---------------------------------------------------------------------------
# has_plus_entitlement
# ---------------------------------------------------------------------------


def test_has_plus_entitlement_false_when_no_document() -> None:
    db = _mock_db_with_doc(exists=False)
    with patch.object(entitlements, "get_db", return_value=db):
        assert entitlements.has_plus_entitlement("u1") is False


def test_has_plus_entitlement_true_when_active_no_expiry() -> None:
    db = _mock_db_with_doc(exists=True, data={"status": "active", "expires_at": None})
    with patch.object(entitlements, "get_db", return_value=db):
        assert entitlements.has_plus_entitlement("u1") is True


def test_has_plus_entitlement_true_when_active_and_not_yet_expired() -> None:
    future = datetime.now(UTC) + timedelta(days=1)
    db = _mock_db_with_doc(exists=True, data={"status": "active", "expires_at": future})
    with patch.object(entitlements, "get_db", return_value=db):
        assert entitlements.has_plus_entitlement("u1") is True


def test_has_plus_entitlement_false_when_active_but_expired() -> None:
    past = datetime.now(UTC) - timedelta(days=1)
    db = _mock_db_with_doc(exists=True, data={"status": "active", "expires_at": past})
    with patch.object(entitlements, "get_db", return_value=db):
        assert entitlements.has_plus_entitlement("u1") is False


@pytest.mark.parametrize("status", ["revoked", "expired", "none"])
def test_has_plus_entitlement_false_for_non_active_status(status: str) -> None:
    db = _mock_db_with_doc(exists=True, data={"status": status})
    with patch.object(entitlements, "get_db", return_value=db):
        assert entitlements.has_plus_entitlement("u1") is False


def test_has_plus_entitlement_is_cached_within_ttl() -> None:
    db = _mock_db_with_doc(exists=True, data={"status": "active"})
    with patch.object(entitlements, "get_db", return_value=db):
        assert entitlements.has_plus_entitlement("u1") is True
        assert entitlements.has_plus_entitlement("u1") is True
    # Only one Firestore read despite two calls within the TTL window.
    assert db.collection.return_value.document.return_value.get.call_count == 1


def test_invalidate_entitlement_cache_forces_a_fresh_read() -> None:
    db = _mock_db_with_doc(exists=True, data={"status": "active"})
    with patch.object(entitlements, "get_db", return_value=db):
        assert entitlements.has_plus_entitlement("u1") is True
        entitlements.invalidate_entitlement_cache("u1")
        assert entitlements.has_plus_entitlement("u1") is True
    assert db.collection.return_value.document.return_value.get.call_count == 2


def test_has_plus_entitlement_fails_open_with_no_cache_on_firestore_error() -> None:
    with patch.object(entitlements, "get_db", side_effect=RuntimeError("boom")):
        assert entitlements.has_plus_entitlement("u1") is True


def test_has_plus_entitlement_fails_open_to_stale_cache_on_firestore_error() -> None:
    db = _mock_db_with_doc(exists=True, data={"status": "revoked"})
    with patch.object(entitlements, "get_db", return_value=db):
        assert entitlements.has_plus_entitlement("u1") is False  # populate cache with a real (negative) result

    with patch.object(entitlements, "get_db", side_effect=RuntimeError("boom")):
        # Firestore is down, but we have a cached value -- serve it stale
        # rather than failing open, since we know it's actually revoked.
        assert entitlements.has_plus_entitlement("u1") is False


# ---------------------------------------------------------------------------
# can_study
# ---------------------------------------------------------------------------


def test_can_study_true_for_free_language_regardless_of_uid() -> None:
    assert entitlements.can_study("en", None) is True
    assert entitlements.can_study("en", "u1") is True


def test_can_study_false_for_plus_language_anonymous() -> None:
    assert entitlements.can_study("it", None) is False


def test_can_study_false_for_plus_language_unentitled_user() -> None:
    db = _mock_db_with_doc(exists=False)
    with patch.object(entitlements, "get_db", return_value=db):
        assert entitlements.can_study("it", "u1") is False


def test_can_study_true_for_plus_language_entitled_user() -> None:
    db = _mock_db_with_doc(exists=True, data={"status": "active"})
    with patch.object(entitlements, "get_db", return_value=db):
        assert entitlements.can_study("it", "u1") is True


# ---------------------------------------------------------------------------
# Admin grant/revoke helpers
# ---------------------------------------------------------------------------


def test_set_entitlement_seeds_full_schema_on_first_write() -> None:
    db = _mock_db_with_doc(exists=False)
    with patch.object(entitlements, "get_db", return_value=db):
        entitlements.set_entitlement(uid="u1", status="active", note="manual comp")

    doc_ref = db.collection.return_value.document.return_value
    written = doc_ref.set.call_args.args[0]
    for field in ("product_id", "purchase_token", "order_id", "expires_at"):
        assert field in written
        assert written[field] is None
    assert written["status"] == "active"
    assert written["plan"] == "plus"
    assert written["source"] == "manual_admin"
    assert written["note"] == "manual comp"
    assert "granted_at" in written


def test_set_entitlement_does_not_reseed_schema_fields_on_update() -> None:
    db = _mock_db_with_doc(exists=True, data={"status": "active", "product_id": "existing"})
    with patch.object(entitlements, "get_db", return_value=db):
        entitlements.set_entitlement(uid="u1", status="revoked", note="")

    doc_ref = db.collection.return_value.document.return_value
    written = doc_ref.set.call_args.args[0]
    assert "product_id" not in written  # not clobbered back to None on a manual edit
    assert written["status"] == "revoked"
    assert "granted_at" not in written  # only set when (re-)activating


def test_set_entitlement_rejects_unsupported_status() -> None:
    with pytest.raises(ValueError):
        entitlements.set_entitlement(uid="u1", status="bogus")


def test_set_entitlement_invalidates_cache() -> None:
    db = _mock_db_with_doc(exists=True, data={"status": "active"})
    with patch.object(entitlements, "get_db", return_value=db):
        assert entitlements.has_plus_entitlement("u1") is True
        db.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {"status": "revoked"}
        entitlements.set_entitlement(uid="u1", status="revoked")
        assert entitlements.has_plus_entitlement("u1") is False
