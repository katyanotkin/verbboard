# Hebrew audio audit (2026-10-04)

Scope: text-level audit of what each Hebrew clip is generated from, plus where Edge TTS (he-IL-HilaNeural / he-IL-AvriNeural) is likely to mispronounce. Nothing was listened to. Source: linguist agent over a dump of all 111 Hebrew verbs in Firestore, plus `core/languages/he/plugin.py`, `_PROMPT_HE` (`core/settings_ai.py`), `core/tts.py`, `app/routes/audio.py`.

## Summary

- 111 verbs, 2,886 form slots (present 4, past 9, future 9, imperative 4 per verb). No empty slot.
- Every form has nikud; no Latin/Cyrillic or stray symbols; every shin carries its dot.
- `tts_forms`: 0 of 111 verbs. No row has a `tts_text` override, so each form clip is the displayed vocalized text. `display_forms` exists on 3 verbs (he_lhykns, he_lqkht, he_ltt), well formed.
- The critical past 2msg (qamatz+dagesh) / 2fsg (shva) homograph named in the prompt is correct everywhere (97/111; the other 14 are vowel-final stems that correctly take no dagesh).

## Findings, ranked by risk

**A. HIGH: example sentences are the main audio risk.**
- 642 sentences (5-6 per verb). 110 (17%, from 26 verbs) have no nikud at all; 20 verbs have no vocalized example. The other 532 are partially vocalized (about 1.7 of 6.1 words, usually only the target form). None is fully vocalized.
- Edge he-IL has no vowel-aware model; it guesses vowels and stress from context. Typical failures: present vs past ambiguity, future vs imperative, loanwords.
- Known collisions with no nikud: he_lbva "אני בא מחר.", he_lhykns "אני נכנס לחדר." (probably fine thanks to אני/מחר, worth a listen).
- Whether Edge honors niqqud at all cannot be confirmed from text.

**B. HIGH: identical-spelling slots inside one verb.** If nikud is ignored, these sound identical.
- Past 2msg vs 2fsg (111/111): differ only in ָּ vs ְּ. Probably the biggest form-clip risk.
- Present m_sg vs past 3msg: 15 verbs identical unvocalized, 8 identical even vocalized (e.g. he_lbva, he_lhykns, he_lqvm, he_lshkkh).
- Present f_sg vs past 3fsg: 11 identical unvocalized, 8 vocalized. Separable only by stress (e.g. אִיחֲרָה vs מְאַחֶרֶת).
- Future 2msg vs 3fsg is identical by design in Hebrew, not a bug.

**C. MEDIUM: stress and binyan risk.** Long-prefix hif'il/hitpael (he_lhshtmsh, he_lhstkl, he_lhtpll), final-stress past 1sg/2sg (-תִּי, -תָּ), segolate presents (אוֹכֶלֶת, מְאַחֶרֶת), irregular infinitives (לוֹמַר, לַעֲרוֹךְ), patach gnuva verbs (he_lqkht, he_lshkkh). Binyan counts: פָּעַל 61, הִפְעִיל 20, פִּיעֵל 16, הִתְפַּעֵל 10, נִפְעַל 4; no Pual/Huf'al.

**D. MEDIUM: voice/gender agreement.** 86 examples use אני/אנחנו (gender-neutral). Gender-marked sentences read by the opposite-gender voice (e.g. he_lhnvt "אני בטוחה...") are inherent; not worth fixing. No case found where a form's gender contradicts the sentence pronoun (partial check, not all 642 read).

**E. LOW: vocalized words matching no stored form.** he_lhnvt "שתֵּהָנִי", he_lmtsa "שנִמְצָא", he_lshkkh "שוֹכֵחַ": clitic prefixes, probably deliberate.

## Data errors found (fix regardless of audio)

