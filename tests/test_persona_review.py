"""Scheduled persona review (issue #142): service and internal route."""

from __future__ import annotations

import logging
from datetime import date

import pytest
from fastapi.testclient import TestClient
from google.auth.exceptions import GoogleAuthError

from core import persona_review_service as svc

TODAY = date(2026, 11, 24)


def _report() -> dict:
    return {
        "range": {"date_from": "2026-11-03", "date_to": "2026-11-23", "days": 21},
        "deltas": {
            "non_bot_sessions": {"current": 120, "previous": 100, "delta": 20},
            "engagement.votd_rate": {"current": 12.34, "previous": 15.0, "delta": -2.66},
        },
        "sign_in": {"failures_by_code": {"popup_closed": 2, "network": 5}},
    }


def _seed_review(fake_db, day: str, status: str = "open") -> None:
    fake_db._docs[f"{svc.COLLECTION}/{day}"] = {
        "date": day,
        "status": status,
        "window": {"date_from": "2026-10-01", "date_to": "2026-10-21"},
    }


def _review_paths(fake_db) -> list[str]:
    return [p for p in fake_db._docs if p.startswith(f"{svc.COLLECTION}/")]


@pytest.fixture()
def report(monkeypatch):
    monkeypatch.setattr(svc, "build_report", lambda *a, **k: _report())


@pytest.fixture()
def github_env(monkeypatch):
    monkeypatch.setenv("GITHUB_ISSUES_TOKEN", "secret-token-value")
    monkeypatch.setenv("PERSONA_REVIEW_REPO", "o/r")


@pytest.fixture()
def no_github_env(monkeypatch):
    monkeypatch.delenv("GITHUB_ISSUES_TOKEN", raising=False)
    monkeypatch.delenv("PERSONA_REVIEW_REPO", raising=False)


def _forbid_github(monkeypatch) -> None:
    def boom(*a, **k):
        raise AssertionError("must not call GitHub")

    monkeypatch.setattr(svc, "create_github_issue", boom)


def test_review_window_is_21_days_ending_yesterday() -> None:
    start, end = svc.review_window(TODAY)
    assert end == date(2026, 11, 23)
    assert start == date(2026, 11, 3)
    assert (end - start).days + 1 == 21


def test_is_due_cases() -> None:
    assert svc.is_due([], TODAY)
    assert not svc.is_due(["2026-11-04"], TODAY)  # 20 days
    assert svc.is_due(["2026-11-03"], TODAY)  # 21 days
    assert svc.is_due(["garbage", "2026-01-01"], TODAY)
    assert svc.is_due(["garbage"], TODAY)


def test_build_issue_body() -> None:
    body = svc.build_issue_body(_report(), TODAY)
    assert "| Non-bot sessions | 120 | 100 | +20 |" in body
    assert "| Verb of the Day click rate % | 12.3 | 15 | -2.7 |" in body
    assert "Practice started" not in body  # missing delta key skipped
    assert body.index("- network: 5") < body.index("- popup_closed: 2")
    assert body.count("- [ ] ") == len(svc.CHECKLIST)


def test_run_review_creates_one_open_doc_and_logs(fake_db, report, no_github_env, caplog) -> None:
    with caplog.at_level(logging.WARNING):
        result = svc.run_review(today=TODAY)
    assert result == {"status": "created", "date": "2026-11-24"}
    assert _review_paths(fake_db) == [f"{svc.COLLECTION}/2026-11-24"]
    doc = fake_db._docs[f"{svc.COLLECTION}/2026-11-24"]
    assert doc["status"] == "open"
    assert doc["window"] == {"date_from": "2026-11-03", "date_to": "2026-11-23"}
    assert doc["title"] == svc.build_issue_title(TODAY)
    assert "Non-bot sessions" in doc["body"]
    assert doc["created_at"]
    assert f"PERSONA_REVIEW_DUE {svc.summary_line(_report(), TODAY)}" in caplog.text
    assert "sessions=120" in caplog.text


def test_second_call_same_day_is_not_due(fake_db, report, no_github_env) -> None:
    svc.run_review(today=TODAY)
    assert svc.run_review(today=TODAY) == {"status": "not_due"}
    assert len(_review_paths(fake_db)) == 1


def test_force_same_day_is_already_opened(fake_db, report, no_github_env) -> None:
    svc.run_review(today=TODAY)
    assert svc.run_review(today=TODAY, force=True) == {"status": "already_opened_today"}
    assert len(_review_paths(fake_db)) == 1


def test_recent_doc_is_not_due(fake_db, report, no_github_env) -> None:
    _seed_review(fake_db, "2026-11-04")  # 20 days old
    assert svc.run_review(today=TODAY) == {"status": "not_due"}


def test_old_doc_is_due(fake_db, report, no_github_env) -> None:
    _seed_review(fake_db, "2026-11-03")  # 21 days old
    assert svc.run_review(today=TODAY)["status"] == "created"


def test_dry_run_writes_nothing(fake_db, report, github_env, monkeypatch) -> None:
    _forbid_github(monkeypatch)
    result = svc.run_review(today=TODAY, dry_run=True)
    assert result["status"] == "dry_run"
    assert "Non-bot sessions" in result["body"]
    assert _review_paths(fake_db) == []


def test_force_bypasses_due(fake_db, report, no_github_env) -> None:
    _seed_review(fake_db, "2026-11-22")
    assert svc.run_review(today=TODAY, force=True)["status"] == "created"


