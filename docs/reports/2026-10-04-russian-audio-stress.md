# Russian audio: wrong stress on homograph forms (2026-10-04)

Scope: can we produce correct audio for Russian forms the TTS stresses wrongly (мою/моет, начала/начало, погоню and the rest of the curated list)? Source: senior-architect agent reading `core/tts.py`, `core/audio_service.py`, `core/audio_backend/`, `tools/cache_audio.py`, `core/languages/ru/homographs.py`, `core/render.py`, `app/routes/audio.py`, plus the installed `edge-tts` 7.2.8 source. No paid calls were made and nothing was edited. Related issue: #46 (stays open).

## Short answer

Not with Edge TTS, which is all we use today. Claude cannot synthesize audio itself; it can only drive a TTS provider. The fix that keeps the voices consistent is Microsoft's paid Azure Speech API: the same ru-RU-SvetlanaNeural and ru-RU-DmitryNeural voices, with SSML `<phoneme>` pronunciation overrides for only the curated homograph words.

## Current state

- `core/tts.py` is Edge TTS only: `edge_tts.Communicate(text, voice, rate="-10%")`, Russian voices ru-RU-SvetlanaNeural (female) and ru-RU-DmitryNeural (male).
- Stress marks (U+0301) are display-only. `ru/plugin.py` sets `tts_text` to the plain form for curated homograph rows, and examples are voiced from the plain `ex.dst`, so the audio is whatever Edge guesses.
- Curated list (`core/languages/ru/homographs.py`, per verb id): платить (плачу́), заплатить (заплачу́), мыть (мо́ю, мо́ем), начать (начала́, на́чало, на́чали), погнать (погоню́, погони́). Each such verb shows a one-line note that the audio may stress some forms wrongly.
- Clip key: `audio/ru/{verb_id}/{female|male}/{base_key}_{sha1(text)[:10]}.mp3`, content-addressed and immutable in the shared bucket `verbboard-audio-prod`.
- The text is hashed in four places: `core/render.py` (about lines 93 and 206), `app/routes/audio.py` (55, 67), `app/routes/admin_candidates.py` (110, 127), `tools/cache_audio.py` (76, 129).

## Why Edge TTS cannot do it

`edge-tts` escapes the text it receives and builds its own SSML wrapper, so any `<phoneme>`, `<say-as>` or `<sub>` we send is read out as literal text. Only rate, pitch and volume are settable. Stress-marked text is already known to read worse.

## Options

| Option | Verdict |
|---|---|
| Edge TTS with SSML / stress markers | Not feasible (see above). |
| Respell the word for Edge (e.g. tts_text with a spelling that moves stress) | Free, same voice, new text means a new cache key. Trial and error per word and one-word clips have no sentence context; not expected to work reliably for мою, начала, погоню. Worth a 10-minute local check per word. |
| Google Cloud TTS (Chirp 3 HD) | Supports ru-RU, SSML and IPA/X-SAMPA custom pronunciation, fits our GCP setup, negligible cost. Different voices: mixing it in for a few forms makes those clips sound like another person; using it for all of Russian means a full re-cache and a voice change. |
| Vertex / Gemini TTS | No phoneme control, output varies between runs. Rejected. |
| Pre-recorded override clips | Worst voice match, does not scale to example sentences. Rejected. |
| **Azure Speech (paid API, not the Edge endpoint)** | **Recommended.** Same two voices, `<phoneme alphabet="ipa" ph="ˈmo.ju">мою</phoneme>`. Volume is a few thousand characters (about 12 words plus the example sentences containing them, times 2 voices), inside the F0 free tier of 0.5M chars/month. Costs: a new vendor account and a secret in Secret Manager. If Azure is down, only those few clips fail. To confirm before building: that ru-RU is in Azure's phoneme-support table. |

## Code changes (recommended path)

1. `core/languages/ru/homographs.py`: add the IPA next to each "+" spec.
2. `ru/plugin.py`: set `tts_text` to the stress-marked text for homograph rows (changes the hash, so new keys are generated and old clips are orphaned, not overwritten).
3. Examples: one helper `audio_text(language, verb_id, text)` returning the marked text for Russian homograph verbs, used at all four example sites; a missed site would link a key the audio route cannot resolve (404).
4. `core/tts.py`: extend `Voice` with an Azure voice name; route Russian text containing U+0301 to an Azure adapter that turns marked words into `<phoneme>` SSML; everything else stays on Edge.

Trial without touching the shared bucket: a throwaway script writing mp3s locally with an Edge-vs-Azure listening page, or `tools/cache_audio.py --bucket <trial bucket>`. Promote only after linguist and owner sign-off.

Effort: about 1 to 1.5 days plus roughly 0.5 day for the listening check.

## Decisions pending (owner)

1. Add Azure as a second vendor, or stay GCP-only and move all of Russian to Chirp 3 HD (new voice, full re-cache)?
2. Spend 10 minutes first trying free Edge respellings on the curated words?
3. If respelling works for some words, is a mix of respelled Edge clips and Azure clips acceptable?
4. Once fixed, drop the audio caveat note from these verbs (visual stress marks stay)?

## Interim user alert

Until audio is fixed, the existing per-verb note stays. The proposed generalisation (a curated `core/audio_caveats.py` list reused by Hebrew, a "Hear a wrong sound? Tell us" link to `/feedback?page=audio&...`, link on flagged verbs only) is on hold until the Hebrew listening results are in.
