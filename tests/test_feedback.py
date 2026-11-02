from __future__ import annotations

from urllib.parse import unquote

from fastapi.testclient import TestClient


def test_feedback_get_returns_form(client: TestClient) -> None:
    response = client.get("/feedback")
    assert response.status_code == 200
    assert "<form" in response.text
    assert "Feedback" in response.text


def test_feedback_get_shows_poll_question(client: TestClient) -> None:
    response = client.get("/feedback?language=en")
    assert response.status_code == 200
    # ACTIVE_POLL_ID is set, so a poll block should appear
    assert "poll_answer" in response.text


def test_feedback_get_success_flag_shows_confirmation(client: TestClient) -> None:
    response = client.get("/feedback?success=1")
    assert "Thanks" in response.text


def test_feedback_get_error_flag_shows_error(client: TestClient) -> None:
    response = client.get("/feedback?error=empty")
    assert "comment" in response.text.lower() or "Yes/No" in response.text


def test_feedback_submit_comment_calls_save_and_redirects(client: TestClient, monkeypatch) -> None:
    saved: list[dict] = []

    def fake_save(**kwargs):
        saved.append(kwargs)
        return "doc-123"

    monkeypatch.setattr("app.routes.feedback.save_feedback", fake_save)

    response = client.post(
        "/feedback",
        data={"comment": "Really useful app!", "return_to": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert len(saved) == 1
    assert saved[0]["comment"] == "Really useful app!"


def test_feedback_submit_poll_answer_saved(client: TestClient, monkeypatch) -> None:
    saved: list[dict] = []

    def fake_save(**kwargs):
        saved.append(kwargs)
        return "doc-456"

    monkeypatch.setattr("app.routes.feedback.save_feedback", fake_save)

    response = client.post(
        "/feedback",
        data={"poll_answer": "more_languages", "return_to": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert saved[0]["poll_answer"] == "more_languages"


def test_feedback_submit_empty_redirects_with_error(client: TestClient) -> None:
    # save_feedback raises ValueError before any Firestore call when both fields empty
    response = client.post(
        "/feedback",
        data={"comment": "", "poll_answer": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=empty" in response.headers["location"]


def test_feedback_submit_invalid_poll_answer_treated_as_empty(client: TestClient, monkeypatch) -> None:
    """An unrecognized poll_answer value is discarded; without a comment it errors."""
    response = client.post(
        "/feedback",
        data={"comment": "", "poll_answer": "maybe"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=empty" in response.headers["location"]


def test_feedback_submit_detects_mobile_device(client: TestClient, monkeypatch) -> None:
    saved: list[dict] = []

    def fake_save(**kwargs):
        saved.append(kwargs)
        return "doc-789"

    monkeypatch.setattr("app.routes.feedback.save_feedback", fake_save)

    mobile_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
    response = client.post(
        "/feedback",
        data={"comment": "sent from phone", "return_to": "/"},
        headers={"User-Agent": mobile_ua},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert saved[0]["device_type"] == "mobile"


def test_feedback_submit_redirects_to_return_to(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.feedback.save_feedback",
        lambda **kw: "doc-000",
    )

    response = client.post(
        "/feedback",
        data={"comment": "good", "return_to": "/learn?language=en&verb_id=en_go"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/learn" in unquote(response.headers["location"])


def test_feedback_comment_truncated_to_4000_chars(client: TestClient, monkeypatch) -> None:
    saved: list[dict] = []

    def _fake_save(**kw) -> str:
        saved.append(kw)
        return "id"

    monkeypatch.setattr("app.routes.feedback.save_feedback", _fake_save)

    response = client.post("/feedback", data={"comment": "x" * 5000, "return_to": "/"}, follow_redirects=False)

    assert response.status_code == 303
    assert len(saved) == 1
    assert len(saved[0]["comment"]) == 4000


def test_feedback_eleventh_submit_in_window_is_not_saved(client: TestClient, monkeypatch) -> None:
    saved: list[dict] = []

    def _fake_save(**kw) -> str:
        saved.append(kw)
        return "id"

    monkeypatch.setattr("app.routes.feedback.save_feedback", _fake_save)

    statuses = [
        client.post("/feedback", data={"comment": f"c{i}", "return_to": "/"}, follow_redirects=False).status_code
        for i in range(11)
    ]

    assert len(saved) == 10
    assert set(statuses) == {303}


# ---------------------------------------------------------------------------
# Success card + Plus access requests
# ---------------------------------------------------------------------------

from core.auth.models import AuthUser  # noqa: E402


def _token_user(monkeypatch, uid="u1", email="acct@example.com"):
    def fake_verify(token):
        if token != "good":
            raise ValueError("bad token")
        return AuthUser(uid=uid, email=email, name="", picture="")

    monkeypatch.setattr("app.routes.feedback.verify_firebase_token", fake_verify)


def _recorder(saved: list[dict]):
    def _save(**kw):
        saved.append(kw)
        return "x"

    return _save


def _plus_post(client, **overrides):
    data = {
        "page": "plus",
        "language": "tr",
        "comment": "please",
        "contact_email": "reply@example.com",
        "ui_language": "en",
        "return_to": "/verbs",
        "id_token": "good",
    }
    data.update(overrides)
    return client.post("/feedback", data=data, follow_redirects=False)


def _plus_docs(fake_db):
    return [d for d in fake_db.collection("plus_requests").stream()]


def test_normal_feedback_redirects_to_success_card(client, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.feedback.save_feedback", lambda **kw: "x")
    response = client.post(
        "/feedback",
        data={"comment": "hi", "page": "verbs", "language": "es", "ui_language": "en", "return_to": "/verbs"},
        follow_redirects=False,
    )
    location = response.headers["location"]
    assert location.startswith("/feedback?")
    for part in ("success=1", "page=verbs", "language=es", "ui_language=en", "return_to=%2Fverbs"):
        assert part in location
    page = client.get(location)
    assert "Thanks" in page.text
    assert "<form" not in page.text


def test_plus_form_renders_variant(client) -> None:
    html = client.get("/feedback?page=plus&language=tr&ui_language=en").text
    assert "Request Plus access" in html
    assert "plus-id-token" in html
    assert "poll_answer" not in html
    assert 'maxlength="300"' in html


def test_plus_form_invalid_language_falls_back_to_normal(client) -> None:
    html = client.get("/feedback?page=plus&language=xx&ui_language=en").text
    assert "plus-id-token" not in html


def test_plus_request_uses_verified_token_identity(client, monkeypatch, fake_db) -> None:
    _token_user(monkeypatch)
    saved: list[dict] = []
    monkeypatch.setattr("app.routes.feedback.save_feedback", _recorder(saved))
    response = _plus_post(client, uid="forged", email="forged@example.com")
    assert response.status_code == 303
    assert "success=1" in response.headers["location"]
    docs = _plus_docs(fake_db)
    assert len(docs) == 1
    data = docs[0].to_dict()
    assert data["uid"] == "u1"
    assert data["email"] == "acct@example.com"
    assert data["status"] == "open" and data["language"] == "tr"
    assert saved[0]["page"] == "plus" and "account_email" not in saved[0]
    assert saved[0]["request_id"] == docs[0].id
    assert data["contact_email"] == "reply@example.com"
    page = client.get(response.headers["location"])
    assert "We will email you" in page.text and "forged" not in page.text


def test_plus_request_anonymous_or_bad_token_401(client, monkeypatch, fake_db) -> None:
    _token_user(monkeypatch)
    assert "error=signin" in _plus_post(client, id_token="").headers["location"]
    assert "error=signin" in _plus_post(client, id_token="bad").headers["location"]
    assert "Sign in with Google" in client.get(_plus_post(client, id_token="").headers["location"]).text
    assert _plus_docs(fake_db) == []


def test_plus_request_honeypot_stores_nothing(client, monkeypatch, fake_db) -> None:
    _token_user(monkeypatch)
    saved: list[dict] = []
    monkeypatch.setattr("app.routes.feedback.save_feedback", _recorder(saved))
    response = _plus_post(client, website="http://spam")
    assert response.status_code == 303
    assert _plus_docs(fake_db) == [] and saved == []


def test_plus_request_dedupes(client, monkeypatch, fake_db) -> None:
    _token_user(monkeypatch)
    saved: list[dict] = []
    monkeypatch.setattr("app.routes.feedback.save_feedback", _recorder(saved))
    _plus_post(client)
    second = _plus_post(client)
    assert "success=dup" in second.headers["location"]
    assert len(_plus_docs(fake_db)) == 1 and len(saved) == 1
    assert "already asked" in client.get(second.headers["location"]).text


def test_plus_request_validation(client, monkeypatch, fake_db) -> None:
    _token_user(monkeypatch)
    monkeypatch.setattr("app.routes.feedback.save_feedback", lambda **kw: "x")
    assert "error=email_invalid" in _plus_post(client, contact_email="nope").headers["location"]
    assert "error=note" in _plus_post(client, comment="x" * 301).headers["location"]
    assert "error=language" in _plus_post(client, language="fr").headers["location"]
    assert "error=language" in _plus_post(client, language="zz").headers["location"]
    assert _plus_docs(fake_db) == []


def test_plus_request_rate_limited(client, monkeypatch, fake_db) -> None:
    _token_user(monkeypatch)
    monkeypatch.setattr("app.routes.feedback.save_feedback", lambda **kw: "x")
    for _ in range(10):
        _plus_post(client)
    response = _plus_post(client)
    assert response.headers["location"] == "/verbs"


def test_admin_row_exposes_plus_fields(fake_db) -> None:
    from core.admin_feedback_service import _normalize_feedback_doc

    class Doc:
        id = "d"

        def to_dict(self):
            return {"page": "plus", "language": "tr", "contact_email": "r@x.com", "account_email": "a@x.com"}

    row = _normalize_feedback_doc(Doc())
    assert row["page"] == "plus" and row["contact_email"] == "r@x.com"


def test_entitlement_grant_marks_request_granted(client, monkeypatch, fake_db) -> None:
    from core.entitlements import set_entitlement

    _token_user(monkeypatch)
    monkeypatch.setattr("app.routes.feedback.save_feedback", lambda **kw: "x")
    _plus_post(client)
    set_entitlement(uid="u1", status="active")
    assert _plus_docs(fake_db)[0].to_dict()["status"] == "granted"


def test_plus_notice_link_and_about_link_resolve(client) -> None:
    about = client.get("/about?ui_language=en").text
    assert "page=plus&amp;language=tr" in about
    assert client.get("/feedback?page=plus&language=tr&ui_language=en").status_code == 200


def test_plus_i18n_keys_in_all_locales() -> None:
    import json
    from pathlib import Path

    keys = None
    for code in ("en", "ru", "he", "es"):
        data = json.loads(Path(f"app/i18n/{code}.json").read_text(encoding="utf-8"))
        plus = {k for k in data if k.startswith("plus.req_") or k == "about.plus_request"}
        assert len(plus) >= 11
        keys = plus if keys is None else keys
        assert plus == keys
        assert "{email}" in data["plus.req_account"]


def test_plus_request_token_without_email_rejected(client, monkeypatch, fake_db) -> None:
    _token_user(monkeypatch, email="")
    assert "error=signin" in _plus_post(client).headers["location"]
    assert _plus_docs(fake_db) == []


def test_plus_request_write_failure_is_friendly(client, monkeypatch, fake_db) -> None:
    _token_user(monkeypatch)

    def boom(**kw):
        raise RuntimeError("firestore down")

    monkeypatch.setattr("app.routes.feedback.create_plus_request", boom)
    response = _plus_post(client)
    assert response.status_code == 303 and "error=failed" in response.headers["location"]


def test_success_card_neutralises_hostile_query(client) -> None:
    url = (
        "/feedback?success=1&page=plus&language=tr&ui_language=en"
        "&plus_email=%3Cscript%3Ealert(1)%3C/script%3E&return_to=https://evil.example/x"
    )
    html = client.get(url).text
    assert "<script>alert(1)" not in html
    assert "evil.example" not in html
    hostile = client.get("/feedback?success=1&return_to=//evil.example&language=%22%3E%3Cb%3E").text
    assert "evil.example" not in hostile and "<b>" not in hostile


def test_account_deletion_removes_plus_requests(client, monkeypatch, fake_db) -> None:
    from core.plus_request_service import delete_plus_requests_for_uid

    _token_user(monkeypatch)
    monkeypatch.setattr("app.routes.feedback.save_feedback", lambda **kw: "x")
    _plus_post(client)
    assert len(_plus_docs(fake_db)) == 1
    delete_plus_requests_for_uid("other")
    assert len(_plus_docs(fake_db)) == 1
    delete_plus_requests_for_uid("u1")
    assert _plus_docs(fake_db) == []


def test_delete_account_invokes_plus_request_cleanup() -> None:
    from unittest.mock import patch

    from core import account_deletion

    with (
        patch.object(account_deletion, "delete_all_progress_data"),
        patch.object(account_deletion, "delete_entitlement"),
        patch.object(account_deletion, "delete_sessions_for_uid"),
        patch.object(account_deletion, "delete_plus_requests_for_uid") as plus,
        patch.object(account_deletion, "_delete_auth_user"),
    ):
        account_deletion.delete_account("u1")
    plus.assert_called_once_with("u1")


def test_admin_rows_resolve_account_email_by_request_id(fake_db) -> None:
    from core.admin_feedback_service import list_feedback_rows
    from core.feedback_store import save_feedback  # noqa: F401
    from core.plus_request_service import create_plus_request, request_doc_id

    for uid, email in (("u1", "a@x.com"), ("u2", "b@x.com")):
        # both users claim the same (forged) contact email
        create_plus_request(uid=uid, email=email, contact_email="a@x.com", language="tr", note="", ui_language="en")
    for i, uid in enumerate(("u1", "u2")):
        fake_db.collection("feedback").document(f"f{i}").set(
            {
                "page": "plus",
                "language": "tr",
                "contact_email": "a@x.com",
                "request_id": request_doc_id(uid, "tr"),
                "created_at": __import__("datetime").datetime(2026, 1, 1 + i),
            }
        )
    # older row without request_id: no account email, so no Grant link
    fake_db.collection("feedback").document("old").set(
        {
            "page": "plus",
            "language": "tr",
            "contact_email": "a@x.com",
            "created_at": __import__("datetime").datetime(2025, 1, 1),
        }
    )
    rows = {
        r["id"]: r
        for r in list_feedback_rows(
            sort="newest", visibility="all", page="", language="", source="", query="", limit=50
        )
    }
    assert rows["f0"]["account_email"] == "a@x.com"
    assert rows["f1"]["account_email"] == "b@x.com"
    assert rows["old"]["account_email"] == ""
