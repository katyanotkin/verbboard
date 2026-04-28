from __future__ import annotations

from fastapi.testclient import TestClient


def test_search_hit_via_firestore_redirects_to_learn(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: {"verb_id": "en_go"},
    )
    response = client.get("/search_verb?language=en&q=go", follow_redirects=False)
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/learn" in location
    assert "en_go" in location
    assert "language=en" in location


def test_search_hit_sets_cookies(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: {"verb_id": "en_go"},
    )
    response = client.get("/search_verb?language=en&q=go", follow_redirects=False)
    assert "language" in response.cookies or "language" in response.headers.get(
        "set-cookie", ""
    )


def test_search_miss_logs_demand_signal(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: None,
    )
    log_calls: list[dict] = []
    monkeypatch.setattr(
        "app.routes.home.log_missing_verb_search",
        lambda **kwargs: log_calls.append(kwargs),
    )
    client.get("/search_verb?language=en&q=xyzzyverb", follow_redirects=False)
    assert len(log_calls) == 1
    assert log_calls[0]["language"] == "en"
    assert log_calls[0]["query"] == "xyzzyverb"


def test_search_miss_redirects_with_not_available(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: None,
    )
    monkeypatch.setattr(
        "app.routes.home.log_missing_verb_search",
        lambda **kwargs: None,
    )
    response = client.get(
        "/search_verb?language=en&q=xyzzyverb", follow_redirects=False
    )
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "not_available=1" in location
    assert "learn" not in location


def test_search_empty_query_redirects_to_home(client: TestClient) -> None:
    response = client.get("/search_verb?language=en&q=", follow_redirects=False)
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "learn" not in location
    assert "not_available" not in location
