from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv
from google.cloud import secretmanager

from core.languages.config import FREE_STUDY_LANGUAGES, default_study_languages

load_dotenv(override=True)

_ADMIN_SECRET_NAME = "verbboard-admin-secret"
_ANTHROPIC_SECRET_NAME = "verbboard-anthropic-api-key"
_ANALYTICS_EXCLUDED_EMAILS_SECRET_NAME = "verbboard-analytics-excluded-emails"

# Real Play App Signing key certificate (not the local upload-key keystore) --
# copied from Play Console > Setup > App integrity > App signing key certificate
# after the first AAB upload. Free-edition default; Plus overrides via env.
_DEFAULT_ANDROID_CERT_FINGERPRINT = (
    "3A:51:9F:C0:80:6A:91:31:16:71:4E:98:49:F8:B9:C2:F9:09:21:CE:06:E4:51:C7:2D:81:B5:40:42:85:F4:9C"
)


@dataclass(frozen=True)
class Settings:
    environment: str
    host: str
    port: int
    google_cloud_project: str
    audio_bucket: str
    verb_signals_collection: str
    verb_signal_labels_collection: str
    verbs_collection: str
    verb_candidates_collection: str
    log_level: str
    admin_secret: str
    firebase_web_config_json: str
    allow_local_dev_auth: bool
    badge_compact_threshold: int
    verbs_page_limit: int
    verbs_display_batch: int
    gcp_region: str
    analytics_excluded_emails: tuple[str, ...]
    edition: str
    study_languages: tuple[str, ...]
    app_name: str
    app_short_name: str
    android_package_name: str
    android_cert_fingerprints: tuple[str, ...]
    on_demand_examples_enabled: bool
    jump_to_example_enabled: bool


def _resolve_environment() -> str:
    env = os.getenv("ENVIRONMENT")
    if env:
        return env
    service_name = os.getenv("K_SERVICE", "")
    if service_name.endswith("-stage"):
        return "stage"
    if service_name:
        return "prod"
    return "local"


@lru_cache(maxsize=1)
def _load_admin_secret() -> str:
    env_secret = os.getenv("ADMIN_SECRET", "").strip()
    if env_secret:
        return env_secret

    environment = _resolve_environment()
    if environment == "local":
        raise ValueError("ADMIN_SECRET is not set in environment or .env for local run")

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT must be set when ADMIN_SECRET is not provided")

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{_ADMIN_SECRET_NAME}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    secret_value = response.payload.data.decode("utf-8").strip()
    if not secret_value:
        raise ValueError(f"Secret {_ADMIN_SECRET_NAME} resolved to an empty value")
    return secret_value


@lru_cache(maxsize=1)
def _load_anthropic_api_key() -> str:
    env_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if env_key:
        return env_key

    environment = _resolve_environment()
    if environment == "local":
        raise ValueError("ANTHROPIC_API_KEY is not set in environment or .env for local run")

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT must be set when ANTHROPIC_API_KEY is not provided")

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{_ANTHROPIC_SECRET_NAME}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    secret_value = response.payload.data.decode("utf-8").strip()
    if not secret_value:
        raise ValueError(f"Secret {_ANTHROPIC_SECRET_NAME} resolved to an empty value")
    return secret_value


