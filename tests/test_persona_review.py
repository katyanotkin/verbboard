"""Scheduled persona review (issue #142): service and internal route."""

from __future__ import annotations

import urllib.error
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


def _seed_marker(fake_db, day: str, issue_number) -> None:
    fake_db._docs[f"{svc.COLLECTION}/{day}"] = {"created_at": day, "issue_number": issue_number}


def _marker_paths(fake_db) -> list[str]:
    return [p for p in fake_db._docs if p.startswith(f"{svc.COLLECTION}/")]


@pytest.fixture()
def report(monkeypatch):
    monkeypatch.setattr(svc, "build_report", lambda *a, **k: _report())


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


def test_run_review_not_due(fake_db, report) -> None:
    _seed_marker(fake_db, "2026-11-19", 7)
    assert svc.run_review(today=TODAY, repo="o/r", token="t") == {"status": "not_due"}


def test_marker_without_issue_does_not_block(fake_db, report, monkeypatch) -> None:
    _seed_marker(fake_db, "2026-11-22", None)
    monkeypatch.setattr(svc, "create_github_issue", lambda *a: 55)
    assert svc.run_review(today=TODAY, repo="o/r", token="t")["status"] == "created"


def test_dry_run_writes_nothing(fake_db, report, monkeypatch) -> None:
    def boom(*a):
        raise AssertionError("must not call GitHub")

    monkeypatch.setattr(svc, "create_github_issue", boom)
    result = svc.run_review(today=TODAY, repo="o/r", token="t", dry_run=True)
    assert result["status"] == "dry_run"
    assert "Non-bot sessions" in result["body"]
    assert _marker_paths(fake_db) == []


def test_created_writes_marker_with_issue_number(fake_db, report, monkeypatch) -> None:
    monkeypatch.setattr(svc, "create_github_issue", lambda *a: 142)
    assert svc.run_review(today=TODAY, repo="o/r", token="t") == {"status": "created", "issue_number": 142}
    assert fake_db._docs[f"{svc.COLLECTION}/2026-11-24"]["issue_number"] == 142


def test_same_day_marker_returns_already_opened(fake_db, report, monkeypatch) -> None:
    _seed_marker(fake_db, "2026-11-24", None)
    monkeypatch.setattr(svc, "create_github_issue", lambda *a: 1)
    assert svc.run_review(today=TODAY, repo="o/r", token="t") == {"status": "already_opened_today"}


def test_http_error_deletes_marker_and_reraises(fake_db, report, monkeypatch) -> None:
    def refuse(*a):
        raise urllib.error.HTTPError("u", 422, "bad", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(svc, "create_github_issue", refuse)
    with pytest.raises(urllib.error.HTTPError):
        svc.run_review(today=TODAY, repo="o/r", token="t")
    assert _marker_paths(fake_db) == []


def test_generic_error_keeps_marker(fake_db, report, monkeypatch) -> None:
    def timeout(*a):
        raise TimeoutError("slow")

    monkeypatch.setattr(svc, "create_github_issue", timeout)
    with pytest.raises(TimeoutError):
        svc.run_review(today=TODAY, repo="o/r", token="t")
    assert _marker_paths(fake_db) == [f"{svc.COLLECTION}/2026-11-24"]


def test_force_bypasses_due(fake_db, report, monkeypatch) -> None:
    _seed_marker(fake_db, "2026-11-22", 9)
    monkeypatch.setattr(svc, "create_github_issue", lambda *a: 77)
    result = svc.run_review(today=TODAY, repo="o/r", token="t", force=True)
    assert result["status"] == "created"


# ---- route ----

_ENV = {
    "PERSONA_REVIEW_AUDIENCE": "aud",
    "PERSONA_REVIEW_INVOKER_EMAIL": "sched@x.iam",
    "PERSONA_REVIEW_REPO": "o/r",
    "GITHUB_ISSUES_TOKEN": "tok",
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
    assert seen["repo"] == "o/r" and seen["token"] == "tok"


def test_route_502_when_run_review_raises(client: TestClient, env, monkeypatch) -> None:
    _good_claims(monkeypatch)

    def boom(**kwargs):
        raise RuntimeError("x")

    monkeypatch.setattr("app.routes.internal_persona_review.run_review", boom)
    assert client.post("/internal/persona-review", headers=_AUTH).status_code == 502
