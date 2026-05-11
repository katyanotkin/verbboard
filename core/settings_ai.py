from __future__ import annotations

from functools import lru_cache
from typing import Any

import anthropic

from core.settings import _load_anthropic_api_key

# ---------------------------------------------------------------------------
# Generation system prompt — split by language so each API call only sends
# the intro + the relevant language section (fewer tokens, better cache odds).
# ---------------------------------------------------------------------------

_PROMPT_INTRO = """\
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
No two examples may use the same grammatical form."""

_PROMPT_EN = """\
────────────────────────────────────────
ENGLISH (en)
  lemma: infinitive (e.g. "went" → "go", "growing" → "grow")
  morph: {}
  forms: flat keys (no nesting) — base, past, past_participle, present_3sg, gerund
  examples: exactly 5 sentences covering in order:
    simple present (1st person: I / we), simple present (3rd singular: she/he),
    simple present (3rd plural: they), simple past, present perfect"""

_PROMPT_RU = """\
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
    single-aspect verb (has a pair): 4-5 sentences
    biaspectual verb, быть, or unpaired verb: exactly 6 sentences
    One example must use the past neuter singular naturally
    (subject is grammatically neuter, e.g. "Солнце начало садиться.", "Молоко закипело.")."""

_PROMPT_ES = """\
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
    and others from different tenses/persons."""

_PROMPT_HE = """\
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
    at least one present, one past, one future, and others from different forms."""

_LANG_PROMPTS: dict[str, str] = {
    "en": f"{_PROMPT_INTRO}\n\n{_PROMPT_EN}\n",
    "ru": f"{_PROMPT_INTRO}\n\n{_PROMPT_RU}\n",
    "es": f"{_PROMPT_INTRO}\n\n{_PROMPT_ES}\n",
    "he": f"{_PROMPT_INTRO}\n\n{_PROMPT_HE}\n",
}

# Full prompt — all languages combined. Used by verb_service and as fallback.
_GENERATION_SYSTEM_PROMPT = (
    "\n\n".join([_PROMPT_INTRO, _PROMPT_EN, _PROMPT_RU, _PROMPT_ES, _PROMPT_HE]) + "\n"
)

# ---------------------------------------------------------------------------
# Model and token settings
# ---------------------------------------------------------------------------

_MODEL: dict[str, str] = {"en": "claude-haiku-4-5-20251001"}
_MODEL_DEFAULT = "claude-sonnet-4-6"

_MAX_TOKENS: dict[str, int] = {"he": 4096}
_MAX_TOKENS_DEFAULT = 2048

# ---------------------------------------------------------------------------
# Anthropic async client (singleton) and per-language cached system prompt
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_anthropic_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=_load_anthropic_api_key())


def get_cached_system(language: str) -> list[dict[str, Any]]:
    """Per-language system prompt block with Anthropic prompt-caching header."""
    prompt = _LANG_PROMPTS.get(language, _GENERATION_SYSTEM_PROMPT)
    return [{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}]
