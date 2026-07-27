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


# ── edition config -- zero-env no-op contract ─────────────────────────────────


def test_zero_env_edition_baseline():
    """With no edition-related env vars set, load_settings() must reproduce
    exactly today's free-edition values. This no-op guarantee is the single
    most important property of the env-driven edition config feature."""
    settings = load_settings()
    assert settings.edition == "free"
    assert settings.study_languages == ("en", "ru", "he", "es")
    assert settings.android_package_name == "com.verbboard.app"
    assert len(settings.android_cert_fingerprints) == 1
    assert settings.on_demand_examples_enabled is False
    assert settings.app_name == "VerbBoard"
    assert settings.app_short_name == "VerbBoard"


def test_edition_plus_adds_study_languages_and_enables_on_demand_examples(monkeypatch):
    monkeypatch.setenv("EDITION", "plus")
    settings = load_settings()
    assert "it" in settings.study_languages
    assert "fr" in settings.study_languages
    assert set(("en", "ru", "he", "es")) <= set(settings.study_languages)
    assert settings.on_demand_examples_enabled is True


def test_edition_plus_on_demand_examples_explicit_override_beats_default(monkeypatch):
    monkeypatch.setenv("EDITION", "plus")
    monkeypatch.setenv("ON_DEMAND_EXAMPLES_ENABLED", "false")
    settings = load_settings()
    assert settings.on_demand_examples_enabled is False


def test_unsupported_edition_raises(monkeypatch):
    monkeypatch.setenv("EDITION", "enterprise")
    with pytest.raises(ValueError, match="Unsupported EDITION"):
        load_settings()


def test_free_edition_with_plus_only_study_language_raises(monkeypatch):
    monkeypatch.setenv("EDITION", "free")
    monkeypatch.setenv("STUDY_LANGUAGES", "en,ru,he,es,it")
    with pytest.raises(ValueError):
        load_settings()


def test_study_languages_env_is_lowercased(monkeypatch):
    monkeypatch.setenv("STUDY_LANGUAGES", "EN,RU")
    settings = load_settings()
    assert settings.study_languages == ("en", "ru")


def test_android_cert_fingerprints_csv_parsed(monkeypatch):
    monkeypatch.setenv("ANDROID_CERT_FINGERPRINTS", "AA:BB,CC:DD")
    settings = load_settings()
    assert settings.android_cert_fingerprints == ("AA:BB", "CC:DD")
