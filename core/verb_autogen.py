"""
On-the-spot verb generation for EN/ES/IT/FR/RU when a search finds no match.

Flow: is_plausible_verb_query gate -> provider-dispatched verb gen (Gemini for
most languages, Claude for Russian -- see _CLAUDE_AUTOGEN_LANGUAGES) ->
pydantic validate (+ Russian-specific aspect/form sanity check) -> dual-write
(verb_candidates as "promoted" + live verbs) -> cache bust -> audio pre-warm.
All runs as a fire-and-forget asyncio task; failures are logged and never
propagate to the caller.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

import vertexai
from pydantic import BaseModel, ValidationError
from vertexai.generative_models import GenerationConfig, GenerativeModel

from core.languages.config import STUDY_LANGUAGE_SCRIPTS
from core.languages.ru.validation import validate_ru_payload
from core.rate_limit import SlidingWindowRateLimiter
from core.settings import load_settings, verb_candidates_collection_name, verbs_collection_name
from core.settings_ai import (
    _LANG_PROMPTS,
    _MAX_TOKENS,
    _MAX_TOKENS_DEFAULT,
    _MODEL,
    _MODEL_DEFAULT,
    get_anthropic_client,
    get_cached_system,
)
from core.storage.firestore_db import get_db
from core.storage.verb_document import build_search_extract_from_entry, build_storage_verb_id
from core.storage.verb_repository import find_verb_by_search_extract
from core.translation_service import translate_examples

logger = logging.getLogger(__name__)

AUTOGEN_LANGUAGES: frozenset[str] = frozenset({"en", "es", "it", "fr", "ru"})

# Russian goes through Claude/Sonnet (this project's convention for all
# non-English languages -- see core/verb_service.py's pair-completion
# generator, which this path deliberately does not duplicate the pipeline of)
# instead of Gemini. Everything else in this module stays Gemini-based.
_CLAUDE_AUTOGEN_LANGUAGES: frozenset[str] = frozenset({"ru"})

_GEMINI_VERB_MODEL = "gemini-2.5-flash"
# Routed through Settings (not a bare os.getenv() here) so the value is
# guaranteed correct regardless of module import order -- Settings' own
# load_dotenv(override=True) is guaranteed to have already run by the time
# this import completes, unlike a direct os.getenv() call in this module.
_GCP_LOCATION = load_settings().gcp_region
_GCP_PROJECT = load_settings().google_cloud_project

# In-process dedup: prevents redundant concurrent tasks for the same query
_GENERATING: set[str] = set()

# Caps paid-LLM-call exposure from a single client varying its query string to
# dodge the exact-string dedup above (e.g. "blorf", "blorf2", "blorfx", ...).
# Per-IP, per-instance -- see core/rate_limit.py docstring for why that's the
# right tradeoff here.
_AUTOGEN_RATE_LIMITER = SlidingWindowRateLimiter(max_calls=5, window_seconds=600)


def autogen_rate_limited(client_ip: str) -> bool:
    """Return True if this client should NOT be allowed to trigger another autogen call."""
    return not _AUTOGEN_RATE_LIMITER.allow(client_ip)


# Translation targets per source language, for translate_examples(). Hebrew is
# intentionally excluded as a *source* -- it routes through Anthropic, which
# translate_examples() only takes for a Hebrew source. Russian as a source
# still resolves entirely through the Gemini branch of translate_examples()
# even though Russian *generation* itself uses Claude (a separate concern).
_TRANSLATION_TARGETS: dict[str, list[str]] = {
    "en": ["ru", "es"],
    "es": ["en", "ru"],
    "it": ["en", "ru", "es"],
    "fr": ["en", "ru", "es"],
    "ru": ["en", "es"],
}


class _VerbGenResponse(BaseModel):
    lemma: str | None = None
    morph: str | dict[str, Any] | None = None
    forms: dict[str, Any] = {}
    examples: list[Any] = []
    pronoun_forms: dict[str, Any] | None = None
    tts_forms: dict[str, Any] | None = None


def is_plausible_verb_query(query: str, language: str) -> bool:
    """Return True if query looks like a real verb search worth generating."""
    if language not in AUTOGEN_LANGUAGES:
        return False
    stripped = query.strip()
    if not stripped or len(stripped) < 2 or len(stripped) > 30:
        return False
    # Script gate, sourced from core.languages.config.STUDY_LANGUAGE_SCRIPTS
    # (single source of truth for which letters are valid per study language)
    # rather than a duplicate per-language dict here. Latin-script languages
    # admit plain ASCII plus their own accented letters (e.g. "être", "però");
    # non-Latin scripts (Russian) admit only their own alphabet -- a Latin or
    # mixed-script query for those languages is rejected here.
    script = STUDY_LANGUAGE_SCRIPTS.get(language)
    if script is None:
        return False
    for char in stripped:
        if char in " '-":
            continue
        if not char.isalpha():
            return False
        if char.lower() in script.extra_letters:
            continue
        if script.ascii_ok and char.isascii():
            continue
        return False
    # Reflexive forms like "se ir" are 2 tokens max; anything longer is a phrase
    if len(stripped.split()) > 2:
        return False
    _STOP_WORDS = frozenset(
        {"the", "a", "an", "and", "or", "el", "la", "los", "las", "un", "una", "не", "это", "как", "что", "или"}
    )
    if stripped.lower() in _STOP_WORDS:
        return False
    return True


def _build_verb_prompt(language: str, query: str) -> str:
    base = _LANG_PROMPTS.get(language, "")
    return f"{base}\nlanguage: {language}\nraw query (may be any inflected form): {query}"


def _generate_verb_gemini(language: str, query: str) -> dict[str, Any] | None:
    try:
        vertexai.init(project=_GCP_PROJECT, location=_GCP_LOCATION)
        model = GenerativeModel(_GEMINI_VERB_MODEL)
        response = model.generate_content(
            _build_verb_prompt(language, query),
            generation_config=GenerationConfig(response_mime_type="application/json", temperature=0),
        )
        return json.loads(response.text)
    except Exception:
        logger.exception("Gemini verb generation failed for %s/%s", language, query)
        return None


async def _generate_verb_claude(language: str, query: str) -> dict[str, Any] | None:
    """Mirrors admin_candidates._call_claude's request shape, but never raises --
    this runs inside a fire-and-forget task, not a request handler."""
    try:
        client = get_anthropic_client()
        message = await client.messages.create(
            model=_MODEL.get(language, _MODEL_DEFAULT),
            max_tokens=_MAX_TOKENS.get(language, _MAX_TOKENS_DEFAULT),
            temperature=0,
            system=get_cached_system(language),
            messages=[
                {
                    "role": "user",
                    "content": f"language: {language}\nraw query (may be any inflected form): {query}",
                }
            ],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            raw = raw.rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except Exception:
        logger.exception("Claude verb generation failed for %s/%s", language, query)
        return None


async def _generate_verb_payload(language: str, query: str) -> dict[str, Any] | None:
    """Provider dispatch: Claude for _CLAUDE_AUTOGEN_LANGUAGES, Gemini otherwise."""
    if language in _CLAUDE_AUTOGEN_LANGUAGES:
        return await _generate_verb_claude(language, query)
    return await asyncio.to_thread(_generate_verb_gemini, language, query)


def _get_max_rank(language: str) -> int:
    db = get_db()
    result = db.collection(verbs_collection_name()).where("language", "==", language).count().get()
    return result[0][0].value


def _allocate_verb_id(*, language: str, lemma: str, max_attempts: int = 5) -> str | None:
    """Return an unused verb_id for `lemma`, or None if it's already live.

    build_storage_verb_id's transliteration can collide distinct lemmas
    (e.g. Russian "сесть" and "съесть" both -> "ru_sest"). Treating "the id
    exists" as "this exact lemma already exists" (the old behavior) silently
    drops the second, different verb. Instead, check the existing doc's own
    `lemma` field and fall through to a numbered suffix on a mismatch.
    """
    db = get_db()
    base_id = build_storage_verb_id(language=language, lemma=lemma)
    candidate = base_id
    for attempt in range(1, max_attempts + 1):
        doc = db.collection(verbs_collection_name()).document(candidate).get()
        if not doc.exists:
            return candidate
        existing_lemma = (doc.to_dict() or {}).get("lemma", "")
        if existing_lemma.strip().lower() == lemma.strip().lower():
            return None
        candidate = f"{base_id}_{attempt + 1}"
    logger.warning("autogen: exhausted verb_id collision suffixes for %s/%s", language, lemma)
    return None


def _allocate_candidate_doc_id(*, language: str, query: str, max_attempts: int = 5) -> str:
    """Return a verb_candidates doc id safe to write for `query`.

    Same collision hazard as _allocate_verb_id, but for the candidates
    collection: build_storage_verb_id's transliteration can map two distinct
    queries to the same id (e.g. Russian "сесть"/"съесть" -> "ru_sest"). A
    plain .set() at that id would silently clobber an unrelated query's
    record (a promoted verb's audit doc, or a different rejection) instead of
    updating this query's own history. Falls through to a numbered suffix
    when the existing doc's own `query` field doesn't match; if attempts are
    exhausted, returns the base id anyway (an overwrite here loses only an
    audit-trail doc, never live verb data, so failing closed isn't worth the
    added complexity of a permanent no-op).
    """
    db = get_db()
    base_id = build_storage_verb_id(language=language, lemma=query)
    candidate = base_id
    for attempt in range(1, max_attempts + 1):
        doc = db.collection(verb_candidates_collection_name()).document(candidate).get()
        if not doc.exists or (doc.to_dict() or {}).get("query", "").strip().lower() == query.strip().lower():
            return candidate
        candidate = f"{base_id}_{attempt + 1}"
    return base_id


def _write_rejection(*, language: str, query: str) -> None:
    """Record that the model confirmed this query is not a verb."""
    db = get_db()
    verb_id = _allocate_candidate_doc_id(language=language, query=query)
    db.collection(verb_candidates_collection_name()).document(verb_id).set(
        {
            "verb_id": verb_id,
            "language": language,
            "query": query,
            "status": "rejected_non_verb",
            "source": "autogen",
            "created_at": datetime.now(UTC).isoformat(),
        }
    )


def _write_needs_review(*, language: str, query: str, lemma: str, reason: str) -> None:
    """Record a generation that failed post-validation without a live write.

    Unlike a hard rejection, this wasn't confirmed non-a-verb -- it's a
    payload an admin should look at (`admin_candidates.py`'s review queue),
    not silently discarded paid model output.
    """
    db = get_db()
    verb_id = _allocate_candidate_doc_id(language=language, query=query)
    db.collection(verb_candidates_collection_name()).document(verb_id).set(
        {
            "verb_id": verb_id,
            "language": language,
            "query": query,
            "lemma": lemma,
            "status": "needs_review",
            "source": "autogen",
            "validation_failure": reason,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )


def check_verb_rejected(language: str, query: str) -> bool:
    """Return True if AI previously confirmed this exact query is not a verb.

    Compares the stored `query` field, not just the doc id -- verb_id space
    can collide for distinct queries (transliteration is lossy for non-Latin
    scripts), so an id match alone isn't enough to trust a cached rejection.
    """
    db = get_db()
    verb_id = build_storage_verb_id(language=language, lemma=query)
    doc = db.collection(verb_candidates_collection_name()).document(verb_id).get()
    if not doc.exists:
        return False
    data = doc.to_dict() or {}
    return data.get("status") == "rejected_non_verb" and data.get("query", "").strip().lower() == query.strip().lower()


def _write_promoted_verb(
    *,
    language: str,
    verb_id: str,
    lemma: str,
    rank: int,
    forms: dict[str, Any],
    examples: list[Any],
    morph: Any,
    search_extract: list[str],
    pronoun_forms: dict[str, Any] | None,
    query: str,
) -> None:
    db = get_db()
    now = datetime.now(UTC).isoformat()

    base: dict[str, Any] = {
        "verb_id": verb_id,
        "language": language,
        "lemma": lemma,
        "morph": morph,
        "rank": rank,
        "forms": forms,
        "examples": examples,
        "search_extract": search_extract,
        "created_at": now,
        "updated_at": now,
    }
    if pronoun_forms:
        base["pronoun_forms"] = pronoun_forms

    # Candidate record: auditable trail; status="promoted" means already live
    candidate_doc = {**base, "query": query, "status": "promoted", "source": "autogen"}
    # Live record: no status/query/source -- matches the shape of manually promoted verbs
    live_doc = {**base}

    # Atomic: a batch commits both writes together or neither, so a crash/kill
    # mid-write can't leave verb_candidates marked "promoted" with no
    # corresponding live verb (invisible to both learners and the admin queue).
    batch = db.batch()
    batch.set(db.collection(verb_candidates_collection_name()).document(verb_id), candidate_doc)
    batch.set(db.collection(verbs_collection_name()).document(verb_id), live_doc)
    batch.commit()

    from core.admin_logging import resolve_signal_label

    resolve_signal_label(language=language, query=query)


async def autogenerate_missing_verb(*, language: str, query: str, audio_backend: Any) -> None:
    """Fire-and-forget: generate a missing verb via Gemini and promote it directly to live verbs."""
    key = f"{language}:{query.lower()}"
    if key in _GENERATING:
        return
    _GENERATING.add(key)
    try:
        # Pre-flight: re-check in case a concurrent request already generated it
        existing = await asyncio.to_thread(find_verb_by_search_extract, language, query)
        if existing:
            return

        raw = await _generate_verb_payload(language, query)
        if raw is None:
            return

        try:
            parsed = _VerbGenResponse.model_validate(raw)
        except ValidationError:
            logger.exception("autogen response failed validation for %s/%s", language, query)
            return

        if parsed.lemma is None:
            logger.info("autogen: model rejected %s/%s as non-verb, recording rejection", language, query)
            await asyncio.to_thread(_write_rejection, language=language, query=query)
            return
        lemma = parsed.lemma.strip()
        if not lemma:
            return
        if not parsed.forms:
            logger.info("autogen: empty forms for %s/%s, aborting write", language, query)
            return

        if language == "ru":
            failure_reason = validate_ru_payload(lemma, parsed.morph, parsed.forms)
            if failure_reason:
                logger.warning("autogen: RU payload for %s/%s failed validation: %s", language, query, failure_reason)
                await asyncio.to_thread(
                    _write_needs_review, language=language, query=query, lemma=lemma, reason=failure_reason
                )
                return

        # Guard against race, and against Cyrillic transliteration collisions
        # (e.g. "сесть"/"съесть" both transliterate to "ru_sest") -- fall
        # through to a numbered suffix when the existing doc's lemma differs
        # from the one just generated, instead of silently no-oping.
        verb_id = await asyncio.to_thread(_allocate_verb_id, language=language, lemma=lemma)
        if verb_id is None:
            logger.debug("autogen: %s/%s already exists under its generated lemma, skipping", language, lemma)
            return

        rank = await asyncio.to_thread(_get_max_rank, language) + 1

        entry_for_extract: dict[str, Any] = {
            "lemma": lemma,
            "forms": parsed.forms,
            "morph": parsed.morph if isinstance(parsed.morph, dict) else None,
        }
        search_extract = build_search_extract_from_entry(language=language, entry=entry_for_extract)

        examples: list[Any] = [ex for ex in parsed.examples if isinstance(ex, dict) and isinstance(ex.get("dst"), str)]

        target_langs = _TRANSLATION_TARGETS.get(language, [])
        if target_langs and examples:
            try:
                # api_key is unused: target_langs excludes "he" so the Claude path is never taken
                examples = await asyncio.to_thread(
                    translate_examples,
                    verb_lang=language,
                    lemma=lemma,
                    examples=examples,
                    target_langs=target_langs,
                    project=_GCP_PROJECT,
                    api_key="",
                )
            except Exception:
                logger.exception("autogen translation failed for %s/%s, saving without translations", language, lemma)

        await asyncio.to_thread(
            _write_promoted_verb,
            language=language,
            verb_id=verb_id,
            lemma=lemma,
            rank=rank,
            forms=parsed.forms,
            examples=examples,
            morph=parsed.morph,
            search_extract=search_extract,
            pronoun_forms=parsed.pronoun_forms,
            query=query,
        )

        # Bust the list cache so the new verb appears on the next /verbs load
        from core.verb_loader import invalidate_entries_cache

        invalidate_entries_cache(language)

        logger.info("autogen: promoted %s/%s (verb_id=%s)", language, lemma, verb_id)

        # Pre-warm audio (best-effort)
        try:
            from app.routes.admin_candidates import _warm_verb_audio

            verb_data: dict[str, Any] = {
                "verb_id": verb_id,
                "language": language,
                "lemma": lemma,
                "rank": rank,
                "forms": parsed.forms,
                "examples": examples,
                "morph": parsed.morph,
            }
            await _warm_verb_audio(audio_backend=audio_backend, language=language, verb_data=verb_data)
        except Exception:
            logger.warning("autogen audio pre-warm failed for %s/%s", language, verb_id)

    except Exception:
        logger.exception("autogen failed for %s/%s", language, query)
    finally:
        _GENERATING.discard(key)
