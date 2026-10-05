"""Known-audio-issue flag (issue #71 follow-up): admin confirm/unconfirm/resolve/fixed, the public flag, the admin page."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core import audio_report_service as service
from core.admin_auth import ADMIN_SESSION_COOKIE, create_admin_session_token
from core.audio_service import build_hashed_audio_key
from core.rate_limit import SlidingWindowRateLimiter
from core.tts import VOICES
from tests.conftest import seed_spanish_verb

EXAMPLE_KEY = build_hashed_audio_key("example_1", "Yo hablo con ella.")
FEMALE_ID = f"es_es_hablar_female_{EXAMPLE_KEY}"
MALE_ID = f"es_es_hablar_male_{EXAMPLE_KEY}"
LEARN = "/learn?language=es&verb_id=es_hablar&ui_language=en"


@pytest.fixture(autouse=True)
def _fresh_limiter(monkeypatch):
    monkeypatch.setattr(service, "_rate_limiter", SlidingWindowRateLimiter(max_calls=50, window_seconds=600))


@pytest.fixture
def seeded(fake_db):
    seed_spanish_verb(fake_db)
    return fake_db


def _admin() -> dict[str, str]:
    return {ADMIN_SESSION_COOKIE: create_admin_session_token()}


def _report(uid="u1", voice="female", comment=None):
    return service.submit_audio_report(
        uid=uid,
        language="es",
        verb_id="es_hablar",
        voice=voice,
        form_key=EXAMPLE_KEY,
        reason="stress",
        comment=comment,
        ui_language="en",
    )


def _act(client, report_id, action):
    return client.post(f"/admin/api/audio-reports/{report_id}/{action}", cookies=_admin())


def _doc(db, report_id):
    return db._docs[f"audio_reports/{report_id}"]


def test_admin_actions_require_auth_and_404_on_unknown(client: TestClient, seeded) -> None:
    for action in ("confirm", "unconfirm", "resolve"):
        assert client.post(f"/admin/api/audio-reports/x/{action}").status_code == 401
    assert _act(client, "nope", "confirm").status_code == 404
    assert _act(client, FEMALE_ID, "fixed").status_code == 404  # no such action any more


def test_confirm_records_state_and_voice_id(client: TestClient, seeded) -> None:
    _report()
    assert _act(client, FEMALE_ID, "confirm").status_code == 200
    doc = _doc(seeded, FEMALE_ID)
    assert doc["status"] == "confirmed" and doc["confirmed_by"] == "admin"
    assert doc["confirmed_voice_id"] == VOICES["es"]["female"].edge_id
    assert doc["reports_since_confirm"] == 0 and doc["confirmed_at"]


def test_wrong_state_is_409(client: TestClient, seeded) -> None:
    _report()
    assert _act(client, FEMALE_ID, "unconfirm").status_code == 409
    _act(client, FEMALE_ID, "confirm")
    assert _act(client, FEMALE_ID, "confirm").status_code == 409
    _act(client, FEMALE_ID, "resolve")
    assert _act(client, FEMALE_ID, "resolve").status_code == 409
    assert _act(client, FEMALE_ID, "unconfirm").status_code == 409


def test_report_on_confirmed_doc_stays_confirmed_and_counts(client: TestClient, seeded) -> None:
    _report("u1", comment="still wrong")
    _act(client, FEMALE_ID, "confirm")
    _report("u2")
    doc = _doc(seeded, FEMALE_ID)
    assert doc["status"] == "confirmed"
    assert doc["reports_since_confirm"] == 1 and doc["count"] == 2


def test_report_on_open_stays_open_and_resolved_reopens(client: TestClient, seeded) -> None:
    _report("u1")
    assert _doc(seeded, FEMALE_ID)["status"] == "open"
    _act(client, FEMALE_ID, "resolve")
    _report("u2")
    assert _doc(seeded, FEMALE_ID)["status"] == "open"


@pytest.mark.parametrize("confirmed_first", [False, True])
def test_resolve_releases_votes_and_resets_counters(client: TestClient, seeded, confirmed_first) -> None:
    _report("u1", comment="x")
    if confirmed_first:
        _act(client, FEMALE_ID, "confirm")
        _report("u2")
    assert [p for p in seeded._docs if p.startswith("audio_report_votes/")]
    assert _act(client, FEMALE_ID, "resolve").status_code == 200
    doc = _doc(seeded, FEMALE_ID)
    assert doc["status"] == "resolved"
    assert doc["count"] == 0 and doc["comments"] == [] and doc["reports_since_confirm"] == 0
    assert doc["resolved_count"] >= 1
    assert not [p for p in seeded._docs if p.startswith("audio_report_votes/")]
    assert service.confirmed_form_keys("es", "es_hablar") == set()


def test_unconfirm_returns_to_open_and_clears_flag(client: TestClient, seeded) -> None:
    _report()
    _act(client, FEMALE_ID, "confirm")
    assert service.confirmed_form_keys("es", "es_hablar") == {EXAMPLE_KEY}
    assert _act(client, FEMALE_ID, "unconfirm").status_code == 200
    assert _doc(seeded, FEMALE_ID)["status"] == "open"
    assert service.confirmed_form_keys("es", "es_hablar") == set()  # cache invalidated by the transition


@pytest.mark.parametrize("voice,report_id", [("female", FEMALE_ID), ("male", MALE_ID)])
def test_confirmed_form_keys_for_either_voice(client: TestClient, seeded, voice, report_id) -> None:
    _report(voice=voice)
    _act(client, report_id, "confirm")
    assert service.confirmed_form_keys("es", "es_hablar") == {EXAMPLE_KEY}
    assert service.confirmed_form_keys("es", "other_verb") == set()


def test_voice_id_mismatch_clears_the_flag(client: TestClient, seeded) -> None:
    _report()
    _act(client, FEMALE_ID, "confirm")
    seeded.collection("audio_reports").document(FEMALE_ID).update({"confirmed_voice_id": "es-ES-OldVoiceNeural"})
    service.invalidate_confirmed_cache("es", "es_hablar")
    assert service.confirmed_form_keys("es", "es_hablar") == set()


def test_confirmed_keys_are_cached_for_a_minute(client: TestClient, seeded, monkeypatch) -> None:
    _report()
    _act(client, FEMALE_ID, "confirm")
    assert service.confirmed_form_keys("es", "es_hablar") == {EXAMPLE_KEY}
    monkeypatch.setattr(service, "get_db", lambda: (_ for _ in ()).throw(AssertionError("queried again")))
    assert service.confirmed_form_keys("es", "es_hablar") == {EXAMPLE_KEY}


def test_learn_shows_issue_icon_and_hides_report_flag_only_for_confirmed(client: TestClient, seeded) -> None:
    _report()
    html = client.get(LEARN).text
    assert "audio-issue-btn" not in html
    flags_before = html.count("class='audio-report-btn'")

    _act(client, FEMALE_ID, "confirm")
    html = client.get(LEARN).text
    assert html.count("audio-issue-btn") >= 1
    assert "Known audio issue" in html and "Read it instead of listening" in html
    # The flagged example row lost its report flag; the other clips on the board keep theirs.
    assert html.count("class='audio-report-btn'") == flags_before - 1
    assert html.count("class='audio-report-btn'") >= 1

    # Both voices show the same flag (it is per form).
    assert "audio-issue-btn" in client.get(LEARN + "&voice=male").text


def test_localized_issue_text(client: TestClient, seeded) -> None:
    _report()
    _act(client, FEMALE_ID, "confirm")
    html = client.get("/learn?language=es&verb_id=es_hablar&ui_language=es").text
    assert "Problema de audio conocido" in html


def test_query_failure_does_not_break_rendering(client: TestClient, seeded, monkeypatch) -> None:
    def boom():
        raise RuntimeError("firestore down")

    monkeypatch.setattr(service, "get_db", boom)
    resp = client.get(LEARN)
    assert resp.status_code == 200
    assert "audio-report-btn" in resp.text and "audio-issue-btn" not in resp.text


# ── admin page and listing ────────────────────────────────────────────────────


def test_admin_page_requires_auth(client: TestClient) -> None:
    resp = client.get("/admin/audio-reports", follow_redirects=False)
    assert resp.status_code in (302, 303, 307) and "/admin/login" in resp.headers["location"]
    assert client.get("/admin/api/audio-reports").status_code == 401


def test_admin_page_renders_and_reports_page_links_to_it(client: TestClient, seeded) -> None:
    page = client.get("/admin/audio-reports", cookies=_admin())
    assert page.status_code == 200 and "/static/admin_audio_reports.js" in page.text
    reports = client.get("/admin/reports", cookies=_admin()).text
    assert "/admin/audio-reports" in reports and 'id="audio-reports-body"' not in reports


def test_listing_filters_and_sorts_by_status(client: TestClient, seeded) -> None:
    _report("u1")
    _report("u2", voice="male")
    _report("u3", voice="male")  # male has 2 open reports
    rows = client.get("/admin/api/audio-reports", cookies=_admin()).json()["reports"]
    assert [r["voice"] for r in rows] == ["male", "female"]

    _act(client, FEMALE_ID, "confirm")
    _report("u4")
    confirmed = client.get("/admin/api/audio-reports?status=confirmed", cookies=_admin()).json()["reports"]
    assert [r["id"] for r in confirmed] == [FEMALE_ID]
    assert confirmed[0]["reports_since_confirm"] == 1 and "uid" not in confirmed[0]

    assert client.get("/admin/api/audio-reports?status=confirmed&language=en", cookies=_admin()).json()["reports"] == []
    assert client.get("/admin/api/audio-reports?status=bogus", cookies=_admin()).status_code == 400


def test_admin_js_escapes_every_interpolated_value() -> None:
    """The page builds rows via innerHTML; a stored <script> comment must only ever pass through escapeHtml."""
    import subprocess
    from pathlib import Path

    js = Path("app/static/admin_audio_reports.js").read_text()
    harness = (
        "const els={};const mk=()=>({dataset:{apiUrl:'/x'},addEventListener(){},innerHTML:'',textContent:'',value:''});"
        "global.document={getElementById:(id)=>els[id]||(els[id]=mk()),querySelectorAll:()=>[]};"
        "global.fetch=()=>Promise.resolve({ok:true,json:()=>Promise.resolve({reports:[{id:'<b>',status:'confirmed',"
        "verb_id:'v',voice:'female',text:'<img src=x onerror=1>',row_kind:'k',count:2,reasons:{stress:1},"
        "comments:['<script>alert(1)</script>'],last_at:'',confirmed_at:'',resolved_at:'',reports_since_confirm:3,"
        "learn_url:'/learn?a=\"><x>'}]})});"
        + js
        + ";setTimeout(()=>{console.log(els['audio-reports-body'].innerHTML)},50);"
    )
    out = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=30).stdout
    assert "&lt;script&gt;" in out and "<script>" not in out
    assert "<img" not in out and "+3 since confirmed" in out


def test_issue_note_is_one_shared_container_not_an_inline_panel(client: TestClient, seeded) -> None:
    _report()
    _act(client, FEMALE_ID, "confirm")
    html = client.get(LEARN).text
    assert html.count('id="audio-issue-note"') == 1
    assert "audio-issue-btn" in html
    # No per-trigger panel inside the (overflow:hidden) tables: the note text rides on the trigger.
    assert "audio-issue-panel" not in html and "help-hint audio-issue" not in html
    assert "data-note=" in html


def test_failed_query_is_cached_briefly(client: TestClient, seeded, monkeypatch) -> None:
    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("down")

    monkeypatch.setattr(service, "get_db", boom)
    assert service.confirmed_form_keys("es", "es_hablar") == set()
    assert service.confirmed_form_keys("es", "es_hablar") == set()
    assert len(calls) == 1


def test_admin_api_rejects_unknown_language(client: TestClient, seeded) -> None:
    assert client.get("/admin/api/audio-reports?language=zz", cookies=_admin()).status_code == 400
