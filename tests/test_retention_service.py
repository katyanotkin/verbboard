"""Signed-in retention cohorts (issue #112): core/retention_service.py + tools/retention_cohort.py."""

import json
from datetime import date

import pytest

from core.retention_service import (
    compute_retention,
    format_text,
    read_uid_session_rows,
)
from tests.conftest import patch_everywhere
from tools import retention_cohort

TODAY = date(2026, 11, 12)


def _weekly(report, week):
    return next(w for w in report["weekly"] if w["cohort_week"] == week)


def test_empty_input_has_zero_users_and_no_pct():
    report = compute_retention([], TODAY)
    assert report["as_of"] == "2026-11-12"
    assert report["overall"]["users"] == 0
    assert report["overall"]["d1"]["pct"] is None
    assert report["overall"]["d7"]["n"] == 0
    assert report["weekly"] == []


def test_maturity_boundary_first_plus_n_equals_today_counts():
    # first 2026-11-05 + 7 == today: mature for day 7; day 30 not mature
    report = compute_retention([("u1", "2026-11-05")], TODAY)
    assert report["overall"]["d7"]["n"] == 1
    assert report["overall"]["d30"]["n"] == 0
    assert report["overall"]["d1_7"]["n"] == 1


def test_maturity_boundary_first_plus_n_after_today_does_not_count():
    # first 2026-11-06 + 7 == tomorrow
    report = compute_retention([("u1", "2026-11-06")], TODAY)
    assert report["overall"]["d7"]["n"] == 0
    assert report["overall"]["d7"]["pct"] is None
    assert report["overall"]["d1"]["n"] == 1
    assert report["overall"]["d1_7"]["n"] == 0


def test_exact_day7_differs_from_rolling_window():
    rows = [
        ("exact", "2026-11-01"),
        ("exact", "2026-11-08"),  # day 7
        ("early", "2026-11-01"),
        ("early", "2026-11-04"),  # day 3 only
    ]
    overall = compute_retention(rows, TODAY)["overall"]
    assert overall["users"] == 2
    assert overall["d7"]["n"] == 2
    assert overall["d7"]["returned"] == 1
    assert overall["d1_7"]["returned"] == 2
    assert overall["d7"]["pct"] == 50.0
    assert overall["d1_7"]["pct"] == 100.0


def test_return_outside_window_not_counted_in_rolling_1_7():
    rows = [("u", "2026-10-01"), ("u", "2026-10-15")]  # day 14
    overall = compute_retention(rows, TODAY)["overall"]
    assert overall["d1_7"]["returned"] == 0
    assert overall["d8_30"]["returned"] == 1


def test_same_day_repeat_sessions_are_not_a_return():
    rows = [("u", "2026-10-01"), ("u", "2026-10-01")]
    overall = compute_retention(rows, TODAY)["overall"]
    assert overall["users"] == 1
    assert overall["d1"]["returned"] == 0


@pytest.mark.parametrize(
    "bad_row",
    [
        ("u", "not-a-date"),
        ("u", ""),
        ("", "2026-10-01"),
        (None, "2026-10-01"),
    ],
)
def test_bad_rows_are_skipped(bad_row):
    report = compute_retention([bad_row, ("good", "2026-10-01")], TODAY)
    assert report["overall"]["users"] == 1


def test_weekly_cohorts_group_by_monday():
    # 2026-11-02 is a Monday; Sun 2026-11-01 belongs to the week of 2026-10-26
    rows = [
        ("a", "2026-11-02"),
        ("b", "2026-11-08"),  # Sunday, same week as a
        ("c", "2026-11-01"),
    ]
    report = compute_retention(rows, TODAY)
    assert [w["cohort_week"] for w in report["weekly"]] == ["2026-10-26", "2026-11-02"]
    assert _weekly(report, "2026-11-02")["users"] == 2
    assert _weekly(report, "2026-10-26")["users"] == 1
    assert report["overall"]["users"] == 3


def test_cohort_day_is_first_date_regardless_of_row_order():
    rows = [("u", "2026-11-03"), ("u", "2026-11-02")]
    report = compute_retention(rows, TODAY)
    assert [w["cohort_week"] for w in report["weekly"]] == ["2026-11-02"]
    assert report["overall"]["d1"]["returned"] == 1


def _session(fake_db, doc_id, **fields):
    fake_db._docs[f"analytics_sessions/{doc_id}"] = dict(fields)


def test_read_rows_drops_bots_no_uid_and_excluded(fake_db):
    _session(fake_db, "ok", uid="u1", date="2026-11-01", device_type="mobile")
    _session(fake_db, "nodevice", uid="u2", date="2026-11-02")
    _session(fake_db, "bot", uid="u3", date="2026-11-01", device_type="Bot")
    _session(fake_db, "nouid", date="2026-11-01", device_type="desktop")
    _session(fake_db, "emptyuid", uid="", date="2026-11-01", device_type="desktop")
    _session(fake_db, "mine", uid="owner", date="2026-11-01", device_type="desktop")
    rows = read_uid_session_rows(None, {"owner"})
    assert sorted(rows) == [("u1", "2026-11-01"), ("u2", "2026-11-02")]


def test_read_rows_honours_since(fake_db):
    _session(fake_db, "old", uid="u1", date="2026-10-01", device_type="mobile")
    _session(fake_db, "edge", uid="u2", date="2026-11-01", device_type="mobile")
    _session(fake_db, "new", uid="u3", date="2026-11-05", device_type="mobile")
    rows = read_uid_session_rows(date(2026, 11, 1), set())
    assert sorted(uid for uid, _ in rows) == ["u2", "u3"]


def test_format_text_handles_empty_and_populated():
    empty = format_text(compute_retention([], TODAY))
    assert "2026-11-12" in empty
    assert "ALL" in empty

    rows = [("u", "2026-10-01"), ("u", "2026-10-02"), ("v", "2026-10-01")]
    text = format_text(compute_retention(rows, TODAY))
    assert "ALL" in text
    assert "2026-09-28" in text  # Monday of the cohort week
    assert "50.0%" in text


def test_cli_json_output(fake_db, monkeypatch, capsys):
    patch_everywhere(monkeypatch, "core.admin_feedback_service._excluded_uids", lambda: set())
    _session(fake_db, "a", uid="u1", date="2026-10-01", device_type="mobile")
    _session(fake_db, "b", uid="u1", date="2026-10-02", device_type="mobile")
    assert retention_cohort.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall"]["users"] == 1
    assert payload["overall"]["d1"]["returned"] == 1


def test_cli_text_output_with_since(fake_db, monkeypatch, capsys):
    patch_everywhere(monkeypatch, "core.admin_feedback_service._excluded_uids", lambda: set())
    assert retention_cohort.main(["--since", "2026-10-01"]) == 0
    assert "Signed-in retention" in capsys.readouterr().out


def test_cli_bad_since_returns_2(capsys):
    assert retention_cohort.main(["--since", "yesterday"]) == 2
    assert "could not run" in capsys.readouterr().err