def test_github_success_stores_issue_number(fake_db, report, github_env, monkeypatch) -> None:
    calls = []

    def fake_create(repo, token, title, body):
        calls.append((repo, token, title))
        return 142

    monkeypatch.setattr(svc, "create_github_issue", fake_create)
    assert svc.run_review(today=TODAY)["status"] == "created"
    assert fake_db._docs[f"{svc.COLLECTION}/2026-11-24"]["issue_number"] == 142
    assert calls == [("o/r", "secret-token-value", svc.build_issue_title(TODAY))]


@pytest.mark.parametrize("error", [RuntimeError("boom"), TimeoutError("slow"), ValueError("bad")])
def test_github_failure_is_non_fatal(fake_db, report, github_env, monkeypatch, caplog, error) -> None:
    def refuse(*a, **k):
        raise error

    monkeypatch.setattr(svc, "create_github_issue", refuse)
    with caplog.at_level(logging.WARNING):
        result = svc.run_review(today=TODAY)
    assert result["status"] == "created"
    doc = fake_db._docs[f"{svc.COLLECTION}/2026-11-24"]
    assert doc["status"] == "open"
    assert "issue_number" not in doc
    assert "PERSONA_REVIEW_DUE" in caplog.text
    assert "PERSONA_REVIEW_GITHUB_FAILED" in caplog.text
    assert "secret-token-value" not in caplog.text


@pytest.mark.parametrize("missing", ["GITHUB_ISSUES_TOKEN", "PERSONA_REVIEW_REPO"])
def test_github_skipped_when_env_missing(fake_db, report, github_env, monkeypatch, missing) -> None:
    monkeypatch.delenv(missing)
    _forbid_github(monkeypatch)
    assert svc.run_review(today=TODAY)["status"] == "created"


def test_open_review_returns_newest_open(fake_db) -> None:
    _seed_review(fake_db, "2026-09-01")
    _seed_review(fake_db, "2026-10-13")
    _seed_review(fake_db, "2026-11-03", status="done")
    assert svc.open_review() == {"date": "2026-10-13", "date_from": "2026-10-01", "date_to": "2026-10-21"}


def test_open_review_none_when_nothing_open(fake_db) -> None:
    assert svc.open_review() is None
    _seed_review(fake_db, "2026-10-13", status="done")
    assert svc.open_review() is None


def test_mark_done(fake_db) -> None:
    _seed_review(fake_db, "2026-10-13")
    assert svc.mark_done("2026-10-13") is True
    doc = fake_db._docs[f"{svc.COLLECTION}/2026-10-13"]
    assert doc["status"] == "done"
    assert doc["done_at"]
    assert svc.open_review() is None
    assert svc.mark_done("2020-01-01") is False


def test_banner_text(fake_db) -> None:
    assert svc.banner_text() is None
    _seed_review(fake_db, "2026-10-13")
    text = svc.banner_text()
    assert text is not None
    assert "2026-10-01" in text and "2026-10-21" in text and "2026-10-13" in text
    assert "Mark done" in text


def test_banner_text_never_raises(monkeypatch) -> None:
    def broken():
        raise RuntimeError("firestore down")

    monkeypatch.setattr(svc, "get_db", broken)
    assert svc.banner_text() is None


# ---- route ----

_ENV = {
    "PERSONA_REVIEW_AUDIENCE": "aud",
    "PERSONA_REVIEW_INVOKER_EMAIL": "sched@x.iam",
}
_AUTH = {"Authorization": "Bearer abc"}
_VERIFY = "app.routes.internal_persona_review.id_token.verify_oauth2_token"


@pytest.fixture()
def env(monkeypatch):
    for key, value in _ENV.items():
        monkeypatch.setenv(key, value)


def _good_claims(monkeypatch) -> None:
    monkeypatch.setattr(_VERIFY, lambda *a, **k: {"email": "sched@x.iam", "email_verified": True})


@pytest.mark.parametrize("missing", list(_ENV))
def test_route_404_when_env_missing(client: TestClient, env, monkeypatch, missing) -> None:
    monkeypatch.delenv(missing)
    assert client.post("/internal/persona-review", headers=_AUTH).status_code == 404


def test_route_401_without_bearer(client: TestClient, env, monkeypatch) -> None:
    _good_claims(monkeypatch)
    assert client.post("/internal/persona-review").status_code == 401


def test_route_401_on_invalid_token(client: TestClient, env, monkeypatch) -> None:
    def bad(*a, **k):
        raise GoogleAuthError("nope")

    monkeypatch.setattr(_VERIFY, bad)
    assert client.post("/internal/persona-review", headers=_AUTH).status_code == 401


@pytest.mark.parametrize(
    "claims",
    [
        {"email": "other@x.iam", "email_verified": True},
        {"email": "sched@x.iam", "email_verified": False},
    ],
)
def test_route_403_wrong_caller(client: TestClient, env, monkeypatch, claims) -> None:
    monkeypatch.setattr(_VERIFY, lambda *a, **k: claims)
    assert client.post("/internal/persona-review", headers=_AUTH).status_code == 403


def test_route_success_passes_params(client: TestClient, env, monkeypatch) -> None:
    _good_claims(monkeypatch)
    seen: dict = {}

    def fake_run(**kwargs):
        seen.update(kwargs)
        return {"status": "dry_run"}

    monkeypatch.setattr("app.routes.internal_persona_review.run_review", fake_run)
    resp = client.post("/internal/persona-review?dry_run=true&force=true", headers=_AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"status": "dry_run"}
    assert seen["dry_run"] is True and seen["force"] is True
    assert "repo" not in seen and "token" not in seen


def test_route_502_when_run_review_raises(client: TestClient, env, monkeypatch) -> None:
    _good_claims(monkeypatch)

    def boom(**kwargs):
        raise RuntimeError("x")

    monkeypatch.setattr("app.routes.internal_persona_review.run_review", boom)
    assert client.post("/internal/persona-review", headers=_AUTH).status_code == 502
