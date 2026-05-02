from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv
from google.cloud import secretmanager


load_dotenv()

_ADMIN_SECRET_NAME = "verbboard-admin-secret"
_ANTHROPIC_SECRET_NAME = "verbboard-anthropic-api-key"
_GENERATION_SYSTEM_PROMPT = """\
You are a linguistic data generator for a language-learning app.
You receive a raw search query (which may be any inflected form, e.g. "went", "growing", "был")
and a language code. First identify the dictionary lemma, then generate full conjugation data.
Return ONLY raw valid JSON.
Do not wrap in markdown fences.
Do not add comments, explanations, or prose.
All keys and string values must use double quotes.

Output shape:
{
  "lemma": "<dictionary base form>",
  "morph": { <language-specific grammatical metadata — see rules below> },
  "forms": { <conjugated forms — nested maps, see rules below> },
  "examples": [ {"dst": "<sentence>"}, ... ],
}

Examples must be idiomatic, everyday language, not too verbose, naturally use the target verb.

ENGLISH (en):
  lemma: infinitive base form (e.g. "went" → "go", "growing" → "grow")
  morph: {} (empty object)
  forms: flat keys (English is the exception — no nesting):
    base, past, past_participle, present_3sg, gerund
  examples: exactly 5 sentences:
    1. simple present first person
    2. simple present third person
    3. simple past
    4. present perfect
    5. present continuous

RUSSIAN (ru):
  lemma: infinitive form
  morph:
    aspect: "perfective" or "imperfective"
    pair: infinitive lemma of the aspect partner, not verb_id (e.g. "ловить" for поймать).
          Use "" if no pair exists.
          Examples for `pair`:
            - "ловить" -> "поймать"
            - "поймать" -> "ловить"
            - "уцелеть" -> ""   (do not invent)
  forms — all nested:
    for imperfective verbs:
      present: 1sg, 2sg, 3sg, 1pl, 2pl, 3pl
      do not create forma.future slot
    for perfective verbs:
      future: 1sg, 2sg, 3sg, 1pl, 2pl, 3pl
      do not create forms.present slot
    past:
      m, f, n, pl
    imperative:
      sg, pl
  pronoun_forms — past forms prefixed with their subject pronoun, for unambiguous TTS:
    m:  "он <past_m>"    (e.g. "он начал")
    f:  "она <past_f>"   (e.g. "она начала")
    n:  "оно <past_n>"   (e.g. "оно начало")
    pl: "они <past_pl>"  (e.g. "они начали")
    Use plain text only — do NOT include stress marks or any diacritics.
  examples: exactly 5 sentences in Russian
    — at least one example MUST use the past tense neuter singular (оно + past_n form)
      in a natural sentence where the subject is grammatically neuter
      (e.g. "Солнце начало садиться.", "Молоко начало закипать.")

SPANISH (es):
  lemma: infinitive form
  morph: {} (empty object)
  forms — all nested:
    present:
      yo, tu, el, nos, ellos
    preterite:
      yo, tu, el, nos, ellos
    imperative:
      tu, vosotros, usted, ustedes
    gerund: "<gerund form>"        (string, not nested)
    participle: "<past participle>" (string, not nested)
  examples: exactly 5 sentences in Spanish

HEBREW (he):
  lemma: infinitive form (לְ prefix form)
  morph:
    binyan: one of פָּעַל, נִפְעַל, פִּיעֵל, פֻּעַל, הִתְפַּעֵל, הִפְעִיל, הוּפְעַל
    root: root letters separated by dots e.g. "ל.מ.ד"
  forms — all nested:
    present:
      m_sg, f_sg, m_pl, f_pl
    past:
      1sg, 2msg, 2fsg, 3msg, 3fsg, 1pl, 2mpl, 2fpl, 3pl
    future:
      1sg, 2msg, 2fsg, 3msg, 3fsg, 1pl, 2mpl, 2fpl, 3pl
    imperative:
      ms, fs, mp, fp
  examples: exactly 5 sentences in Hebrew script

"""


@dataclass(frozen=True)
class Settings:
    environment: str
    host: str
    port: int
    audio_backend: str
    local_audio_cache_dir: str
    google_cloud_project: str
    audio_bucket: str
    verb_data_source: str
    verb_signals_collection: str
    verb_signal_labels_collection: str
    verbs_collection: str
    verb_candidates_collection: str
    log_level: str
    admin_secret: str


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


def _resolve_verb_data_source(environment: str) -> str:
    override = os.getenv("VERB_DATA_SOURCE")
    if override:
        return override
    if environment in {"stage", "prod"}:
        return "firestore"
    return "local"


def _resolve_audio_backend(environment: str) -> str:
    override = os.getenv("AUDIO_BACKEND")
    if override:
        return override
    if environment in {"stage", "prod"}:
        return "gcs"
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
        raise ValueError(
            "GOOGLE_CLOUD_PROJECT must be set when ADMIN_SECRET is not provided"
        )

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
        raise ValueError(
            "ANTHROPIC_API_KEY is not set in environment or .env for local run"
        )

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project_id:
        raise ValueError(
            "GOOGLE_CLOUD_PROJECT must be set when ANTHROPIC_API_KEY is not provided"
        )

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{_ANTHROPIC_SECRET_NAME}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    secret_value = response.payload.data.decode("utf-8").strip()
    if not secret_value:
        raise ValueError(f"Secret {_ANTHROPIC_SECRET_NAME} resolved to an empty value")
    return secret_value


def load_settings() -> Settings:
    environment = _resolve_environment()
    settings = Settings(
        environment=environment,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        audio_backend=_resolve_audio_backend(environment),
        local_audio_cache_dir=os.getenv("LOCAL_AUDIO_CACHE_DIR", "runtime/audio_cache"),
        google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        audio_bucket=os.getenv("AUDIO_BUCKET", ""),
        verb_data_source=_resolve_verb_data_source(environment),
        verb_signals_collection=os.getenv("VERB_SIGNALS_COLLECTION", "demand_signal"),
        verb_signal_labels_collection=os.getenv(
            "VERB_SIGNAL_LABELS_COLLECTION",
            "demand_signal_labels",
        ),
        verbs_collection=os.getenv("VERBS_COLLECTION", "verbs"),
        verb_candidates_collection=os.getenv(
            "VERB_CANDIDATES_COLLECTION", "verb_candidates"
        ),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        admin_secret=_load_admin_secret(),
    )
    _validate(settings)
    return settings


def _validate(settings: Settings) -> None:
    if settings.audio_backend not in {"local", "gcs"}:
        raise ValueError(
            f"Unsupported AUDIO_BACKEND={settings.audio_backend}. "
            "Expected 'local' or 'gcs'."
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
    if not settings.admin_secret:
        raise ValueError("ADMIN_SECRET must not be empty")
