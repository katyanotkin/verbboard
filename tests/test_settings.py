from __future__ import annotations

import pytest

from core.settings import _load_admin_secret, load_settings


def test_missing_audio_bucket_raises(monkeypatch):
    monkeypatch.delenv("AUDIO_BUCKET", raising=False)
    with pytest.raises(ValueError, match="AUDIO_BUCKET must be set"):
        load_settings()


def test_missing_gcp_project_raises(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT must be set"):
        load_settings()


def test_missing_admin_secret_raises(monkeypatch):
    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    _load_admin_secret.cache_clear()
    try:
        with pytest.raises(ValueError):
            load_settings()
    finally:
        _load_admin_secret.cache_clear()


def test_valid_settings_loads():
    settings = load_settings()
    assert settings.audio_bucket
    assert settings.google_cloud_project
    assert settings.admin_secret
