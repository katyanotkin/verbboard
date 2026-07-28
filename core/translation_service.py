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
import os
import re

import anthropic
import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel

logger = logging.getLogger(__name__)

_GCP_LOCATION = os.getenv("GCP_REGION", "us-east1")

SUPPORTED_LANGUAGES = ["en", "ru", "he", "es"]
HEBREW = "he"
GEMINI_MODEL = "gemini-2.5-flash-lite"
CLAUDE_MODEL = "claude-sonnet-4-6"

_LANG_NAMES = {"en": "English", "ru": "Russian", "he": "Hebrew", "es": "Spanish", "it": "Italian"}


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
- Prefer to translate the verb "{lemma}" using the same root word across all sentences, inflected naturally for each sentence's tense and person. Use a different word only if the primary translation genuinely doesn't fit — due to meaning, register, or idiom.
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
) -> list[dict[str, str]]:
    vertexai.init(project=project, location=_GCP_LOCATION)
    model = GenerativeModel(GEMINI_MODEL)
    prompt = _translation_prompt(verb_lang, lemma, target_langs, sentences)
    response = model.generate_content(
        prompt,
        generation_config=GenerationConfig(response_mime_type="application/json", temperature=0),
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
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(message.content[0].text.strip())


def _lemma_prompt(verb_lang: str, lemma: str, target_langs: list[str]) -> str:
    src_name = _LANG_NAMES.get(verb_lang, verb_lang)
    targets = ", ".join(_LANG_NAMES.get(t, t) for t in target_langs)
    return f"""\
Translate the following {src_name} verb infinitive (dictionary form) into: {targets}.
Verb: "{lemma}"

Rules:
- Return the dictionary/infinitive form in each target language, not a conjugated form.
- Keep each translation to a single word or short phrase (e.g. English infinitives may include "to").

If the source word is ambiguous -- multiple meanings/senses, or multiple valid
conjugation patterns in the source language (e.g. English "fit" as
fit-fit-fit vs fit-fitted-fitted) -- silently pick the single most common
meaning and translate that, ignoring which source-language conjugation
pattern applies. Do not explain the ambiguity or second-guess yourself.

Return ONLY a JSON object with language codes as keys, e.g. {{"en": "...", "ru": "..."}}.
No commentary, no markdown fences, no text before or after the JSON object.
"""


def _call_gemini_lemma(
    verb_lang: str,
    lemma: str,
    target_langs: list[str],
    project: str,
) -> dict[str, str]:
    vertexai.init(project=project, location=_GCP_LOCATION)
    model = GenerativeModel(GEMINI_MODEL)
    prompt = _lemma_prompt(verb_lang, lemma, target_langs)
    response = model.generate_content(
        prompt,
        generation_config=GenerationConfig(response_mime_type="application/json", temperature=0),
    )
    return json.loads(response.text)


def _call_claude_lemma(
    verb_lang: str,
    lemma: str,
    target_langs: list[str],
    api_key: str,
) -> dict[str, str]:
    client = anthropic.Anthropic(api_key=api_key)
    prompt = _lemma_prompt(verb_lang, lemma, target_langs)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    # Claude occasionally prepends commentary or second-guesses itself before
    # settling on an answer despite instructions -- pull out the last {...}
    # block (the model's final answer) rather than parsing the whole response.
    matches = re.findall(r"\{[^{}]*\}", raw)
    return json.loads(matches[-1] if matches else raw)


def translate_lemma(
    *,
    verb_lang: str,
    lemma: str,
    existing_translations: dict[str, str] | None = None,
    target_langs: list[str] | None = None,
    project: str,
    api_key: str,
) -> dict[str, str]:
    """
    Translate a verb's infinitive/lemma into other UI languages.

    Only fills missing target languages; returns the merged translations dict.
    Non-fatal: on any error the existing translations are returned unchanged.
    """
    existing = dict(existing_translations or {})

    if target_langs is None:
        target_langs = [lang for lang in SUPPORTED_LANGUAGES if lang != verb_lang]

    missing_targets = [t for t in target_langs if t not in existing]
    if not missing_targets:
        return existing

    if verb_lang == HEBREW:
        gemini_targets: list[str] = []
        claude_targets: list[str] = missing_targets
    else:
        gemini_targets = [t for t in missing_targets if t != HEBREW]
        claude_targets = [t for t in missing_targets if t == HEBREW]

    result = dict(existing)

    if gemini_targets:
        try:
            row = _call_gemini_lemma(verb_lang, lemma, gemini_targets, project)
            result.update({k: v for k, v in row.items() if isinstance(v, str) and v.strip()})
        except Exception:
            logger.exception("Gemini lemma translation failed for %s/%s", verb_lang, lemma)

    if claude_targets:
        try:
            row = _call_claude_lemma(verb_lang, lemma, claude_targets, api_key)
            result.update({k: v for k, v in row.items() if isinstance(v, str) and v.strip()})
        except anthropic.APIStatusError as exc:
            if exc.status_code != 529:
                logger.exception("Claude lemma translation failed for %s/%s", verb_lang, lemma)
            elif verb_lang == HEBREW:
                raise
            else:
                logger.warning("Claude overloaded (529), skipping Hebrew lemma translation for %s/%s", verb_lang, lemma)
        except Exception:
            logger.exception("Claude lemma translation failed for %s/%s", verb_lang, lemma)

    return result


def translate_search_query(
    query: str,
    source_lang: str,
    target_lang: str,
) -> str | None:
    """Translate a single search query word to the target language verb lemma.

    Returns the native-script verb string, or None on failure.
    """
    src_name = _LANG_NAMES.get(source_lang, source_lang)
    tgt_name = _LANG_NAMES.get(target_lang, target_lang)
    prompt = (
        f"You are a language-learning dictionary. "
        f"Given a {src_name} word (any inflected form), find its base verb, then return its {tgt_name} infinitive.\n"
        f'Word: "{query}"\n'
        f"Rules: reply with exactly one word in {tgt_name} script, no punctuation, no explanation."
    )
    try:
        model = GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt, generation_config=GenerationConfig(temperature=0))
        text = (response.text or "").strip()
        return text or None
    except Exception:
        logger.exception(
            "Gemini search translation failed query=%r %s->%s",
            query,
            source_lang,
            target_lang,
        )
        return None


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

    sentences = [ex["dst"] for ex in examples if isinstance(ex, dict) and isinstance(ex.get("dst"), str)]
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
                    translations_by_index[i].update({k: v for k, v in row.items() if isinstance(v, str) and v.strip()})
        except Exception:
            logger.exception("Gemini translation failed for %s/%s", verb_lang, lemma)

    if claude_targets:
        try:
            results = _call_claude(verb_lang, lemma, claude_targets, sentences, api_key)
            for i, row in enumerate(results):
                if i < len(translations_by_index):
                    translations_by_index[i].update({k: v for k, v in row.items() if isinstance(v, str) and v.strip()})
        except anthropic.APIStatusError as exc:
            if exc.status_code != 529:
                logger.exception("Claude translation failed for %s/%s", verb_lang, lemma)
            elif verb_lang == HEBREW:
                # Hebrew source: Claude is the only backend; no translations at all is a hard failure.
                raise
            else:
                logger.warning(
                    "Claude overloaded (529), skipping Hebrew target translation for %s/%s", verb_lang, lemma
                )
        except Exception:
            logger.exception("Claude translation failed for %s/%s", verb_lang, lemma)

    updated: list[dict] = []
    for ex, new_t in zip(examples, translations_by_index):
        if not isinstance(ex, dict):
            updated.append(ex)
            continue
        existing = ex.get("translations", {}) if isinstance(ex.get("translations"), dict) else {}
        merged = {**existing, **new_t}
        updated.append({**ex, "translations": merged} if merged else ex)

    return updated
