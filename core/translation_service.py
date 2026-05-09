"""
Shared translation logic used by:
  - app/routes/admin_candidates.py  (post-generate / post-regen)
  - tools/backfill_translations.py  (bulk backfill)

Routing:
  Hebrew source or any Hebrew target  →  Anthropic Claude
  All other pairs                     →  Vertex AI Gemini Flash
"""

from __future__ import annotations

import json
import logging

import anthropic
import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ["en", "ru", "he", "es"]
HEBREW = "he"
GEMINI_MODEL = "gemini-2.5-flash-lite"
CLAUDE_MODEL = "claude-sonnet-4-6"

_LANG_NAMES = {"en": "English", "ru": "Russian", "he": "Hebrew", "es": "Spanish"}


def _translation_prompt(
    verb_lang: str,
    lemma: str,
    target_langs: list[str],
    sentences: list[str],
) -> str:
    src_name = _LANG_NAMES.get(verb_lang, verb_lang)
    targets = ", ".join(_LANG_NAMES.get(t, t) for t in target_langs)
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sentences))
    return f"""\
Translate the following {src_name} example sentences from a verb conjugation app.
Verb: {lemma}
Each sentence demonstrates a conjugated form of this verb.

Rules:
- Translate the verb "{lemma}" using the SAME word in every sentence — pick the one most common direct translation and use it consistently across all sentences. Do not use synonyms or alternate words even if they fit the context.
- Preserve the grammatical tense and aspect of the source sentence.
- Keep translations natural and short — match the register of the source.

Translate each sentence into: {targets}

Return ONLY a JSON array — one object per sentence, in the same order.
Each object has language codes as keys. Do not wrap in markdown fences.

Sentences:
{numbered}

Expected shape (example for 2 sentences, targets en + ru):
[
  {{"en": "...", "ru": "..."}},
  {{"en": "...", "ru": "..."}}
]
"""


def _call_gemini(
    verb_lang: str,
    lemma: str,
    target_langs: list[str],
    sentences: list[str],
    project: str,
    location: str = "us-central1",
) -> list[dict[str, str]]:
    vertexai.init(project=project, location=location)
    model = GenerativeModel(GEMINI_MODEL)
    prompt = _translation_prompt(verb_lang, lemma, target_langs, sentences)
    response = model.generate_content(
        prompt,
        generation_config=GenerationConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)


def _call_claude(
    verb_lang: str,
    lemma: str,
    target_langs: list[str],
    sentences: list[str],
    api_key: str,
) -> list[dict[str, str]]:
    client = anthropic.Anthropic(api_key=api_key)
    prompt = _translation_prompt(verb_lang, lemma, target_langs, sentences)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(message.content[0].text.strip())


def translate_examples(
    *,
    verb_lang: str,
    lemma: str,
    examples: list[dict],
    target_langs: list[str] | None = None,
    project: str,
    api_key: str,
) -> list[dict]:
    """
    Add translations to a list of example dicts in-place (returns new list).

    Only fills missing target languages. Non-fatal: on any error the original
    examples are returned unchanged so the caller can still save the verb.

    target_langs defaults to all supported languages except verb_lang.
    """
    if target_langs is None:
        target_langs = [lang for lang in SUPPORTED_LANGUAGES if lang != verb_lang]

    sentences = [
        ex["dst"]
        for ex in examples
        if isinstance(ex, dict) and isinstance(ex.get("dst"), str)
    ]
    if not sentences or not target_langs:
        return examples

    # Split by backend: Hebrew-involved → Claude, rest → Gemini.
    if verb_lang == HEBREW:
        gemini_targets: list[str] = []
        claude_targets: list[str] = target_langs
    else:
        gemini_targets = [t for t in target_langs if t != HEBREW]
        claude_targets = [t for t in target_langs if t == HEBREW]

    translations_by_index: list[dict[str, str]] = [{} for _ in sentences]

    if gemini_targets:
        try:
            results = _call_gemini(verb_lang, lemma, gemini_targets, sentences, project)
            for i, row in enumerate(results):
                if i < len(translations_by_index):
                    translations_by_index[i].update(
                        {
                            k: v
                            for k, v in row.items()
                            if isinstance(v, str) and v.strip()
                        }
                    )
        except Exception:
            logger.exception("Gemini translation failed for %s/%s", verb_lang, lemma)

    if claude_targets:
        try:
            results = _call_claude(verb_lang, lemma, claude_targets, sentences, api_key)
            for i, row in enumerate(results):
                if i < len(translations_by_index):
                    translations_by_index[i].update(
                        {
                            k: v
                            for k, v in row.items()
                            if isinstance(v, str) and v.strip()
                        }
                    )
        except Exception:
            logger.exception("Claude translation failed for %s/%s", verb_lang, lemma)

    updated: list[dict] = []
    for ex, new_t in zip(examples, translations_by_index):
        if not isinstance(ex, dict):
            updated.append(ex)
            continue
        existing = (
            ex.get("translations", {})
            if isinstance(ex.get("translations"), dict)
            else {}
        )
        merged = {**existing, **new_t}
        updated.append({**ex, "translations": merged} if merged else ex)

    return updated
