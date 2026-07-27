"""Tests for /.well-known/assetlinks.json -- Android TWA Digital Asset Links.

The assetlinks endpoint is required for Trusted Web Activity (TWA) on Android.
It must declare the correct relation, namespace, package name, and SHA-256
fingerprint so the Android OS can verify the app's origin.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_assetlinks_returns_200(client: TestClient) -> None:
    resp = client.get("/.well-known/assetlinks.json")
    assert resp.status_code == 200


def test_assetlinks_content_type_is_json(client: TestClient) -> None:
    resp = client.get("/.well-known/assetlinks.json")
    assert "application/json" in resp.headers["content-type"]


def test_assetlinks_is_a_list(client: TestClient) -> None:
    data = client.get("/.well-known/assetlinks.json").json()
    assert isinstance(data, list)
    assert len(data) == 1


def test_assetlinks_has_required_relation(client: TestClient) -> None:
    data = client.get("/.well-known/assetlinks.json").json()
    entry = data[0]
    assert "relation" in entry
    assert "delegate_permission/common.handle_all_urls" in entry["relation"]


def test_assetlinks_target_has_namespace_and_package(client: TestClient) -> None:
    data = client.get("/.well-known/assetlinks.json").json()
    target = data[0]["target"]
    assert target["namespace"] == "android_app"
    assert target["package_name"] == "com.verbboard.app"


def test_assetlinks_target_has_fingerprints_list(client: TestClient) -> None:
    data = client.get("/.well-known/assetlinks.json").json()
    fps = data[0]["target"]["sha256_cert_fingerprints"]
    assert isinstance(fps, list)
    assert len(fps) >= 1


# ── edition config overrides ──────────────────────────────────────────────────


def test_assetlinks_reflects_android_package_and_fingerprint_overrides(client: TestClient, monkeypatch) -> None:
    """A Plus-edition deployment overriding ANDROID_PACKAGE_NAME/ANDROID_CERT_FINGERPRINTS
    must be reflected in the served assetlinks.json (settings are read per-request,
    not cached at startup)."""
    monkeypatch.setenv("ANDROID_PACKAGE_NAME", "com.example.plus")
    monkeypatch.setenv("ANDROID_CERT_FINGERPRINTS", "AA:BB:CC,DD:EE:FF")

    data = client.get("/.well-known/assetlinks.json").json()
    target = data[0]["target"]

    assert target["package_name"] == "com.example.plus"
    assert target["sha256_cert_fingerprints"] == ["AA:BB:CC", "DD:EE:FF"]
