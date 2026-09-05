from __future__ import annotations

from types import SimpleNamespace

from core.admin_logging import log_missing_verb_search, resolve_signal_label


def test_empty_query_is_skipped(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr("core.admin_logging._write_firestore_signal", lambda r: calls.append(r))

    log_missing_verb_search(language="en", query="")
    log_missing_verb_search(language="en", query="   ")

    assert calls == []


def test_query_is_normalized(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr("core.admin_logging._write_firestore_signal", lambda r: calls.append(r))

    log_missing_verb_search(language="en", query="  Go  ")

    assert len(calls) == 1
    assert calls[0]["query"] == "go"


def test_language_is_recorded(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr("core.admin_logging._write_firestore_signal", lambda r: calls.append(r))

    log_missing_verb_search(language="ru", query="идти")

    assert calls[0]["language"] == "ru"


def test_firestore_signal_is_attempted(monkeypatch) -> None:
    firestore_calls: list[dict] = []
    monkeypatch.setattr(
        "core.admin_logging._write_firestore_signal",
        lambda r: firestore_calls.append(r),
    )

    log_missing_verb_search(language="es", query="hablar")

    assert len(firestore_calls) == 1
    assert firestore_calls[0]["language"] == "es"


class _FakeDocSnapshot:
    def __init__(self, exists: bool) -> None:
        self.exists = exists


class _FakeDocRef:
    def __init__(self, exists: bool, on_update=None) -> None:
        self._exists = exists
        self._on_update = on_update
        self.update_calls: list[dict] = []

    def get(self):
        return _FakeDocSnapshot(self._exists)

    def update(self, data):
        if self._on_update:
            self._on_update()
        self.update_calls.append(data)


class _FakeCollection:
    def __init__(self, doc_ref: _FakeDocRef) -> None:
        self._doc_ref = doc_ref
        self.requested_ids: list[str] = []

    def document(self, doc_id):
        self.requested_ids.append(doc_id)
        return self._doc_ref


class _FakeDb:
    def __init__(self, doc_ref: _FakeDocRef) -> None:
        self.collection_ = _FakeCollection(doc_ref)

    def collection(self, name):
        return self.collection_


def _patch_label_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.settings.load_settings",
        lambda: SimpleNamespace(verb_signal_labels_collection="demand_signal_labels"),
    )


def test_resolve_signal_label_normalizes_casing_to_match_stored_query(monkeypatch) -> None:
    # log_missing_verb_search always casefolds the query before writing, so the
    # label doc id is always lowercase -- resolve_signal_label must match that
    # even when callers (e.g. the autogen path) pass an un-normalized query.
    _patch_label_settings(monkeypatch)
    doc_ref = _FakeDocRef(exists=True)
    fake_db = _FakeDb(doc_ref)
    monkeypatch.setattr("core.storage.firestore_db.get_db", lambda: fake_db)

    resolve_signal_label(language="en", query="  Speak  ")

    assert fake_db.collection_.requested_ids == ["en_speak"]
    assert doc_ref.update_calls == [{"hidden": True, "updated_at": doc_ref.update_calls[0]["updated_at"]}]


def test_resolve_signal_label_is_noop_when_no_label_exists(monkeypatch) -> None:
    _patch_label_settings(monkeypatch)
    doc_ref = _FakeDocRef(exists=False)
    fake_db = _FakeDb(doc_ref)
    monkeypatch.setattr("core.storage.firestore_db.get_db", lambda: fake_db)

    resolve_signal_label(language="en", query="ghost")

    assert doc_ref.update_calls == []


def test_resolve_signal_label_never_raises_on_concurrent_delete(monkeypatch) -> None:
    _patch_label_settings(monkeypatch)

    def _boom():
        raise RuntimeError("label deleted concurrently")

    doc_ref = _FakeDocRef(exists=True, on_update=_boom)
    fake_db = _FakeDb(doc_ref)
    monkeypatch.setattr("core.storage.firestore_db.get_db", lambda: fake_db)

    resolve_signal_label(language="en", query="speak")  # must not raise


def test_resolve_signal_label_skips_empty_input_without_touching_firestore(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr("core.storage.firestore_db.get_db", lambda: calls.append("called"))

    resolve_signal_label(language="", query="speak")
    resolve_signal_label(language="en", query="   ")

    assert calls == []
