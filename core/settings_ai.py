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
  "examples": [ {"dst": "<sentence>", "form": "<tense>.<person>", "answer": "<words in the sentence>"}, ... ]
}

Examples: write the way a careful native speaker would, natural and idiomatic, each sentence a single concrete everyday
situation (5-14 words) with the word order natural to the language (do not copy English order). Each example shows ONE
conjugated form, and no two examples use the same tense+person cell. Follow the tense distribution given for the language
below: never spend two examples on cells of one tense while a required tense has none. Across the set use at least three
different persons, including one plural. Do not reuse a sentence frame within the verb. If a form is unnatural for this
verb (a progressive of a stative verb, a command nobody would give), cover another required form instead and never
invent a context to fill the slot.

Example tagging: for every example, "form" is the path into YOUR "forms" object of the one conjugated form the sentence shows, as "<tense>.<person>" (e.g. "present.3sg") or just "<tense>" for a form without persons (e.g. "gerund", "past_participle"). "answer" is those exact words as written in the sentence: one word for a simple tense; for a compound tense the auxiliary plus participle without the subject pronoun. The answer must appear in "dst" exactly once and match the stored form. If the sentence shows no listed form (e.g. a bare infinitive), set "form" to null and omit "answer"."""

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

  examples: exactly 6 sentences:
    simple present (I / we), simple present (3rd singular: she/he), simple past, present perfect,
    a progressive using the gerund form ("is eating"; for a stative verb such as know, need, believe, seem,
    understand, like, own, use a second simple past instead), and an imperative only if the verb has a natural one
    (otherwise a simple present with they/you). An imperative must be a real command addressed to someone, never a
    bare fragment ("Mean it.") or a present-tense sentence that merely contains the verb."""

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

  examples: exactly 7 sentences, with the split depending on aspect. Imperfective shows process, repetition or habit;
    perfective shows one completed result.
    imperfective: 3 present (three different persons, one ты/вы and one мы/они; one habitual, one ongoing),
      2 past (different gender/number), 1 imperative, 1 more present or past.
    Do not use the compound future "буду/будешь... + infinitive" in examples (it has no cell on the board).
    perfective: 3 future (different persons, a single completed result), 2 past, 1 imperative,
      1 more future or past.
    biaspectual: 2 present, 2 future, 2 past, 1 imperative.
    Skip the imperative for verbs with no natural command (хотеть, мочь, ненавидеть, значить) and add one more
    present (imperfective) or future (perfective) instead.
    Past neuter only with a naturally neuter subject (солнце, молоко, письмо, время), never это, эхо, дитя or
    привидение; at most one. Natural word order ("Она медленно закрыла книгу")."""

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
    conditional:           { yo, tu, el, nos, vosotros, ellos }  ← condicional simple: the FUTURE stem plus
      -ía, -ías, -ía, -íamos, -íais, -ían, so it must agree with the future you give (tener → tendría,
      hacer → haría, poder → podría, querer → querría, saber → sabría, venir → vendría, decir → diría,
      poner → pondría, salir → saldría, haber → habría, ir → iría, ser → sería). Never copy the imperfect.
    subjunctive_present:   { yo, tu, el, nos, vosotros, ellos }  ← presente de subjuntivo, bare forms WITHOUT
      "que" (comprar → compre, compres, compre, compremos, compréis, compren). Derive from the yo form of the
      present (tengo → tenga), keep stem changes (poder → pueda ... podamos, podáis ... puedan; pedir → pida
      ... pidamos), and use the true irregulars: ser (sea, seas, sea, seamos, seáis, sean), estar (esté, estés,
      esté, estemos, estéis, estén), ir (vaya ...), saber (sepa ...), haber (haya ...), dar (dé, des, dé,
      demos, deis, den). Never copy the indicative present.
    subjunctive_imperfect: { yo, tu, el, nos, vosotros, ellos }  ← imperfecto de subjuntivo in the -ra form
      (comprar → comprara, compraras, comprara, compráramos, comprarais, compraran), built from the ellos
      form of the preterite (hacer → hicieran → hiciera; ser/ir → fuera, fueras, fuera, fuéramos, fuerais,
      fueran; tener → tuviera; poder → pudiera). Write the accent on nosotros (compráramos, comiéramos).
      Never copy the preterite or the imperfect.
    For the three tenses above, reflexive verbs keep the pronoun per person (me/te/se/nos/os/se), a verb
      with no natural form of a tense returns {} for it, and impersonal verbs fill only the "el" slot.
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
  examples: 7 sentences in Spanish (Spain Spanish), one each of present, preterite, imperfect, future, conditional,
    subjunctive and imperative (a different form instead if the verb has no natural imperative), plus an optional
    gerund as an 8th; at least four persons including vosotros and ellos. In detail: the conditional (a polite request, a
    wish or the result of "si + imperfecto de subjuntivo"), one subjunctive (presente after a trigger like
    "quiero que", "es importante que", "para que", or imperfecto in "Si fuera barato, lo compraría")
    unless the verb has none. Use real scenes with a complete meaning (a subject, an object where the verb needs
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
  lemma: infinitive (לְ prefix form) WITH full nikud on every letter that takes a vowel, e.g. "לֶאֱכֹל",
    "לָלֶכֶת", "לְדַבֵּר" (never bare consonants such as "לאכול"; the infinitive is voiced by TTS)
  morph:
    binyan: one of פָּעַל, נִפְעַל, פִּיעֵל, פֻּעַל, הִתְפַּעֵל, הִפְעִיל, הוּפְעַל
    root: letters separated by dots, e.g. "ל.מ.ד"
  forms (all nested) — WITH full nikud so learners can read pronunciation:
    present:   { m_sg, f_sg, m_pl, f_pl }
    past:      { 1sg, 2msg, 2fsg, 3msg, 3fsg, 1pl, 2mpl, 2fpl, 3pl }
    future:    { 1sg, 2msg, 2fsg, 3msg, 3fsg, 1pl, 2mpl, 2fpl, 3pl }
    imperative: { ms, fs, mp }  ← masculine singular, feminine singular, masculine plural only (no feminine
      plural: it is literary and error-prone). A verb with no natural command form (stative, no real command: to need,
      to want, to prefer; but verbs like to die DO have a natural imperative) returns imperative as an empty object {} instead of an invented form.
    Critical homographs: past 2msg ends in ָּ (qamatz + dagesh), 2fsg ends in ְ (shva). Never omit.
    Example for הלך: past.2msg = "הָלַכְתָּ", past.2fsg = "הָלַכְתְּ"
  examples: 6 sentences in Hebrew script: 2 present (different gender/number), 1-2 past, 1-2 future (including a
    2nd person, at least one feminine), and 1 imperative if the verb has one (otherwise another future or past).
    Point the conjugated verb fully with nikud and leave the other words unpointed. Check that numerals agree in
    gender with their noun."""

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
    condizionale_presente: { io, tu, lui, noi, voi, loro }  ← condizionale presente, same shape as presente,
      bare forms. It is the FUTURO stem plus -ei, -esti, -ebbe, -emmo, -este, -ebbero, so it must agree
      with the futuro you give: essere (sarei), avere (avrei), andare (andrei), fare (farei), potere
      (potrei), volere (vorrei), sapere (saprei), dare (darei), stare (starei), dire (direi). Never copy
      the imperfetto or the futuro. Reflexives keep the clitic ("mi chiamerei").
    congiuntivo_presente: { io, tu, lui, noi, voi, loro }  ← congiuntivo presente, WITHOUT "che". Use the
      true forms; io, tu and lui are identical: essere (sia, sia, sia, siamo, siate, siano), avere (abbia
      ... abbiamo, abbiate, abbiano), andare (vada ... andiamo, andiate, vadano), fare (faccia ...
      facciamo, facciate, facciano), potere (possa ... possiamo, possiate, possano), volere (voglia ...
      vogliamo, vogliate, vogliano), sapere (sappia), dare (dia ... diamo, diate, diano), stare (stia),
      dire (dica ... diciamo, diciate, dicano). Never copy the indicativo presente. Its lui form must
      equal imperativo.lei.
    congiuntivo_imperfetto: { io, tu, lui, noi, voi, loro }  ← congiuntivo imperfetto, WITHOUT "se"/"che".
      io and tu are identical: essere (fossi, fossi, fosse, fossimo, foste, fossero), avere (avessi ...
      aveste), andare (andassi ... andaste), fare (facessi ... faceste), dire (dicessi ... diceste), dare
      (dessi ... deste), stare (stessi ... steste). Never copy the indicativo imperfetto.
    Impersonal verbs (piovere, bisognare) fill only "lui" for the three tenses above, other slots empty
      strings; a verb with no natural form of a tense returns {} for it.
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
  examples: 7 sentences in Italian, one each of presente, passato prossimo, imperfetto, futuro, condizionale,
    congiuntivo and imperativo (a different form instead if the verb has no natural imperativo), plus an optional
    gerundio as an 8th; at least four persons including voi and loro. In detail: the condizionale (a polite
    request or a wish) and the congiuntivo (presente after "penso che" or
    "voglio che", or imperfetto in "Se fossi ricco, comprerei ...") unless the verb has none.
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
    conditionnel_present: { je, tu, il, nous, vous, ils }  ← conditionnel présent, same shape as présent
      (pronoun with elision, e.g. "j'aurais", "il aurait", "nous aurions"). It is the FUTUR stem plus
      the imparfait endings (-ais, -ais, -ait, -ions, -iez, -aient), so it must agree with the futur
      you give: avoir (aurais), être (serais), aller (irais), faire (ferais), pouvoir (pourrais),
      vouloir (voudrais), savoir (saurais), voir (verrais), venir (viendrais), devoir (devrais).
      Never copy the imparfait or the futur. Impersonal verbs (falloir: il faudrait) fill only "il"
      and leave other slots empty strings; if a verb has no conditionnel at all, return {}.
    subjonctif_present: { je, tu, il, nous, vous, ils }  ← subjonctif présent, same shape as présent
      (pronoun with elision, e.g. "j'aie", "tu aies", "il ait"), WITHOUT "que" or "qu'" (write "il ait",
      never "qu'il ait"; the board title already says "que…"). Use the true stems:
      avoir (aie, aies, ait, ayons, ayez, aient), être (sois, sois, soit, soyons, soyez, soient),
      aller (aille ... allions, alliez ... aillent), faire (fasse), pouvoir (puisse), savoir (sache),
      vouloir (veuille ... voulions, vouliez ... veuillent). Stem-changing verbs keep nous/vous on the
      imparfait stem (boire: boive ... buvions). Never copy the indicative présent. Impersonal verbs
      (falloir, pleuvoir) fill only "il" and leave other slots empty strings; if a verb has no
      subjunctive at all, return {}.
    imperatif:      { tu, nous, vous }  ← include all three slots for verbs that have an imperative.
      A small number of verbs (e.g. pouvoir) are grammatically defective in the imperative mood in
      standard French — no genuine command form exists. For these, return imperatif as an empty
      object {} rather than fabricating forms by copying the présent (e.g. do NOT return
      pouvoir.imperatif = {tu: "peux", nous: "pouvons", vous: "pouvez"} — that is not real French).
      When in doubt whether a verb has a natural imperative, prefer omitting it over inventing one.
    gerondif: "<gérondif, e.g. 'en parlant'>"  (string)
    participe_passe: "<past participle>"       (string, masculine singular form)
  Elision: use standard French elision (je → j') before a vowel sound, e.g. "j'ai parlé", "j'aime".
  examples: 7 sentences in French, one each of présent, passé composé, imparfait, futur, conditionnel présent,
    subjonctif présent and impératif (a different form instead if the verb has no natural impératif), plus an
    optional gérondif as an 8th; at least four persons including vous and ils. In detail: the conditionnel présent
    (a polite request, a wish or the result of "si + imparfait") and the subjonctif présent after a
    real trigger (il faut que, bien que, pour que, je veux que) unless the verb has none; skip the impératif
    if the verb has no natural imperative (see above) and cover another form instead.
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
  examples: 4 to 6 sentences in Turkish: at least one present continuous, one aorist, one past, one future, and one
    imperative where it is natural; use at least four persons including onlar."""

_PROMPT_PT = """\
────────────────────────────────────────
BRAZILIAN PORTUGUESE (pt)
  Use Brazilian Portuguese (pt-BR) only: Brazilian spelling and usage ("você" for singular "you"),
  never European forms (no "tu"/"vós" slots, no "estou a fazer", no clitic-after-verb "dá-me").
  lemma: infinitive form, e.g. "falar".
  morph: {}
  forms (all nested). Slots are eu, ele, nos, eles, with NO pronoun in the stored text (the row label
    shows it); "ele" also stands for ela/você and "eles" for elas/vocês, which take the third-person forms:
    present:              { eu, ele, nos, eles }  ← presente do indicativo, e.g. "falo", "fala", "falamos", "falam"
    preterite:            { eu, ele, nos, eles }  ← pretérito perfeito simples, e.g. "falei", "falou", "falamos", "falaram"
      (note: nós is the same as the present for regular -ar verbs; that is correct)
    imperfect:            { eu, ele, nos, eles }  ← pretérito imperfeito, e.g. "falava", "falava", "falávamos", "falavam"
    future:               { eu, ele, nos, eles }  ← futuro do presente (simple form), e.g. "falarei", "falará", "falaremos", "falarão"
    conditional:          { eu, ele, nos, eles }  ← futuro do pretérito, e.g. "falaria", "falaria", "falaríamos", "falariam"
    subjunctive_present:  { eu, ele, nos, eles }  ← presente do subjuntivo, bare forms without "que",
      e.g. "fale", "fale", "falemos", "falem"; ser (seja), ter (tenha), ir (vá), estar (esteja), dar (dê).
    subjunctive_imperfect:{ eu, ele, nos, eles }  ← pretérito imperfeito do subjuntivo, bare forms without "se",
      e.g. "falasse", "falasse", "falássemos", "falassem"; built from the preterite eles stem
      (fazer: fizesse, ter: tivesse, ir/ser: fosse, ver: visse).
    imperative:           { voce, nos, voces }  ← e.g. "fale", "falemos", "falem" (the imperative of você/vocês
      is the subjunctive present). If a verb has no natural command form, return {}.
      Reflexive imperatives follow written pt-BR: "levante-se", "levantemo-nos", "levantem-se".
    gerund: "<gerúndio, e.g. 'falando'>"        (string)
    participle: "<past participle, masculine singular>"  (string)
  Accents are required (é, ê, á, â, ã, õ, ç, í, ó, ú). Reflexive verbs (levantar-se, chamar-se): use the
    Brazilian proclitic pronoun before the finite form ("me levanto", "se levanta", "nos levantamos", "se levantam"),
    and keep the lemma as "levantar-se".
  examples: 7 sentences in Brazilian Portuguese, one each of presente, pretérito perfeito, imperfeito, futuro,
    condicional, subjuntivo presente (after a real trigger such as "quero que", "talvez" or "é importante que")
    and imperativo (a different form instead if the verb has no natural command); at least three persons
    including nós and eles/vocês. Use "você" for the singular "you" and never "tu". Vary the sentence frames and
    situations for each verb."""

_LANG_PROMPTS: dict[str, str] = {
    "en": f"{_PROMPT_INTRO}\n\n{_PROMPT_EN}\n",
    "ru": f"{_PROMPT_INTRO}\n\n{_PROMPT_RU}\n",
    "es": f"{_PROMPT_INTRO}\n\n{_PROMPT_ES}\n",
    "he": f"{_PROMPT_INTRO}\n\n{_PROMPT_HE}\n",
    "it": f"{_PROMPT_INTRO}\n\n{_PROMPT_IT}\n",
    "fr": f"{_PROMPT_INTRO}\n\n{_PROMPT_FR}\n",
    "pt": f"{_PROMPT_INTRO}\n\n{_PROMPT_PT}\n",
    "tr": f"{_PROMPT_INTRO}\n\n{_PROMPT_TR}\n",
}

# Full prompt — all languages combined. Used by verb_service and as fallback.
_GENERATION_SYSTEM_PROMPT = (
    "\n\n".join(
        [_PROMPT_INTRO, _PROMPT_EN, _PROMPT_RU, _PROMPT_ES, _PROMPT_HE, _PROMPT_IT, _PROMPT_FR, _PROMPT_PT, _PROMPT_TR]
    )
    + "\n"
)

# ---------------------------------------------------------------------------
# Model and token settings
# ---------------------------------------------------------------------------

_MODEL: dict[str, str] = {"en": "claude-haiku-4-5-20251001"}
_MODEL_DEFAULT = "claude-sonnet-4-6"

_MAX_TOKENS: dict[str, int] = {
    "he": 4096,
    "ru": 3072,
    "fr": 3072,
    "es": 3072,
    "it": 3072,
    "en": 3072,
    "pt": 3072,
    "tr": 3072,
}
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
