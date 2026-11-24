# VerbBoard marketing personas (source of truth)

This file is the source. `verbboard-personas.html` is a readable copy and is rebuilt from it at each review, never edited by hand. Process: `.claude/skills/persona-review/SKILL.md`.

Review cadence: every 3 weeks, opened automatically as a GitHub issue by Cloud Scheduler (#142). Last review: 2026-11-24. Next review: 2026-12-15.

## Claim statuses

- **assumed**: our own reasoning, or fewer than about 30 sessions behind it.
- **observed**: a named number backs it (Reports date range and n, or an issue/feedback item).
- **refuted**: data says no. Move the claim to Retired claims with what we learned.

Sessions are keyed by IP, browser and day, so they are not visitors. Referrer counts are lower bounds. Search terms are guesses until #117 (Search Console) is done.

## Dana, the stuck intermediate (web search)

32, phone-first, learning Spanish, Italian or French. Freezes when she has to conjugate aloud. Searches "conjugate hablar", "preterite vs imperfect"; lands on a verb page (/learn) with table, audio and examples, no login. Keeps because she hears the form in a sentence, stars it, returns for the Verb of the Day. Leaves if her verb is missing or a sign-in wall appears before value. Signal: verb pages per session, starred verbs, practice started.

| Claim | Status | Evidence | n | Last checked |
|---|---|---|---|---|
| Learners search "conjugate <verb>" and land on /learn | assumed | none until Search Console (#117) | 0 | 2026-11-24 |
| Titles phrased as learners search earn more clicks than #104 wording | assumed | #136 (blocked by #117) | 0 | 2026-11-24 |

Next test: #136

## Misha, learning English in his own language (community channel)

27, Russian or Hebrew speaker, Android, learning English for work. Found through local communities (Reddit first), plus "English irregular verbs", "past tense of go". Keeps because it feels built for him, with translations in his language. Leaves if translations are missing or the post reads like an ad. Signal: sessions with a reddit.com referrer, UI language selected, rate-link taps. No Google Play localization (owner decision 2026-11-23).

| Claim | Status | Evidence | n | Last checked |
|---|---|---|---|---|
| Local-community posts bring ru/he English learners | assumed | #135 (needs owner to post) | 0 | 2026-11-24 |
| Hebrew-speaking variant is big enough to keep the Hebrew UI | assumed | check around 2026-12-25 | 0 | 2026-11-24 |

Next test: #135

## Ana, the teacher who sends links (referral channel)

41, tutors Spanish and Portuguese online. Wants one clean page per verb to send a student. Lands on a verb page with a share button and a link preview. Keeps because the link opens instantly with no account. Leaves if the page is cluttered or the link breaks. Signal: share_tapped, share_landed, utm_source=share.

| Claim | Status | Evidence | n | Last checked |
|---|---|---|---|---|
| Teachers are the main users of the /learn share button | assumed | #137, check around 2026-12-19 | 0 | 2026-11-24 |
| Sharing drives growth (rule: under about 10 share_landed in 30 days means no) | assumed | #128, #137 | 0 | 2026-11-24 |

Next test: #137

## Leo, the deck builder (power user)

36, desktop, two or three languages, already uses Anki. Searches "verb list for anki". Lands on /verbs. Keeps because starring builds an importable CSV and sign-in syncs devices. Leaves if the catalog is thin in his language. Signal: signed-in share of sessions, 30-day return, export use.

| Claim | Status | Evidence | n | Last checked |
|---|---|---|---|---|
| The Anki export is a real draw for power users | assumed | #138 (no export_clicked flag yet, so no signal at all) | 0 | 2026-11-24 |
| First-time visitors never learn the export exists (it appears only after starring) | assumed | reasoning from the code | 0 | 2026-11-24 |

Next test: #138

## Rosa, 82, learning for pleasure (accessibility and family channel)

Retired, phone or tablet set up by a grandchild, easily put off by anything that looks like a test. Arrives mostly from a family share link. Keeps because she can listen as often as she likes with no score. Leaves if a sign-in appears or the page behaves unexpectedly. Age is not visible, so use all visitors as the measure. Owner decision 2026-11-23: skip the large-text check, make sign-in easier.

| Claim | Status | Evidence | n | Last checked |
|---|---|---|---|---|
| Sign-in is a wall for a first-time, non-technical visitor | assumed | 2026-11-23, 60 days, non-bot: 59 of 3,144 sessions tapped sign-in, 44 signed in; 8 of 26 who saw the practice gate did not sign in. Desktop popup 9 of 21 did not. Below 30 for the gate, and "not signed in" overstates failure | 26 | 2026-11-24 |
| Failed attempts end in a technical alert or silence | observed | code reading, fixed by #141 (shipped 2026-11-23) | n/a | 2026-11-24 |
| Failure reasons can be told apart | observed | #140 shipped 2026-11-23; read the Sign-in attempts card on /admin/reports after 2 to 3 weeks | n/a | 2026-11-24 |
| A second sign-in method (not Google only) would help | assumed | owner decision pending, #139 | 0 | 2026-11-24 |

Next test: #139 follow-up, read the Sign-in attempts card at the 2026-12-15 review.

## Retired claims

None yet. Format: claim, evidence, date, one line on what we learned.
