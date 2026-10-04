"""Tests for core.admin_report_service.build_report (issue #67)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core import admin_report_service
from core.admin_report_service import build_report


@pytest.fixture(autouse=True)
def _no_excluded_uids(monkeypatch):
    monkeypatch.setattr(admin_report_service, "_excluded_uids", lambda: set())


def _session(fake_db, key: str, date: str, **fields) -> None:
    fake_db._docs[f"analytics_sessions/{date}_{key}"] = {"date": date, "device_type": "desktop", **fields}


def _user(fake_db, uid: str, created: datetime) -> None:
    fake_db._docs[f"users/{uid}"] = {"created_at": created}


def test_date_bounds_are_inclusive(fake_db) -> None:
    _session(fake_db, "a", "2026-09-30")  # before
    _session(fake_db, "b", "2026-10-01")  # first day
    _session(fake_db, "c", "2026-10-03")  # last day
    _session(fake_db, "d", "2026-10-04")  # after

    report = build_report("2026-10-01", "2026-10-03")

    assert report["non_bot_sessions"] == 2
    assert report["range"]["days"] == 3


def test_bots_counted_separately_and_excluded_uids_dropped(fake_db, monkeypatch) -> None:
    monkeypatch.setattr(admin_report_service, "_excluded_uids", lambda: {"me"})
    _session(fake_db, "human", "2026-10-01")
    _session(fake_db, "bot", "2026-10-01", device_type="bot")
    _session(fake_db, "owner", "2026-10-01", uid="me")
    _session(fake_db, "tester", "2026-10-01", uid="u1")

    report = build_report("2026-10-01", "2026-10-01")

    assert report["non_bot_sessions"] == 2
    assert report["bot_sessions"] == 1
    assert report["registered"]["sessions_with_uid"] == 1
    assert report["by_device"] == {"desktop": 2}


def test_registered_and_twa_counts_and_percentages(fake_db) -> None:
    _session(fake_db, "a", "2026-10-03", uid="u1", twa=True)
    _session(fake_db, "b", "2026-10-03", uid="u1")
    _session(fake_db, "c", "2026-10-03", twa=True)
    _session(fake_db, "d", "2026-10-03")

    report = build_report("2026-10-03", "2026-10-03")

    assert report["registered"]["sessions_with_uid"] == 2
    assert report["registered"]["distinct_users"] == 1
    assert report["registered"]["pct"] == 50.0
    assert report["twa"]["sessions"] == 2
    assert report["twa"]["pct"] == 50.0
    assert report["twa"]["signed_in_users"] == 1


def test_zero_sessions_gives_zero_percentages(fake_db) -> None:
    _session(fake_db, "bot", "2026-10-01", device_type="bot")

    report = build_report("2026-10-01", "2026-10-01")

    assert report["non_bot_sessions"] == 0
    assert report["registered"]["pct"] == 0.0
    assert report["twa"]["pct"] == 0.0


def test_daily_series_is_zero_filled_and_ordered(fake_db) -> None:
    _session(fake_db, "a", "2026-10-01", uid="u1")
    _session(fake_db, "b", "2026-10-03", twa=True)

    daily = build_report("2026-10-01", "2026-10-04")["daily"]

    assert [d["date"] for d in daily] == ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"]
    assert daily[0] == {"date": "2026-10-01", "sessions": 1, "registered": 1, "twa": 0}
    assert daily[1] == {"date": "2026-10-02", "sessions": 0, "registered": 0, "twa": 0}
    assert daily[2]["twa"] == 1


def test_compare_window_is_same_length_and_ends_day_before(fake_db) -> None:
    _session(fake_db, "cur1", "2026-10-03")
    _session(fake_db, "cur2", "2026-10-02")
    _session(fake_db, "prev", "2026-10-01")
    _session(fake_db, "older", "2026-09-29")  # outside previous window

    report = build_report("2026-10-02", "2026-10-03", compare=True)

    assert report["previous"]["range"]["date_from"] == "2026-09-30"
    assert report["previous"]["range"]["date_to"] == "2026-10-01"
    assert report["previous"]["range"]["days"] == report["range"]["days"] == 2
    assert report["previous"]["non_bot_sessions"] == 1
    assert report["deltas"]["non_bot_sessions"] == {"current": 2, "previous": 1, "delta": 1}


def test_no_compare_means_no_previous_or_deltas(fake_db) -> None:
    report = build_report("2026-10-01", "2026-10-01")

    assert "previous" not in report
    assert "deltas" not in report


def test_legacy_approximate_sessions_are_separate_from_twa(fake_db) -> None:
    _session(fake_db, "ref", "2026-10-01", referrer="android-app://com.verbboard")
    _session(fake_db, "tap", "2026-10-01", sign_in_tapped_branch="twa")
    _session(fake_db, "flagged", "2026-10-01", twa=True, referrer="android-app://com.verbboard")
    _session(fake_db, "explicit_false", "2026-10-01", twa=False, referrer="android-app://com.verbboard")
    _session(fake_db, "plain", "2026-10-01", referrer="https://google.com")

    report = build_report("2026-10-01", "2026-10-01")

    assert report["twa"]["sessions"] == 1
    assert report["twa"]["legacy_approximate_sessions"] == 2


def test_new_registrations_use_user_created_at_within_range(fake_db, monkeypatch) -> None:
    monkeypatch.setattr(admin_report_service, "_excluded_uids", lambda: {"owner"})
    _user(fake_db, "in1", datetime(2026, 10, 1, 0, 0, tzinfo=UTC))
    _user(fake_db, "in2", datetime(2026, 10, 3, 23, 59, tzinfo=UTC))
    _user(fake_db, "before", datetime(2026, 9, 30, 23, 59, tzinfo=UTC))
    _user(fake_db, "after", datetime(2026, 10, 4, 0, 1, tzinfo=UTC))
    _user(fake_db, "owner", datetime(2026, 10, 2, 12, 0, tzinfo=UTC))

    report = build_report("2026-10-01", "2026-10-03")

    assert report["registered"]["new_registrations"] == 2


@pytest.mark.parametrize(
    ("date_from", "date_to"),
    [
        ("2026/10/01", "2026-10-03"),
        ("2026-10-01", "nope"),
        ("2026-02-30", "2026-03-01"),
        ("2026-10-03", "2026-10-01"),
        ("2025-01-01", "2026-10-01"),  # > 366 days
    ],
)
def test_invalid_input_raises_value_error(date_from: str, date_to: str) -> None:
    with pytest.raises(ValueError):
        build_report(date_from, date_to)


def test_range_of_exactly_366_days_is_allowed(fake_db) -> None:
    report = build_report("2025-10-03", "2026-10-03")  # 366 days inclusive

    assert report["range"]["days"] == 366
