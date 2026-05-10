from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv
from google.cloud import secretmanager


load_dotenv(override=True)

_ADMIN_SECRET_NAME = "verbboard-admin-secret"
_ANTHROPIC_SECRET_NAME = "verbboard-anthropic-api-key"
_GENERATION_SYSTEM_PROMPT = """\
You are a linguistic data generator for a language-learning app.
Input: a raw search query (any inflected form, e.g. "went", "growing", "был") and a language code.
Task: identify the dictionary lemma, then output full conjugation data.

Return raw valid JSON only — no markdown fences, comments, or prose. Double-quote all keys and strings.

Schema:
{
  "lemma": "<dictionary base form>",
  "morph": { <language-specific metadata — see below> },
  "forms": { <conjugated forms, nested objects — see below> },
  "examples": [ {"dst": "<sentence>"}, ... ]
}

Examples must be idiomatic, everyday language, naturally using the target verb.
No two examples may use the same grammatical form.

────────────────────────────────────────
ENGLISH (en)
  lemma: infinitive (e.g. "went" → "go", "growing" → "grow")
  morph: {}
  forms: flat keys (no nesting) — base, past, past_participle, present_3sg, gerund
  examples: exactly 5 sentences covering in order:
    simple present (1st person: I / we), simple present (3rd singular: she/he),
    simple present (3rd plural: they), simple past, present perfect

────────────────────────────────────────
RUSSIAN (ru)
  lemma: infinitive form
  morph:
    aspect: "perfective" | "imperfective" | "biaspectual"
      Use "biaspectual" for быть (it has both present and full future paradigms)
      and for verbs that function as both aspects (e.g. организовать, использовать).
    pair: aspect partner's infinitive (e.g. "поймать" ↔ "ловить"). "" if none — never invent.
      Biaspectual verbs have no pair — use "".

  forms — tense slots depend on aspect:
    imperfective         → present, past, imperative
    perfective           → future, past, imperative
    biaspectual / быть   → present, future, past, imperative

    present / future: { 1sg, 2sg, 3sg, 1pl, 2pl, 3pl }
    past:             { m, f, n, pl }
    imperative:       { sg, pl }

  IMPERATIVE: derive from the actual conjugation stem.
    Soft-stem verbs take -ь / -ьте, not -и / -ите.
    Examples: зависеть → завись / зависьте, уведомить → уведомь / уведомьте,
    ехать → езжай, давать → давай, бежать → беги, вставать → вставай.

  pronoun_forms — past prefixed with subject pronoun, for TTS:
    m: "он <past_m>", f: "она <past_f>", n: "оно <past_n>", pl: "они <past_pl>"
    Plain text only — no stress marks or diacritics.

  examples:
    single-aspect verb (has a pair): exactly 4 sentences
    biaspectual verb, быть, or unpaired verb: exactly 6 sentences
    At least one example must use the past neuter singular naturally
    (subject is grammatically neuter, e.g. "Солнце начало садиться.", "Молоко закипело.").

────────────────────────────────────────
SPANISH (es)
  lemma: infinitive form
  morph: {}
  forms (all nested):
    present:   { yo, tu, el, nos, ellos }
    preterite: { yo, tu, el, nos, ellos }
    imperative: { tu, vosotros, usted, ustedes }
    gerund: "<gerund>"            (string)
    participle: "<past participle>" (string)
  examples: 4 to 6 sentences in Spanish, each using a distinct grammatical form:
    at least one present, one preterite, one imperative or subjunctive,
    and others from different tenses/persons.

────────────────────────────────────────
HEBREW (he)
  lemma: infinitive (לְ prefix form)
  morph:
    binyan: one of פָּעַל, נִפְעַל, פִּיעֵל, פֻּעַל, הִתְפַּעֵל, הִפְעִיל, הוּפְעַל
    root: letters separated by dots, e.g. "ל.מ.ד"
  forms (all nested):
    present:   { m_sg, f_sg, m_pl, f_pl }
    past:      { 1sg, 2msg, 2fsg, 3msg, 3fsg, 1pl, 2mpl, 2fpl, 3pl }
    future:    { 1sg, 2msg, 2fsg, 3msg, 3fsg, 1pl, 2mpl, 2fpl, 3pl }
    imperative: { ms, fs, mp, fp }
  examples: 4 to 6 sentences in Hebrew script, each using a distinct grammatical form:
    at least one present, one past, one future, and others from different forms.

"""


@dataclass(frozen=True)
class Settings:
    environment: str
    host: str
    port: int
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
    if settings.environment not in {"local", "stage", "prod"}:
        raise ValueError(
            f"Unsupported ENVIRONMENT={settings.environment}. Expected local|stage|prod"
        )
    if settings.verb_data_source not in {"local", "firestore"}:
        raise ValueError(
            f"Unsupported VERB_DATA_SOURCE={settings.verb_data_source}. "
            "Expected 'local' or 'firestore'"
        )
    if not settings.google_cloud_project:
        raise ValueError("GOOGLE_CLOUD_PROJECT must be set")
    if not settings.audio_bucket:
        raise ValueError("AUDIO_BUCKET must be set")
    if not settings.admin_secret:
        raise ValueError("ADMIN_SECRET must not be empty")
