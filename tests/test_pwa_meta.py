"""Tests for PWA meta tags and manifest.json.

Every page that is part of the PWA shell must include:
- <link rel="manifest" href="/static/manifest.json">
- <meta name="theme-color" content="#2d6a4f">
- viewport-fit=cover (for iOS safe area insets)
- /static/pwa.js script tag (install prompt, beforeinstallprompt)

manifest.json must declare scope='/' so the service worker controls the full
origin (required for offline and TWA).
"""

from __future__ import annotations

import contextlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _multi_patch(patches):
    @contextlib.contextmanager
    def _cm():
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            yield

    return _cm()


_PWA_PAGES: list[tuple[str, dict[str, list]]] = [
    ("/?language=en", {"app.routes.home.list_verbs_recent": []}),
    ("/verbs?language=en", {"app.routes.verbs.load_entries_for_language": []}),
    ("/about", {}),
]


@pytest.mark.parametrize("url,patches", _PWA_PAGES)
def test_page_has_pwa_manifest_link(client: TestClient, url: str, patches: dict) -> None:
    ctx_patches = [patch(target, return_value=val) for target, val in patches.items()]
    with _multi_patch(ctx_patches):
        html = client.get(url).text
    assert 'href="/static/manifest.json"' in html


@pytest.mark.parametrize("url,patches", _PWA_PAGES)
def test_page_has_theme_color_meta(client: TestClient, url: str, patches: dict) -> None:
    ctx_patches = [patch(target, return_value=val) for target, val in patches.items()]
    with _multi_patch(ctx_patches):
        html = client.get(url).text
    assert 'name="theme-color"' in html
    assert "#2d6a4f" in html


@pytest.mark.parametrize("url,patches", _PWA_PAGES)
def test_page_has_viewport_fit_cover(client: TestClient, url: str, patches: dict) -> None:
    ctx_patches = [patch(target, return_value=val) for target, val in patches.items()]
    with _multi_patch(ctx_patches):
        html = client.get(url).text
    assert "viewport-fit=cover" in html


@pytest.mark.parametrize("url,patches", _PWA_PAGES)
def test_page_loads_pwa_js(client: TestClient, url: str, patches: dict) -> None:
    ctx_patches = [patch(target, return_value=val) for target, val in patches.items()]
    with _multi_patch(ctx_patches):
        html = client.get(url).text
    assert "/static/pwa.js" in html


def test_manifest_has_scope_root() -> None:
    """manifest.json must declare scope '/' so the SW controls the whole origin."""
    import json
    import pathlib

    manifest = json.loads(pathlib.Path("app/static/manifest.json").read_text())
    assert manifest.get("scope") == "/"
