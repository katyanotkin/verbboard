"""Tests for core/verb_service.py's generate_and_promote_verb().

The clean-success path (translations persisted for all languages) is already
covered by tests/test_translations.py::test_generated_verb_examples_have_translations_for_all_other_langs.

This file covers the behavior added/changed on top of that:
- Claude resolving the input lemma to a different spelling: written under the
  resolved id, and a second call under the original input returns the
  existing resolved doc WITHOUT a second Claude call.
- A Claude call raising an exception: returns None, writes nothing live.
- A recent (< 24h) recorded attempt short-circuits without calling Claude.
- An attempt recorded > 24h ago is retried.
- The in-process _GENERATING dedup blocks a concurrent second call for the
  same (language, lemma).
- get_cached_system(language) is used for the `system` kwarg (not the old
  module-level prompt blob).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.storage.verb_document import build_storage_verb_id

VERBS_COLLECTION = "verbs"
PAIR_ATTEMPTS_COLLECTION = "verb_pair_generation_attempts"


@pytest.fixture(autouse=True)
def _reset_generating_set():
    """The module-level _GENERATING set must not leak state between tests."""
    from core.verb_service import _GENERATING

    _GENERATING.clear()
    yield
    _GENERATING.clear()


# ---------------------------------------------------------------------------
# Minimal in-memory Firestore fake -- separates documents by collection name,
# unlike a single shared MagicMock, so tests can assert independently on the
# live "verbs" collection vs the "verb_pair_generation_attempts" collection.
# ---------------------------------------------------------------------------


class _FakeSnapshot:
    def __init__(self, doc_id: str, data: dict[str, Any] | None) -> None:
        self.id = doc_id
        self.exists = data is not None
        self._data = data

    def to_dict(self) -> dict[str, Any] | None:
        return dict(self._data) if self._data is not None else None


class _FakeDocRef:
    def __init__(self, store: dict[str, dict[str, Any]], doc_id: str) -> None:
        self._store = store
        self.id = doc_id

    def get(self) -> _FakeSnapshot:
        return _FakeSnapshot(self.id, self._store.get(self.id))

    def set(self, data: dict[str, Any]) -> None:
        self._store[self.id] = dict(data)


class _FakeWhereQuery:
    def stream(self):
        return iter([])


class _FakeCollection:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self._store = store

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(self._store, doc_id)

    def where(self, *args, **kwargs) -> _FakeWhereQuery:
        return _FakeWhereQuery()


class _FakeDb:
    def __init__(self) -> None:
        self._collections: dict[str, dict[str, Any]] = {}

    def collection(self, name: str) -> _FakeCollection:
        store = self._collections.setdefault(name, {})
        return _FakeCollection(store)

    def verbs_store(self) -> dict[str, Any]:
        return self._collections.setdefault(VERBS_COLLECTION, {})

    def attempts_store(self) -> dict[str, Any]:
        return self._collections.setdefault(PAIR_ATTEMPTS_COLLECTION, {})


def _message_mock(fixture: dict[str, Any]) -> MagicMock:
    message = MagicMock()
    message.content = [MagicMock(text=json.dumps(fixture))]
    return message


def _client_mock(fixture: dict[str, Any] | None = None, *, side_effect: Any = None) -> MagicMock:
    client = MagicMock()
    if side_effect is not None:
        client.messages.create.side_effect = side_effect
    else:
        client.messages.create.return_value = _message_mock(fixture or {})
    return client


# ---------------------------------------------------------------------------
# Claude resolves to a different lemma than the input lookup key
# ---------------------------------------------------------------------------


def test_resolved_lemma_written_under_resolved_id_not_input_id() -> None:
    db = _FakeDb()
    fixture = {"lemma": "go", "forms": {"base": "go"}, "examples": [{"dst": "I go."}]}
    client = _client_mock(fixture)
    anthropic_cls = MagicMock(return_value=client)

    with (
        patch("core.verb_service.anthropic.Anthropic", anthropic_cls),
        patch("core.verb_service._load_anthropic_api_key", return_value="test-key"),
        patch("core.verb_service.get_db", return_value=db),
    ):
        from core.verb_service import generate_and_promote_verb

        result = generate_and_promote_verb("en", "goe")

    input_id = build_storage_verb_id(language="en", lemma="goe")
    resolved_id = build_storage_verb_id(language="en", lemma="go")
    assert input_id != resolved_id

    assert result is not None
    assert result["lemma"] == "go"
    assert resolved_id in db.verbs_store()
    assert input_id not in db.verbs_store(), "must never write under the pre-resolution input id"

    # An attempt marker was recorded under the *input* id pointing at the
    # resolved id, so a future lookup by the original spelling can find it.
    attempt = db.attempts_store().get(input_id)
    assert attempt is not None
    assert attempt["resolved_verb_id"] == resolved_id


def test_second_call_with_original_input_reuses_resolved_doc_without_new_claude_call() -> None:
    db = _FakeDb()
    fixture = {"lemma": "go", "forms": {"base": "go"}, "examples": [{"dst": "I go."}]}
    client = _client_mock(fixture)
    anthropic_cls = MagicMock(return_value=client)

    with (
        patch("core.verb_service.anthropic.Anthropic", anthropic_cls),
        patch("core.verb_service._load_anthropic_api_key", return_value="test-key"),
        patch("core.verb_service.get_db", return_value=db),
    ):
        from core.verb_service import generate_and_promote_verb

        first = generate_and_promote_verb("en", "goe")
        assert client.messages.create.call_count == 1

        second = generate_and_promote_verb("en", "goe")

    assert client.messages.create.call_count == 1, "second call under the same input lemma must not re-call Claude"
    assert second is not None
    assert second == first


# ---------------------------------------------------------------------------
# Claude call raises -> None, nothing written live
# ---------------------------------------------------------------------------


def test_claude_exception_returns_none_and_writes_nothing_live() -> None:
    db = _FakeDb()
    client = _client_mock(side_effect=RuntimeError("boom"))
    anthropic_cls = MagicMock(return_value=client)

    with (
        patch("core.verb_service.anthropic.Anthropic", anthropic_cls),
        patch("core.verb_service._load_anthropic_api_key", return_value="test-key"),
        patch("core.verb_service.get_db", return_value=db),
    ):
        from core.verb_service import generate_and_promote_verb

        result = generate_and_promote_verb("en", "break")

    assert result is None
    assert db.verbs_store() == {}, "a failed generation must not write anything to the live verbs collection"

    verb_id = build_storage_verb_id(language="en", lemma="break")
    attempt = db.attempts_store().get(verb_id)
    assert attempt is not None
    assert attempt["reason"] == "generation_failed"


# ---------------------------------------------------------------------------
# Recorded attempt within 24h blocks a retry; older than 24h retries
# ---------------------------------------------------------------------------


def test_recent_failed_attempt_skips_claude_call() -> None:
    db = _FakeDb()
    verb_id = build_storage_verb_id(language="en", lemma="missed")
    db.attempts_store()[verb_id] = {
        "verb_id": verb_id,
        "language": "en",
        "lemma": "missed",
        "reason": "generation_failed",
        "resolved_verb_id": None,
        "attempted_at": datetime.now(UTC).isoformat(),
    }

    client = _client_mock({"lemma": "missed", "forms": {}, "examples": []})
    anthropic_cls = MagicMock(return_value=client)

    with (
        patch("core.verb_service.anthropic.Anthropic", anthropic_cls),
        patch("core.verb_service._load_anthropic_api_key", return_value="test-key"),
        patch("core.verb_service.get_db", return_value=db),
    ):
        from core.verb_service import generate_and_promote_verb

        result = generate_and_promote_verb("en", "missed")

    assert result is None
    assert client.messages.create.call_count == 0, "an attempt recorded within the retry window must not call Claude"


def test_attempt_older_than_retry_window_calls_claude_again() -> None:
    db = _FakeDb()
    verb_id = build_storage_verb_id(language="en", lemma="retryme")
    stale_attempted_at = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    db.attempts_store()[verb_id] = {
        "verb_id": verb_id,
        "language": "en",
        "lemma": "retryme",
        "reason": "generation_failed",
        "resolved_verb_id": None,
        "attempted_at": stale_attempted_at,
    }

    fixture = {"lemma": "retryme", "forms": {"base": "retryme"}, "examples": [{"dst": "I retry."}]}
    client = _client_mock(fixture)
    anthropic_cls = MagicMock(return_value=client)

    with (
        patch("core.verb_service.anthropic.Anthropic", anthropic_cls),
        patch("core.verb_service._load_anthropic_api_key", return_value="test-key"),
        patch("core.verb_service.get_db", return_value=db),
    ):
        from core.verb_service import generate_and_promote_verb

        result = generate_and_promote_verb("en", "retryme")

    assert client.messages.create.call_count == 1, "an attempt older than the retry window must be retried"
    assert result is not None
    assert verb_id in db.verbs_store()


# ---------------------------------------------------------------------------
# In-process _GENERATING dedup blocks a concurrent second call
# ---------------------------------------------------------------------------


def test_generating_dedup_blocks_concurrent_call_for_same_key() -> None:
    db = _FakeDb()
    fixture = {"lemma": "dup", "forms": {"base": "dup"}, "examples": [{"dst": "I duplicate."}]}
    nested_result: dict[str, Any] = {}

    from core.verb_service import _GENERATING, generate_and_promote_verb

    def _create_side_effect(*args, **kwargs):
        # Fired while the outer call still holds the dedup key -- a nested
        # call for the same (language, lemma) must be rejected immediately,
        # without itself reaching Claude.
        nested_result["value"] = generate_and_promote_verb("en", "dup")
        return _message_mock(fixture)

    client = _client_mock(side_effect=_create_side_effect)
    anthropic_cls = MagicMock(return_value=client)

    with (
        patch("core.verb_service.anthropic.Anthropic", anthropic_cls),
        patch("core.verb_service._load_anthropic_api_key", return_value="test-key"),
        patch("core.verb_service.get_db", return_value=db),
    ):
        outer_result = generate_and_promote_verb("en", "dup")

    assert nested_result["value"] is None, "a concurrent call for the same key must return None immediately"
    assert outer_result is not None
    assert client.messages.create.call_count == 1, "only the outer call should have reached Claude"

    verb_id = build_storage_verb_id(language="en", lemma="dup")
    assert f"en:{verb_id}" not in _GENERATING, "dedup key must be released once the outer call finishes"


# ---------------------------------------------------------------------------
# get_cached_system(language) is used for the `system` kwarg
# ---------------------------------------------------------------------------


def test_uses_get_cached_system_for_system_prompt() -> None:
    db = _FakeDb()
    fixture = {"lemma": "идти", "forms": {}, "examples": []}
    client = _client_mock(fixture)
    anthropic_cls = MagicMock(return_value=client)
    sentinel_system = [{"type": "text", "text": "SENTINEL RU PROMPT", "cache_control": {"type": "ephemeral"}}]

    with (
        patch("core.verb_service.anthropic.Anthropic", anthropic_cls),
        patch("core.verb_service._load_anthropic_api_key", return_value="test-key"),
        patch("core.verb_service.get_db", return_value=db),
        patch("core.verb_service.get_cached_system", return_value=sentinel_system) as mock_get_cached_system,
    ):
        from core.verb_service import generate_and_promote_verb

        generate_and_promote_verb("ru", "идти")

    mock_get_cached_system.assert_called_once_with("ru")
    assert client.messages.create.call_args.kwargs["system"] == sentinel_system