def _parse_excluded_emails(raw: str) -> tuple[str, ...]:
    return tuple(sorted({email.strip().lower() for email in raw.split(",") if email.strip()}))


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _parse_csv_tuple(raw: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@lru_cache(maxsize=1)
def _load_analytics_excluded_emails() -> tuple[str, ...]:
    """Comma-separated allowlist of own/test emails to drop from analytics counts.

    Optional -- unlike admin_secret/anthropic_api_key, a missing value just
    means no exclusions, not a broken deployment.
    """
    env_value = os.getenv("ANALYTICS_EXCLUDED_EMAILS", "").strip()
    if env_value:
        return _parse_excluded_emails(env_value)

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    if _resolve_environment() == "local" or not project_id:
        return ()

    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{_ANALYTICS_EXCLUDED_EMAILS_SECRET_NAME}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return _parse_excluded_emails(response.payload.data.decode("utf-8"))
    except Exception:
        return ()


def load_settings() -> Settings:
    environment = _resolve_environment()
    edition = os.getenv("EDITION", "free").strip().lower() or "free"
    study_languages_raw = os.getenv("STUDY_LANGUAGES", "").strip().lower()
    android_fingerprints_raw = os.getenv("ANDROID_CERT_FINGERPRINTS", "").strip()
    settings = Settings(
        environment=environment,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        audio_bucket=os.getenv("AUDIO_BUCKET", ""),
        verb_signals_collection=os.getenv("VERB_SIGNALS_COLLECTION", "demand_signal"),
        verb_signal_labels_collection=os.getenv(
            "VERB_SIGNAL_LABELS_COLLECTION",
            "demand_signal_labels",
        ),
        verbs_collection=os.getenv("VERBS_COLLECTION", "verbs"),
        verb_candidates_collection=os.getenv("VERB_CANDIDATES_COLLECTION", "verb_candidates"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        admin_secret=_load_admin_secret(),
        firebase_web_config_json=_safe_firebase_config(os.getenv("FIREBASE_WEB_CONFIG_JSON", "")),
        allow_local_dev_auth=os.getenv("ALLOW_LOCAL_DEV_AUTH", "").lower() == "true",
        badge_compact_threshold=int(os.getenv("BADGE_COMPACT_THRESHOLD", "20")),
        verbs_page_limit=int(os.getenv("VERBS_PAGE_LIMIT", "300")),
        verbs_display_batch=int(os.getenv("VERBS_DISPLAY_BATCH", "20")),
        gcp_region=os.getenv("GCP_REGION", "us-east1"),
        analytics_excluded_emails=_load_analytics_excluded_emails(),
        edition=edition,
        study_languages=(
            _parse_csv_tuple(study_languages_raw) if study_languages_raw else default_study_languages(edition)
        ),
        app_name=os.getenv("APP_NAME", "VerbBoard"),
        app_short_name=os.getenv("APP_SHORT_NAME", "VerbBoard"),
        android_package_name=os.getenv("ANDROID_PACKAGE_NAME", "com.verbboard.app"),
        android_cert_fingerprints=(
            _parse_csv_tuple(android_fingerprints_raw)
            if android_fingerprints_raw
            else (_DEFAULT_ANDROID_CERT_FINGERPRINT,)
        ),
        on_demand_examples_enabled=_env_flag("ON_DEMAND_EXAMPLES_ENABLED", default=(edition == "plus")),
        # Kill switch, not an edition gate -- defaults on (today's behavior).
        # Matching correctness is under audit (superficial substring match,
        # untested against multi-word compound forms like Italian's passato
        # prossimo); this lets it be disabled without a code change/redeploy
        # if the audit finds it materially broken for a shipped language.
        jump_to_example_enabled=_env_flag("JUMP_TO_EXAMPLE_ENABLED", default=True),
    )
    _validate(settings)
    return settings


def _safe_firebase_config(raw: str) -> str:
    """Re-parse and re-serialize Firebase config JSON with <, >, & unicode-escaped.

    Stored once at settings load time so every route that embeds this value
    inside an HTML <script> block is safe even if the secret value contains
    </script> or other HTML-breaking sequences.
    """
    try:
        parsed = json.loads(raw or "null")
    except (TypeError, ValueError):
        return "null"
    return json.dumps(parsed).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _validate(settings: Settings) -> None:
    if settings.environment not in {"local", "stage", "prod"}:
        raise ValueError(f"Unsupported ENVIRONMENT={settings.environment}. Expected local|stage|prod")
    if settings.allow_local_dev_auth and settings.environment == "prod":
        raise ValueError("ALLOW_LOCAL_DEV_AUTH must not be enabled in prod")
    if not settings.google_cloud_project:
        raise ValueError("GOOGLE_CLOUD_PROJECT must be set")
    if not settings.audio_bucket:
        raise ValueError("AUDIO_BUCKET must be set")
    if not settings.admin_secret:
        raise ValueError("ADMIN_SECRET must not be empty")
    if settings.verbs_page_limit > 0 and settings.verbs_page_limit <= settings.verbs_display_batch:
        raise ValueError(
            f"VERBS_PAGE_LIMIT ({settings.verbs_page_limit}) must be greater than "
            f"VERBS_DISPLAY_BATCH ({settings.verbs_display_batch})"
        )
    if settings.edition not in {"free", "plus"}:
        raise ValueError(f"Unsupported EDITION={settings.edition}. Expected free|plus")
    if settings.edition == "free" and not set(settings.study_languages) <= set(FREE_STUDY_LANGUAGES):
        raise ValueError("Free edition must not enable Plus-only study languages")
