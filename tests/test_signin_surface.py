"""Regression guards for the sign-in surface that are not behavior of auth.js itself.

1. window.FIREBASE_WEB_CONFIG is present and complete on every page that loads
   auth.js (and /auth/signin), carries the public GIS client id, and leaks
   nothing beyond the configured public web config.
2. /auth/signin is localized and forwards the UI language to Google as `hl`.
3. The app never shadows Firebase Hosting's /__/auth/* helper.
4. The service worker never caches sign-in pages or the auth handler, every
   precached asset exists, and the cache version documented in CLAUDE.md
   matches sw.js.

A stale cached sign-in page or auth handler is a classic cause of
"missing initial state" style failures, so these are static and cheap.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.settings import _DEFAULT_GOOGLE_OAUTH_WEB_CLIENT_ID, _safe_firebase_config
from tests.conftest import seed_spanish_verb

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"

_WEB_CONFIG = {
    "apiKey": "AIza-test-key",
    "authDomain": "stage.verbboard.com",
    "projectId": "verbboard-test",
    "appId": "1:123:web:abc",
    "messagingSenderId": "123",
}
_REQUIRED_KEYS = {"apiKey", "authDomain", "projectId", "appId", "gisClientId"}

_CONFIG_RE = re.compile(r"window\.FIREBASE_WEB_CONFIG\s*=\s*(.*?);\s*(?:\n|</script>)", re.S)


def _first_group(match: re.Match[str] | None) -> str:
    assert match is not None, "pattern not found"
    return match.group(1)


def _page_config(html: str) -> dict:
    match = _CONFIG_RE.search(html)
    assert match, "window.FIREBASE_WEB_CONFIG assignment missing"
    return json.loads(match.group(1))


@pytest.fixture()
def configured(monkeypatch, fake_db):
    monkeypatch.setenv("FIREBASE_WEB_CONFIG_JSON", json.dumps(_WEB_CONFIG))
    monkeypatch.delenv("GOOGLE_OAUTH_WEB_CLIENT_ID", raising=False)
    seed_spanish_verb(fake_db)


_SIGNIN_PAGES = [
    "/",
    "/verbs?language=es",
    "/learn?language=es&verb_id=es_hablar",
    "/feedback",
    "/auth/signin",
]


@pytest.mark.parametrize("path", _SIGNIN_PAGES)
def test_firebase_web_config_complete_on_auth_pages(client: TestClient, configured, path: str) -> None:
    resp = client.get(path)
    assert resp.status_code == 200, path
    cfg = _page_config(resp.text)
    assert _REQUIRED_KEYS <= set(cfg), f"{path} missing {_REQUIRED_KEYS - set(cfg)}"
    assert cfg["authDomain"] == _WEB_CONFIG["authDomain"]  # passed through untouched
    assert cfg["gisClientId"] == _DEFAULT_GOOGLE_OAUTH_WEB_CLIENT_ID
    assert cfg["gisClientId"].endswith(".apps.googleusercontent.com")


@pytest.mark.parametrize("path", ["/", "/verbs?language=es", "/learn?language=es&verb_id=es_hablar"])
def test_auth_js_is_loaded_after_config_on_auth_pages(client: TestClient, configured, path: str) -> None:
    html = client.get(path).text
    assert html.index("window.FIREBASE_WEB_CONFIG") < html.index("/static/auth.js")


def test_gis_client_id_is_overridable_by_env(client: TestClient, monkeypatch, configured) -> None:
    monkeypatch.setenv("GOOGLE_OAUTH_WEB_CLIENT_ID", "override.apps.googleusercontent.com")
    assert _page_config(client.get("/feedback").text)["gisClientId"] == "override.apps.googleusercontent.com"


def test_safe_firebase_config_adds_only_the_gis_client_id() -> None:
    out = json.loads(_safe_firebase_config(json.dumps(_WEB_CONFIG), gis_client_id="cid.apps.googleusercontent.com"))
    assert set(out) - set(_WEB_CONFIG) == {"gisClientId"}
    assert {k: out[k] for k in _WEB_CONFIG} == _WEB_CONFIG


@pytest.mark.parametrize("raw", ["", "not json", "null"])
def test_safe_firebase_config_without_real_config_stays_null(raw: str) -> None:
    assert _safe_firebase_config(raw, gis_client_id="x.apps.googleusercontent.com") == "null"


def test_safe_firebase_config_escapes_script_breakers() -> None:
    out = _safe_firebase_config(json.dumps({"apiKey": "</script><b>&"}), gis_client_id="c")
    assert "<" not in out and ">" not in out and "&" not in out
    assert json.loads(out)["apiKey"] == "</script><b>&"


def test_page_config_does_not_leak_server_secrets(client: TestClient, monkeypatch, configured) -> None:
    """Only the public web config + gisClientId may reach the page."""
    monkeypatch.setenv("ADMIN_SECRET", "super-secret-admin-value")
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "super-secret-session-value")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-value")
    for path in _SIGNIN_PAGES:
        html = client.get(path).text
        for secret in ("super-secret-admin-value", "super-secret-session-value", "sk-ant-secret-value"):
            assert secret not in html, f"{secret} leaked on {path}"
        assert set(_page_config(html)) <= set(_WEB_CONFIG) | {"gisClientId"}


# --- /auth/signin ------------------------------------------------------------


@pytest.mark.parametrize("lang", ["en", "ru", "es", "he"])
def test_signin_page_passes_ui_language_as_hl(client: TestClient, configured, lang: str) -> None:
    html = client.get(f"/auth/signin?ui_language={lang}").text
    assert f"hl: {json.dumps(lang)}" in html
    assert "prompt: 'select_account'" in html


def test_signin_page_strings_are_localized_and_complete(client: TestClient, configured) -> None:
    from app.routes.auth_pages import _SIGNIN_STRINGS

    html = client.get("/auth/signin?ui_language=ru").text
    strings = json.loads(_first_group(re.search(r"const S = (\{.*?\});\n", html, re.S)))
    assert set(strings) == set(_SIGNIN_STRINGS)
    assert strings["signin.button"] != _SIGNIN_STRINGS["signin.button"]  # not the English fallback


def test_signin_page_without_return_to_is_not_an_open_redirect(client: TestClient, configured) -> None:
    html = client.get("/auth/signin?return_to=https://evil.example/x").text
    assert "evil.example" not in html


# --- Firebase Hosting helper is not shadowed ---------------------------------


def test_no_app_route_shadows_firebase_auth_helper(client: TestClient) -> None:
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert not [p for p in paths if p.startswith("/__")], (
        "app must not define /__/* routes (Firebase Hosting owns them)"
    )
    # Falling through to the app must be a plain 404, never a page or redirect.
    for path in ("/__/auth/handler", "/__/auth/iframe", "/__/firebase/init.json"):
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code == 404, path


# --- service worker ----------------------------------------------------------


def _sw_text() -> str:
    return (STATIC / "sw.js").read_text()


def _precache_list() -> list[str]:
    block = _first_group(re.search(r"const PRECACHE = \[(.*?)\];", _sw_text(), re.S))
    return re.findall(r'"([^"]+)"', block)


def test_precached_assets_exist() -> None:
    missing = [u for u in _precache_list() if not (ROOT / "app" / u.lstrip("/")).is_file()]
    assert not missing, f"sw.js precaches files that do not exist: {missing}"


def test_sw_never_precaches_auth_pages() -> None:
    bad = [u for u in _precache_list() if u.startswith(("/auth", "/__/auth", "/api"))]
    assert not bad
    # auth.js is the one auth asset allowed in the cache; it is a /static file.
    assert "/static/auth.js" in _precache_list()


def test_sw_navigations_are_network_only_with_offline_fallback() -> None:
    """Navigations (including /auth/signin and /__/auth/handler) must never be
    answered from the cache; only the offline page is a fallback."""
    sw = _sw_text()
    nav_block = _first_group(re.search(r'mode === "navigate"\) \{(.*?)\n  \}', sw, re.S))
    assert "fetch(e.request)" in nav_block
    assert 'caches.match("/static/offline.html")' in nav_block
    assert "caches.match(e.request)" not in nav_block
    assert "cache.put" not in sw and ".put(" not in sw  # nothing is added to the cache at runtime


def test_sw_does_not_claim_clients() -> None:
    """clients.claim() mid-session cancels in-progress Firebase sign-in popups."""
    assert not re.search(r"^\s*[^/\n]*clients\.claim\(\)", _sw_text(), re.M)


def test_sw_cache_version_matches_claude_md() -> None:
    version = _first_group(re.search(r'const CACHE = "(vb-v\d+)"', _sw_text()))
    mentions = set(re.findall(r"vb-v\d+", (ROOT / "CLAUDE.md").read_text()))
    assert mentions == {version}, f"CLAUDE.md mentions {mentions}, sw.js is {version}"


# --- assets referenced by sign-in pages --------------------------------------


@pytest.mark.parametrize("path", ["/auth/signin", "/feedback", "/verbs?language=es"])
def test_static_assets_referenced_by_signin_pages_exist(client: TestClient, configured, path: str) -> None:
    html = client.get(path).text
    refs = set(re.findall(r'(?:src|href)="(/static/[^"?#]+)', html))
    assert refs, path
    missing = [r for r in refs if not (ROOT / "app" / r.lstrip("/")).is_file()]
    assert not missing, f"{path} references missing assets: {missing}"
