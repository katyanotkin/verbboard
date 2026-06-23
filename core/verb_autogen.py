"""
On-the-spot verb generation for EN and ES when a search finds no match.

Flow: is_plausible_verb_query gate -> Gemini verb gen -> pydantic validate ->
dual-write (verb_candidates as "promoted" + live verbs) -> cache bust ->
audio pre-warm.  All runs as a fire-and-forget asyncio task; failures are
logged and never propagate to the caller.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import vertexai
from pydantic import BaseModel, ValidationError
from vertexai.generative_models import GenerationConfig, GenerativeModel

from core.settings_ai import _LANG_PROMPTS
from core.storage.firestore_db import get_db
from core.storage.verb_document import build_search_extract_from_entry, build_storage_verb_id
from core.storage.verb_repository import find_verb_by_search_extract
from core.translation_service import translate_examples

logger = logging.getLogger(__name__)

AUTOGEN_LANGUAGES: frozenset[str] = frozenset({"en", "es"})

_GEMINI_VERB_MODEL = "gemini-2.5-flash"
_GCP_LOCATION = os.getenv("GCP_REGION", "us-east1")
_GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")

_CANDIDATES_COLLECTION = "verb_candidates"
_VERBS_COLLECTION = "verbs"

# In-process dedup: prevents redundant concurrent tasks for the same query
_GENERATING: set[str] = set()

# Gemini-only translation targets per source language.
# Hebrew is intentionally excluded -- it routes through Anthropic which we avoid here.
_TRANSLATION_TARGETS: dict[str, list[str]] = {
    "en": ["ru", "es"],
    "es": ["en", "ru"],
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
    # EN and ES are Latin-script; reject Cyrillic, Hebrew, digits, symbols
    if not all(c.isascii() and (c.isalpha() or c in " '-") for c in stripped):
        return False
    # Reflexive forms like "se ir" are 2 tokens max; anything longer is a phrase
    if len(stripped.split()) > 2:
        return False
    _STOP_WORDS = frozenset({"the", "a", "an", "and", "or", "el", "la", "los", "las", "un", "una"})
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


def _get_max_rank(language: str) -> int:
    db = get_db()
    result = db.collection(_VERBS_COLLECTION).where("language", "==", language).count().get()
    return result[0][0].value


def _verb_id_exists(verb_id: str) -> bool:
    db = get_db()
    return db.collection(_VERBS_COLLECTION).document(verb_id).get().exists


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

    db.collection(_CANDIDATES_COLLECTION).document(verb_id).set(candidate_doc)
    db.collection(_VERBS_COLLECTION).document(verb_id).set(live_doc)


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

        raw = await asyncio.to_thread(_generate_verb_gemini, language, query)
        if raw is None:
            return

        try:
            parsed = _VerbGenResponse.model_validate(raw)
        except ValidationError:
            logger.exception("autogen response failed validation for %s/%s", language, query)
            return

        lemma = (parsed.lemma or query).strip()
        if not lemma:
            return

        verb_id = build_storage_verb_id(language=language, lemma=lemma)

        # Guard against race: same lemma generated by two concurrent requests
        if await asyncio.to_thread(_verb_id_exists, verb_id):
            logger.debug("autogen: %s already exists, skipping", verb_id)
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
