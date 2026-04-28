from __future__ import annotations

from core.admin_logging import log_missing_verb_search


def test_empty_query_is_skipped(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr("core.admin_logging._append_local", lambda r: calls.append(r))
    monkeypatch.setattr("core.admin_logging._write_firestore_signal", lambda r: None)

    log_missing_verb_search(language="en", query="")
    log_missing_verb_search(language="en", query="   ")

    assert calls == []


def test_query_is_normalized(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr("core.admin_logging._append_local", lambda r: calls.append(r))
    monkeypatch.setattr("core.admin_logging._write_firestore_signal", lambda r: None)

    log_missing_verb_search(language="en", query="  Go  ")

    assert len(calls) == 1
    assert calls[0]["query"] == "go"


def test_language_is_recorded(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr("core.admin_logging._append_local", lambda r: calls.append(r))
    monkeypatch.setattr("core.admin_logging._write_firestore_signal", lambda r: None)

    log_missing_verb_search(language="ru", query="идти")

    assert calls[0]["language"] == "ru"


def test_device_type_detected_from_user_agent(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr("core.admin_logging._append_local", lambda r: calls.append(r))
    monkeypatch.setattr("core.admin_logging._write_firestore_signal", lambda r: None)

    mobile_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148"
    log_missing_verb_search(language="en", query="run", user_agent=mobile_ua)

    assert calls[0]["device_type"] == "mobile"


def test_explicit_device_type_overrides_ua(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr("core.admin_logging._append_local", lambda r: calls.append(r))
    monkeypatch.setattr("core.admin_logging._write_firestore_signal", lambda r: None)

    log_missing_verb_search(
        language="en",
        query="run",
        device_type="tablet",
        user_agent="Mozilla/5.0 (iPhone; Mobile)",
    )

    assert calls[0]["device_type"] == "tablet"


def test_firestore_signal_is_attempted(monkeypatch) -> None:
    monkeypatch.setattr("core.admin_logging._append_local", lambda r: None)
    firestore_calls: list[dict] = []
    monkeypatch.setattr(
        "core.admin_logging._write_firestore_signal",
        lambda r: firestore_calls.append(r),
    )

    log_missing_verb_search(language="es", query="hablar")

    assert len(firestore_calls) == 1
    assert firestore_calls[0]["language"] == "es"
