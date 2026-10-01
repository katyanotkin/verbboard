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

Return raw valid JSON only — no markdown fences, comments, or prose. Double-quote all keys and strings. Begin your response with `{`.

If the query is NOT a verb (e.g. it is a noun, adjective, number, proper name, or nonsense), return exactly: {"lemma": null, "forms": {}} — nothing else.

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

  Variant past/past_participle forms: some verbs have more than one valid
  past-tense form depending on dialect or sense (e.g. "fit" → past "fit" in US
  English, "fitted" in UK English and always for the "installed/tailored"
  sense; "dreamed"/"dreamt", "learned"/"learnt"). Silently pick the single most
  common form and use it consistently for both past and past_participle —
  do not hedge, mention the variant, or return alternatives.

  examples: exactly 5 sentences covering in order:
    simple present (1st person: I / we), simple present (3rd singular: she/he),
    simple present (3rd plural: they), simple past, present perfect"""

_PROMPT_RU = """\
────────────────────────────────────────
RUSSIAN (ru)
  lemma: infinitive form
  morph:
    aspect: "perfective" | "imperfective" | "biaspectual"
      Use "biaspectual" for verbs that function as both aspects (e.g. организовать, использовать).
    pair: aspect partner's infinitive (e.g. "поймать" ↔ "ловить"). "" if none — never invent.
      Biaspectual verbs have no pair — use "".

  forms — tense slots depend on aspect:
    imperfective  → present, past, imperative
    perfective    → future, past, imperative
    biaspectual   → present, future, past, imperative

    present / future: { 1sg, 2sg, 3sg, 1pl, 2pl, 3pl }
    past:             { m, f, n, pl }
    imperative:       { sg, pl }

  IMPERATIVE: derive from the actual conjugation stem.
    Soft-stem verbs take -ь / -ьте, not -и / -ите.
    Examples: зависеть → завись / зависьте, уведомить → уведомь / уведомьте,
    ехать → езжай, давать → давай, бежать → беги, вставать → вставай.

  pronoun_forms — top-level output key (alongside "forms"); past forms prefixed with subject pronoun, for TTS:
    m: "он <past_m>", f: "она <past_f>", n: "оно <past_n>", pl: "они <past_pl>"
    Plain text only — no stress marks or diacritics.

  PLAIN TEXT EVERYWHERE: the same rule applies to every Russian string you output (lemma, forms,
    pronoun_forms, pair, examples). Never write a combining acute accent (U+0301) or any other
    stress mark, even for words whose stress is hard to predict.

  examples:
    paired verb: 5 sentences
    biaspectual or unpaired verb: 6 sentences
    Aim to include one past neuter singular example (subject is grammatically neuter,
    e.g. "Солнце начало садиться.", "Молоко закипело."), but skip it if it would feel
    forced or unnatural. Never use more than one."""

_PROMPT_ES = """\
────────────────────────────────────────
SPANISH (es)
  lemma: infinitive form
  morph: {}
  forms (all nested):
    present:    { yo, tu, el, nos, vosotros, ellos }
    preterite:  { yo, tu, el, nos, vosotros, ellos }
    imperfect:  { yo, tu, el, nos, vosotros, ellos }
    future:     { yo, tu, el, nos, vosotros, ellos }
    imperative: { tu, vosotros, usted, ustedes }  ← include all four slots, with the real forms
      (ser → sé / sed / sea / sean; estar → está / estad / esté / estén; ir → ve / id / vaya / vayan).
      Exception: a verb with no natural command form (poder, haber as auxiliary) gets only the
      slots that really exist ("usted"/"ustedes" via the subjunctive); leave the others as empty
      strings and never pass off an indicative (puede) as an imperative.
    gerund: "<gerund>"              (string)
    participle: "<past participle>" (string)
  Reflexive verbs (llamarse, levantarse, sentarse): attach the pronoun to every finite form per
    person (me/te/se/nos/os/se), e.g. present.yo = "me llamo"; imperative.tu = "levántate",
    vosotros = "levantaos"; gerund "levantándose"; participle plain ("levantado").
  Verbs used with an indirect object (gustar, parecer): give the forms as they are used
    (me gusta / me gustan are examples, forms follow the 3rd person), and say so in the examples.
  examples: 5 to 6 sentences in Spanish (Spain Spanish), each using a distinct grammatical form:
    at least one present, one preterite, one imperfect or future, one imperative — and no more than
    two presents. Use real scenes with a complete meaning (a subject, an object where the verb needs
    one); do NOT use filler frames like "Yo ... cada día", "Él ... ahora", "Ayer nosotros ... juntos"
    or "Estamos <gerund> hoy". Vary persons (tú, ella, ellos, vosotros, usted) and settings from verb
    to verb. Use vosotros for informal plural (imperative "Venid aquí", "¿Queréis un café?") and
    ustedes only for formal plural. Prefer Spain vocabulary (coger, vale, ordenador). A gerund
    example needs a clear subject and a real ongoing action; skip the gerund for verbs where it is
    unnatural (saber, poder, querer). Keep the preterite and imperfect senses distinct (supimos =
    we found out, sabíamos = we knew).
    Do NOT open examples with "De pequeño/a, mi abuelo/a ..." or reuse stock scenes (bomberos,
    fontanero, técnico, ordenador that crashes, "Si seguís así", "El año que viene", "cola de una
    hora", "el mío se ha quedado sin batería"); each sentence needs its own concrete situation.
    When an example says "when I was little", write "Cuando yo era pequeño/a, ..." so the speaker
    is clear. Keep addressee and speaker gender consistent within each sentence."""

_PROMPT_HE = """\
────────────────────────────────────────
HEBREW (he)
  lemma: infinitive (לְ prefix form)
  morph:
    binyan: one of פָּעַל, נִפְעַל, פִּיעֵל, פֻּעַל, הִתְפַּעֵל, הִפְעִיל, הוּפְעַל
    root: letters separated by dots, e.g. "ל.מ.ד"
  forms (all nested) — WITH full nikud so learners can read pronunciation:
    present:   { m_sg, f_sg, m_pl, f_pl }
    past:      { 1sg, 2msg, 2fsg, 3msg, 3fsg, 1pl, 2mpl, 2fpl, 3pl }
    future:    { 1sg, 2msg, 2fsg, 3msg, 3fsg, 1pl, 2mpl, 2fpl, 3pl }
    imperative: { ms, fs, mp, fp }
    Critical homographs: past 2msg ends in ָּ (qamatz + dagesh), 2fsg ends in ְ (shva). Never omit.
    Example for הלך: past.2msg = "הָלַכְתָּ", past.2fsg = "הָלַכְתְּ"
  examples: 4 to 6 sentences in Hebrew script, each using a distinct grammatical form:
    at least one present, one past, one future, and others from different forms."""

_PROMPT_IT = """\
────────────────────────────────────────
ITALIAN (it)
  lemma: infinitive form
  morph: {}
  forms (all nested):
    presente:         { io, tu, lui, noi, voi, loro }
    passato_prossimo:  { io, tu, lui, noi, voi, loro }  ← full compound form per person,
      e.g. "ho parlato", "hai parlato", "ha parlato", "abbiamo parlato", "avete parlato", "hanno parlato".
      Use the correct auxiliary (avere vs essere) and agree the participle in gender/number
      for essere-verbs — default to masculine singular agreement (e.g. "sono andato", not "andata")
      unless the verb is reflexive, in which case still default masculine singular.
    imperfetto:        { io, tu, lui, noi, voi, loro }
    futuro:            { io, tu, lui, noi, voi, loro }
    imperativo:        { tu, lei, noi, voi }  ← include all four slots (no "io" imperative in Italian).
      Exception: potere, dovere and other verbs with no natural command form — give only "lei"
      (the congiuntivo form) and leave tu/noi/voi as empty strings; never pass off the indicative
      (puoi, devi, possiamo) as an imperative.
      "lei" MUST be derived from the congiuntivo presente 3rd singular, never copied from the presente
      indicativo — this is a common error specifically for modal verbs: e.g. dovere → "debba" (not
      "deve"), potere → "possa" (not "può"), volere → "voglia" (not "vuole").
    gerundio: "<gerundio>"                  (string)
    participio: "<past participle>"         (string, masculine singular form)
  Reflexive verbs (e.g. chiamarsi, alzarsi, svegliarsi): include the clitic pronoun
    attached to each finite form per the normal person (mi/ti/si/ci/vi/si), e.g.
    presente.io = "mi chiamo", presente.tu = "ti chiami"; imperativo drops "si" for
    "lei" only in formal register the same as any other imperativo slot (e.g.
    "si chiami" for lei, "chiamati" for tu with clitic postposed and attached).
    gerundio/participio keep the clitic postposed and attached: "chiamandosi", "chiamatosi".
  examples: 4 to 6 sentences in Italian, each using a distinct grammatical form:
    at least one presente, one passato prossimo, one imperfetto or futuro, one imperativo.
    Vary the sentence frames: do not open the imperfetto example with "Da bambino"/"Quando ero
    bambino", the presente with "Ogni mattina", or the futuro with "L'anno prossimo" by default;
    use different subjects, places and situations for each verb. A gerundio example needs a clear
    subject (the gerundio's subject must be the main clause's subject). Do not use the reflexive
    or reciprocal form of a verb (ricordarsi, conoscersi) to illustrate the plain verb's tense."""

_PROMPT_FR = """\
────────────────────────────────────────
FRENCH (fr)
  lemma: infinitive form
  morph: {}
  forms (all nested):
    present:        { je, tu, il, nous, vous, ils }
    passe_compose:  { je, tu, il, nous, vous, ils }  ← full compound form per person,
      e.g. "j'ai parlé", "tu as parlé", "il a parlé", "nous avons parlé", "vous avez parlé", "ils ont parlé".
      Use the correct auxiliary (avoir vs être) and agree the participle in gender/number
      for être-verbs — default to masculine singular agreement (e.g. "il est allé", not "allée")
      unless the verb is reflexive, in which case still default masculine singular.
    imparfait:      { je, tu, il, nous, vous, ils }
    futur:          { je, tu, il, nous, vous, ils }
    imperatif:      { tu, nous, vous }  ← include all three slots for verbs that have an imperative.
      A small number of verbs (e.g. pouvoir) are grammatically defective in the imperative mood in
      standard French — no genuine command form exists. For these, return imperatif as an empty
      object {} rather than fabricating forms by copying the présent (e.g. do NOT return
      pouvoir.imperatif = {tu: "peux", nous: "pouvons", vous: "pouvez"} — that is not real French).
      When in doubt whether a verb has a natural imperative, prefer omitting it over inventing one.
    gerondif: "<gérondif, e.g. 'en parlant'>"  (string)
    participe_passe: "<past participle>"       (string, masculine singular form)
  Elision: use standard French elision (je → j') before a vowel sound, e.g. "j'ai parlé", "j'aime".
  examples: 4 to 6 sentences in French, each using a distinct grammatical form:
    at least one present, one passé composé, one imparfait or futur, and one impératif —
    unless the verb has no natural imperative (see above), in which case cover another form instead.
    Some verbs (e.g. devoir) DO have real, grammatically valid imperative forms, but those
    forms are pragmatically near-unusable as genuine commands in natural French (ordering
    someone to "obligate themselves" is semantically redundant as a speech act — native
    speakers use the imperative of the main verb, or the indicative "Vous devez...", instead).
    For such verbs, do not force an example sentence into the imperative slot just to cover
    it — a contrived, unnatural-sounding "command" teaches the wrong register more actively
    than simply covering a different distinct form there instead."""

_PROMPT_TR = """\
────────────────────────────────────────
TURKISH (tr)
  lemma: infinitive (mastar) ending in -mek / -mak, e.g. "gitmek".
  morph: {}
  forms (all nested). Every form is ONE word with the person ending attached (no separate
    pronoun) and uses the normal Turkish letters (ç, ğ, ı, İ, ö, ş, ü); plain text, no
    apostrophes or diacritics added:
    present_continuous: { ben, sen, o, biz, siz, onlar }  ← -iyor tense,
      e.g. "geliyorum", "geliyorsun", "geliyor", "geliyoruz", "geliyorsunuz", "geliyorlar".
    aorist:             { ben, sen, o, biz, siz, onlar }  ← geniş zaman,
      e.g. "gelirim", "gelirsin", "gelir", "geliriz", "gelirsiniz", "gelirler".
    past:               { ben, sen, o, biz, siz, onlar }  ← -di tense (görülen geçmiş),
      e.g. "geldim", "geldin", "geldi", "geldik", "geldiniz", "geldiler".
    future:             { ben, sen, o, biz, siz, onlar }  ← -ecek / -acak tense,
      e.g. "geleceğim", "geleceksin", "gelecek", "geleceğiz", "geleceksiniz", "gelecekler".
    imperative:         { sen, siz }  ← e.g. "gel", "gelin".
  Apply vowel harmony, consonant softening (gitmek → gidiyorum, gidecek; etmek → ediyorum)
    and the verb's real aorist vowel (almak → alırım, görmek → görürüm, olmak → olurum,
    vermek → veririm, bilmek → bilirim, yapmak → yaparım). Never invent a form.
  examples: 4 to 6 sentences in Turkish, each using a distinct grammatical form: at least one
    present continuous, one aorist, one past, one future, and one imperative where it is natural."""

_LANG_PROMPTS: dict[str, str] = {
    "en": f"{_PROMPT_INTRO}\n\n{_PROMPT_EN}\n",
    "ru": f"{_PROMPT_INTRO}\n\n{_PROMPT_RU}\n",
    "es": f"{_PROMPT_INTRO}\n\n{_PROMPT_ES}\n",
    "he": f"{_PROMPT_INTRO}\n\n{_PROMPT_HE}\n",
    "it": f"{_PROMPT_INTRO}\n\n{_PROMPT_IT}\n",
    "fr": f"{_PROMPT_INTRO}\n\n{_PROMPT_FR}\n",
    "tr": f"{_PROMPT_INTRO}\n\n{_PROMPT_TR}\n",
}

# Full prompt — all languages combined. Used by verb_service and as fallback.
_GENERATION_SYSTEM_PROMPT = (
    "\n\n".join([_PROMPT_INTRO, _PROMPT_EN, _PROMPT_RU, _PROMPT_ES, _PROMPT_HE, _PROMPT_IT, _PROMPT_FR, _PROMPT_TR])
    + "\n"
)

# ---------------------------------------------------------------------------
# Model and token settings
# ---------------------------------------------------------------------------

_MODEL: dict[str, str] = {"en": "claude-haiku-4-5-20251001"}
_MODEL_DEFAULT = "claude-sonnet-4-6"

_MAX_TOKENS: dict[str, int] = {"he": 4096, "ru": 3072}
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