- 6 forms in 2 verbs carry a dagesh that cannot occur (holam + dagesh on the future prefix):
  - he_lakvl.future.3msg יֹּאכַל, 3pl יֹּאכְלוּ, 1pl נֹּאכַל
  - he_lvmr.future.3msg יֹּאמַר, 3pl יֹּאמְרוּ, 1pl נֹּאמַר
  - correct: יֹאכַל, יֹאכְלוּ, נֹאכַל, יֹאמַר, יֹאמְרוּ, נֹאמַר (the tav forms תֹּאכַל / תֹּאמַר are correct).
- 21 of 111 infinitives (19%) have no nikud (e.g. לאכול, לבקש, לבוא, לדבר, לדעת, להביא, להבין, להתחיל, לכתוב, ללכת, לקחת, לראות, לשלם, לתת, לוותר). The infinitive row has audio, so these 21 clips are read from bare consonants. Cause: `_PROMPT_HE` says only "infinitive (לְ prefix form)" without asking for nikud.
- Coverage gap, not an audio bug: `forms.imperative` (ms/fs/mp/fp) is generated and stored for all 111 verbs but never rendered or voiced. PRODUCT_BACKLOG was not checked for a scoping decision.

## Where a `tts_text` override (via `tts_forms`) would help, only if listening confirms a problem

- Past 2msg/2fsg for all 111 verbs (plene spelling, e.g. הלכת vs הלכתְּ).
- Present f_sg vs past 3fsg in the 8 vocalized-identical verbs; present m_sg in the 15 collision verbs.
- The 21 bare infinitives: fix at data level (vocalize the lemma), no `tts_text` needed.
- Not worth overriding: future 2msg/3fsg.

## What only listening can confirm

Whether Hila/Avri honor niqqud (compare a bare clip with a vocalized clip of the same word); whether the 2msg/2fsg and present/past pairs are distinguishable; whether stress is correct in the forms above; whether partially vocalized examples read naturally; whether the 3 `display_forms` verbs sound right.

## Listening checklist (about 15 clips)

URL pattern `/audio/he/{verb_id}/{female|male}/{form_key}.mp3`; `form_key` is the row key plus a hash suffix, so take exact URLs from the rendered `/learn` page.

1. he_lhlkh past_2msg vs past_2fsg (female voice); if the verb is absent use he_lbva
2. he_lbva pres_m_sg vs past_3msg
3. he_lhykns pres_m_sg vs past_3msg (display_forms verb)
4. he_lakvl pres_f_sg vs past_3fsg (stress pair)
5. he_lakvl fut_3msg and fut_1pl (the dagesh error)
6. he_lvmr fut_3msg and infinitive (לוֹמַר)
7. he_lqkht infinitive and pres_m_sg (patach gnuva; display_forms verb)
8. he_ltt fut_3msg and past_2fsg (display_forms verb)
9. he_lshkkh pres_m_sg and its example containing שוֹכֵחַ
10. he_lhshtmsh past_3fsg and past_1sg (long hitpael prefix)
11. he_lbqsh past_3fsg and pres_m_pl (shva+dagesh patterns)
12. an unvocalized infinitive (he_lakvl לאכול) vs a vocalized one (he_lvmr לוֹמַר)
13. he_lakvl example 1 "אני אוכל תפוח." (fully bare) vs he_lhkyr example 1 (partial nikud)
14. he_lbva example "אני בא מחר." (ambiguous present/past, bare); example keys are `example_{idx}_{hash}`

## Recommended next steps

1. Listen to the checklist first; the rest depends on whether the engine honors nikud.
2. Fix the 6 wrong future forms (he_lakvl, he_lvmr) in Firestore and regenerate those clips.
3. Vocalize the 21 bare lemmas and make `_PROMPT_HE` require a vocalized infinitive.
4. If listening shows nikud is ignored: decide between plene `tts_forms` for the 2msg/2fsg pair and collision verbs, and fully vocalizing examples (needs a prompt change and regeneration of 642 sentences; not to be done blindly).
5. Decide whether to render the imperative (free coverage gain).
6. If a clip problem is confirmed, reuse the per-verb audio note from the UX proposal (curated list, "Audio may mispronounce some forms of this verb" + report link).
