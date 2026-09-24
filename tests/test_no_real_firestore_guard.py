"""Regression guard for the autouse `_no_real_firestore` fixture (issue #8).

Unit tests must never reach the live Firestore project (.env points at it and
ADC credentials exist on dev machines). Writers swallow exceptions, so a leak
would be silent: search tests once bumped real `verb_search_hits` counters.
"""

from __future__ import annotations

from unittest.mock import patch

from core.analytics import search_hits
from core.storage.firestore_db import get_db
from tests.fake_firestore import FakeFirestore


def test_get_db_returns_in_memory_fake_by_default() -> None:
    assert isinstance(get_db(), FakeFirestore)


def test_real_client_is_never_constructed() -> None:
    with patch("google.cloud.firestore.Client", side_effect=AssertionError("real Firestore client built")):
        get_db().collection("anything").document("x").set({"a": 1})


def test_unmocked_search_hit_write_lands_in_fake_not_real_project(fake_db) -> None:
    # Bypass the route-level _no_search_hit_writes patch: call the real writer.
    search_hits._record_search_hit("en", "en_go", "search")
    assert "verb_search_hits/en_en_go" in fake_db._docs


def test_fake_state_does_not_leak_between_tests(fake_db) -> None:
    assert fake_db._docs == {}
