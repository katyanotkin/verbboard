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


def test_plus_page_renders_card_and_ordinary_form(client) -> None:
    html = client.get("/feedback?page=plus&language=tr&ui_language=en").text
    assert 'id="plus-request"' in html and "plus_request.js" in html
    assert 'data-plus-act="request"' in html
    assert 'id="feedback-form"' in html
    assert "plus-id-token" not in html


def test_plus_page_invalid_language_falls_back_to_normal(client) -> None:
    html = client.get("/feedback?page=plus&language=xx&ui_language=en").text
    assert 'id="plus-request"' not in html


def _record_into(saved: list[dict]):
    def record(**kwargs) -> str:
        saved.append(kwargs)
        return "x"

    return record


def test_plus_page_posts_ordinary_feedback_without_required_email(client, monkeypatch) -> None:
    saved: list[dict] = []
    monkeypatch.setattr("app.routes.feedback.save_feedback", _record_into(saved))
    response = client.post(
        "/feedback",
        data={"page": "plus", "language": "tr", "comment": "hi", "ui_language": "en", "return_to": "/verbs"},
        follow_redirects=False,
    )
    assert response.status_code == 303 and "success=1" in response.headers["location"]
    assert saved and saved[0]["page"] == "plus"


def test_verbs_and_about_link_to_plus_page(client) -> None:
    about = client.get("/about?ui_language=en").text
    assert "page=plus&amp;language=tr" in about and "VerbBoard Plus" in about
    assert client.get("/feedback?page=plus&language=tr&ui_language=en").status_code == 200


def test_plus_i18n_keys_in_all_locales() -> None:
    import json
    from pathlib import Path

    wanted = {
        "plus.request_btn",
        "plus.request_done",
        "plus.request_already",
        "plus.request_error",
        "plus.signin_prompt",
        "plus.signin_btn",
        "plus.about_title",
        "plus.about_body",
        "plus.req_account",
        "plus.req_lang",
    }
    for code in ("en", "ru", "he", "es"):
        data = json.loads(Path(f"app/i18n/{code}.json").read_text(encoding="utf-8"))
        assert wanted <= set(data)
        assert "{email}" in data["plus.req_account"]
        assert "note_label" not in "".join(data)


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


# ---------------------------------------------------------------------------
# Spam filtering
# ---------------------------------------------------------------------------


def _capture_saves(monkeypatch) -> list[dict]:
    saved: list[dict] = []

    def _fake_save(**kw) -> str:
        saved.append(kw)
        return "id"

    monkeypatch.setattr("app.routes.feedback.save_feedback", _fake_save)
    return saved


def test_feedback_blocked_email_domain_is_not_saved(client: TestClient, monkeypatch) -> None:
    saved = _capture_saves(monkeypatch)
    for email in ("bot@formtests.info", "Bot@FormTests.Info", "x@mail.formtests.info"):
        resp = client.post(
            "/feedback", data={"comment": "garbage", "contact_email": email, "return_to": "/"}, follow_redirects=False
        )
        assert resp.status_code == 303
    assert saved == []


def test_feedback_filled_honeypot_is_not_saved(client: TestClient, monkeypatch) -> None:
    saved = _capture_saves(monkeypatch)
    resp = client.post(
        "/feedback", data={"comment": "hi", "hp_url": "http://spam", "return_to": "/"}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert saved == []


def test_feedback_similar_domain_and_normal_submit_still_saved(client: TestClient, monkeypatch) -> None:
    saved = _capture_saves(monkeypatch)
    client.post(
        "/feedback",
        data={"comment": "real", "contact_email": "a@notformtests.info", "return_to": "/"},
        follow_redirects=False,
    )
    client.post("/feedback", data={"comment": "real2", "return_to": "/"}, follow_redirects=False)
    assert len(saved) == 2


def test_feedback_form_has_honeypot_input(client: TestClient) -> None:
    assert 'name="hp_url"' in client.get("/feedback").text


def test_feedback_spam_redirect_matches_real_success_redirect(client: TestClient, monkeypatch) -> None:
    _capture_saves(monkeypatch)
    data = {"comment": "x", "return_to": "/", "page": "about"}
    real = client.post("/feedback", data=data, follow_redirects=False)
    spam = client.post("/feedback", data={**data, "hp_url": "bot"}, follow_redirects=False)
    assert spam.headers["location"] == real.headers["location"]


def test_feedback_blocked_email_in_angle_brackets(client: TestClient, monkeypatch) -> None:
    saved = _capture_saves(monkeypatch)
    client.post(
        "/feedback",
        data={"comment": "x", "contact_email": "Bot <a@formtests.info>", "return_to": "/"},
        follow_redirects=False,
    )
    assert saved == []


def test_feedback_with_two_links_is_saved_hidden(client: TestClient, monkeypatch) -> None:
    saved = _capture_saves(monkeypatch)
    comment = "Boost your SEO https://spam.example and www.spam2.example today"
    resp = client.post("/feedback", data={"comment": comment, "return_to": "/"}, follow_redirects=False)
    assert resp.status_code == 303
    assert len(saved) == 1
    assert saved[0]["hidden"] is True


def test_feedback_genuine_comments_are_not_hidden(client: TestClient, monkeypatch) -> None:
    saved = _capture_saves(monkeypatch)
    for comment in (
        "Great app. The audio for the Spanish past tense is sometimes cut off. Please check it again soon.",
        "See https://example.com for the rule I mean.",
    ):
        client.post("/feedback", data={"comment": comment, "return_to": "/"}, follow_redirects=False)
    assert [kwargs["hidden"] for kwargs in saved] == [False, False]


def test_link_spam_counts_each_url_once() -> None:
    from core.feedback_spam import looks_like_link_spam

    assert not looks_like_link_spam("see https://www.example.com for the rule")
    assert not looks_like_link_spam("awww. nice, www.example.com")
    assert looks_like_link_spam("https://www.a.example and https://www.b.example")
