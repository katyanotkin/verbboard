from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str
    host: str
    port: int

    audio_backend: str
    local_audio_cache_dir: str

    google_cloud_project: str
    audio_bucket: str

    log_level: str


def load_settings() -> Settings:
    settings = Settings(
        app_env=os.getenv("APP_ENV", "local"),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        audio_backend=os.getenv("AUDIO_BACKEND", "local"),
        local_audio_cache_dir=os.getenv("LOCAL_AUDIO_CACHE_DIR", "runtime/audio_cache"),
        google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        audio_bucket=os.getenv("AUDIO_BUCKET", ""),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )

    _validate(settings)

    return settings


def _validate(settings: Settings) -> None:
    if settings.audio_backend not in {"local", "gcs"}:
        raise ValueError(
            f"Unsupported AUDIO_BACKEND={settings.audio_backend}. "
            "Expected 'local' or 'gcs'."
        )

    if settings.app_env not in {"local", "cloud", "test"}:
        raise ValueError(
            f"Unsupported APP_ENV={settings.app_env}. " "Expected local|cloud|test"
        )

    if settings.audio_backend == "gcs":
        if not settings.google_cloud_project:
            raise ValueError("GOOGLE_CLOUD_PROJECT must be set when AUDIO_BACKEND=gcs")

        if not settings.audio_bucket:
            raise ValueError("AUDIO_BUCKET must be set when AUDIO_BACKEND=gcs")
