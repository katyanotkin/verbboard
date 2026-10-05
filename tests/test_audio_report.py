"""Audio problem reports (issue #71): API validation/auth, dedupe, rate limit, reopen, admin view."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core import audio_report_service as service
from core.admin_auth import ADMIN_SESSION_COOKIE, create_admin_session_token
from core.audio_service import build_hashed_audio_key
from core.rate_limit import SlidingWindowRateLimiter
from tests.conftest import seed_spanish_verb

AUTH = {"Authorization": "Bearer local-dev"}
EXAMPLE_TEXT = "Yo hablo con ella."
EXAMPLE_KEY = build_hashed_audio_key("example_1", EXAMPLE_TEXT)


@pytest.fixture(autouse=True)
def _fresh_limiter(monkeypatch):
    monkeypatch.setattr(service, "_rate_limiter", SlidingWindowRateLimiter(max_calls=20, window_seconds=600))


@pytest.fixture
def seeded(fake_db):
    seed_spanish_verb(fake_db)
    return fake_db


def _payload(**overrides):
    body = {
        "language": "es",
        "verb_id": "es_hablar",
        "voice": "female",
        "form_key": EXAMPLE_KEY,
        "reason": "stress",
        "ui_language": "en",
    }
    body.update(overrides)
    return body


def _aggregate(db):
    return db._docs[f"audio_reports/es_es_hablar_female_{EXAMPLE_KEY}"]


def test_anonymous_gets_401(client: TestClient, seeded) -> None:
    assert client.post("/api/audio_report", json=_payload()).status_code == 401


def test_report_resolves_text_server_side_and_aggregates(client: TestClient, seeded) -> None:
    resp = client.post("/api/audio_report", json=_payload(comment="  too   fast\n"), headers=AUTH)

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "duplicate": False}
    doc = _aggregate(seeded)
    assert doc["text"] == EXAMPLE_TEXT
    assert doc["row_kind"] == "example"
    assert doc["count"] == 1
    assert doc["reasons"] == {"stress": 1}
    assert doc["ui_langs"] == {"en": 1}
    assert doc["comments"] == ["too fast"]
    assert doc["status"] == "open"
    assert "uid" not in doc


def test_same_user_same_clip_is_deduped(client: TestClient, seeded) -> None:
    client.post("/api/audio_report", json=_payload(), headers=AUTH)
    resp = client.post("/api/audio_report", json=_payload(reason="glitch"), headers=AUTH)

    assert resp.json() == {"ok": True, "duplicate": True}
    assert _aggregate(seeded)["count"] == 1


def test_unknown_form_key_is_404(client: TestClient, seeded) -> None:
    resp = client.post("/api/audio_report", json=_payload(form_key="example_1_deadbeef00"), headers=AUTH)
    assert resp.status_code == 404
    assert not [p for p in seeded._docs if p.startswith("audio_report")]


@pytest.mark.parametrize(
    "override",
    [{"language": "xx"}, {"voice": "robot"}, {"reason": "bored"}],
)
def test_invalid_fields_are_400(client: TestClient, seeded, override) -> None:
    assert client.post("/api/audio_report", json=_payload(**override), headers=AUTH).status_code == 400


def test_rate_limit_is_429(client: TestClient, seeded, monkeypatch) -> None:
    monkeypatch.setattr(service, "_rate_limiter", SlidingWindowRateLimiter(max_calls=2, window_seconds=600))
    codes = [
        client.post("/api/audio_report", json=_payload(reason="glitch"), headers=AUTH).status_code for _ in range(3)
    ]
    assert codes == [200, 200, 429]


def test_comments_stop_at_five_and_are_trimmed() -> None:
    assert len(service.clean_comment("x" * 500)) == service.MAX_COMMENT_LENGTH
    assert service.clean_comment(None) == ""


def test_comment_cap_per_clip(seeded) -> None:
    for index in range(7):
        service.submit_audio_report(
            uid=f"u{index}",
            language="es",
            verb_id="es_hablar",
            voice="female",
            form_key=EXAMPLE_KEY,
            reason="other",
            comment=f"note {index}",
            ui_language="en",
        )
    doc = _aggregate(seeded)
    assert doc["count"] == 7
    assert len(doc["comments"]) == service.MAX_COMMENTS_STORED


def test_failed_aggregate_write_releases_the_vote_so_a_retry_counts(seeded, monkeypatch) -> None:
    kwargs = dict(
        uid="u1",
        language="es",
        verb_id="es_hablar",
        voice="female",
        form_key=EXAMPLE_KEY,
        reason="stress",
        comment="",
        ui_language="en",
    )
    real_set = type(seeded.collection(service.REPORTS_COLLECTION).document("x")).set

    def failing_set(self, *args, **kw):
        if self.path.startswith(f"{service.REPORTS_COLLECTION}/"):
            raise RuntimeError("firestore down")
        return real_set(self, *args, **kw)

    with monkeypatch.context() as patched:
        patched.setattr(type(seeded.collection("x").document("y")), "set", failing_set)
        with pytest.raises(RuntimeError):
            service.submit_audio_report(**kwargs)

    assert not any(key.startswith(service.VOTES_COLLECTION) for key in seeded._docs)
    assert service.submit_audio_report(**kwargs) == {"ok": True, "duplicate": False}
    assert _aggregate(seeded)["count"] == 1


def _admin() -> dict[str, str]:
    return {ADMIN_SESSION_COOKIE: create_admin_session_token()}


def test_admin_requires_auth(client: TestClient) -> None:
    assert client.get("/admin/api/audio-reports").status_code == 401
    assert client.post("/admin/api/audio-reports/x/resolve").status_code == 401


def test_admin_lists_by_count_resolves_and_new_report_reopens(client: TestClient, seeded) -> None:
    for uid in ("a", "b"):
        service.submit_audio_report(
            uid=uid,
            language="es",
            verb_id="es_hablar",
            voice="female",
            form_key=EXAMPLE_KEY,
            reason="stress",
            comment=None,
            ui_language="en",
        )
    other_key = build_hashed_audio_key("example_1", EXAMPLE_TEXT)
    seeded.collection("audio_reports").document("es_es_hablar_male_x").set(
        {
            "language": "es",
            "verb_id": "es_hablar",
            "voice": "male",
            "form_key": other_key,
            "text": "t",
            "count": 1,
            "status": "open",
        }
    )

    rows = client.get("/admin/api/audio-reports", cookies=_admin()).json()["reports"]
    assert [row["count"] for row in rows] == [2, 1]
    assert "uid" not in rows[0] and "verb_id=es_hablar" in rows[0]["learn_url"]

    report_id = rows[0]["id"]
    assert client.post(f"/admin/api/audio-reports/{report_id}/resolve", cookies=_admin()).status_code == 200
    assert [r["id"] for r in client.get("/admin/api/audio-reports", cookies=_admin()).json()["reports"]] == [
        "es_es_hablar_male_x"
    ]
    assert client.post("/admin/api/audio-reports/nope/resolve", cookies=_admin()).status_code == 404

    service.submit_audio_report(
        uid="c",
        language="es",
        verb_id="es_hablar",
        voice="female",
        form_key=EXAMPLE_KEY,
        reason="glitch",
        comment=None,
        ui_language="en",
    )
    reopened = {r["id"]: r for r in client.get("/admin/api/audio-reports", cookies=_admin()).json()["reports"]}
    # Resolving restarts the counters, so the reopened row counts only reports made after the fix.
    assert reopened[report_id]["count"] == 1


def test_learn_page_renders_report_buttons_and_popover(client: TestClient, seeded) -> None:
    html = client.get("/learn?language=es&verb_id=es_hablar&ui_language=ru").text

    assert "audio-report-btn" in html
    assert html.count("class='audio-report-btn'") >= 2  # a form row and the example row
    assert 'id="audio-report-pop"' in html
    assert "Сообщить о проблеме с этим аудио" in html  # popover heading, ru
    assert "/static/audio_report.js" in html


# ── cross-device "already reported" state: GET /api/audio_report/mine ─────────


def _mine(client, **params):
    query = {"language": "es", "verb_id": "es_hablar", **params}
    return client.get("/api/audio_report/mine", params=query, headers=AUTH)


def test_mine_anonymous_gets_401(client: TestClient, seeded) -> None:
    resp = client.get("/api/audio_report/mine", params={"language": "es", "verb_id": "es_hablar"})
    assert resp.status_code == 401


def test_mine_empty_when_nothing_reported(client: TestClient, seeded) -> None:
    resp = _mine(client)
    assert resp.status_code == 200
    assert resp.json() == {"reported": []}


def test_mine_includes_a_report_just_submitted_for_both_voices(client: TestClient, seeded) -> None:
    for voice in ("female", "male"):
        assert client.post("/api/audio_report", json=_payload(voice=voice), headers=AUTH).status_code == 200

    reported = _mine(client).json()["reported"]

    assert sorted(reported, key=lambda c: c["voice"]) == [
        {"voice": "female", "form_key": EXAMPLE_KEY},
        {"voice": "male", "form_key": EXAMPLE_KEY},
    ]


def test_mine_does_not_return_another_users_vote(client: TestClient, seeded) -> None:
    from core.audio_report_service import _vote_doc_id

    other_id = _vote_doc_id("someone-else", "es", "es_hablar", "female", EXAMPLE_KEY)
    seeded.seed("audio_report_votes", {other_id: {"language": "es", "verb_id": "es_hablar"}})

    resp = _mine(client)

    assert resp.json() == {"reported": []}
    assert "someone-else" not in resp.text


def test_mine_rejects_bad_language(client: TestClient, seeded) -> None:
    assert _mine(client, language="zz").status_code == 400


def test_mine_reads_only_this_users_votes_for_this_verb(client: TestClient, seeded) -> None:
    other_verb = {
        "uid": "local-dev-user",
        "language": "es",
        "verb_id": "es_comer",
        "voice": "female",
        "form_key": "x_0",
    }
    seeded._docs["audio_report_votes/other_verb_vote"] = other_verb
    client.post("/api/audio_report", json=_payload(), headers=AUTH)

    reported = _mine(client).json()["reported"]

    assert reported == [{"voice": "female", "form_key": EXAMPLE_KEY}]
    assert all("uid" not in clip for clip in reported)


def test_vote_doc_stores_uid_but_aggregate_does_not(client: TestClient, seeded) -> None:
    client.post("/api/audio_report", json=_payload(), headers=AUTH)

    votes = [doc for path, doc in seeded._docs.items() if path.startswith("audio_report_votes/")]
    assert len(votes) == 1 and votes[0]["uid"]
    assert "uid" not in str(_aggregate(seeded)).lower()


def test_resolving_releases_votes_so_the_user_can_report_again(client: TestClient, seeded) -> None:
    client.post("/api/audio_report", json=_payload(), headers=AUTH)
    assert _mine(client).json()["reported"] == [{"voice": "female", "form_key": EXAMPLE_KEY}]
    report_id = f"es_es_hablar_female_{EXAMPLE_KEY}"

    assert client.post(f"/admin/api/audio-reports/{report_id}/resolve", cookies=_admin()).status_code == 200

    assert _mine(client).json()["reported"] == []
    doc = _aggregate(seeded)
    assert doc["status"] == "resolved" and doc["count"] == 0 and doc["resolved_count"] == 1
    again = client.post("/api/audio_report", json=_payload(), headers=AUTH)
    assert again.json() == {"ok": True, "duplicate": False}
    assert _aggregate(seeded)["status"] == "open" and _aggregate(seeded)["count"] == 1


def test_resolving_keeps_votes_for_other_clips(client: TestClient, seeded) -> None:
    client.post("/api/audio_report", json=_payload(), headers=AUTH)
    client.post("/api/audio_report", json=_payload(voice="male"), headers=AUTH)

    client.post(f"/admin/api/audio-reports/es_es_hablar_female_{EXAMPLE_KEY}/resolve", cookies=_admin())

    assert _mine(client).json()["reported"] == [{"voice": "male", "form_key": EXAMPLE_KEY}]
