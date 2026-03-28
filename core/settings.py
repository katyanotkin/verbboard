from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str
    environment: str  # <-- NEW

    host: str
    port: int

    audio_backend: str
    local_audio_cache_dir: str

    google_cloud_project: str
    audio_bucket: str

    verb_data_source: str
    verb_signal_bucket: str
    verb_signal_prefix: str
    verbs_collection: str

    log_level: str


def _resolve_environment() -> str:
    # 1) explicit override (preferred)
    env = os.getenv("ENVIRONMENT")
    if env:
        return env

    # 2) infer from Cloud Run service name
    service_name = os.getenv("K_SERVICE", "")
    if service_name.endswith("-stage"):
        return "stage"
    if service_name:
        return "prod"

    # 3) fallback
    return "local"


def load_settings() -> Settings:
    settings = Settings(
        app_env=os.getenv("APP_ENV", "local"),
        environment=_resolve_environment(),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        audio_backend=os.getenv("AUDIO_BACKEND", "local"),
        local_audio_cache_dir=os.getenv("LOCAL_AUDIO_CACHE_DIR", "runtime/audio_cache"),
        google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        audio_bucket=os.getenv("AUDIO_BUCKET", ""),
        verb_data_source=os.getenv("VERB_DATA_SOURCE", "local"),
        verb_signal_bucket=os.getenv("VERB_SIGNAL_BUCKET", ""),
        verb_signal_prefix=os.getenv(
            "VERB_SIGNAL_PREFIX",
            "admin/missing-verb-searches/",
        ),
        verbs_collection=os.getenv("VERBS_COLLECTION", "verbs"),
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
            f"Unsupported APP_ENV={settings.app_env}. Expected local|cloud|test"
        )

    if settings.environment not in {"local", "stage", "prod"}:
        raise ValueError(
            f"Unsupported ENVIRONMENT={settings.environment}. "
            "Expected local|stage|prod"
        )

    if settings.verb_data_source not in {"local", "firestore"}:
        raise ValueError(
            f"Unsupported VERB_DATA_SOURCE={settings.verb_data_source}. "
            "Expected 'local' or 'firestore'"
        )

    if settings.audio_backend == "gcs":
        if not settings.google_cloud_project:
            raise ValueError("GOOGLE_CLOUD_PROJECT must be set when AUDIO_BACKEND=gcs")

        if not settings.audio_bucket:
            raise ValueError("AUDIO_BUCKET must be set when AUDIO_BACKEND=gcs")

    if settings.verb_data_source == "firestore" and not settings.google_cloud_project:
        raise ValueError(
            "GOOGLE_CLOUD_PROJECT must be set when VERB_DATA_SOURCE=firestore"
        )

    # --- safety guardrails ---
    if settings.environment == "prod" and "stage" in settings.verb_signal_bucket:
        raise ValueError("Prod cannot use stage verb signal bucket")

    if settings.environment == "stage" and "prod" in settings.verb_signal_bucket:
        raise ValueError("Stage cannot use prod verb signal bucket")
