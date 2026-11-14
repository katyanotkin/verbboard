"""robots.txt and sitemap.xml (issue #103)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import seed_spanish_verb

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _locs(response) -> list[str]:
    return [el.text or "" for el in ET.fromstring(response.text).findall("s:url/s:loc", NS)]


def test_robots_prod(client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    for prefix in ("/admin", "/audio", "/api", "/auth", "/feedback"):
        assert f"Disallow: {prefix}\n" in r.text
    assert "Disallow: /__/\n" in r.text
    for allowed in ("/static", "/learn", "/verbs", "/about", "/terms"):
        assert f"Disallow: {allowed}" not in r.text
    assert "Disallow: /\n" not in r.text
    assert "Sitemap: https://verbboard.com/sitemap.xml" in r.text


@pytest.mark.parametrize("env", ["stage", "local"])
def test_robots_non_prod_blocks_all(client, monkeypatch, env):
    monkeypatch.setenv("ENVIRONMENT", env)
    r = client.get("/robots.txt")
    assert r.text == "User-agent: *\nDisallow: /\n"
    assert "/__/" not in r.text
    assert "Sitemap" not in r.text


def test_sitemap_contains_free_verb_and_is_valid_xml(client, fake_db):
    seed_spanish_verb(fake_db)
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    assert r.headers["cache-control"] == "public, max-age=3600"
    locs = _locs(r)
    assert "https://verbboard.com/learn?language=es&verb_id=es_hablar&ui_language=en" in locs
    assert "https://verbboard.com/verbs?language=es&ui_language=en" in locs
    assert "&amp;" in r.text and "&verb_id" not in r.text


def test_sitemap_excludes_plus_only_language(client, fake_db):
    fake_db.collection("verbs").document("tr_yapmak").set(
        {"language": "tr", "verb_id": "tr_yapmak", "lemma": "yapmak", "rank": 1, "forms": {}, "examples": []}
    )
    seed_spanish_verb(fake_db)
    r = client.get("/sitemap.xml")
    assert not any("language=tr" in loc or "tr_yapmak" in loc for loc in _locs(r))


def test_sitemap_503_on_loader_failure(client, monkeypatch):
    def boom(**_kwargs):
        raise RuntimeError("firestore down")

    monkeypatch.setattr("core.sitemap_service.load_entries_for_language", boom)
    r = client.get("/sitemap.xml")
    assert r.status_code == 503
    assert r.headers["cache-control"] == "no-store"


def test_sitemap_truncates_over_limit(client, fake_db, monkeypatch):
    seed_spanish_verb(fake_db)
    monkeypatch.setattr("core.sitemap_service.MAX_SITEMAP_URLS", 2)
    assert len(_locs(client.get("/sitemap.xml"))) == 2
