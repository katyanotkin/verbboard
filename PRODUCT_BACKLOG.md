# Product Backlog — User Feedback Triage

Living log of feature requests and UI feedback collected from users, triaged into actionable items. Append new sessions below rather than editing old ones.

---

## 2026-07-02 session

### 1. Translate verb infinitive — ✅ SHIPPED 2026-07-02
Same mechanism as example translations (`Example.translations` dict, Gemini/Claude routing per language — see `core/translation_service.py`). Currently only examples are translated; the infinitive/lemma itself is not.

- **Needs:** backfill script for existing verbs (analogous to the existing translation backfill tool)
- **Size:** small-medium — extends an existing pattern rather than introducing a new one
- **Shipped:** `translate_lemma()` in `core/translation_service.py`, `lemma_translations` field on `VerbEntry`/Firestore docs, wired into candidate generate/regenerate, rendered under the board title, toggled by the existing translations button. `tools/backfill_lemma_translations.py` backfilled all 384 pre-existing verbs across en/ru/he/es. Promoted to prod.
- **Hardening found in production use:** `anthropic.OverloadedError` doesn't exist in the installed SDK (0.96.0) — that error-handling branch was dead code that crashed with `AttributeError` on any Claude error, in both `translate_lemma` and the pre-existing `translate_examples`; fixed to check `APIStatusError.status_code == 529`. Also hardened the lemma-translation prompt/parsing against Claude prepending commentary or rambling instead of returning clean JSON (surfaced by two real verbs, `ru/засыпать` and `ru/значить`), and added an explicit rule for source-language conjugation-pattern ambiguity (e.g. English "fit" as fit-fit-fit vs fit-fitted-fitted) in both the lemma-translation prompt and the English verb-generation prompt in `core/settings_ai.py`.

### 2. Jump to example from a conjugation form (on demand) — ✅ SHIPPED 2026-07-02
From a specific form row in the conjugation table, let the user jump to/reveal the matching example, when one already exists.

- **Depends on:** existing form <-> example association (need to confirm current data model links a form to a specific example, or only to the verb as a whole)
- **Size:** small if the link already exists in data; medium if it requires new association data
- **Shipped:** `data-form` attribute + 🔎 button per conjugation row (`core/render.py`), client-side word-boundary-aware substring match against rendered example text (`app/static/learn.js`, Hebrew nikud and other diacritics stripped before matching), scroll+highlight on match, toast + demand-signal log via new `POST /api/learn/form_signal` (reuses `log_missing_verb_search()`) on no match. Promoted to prod.
- **Bug found post-deploy:** the service worker (`app/static/sw.js`) caches static assets cache-first under a fixed version string that wasn't bumped on first deploy, so returning visitors kept getting the pre-feature `learn.js` with no visible error ("no response" on click). Fixed by bumping `vb-v20` → `vb-v21`.

### 3. Generate example for a selected form on demand — PREMIUM
User selects a form with no example yet; app generates one via Claude/Gemini on demand and persists it (so it's not regenerated next time).

- **Depends on:** #2's form/example association model
- **Flagged by user as a premium feature** — implies a paywall/gating decision needs to be made (no premium tier exists yet in the codebase as far as known)
- **Size:** medium — new on-demand generation endpoint + storage write path

### 4. Timed (spaced) repetition — PREMIUM
Anki-style spaced repetition: a learned/practiced verb resurfaces after a few days (e.g. +3 days, +5 days) instead of being "done."

- **Flagged by user as a premium feature**
- **Size:** large — new scheduling data model (per-verb review due-date), a background/query mechanism to surface due verbs, and practice-loop integration. Distinct from the existing `user_practice` badge/session model.

### 5. UI feedback (raw, from a Russian-speaking user; translated below)

**Labels & controls:**
- The "Abandon" label feels too dramatic/tragic for the verb list action — wants a softer, less final-sounding label
- The "выучила" ("Learned"/"I learned it") button confused her — unclear what it does or when to press it

**Visual:**
- Dislikes the snail icon; wants something cuter/friendlier
- General sense the interface would be hard for her to use as-is; her instinct would be to hire a UX designer and redesign every screen while keeping functionality exactly as-is — she flagged this as her opinion, not a certainty

**New requests surfaced in the same feedback (Anki-inspired):**
- Spaced repetition (same underlying ask as #4 — she named Anki explicitly as the reference model)
- **Streaks:** show consecutive days practiced without a break
- **Known-word counter:** show total verbs known
- **Illustrative images per verb:** e.g. for "to drink," show an icon/image of a girl drinking water — meaning-linked art, not generic icons

**Tone of the feedback:** overall positive and encouraging ("you're an absolute giant" / "гигант"), explicit that functionality works and she doesn't want the critique to land as harsh — reads as a real, engaged user, not a complaint.

- **Size:** the label/icon fixes are trivial-to-small; "redesign every screen" is a large, open-ended ask that needs scoping before anything is built. Streaks and known-word counter are small-medium (data mostly exists via `user_practice`/progress collections, needs display work). Verb illustration images are a new content type — needs a sourcing/generation decision (stock icons vs. AI-generated vs. hand-picked) before sizing.

### 6. Design and implement a premium mechanism
Prerequisite for #3 and #4 above, which both assume a paid tier exists. Rough shape as described: a paid version of the app, hosted on a different URL, listed on Google Play as a separate/upgraded listing with a subscription at a higher price point (as opposed to in-app purchase gating within the existing free listing).

- **Open questions to settle before sizing:** separate deployment vs. single deployment with entitlement checks; separate Google Play listing vs. Play Billing subscription on the existing listing; how entitlement is checked server-side (Firestore user doc flag vs. Play Billing receipt validation vs. Stripe); whether free-tier data (progress, practice history) carries over to the paid experience if hosted separately
- **Size:** large — touches auth/entitlement, deployment/infra (Cloud Run + Firebase Hosting), Google Play Console listing/billing setup, and every premium-gated feature's access check
- **Blocks:** #3 (on-demand example generation), #4 (spaced repetition)

### 7. Carried-over engineering/architecture TODOs (from prior senior-architect reviews, not user-driven)

Not from this feedback session, but open in the codebase and relevant to sequencing below.

- **Admin password and JWT signing key share the same secret** — flagged, not fixed. Deliberately deferred to a dedicated infra pass (needs a Secret Manager change + redeploy, not just a code change).
- **Inline `style=` in admin JS template literals** (`admin_signals.js`, `admin_candidates.js`, `admin_live_verbs.js`, `admin.html`) — should be CSS classes (`.action-cell`, `.cell-meta`, `.hidden`). No behavior change, no tests needed, admin-only surface.
- **Consolidate JS link-building into server-rendered construction** — `verbs_filters.js`, `practice_loop.js`, `home.js`, `learn_practice.js`, `auth.js` each hand-append `language`/`ui_language`/`return_to` to hrefs. Real refactor across 5 files; biggest lever for e2e-test simplification but requires a full caller/invariant audit first.
- **Firestore fake/mock seam** — `session_tracker.py`, `admin_feedback_service.py`, `verb_repository.py` write paths have no unit coverage (no emulator/fake exists). Adds tests, doesn't reduce risk elsewhere.
- **DI container for monkeypatch drag in tests** — correctness/maintainability risk (silent false-green if a patched function moves modules). Not urgent.

**Also relevant:** the form-row "Examples" button from item #2 above already has a **fully settled, greenfield design** sitting in planning notes — `data-form` attribute on conjugation rows, DOM-only substring match against already-rendered example text, a thin new endpoint reusing existing signal-logging code, and an agent split (`senior-web-engineer` for render/endpoint, `ui-ux-engineer` for panel CSS). Nothing is committed yet, but the design work that usually adds risk to a "medium" item is already done — this re-rates #2 as closer to low risk than a typical net-new feature. One called-out risk to watch: Hebrew nikud must be stripped from both form text and example text before matching, or Hebrew never matches.

---

## Prioritization (impact vs. risk)

Impact = expected value to retention/learning outcomes/revenue. Risk = implementation risk: scope size, unknowns, and external dependencies (billing, Play Console, content sourcing).

| Item | Impact | Risk | Why |
|---|---|---|---|
| ~~Streaks (from #5)~~ | High | Low | Shipped 2026-07-08, see 2026-07-09 update below |
| Known-word counter (from #5) | Medium | Low | Motivational, data already tracked in progress collections; display-only work |
| Label/icon fixes: "Abandon" wording, "выучила" clarity, snail icon (from #5) | Medium | Low | Cheap, removes real confusion this user hit; no data model changes |
| #1 Translate verb infinitive | Medium | Low | Extends an existing, working pattern (`Example.translations`); backfill is a known quantity |
| #2 Jump to example from a form | Medium | Low-Med | Cheap if form->example association already exists; needs a quick data-model check first |
| Verb illustration images (from #5) | Medium | Medium | Real delight/memorability value, but new content type — needs an image-sourcing decision (stock/AI-gen/hand-picked) before it can be sized |
| #6 Premium mechanism | High | High | Blocks #3 and #4; touches billing, Play Console listing, entitlement architecture, and possibly a second deployment — largest unknowns in this batch |
| #4 Timed/spaced repetition | High | High | Highest-value ask in the raw feedback (named Anki explicitly, ties directly to retention/learning efficacy) but needs new scheduling data model + practice-loop integration; also currently gated behind #6 |
| #3 On-demand example generation per form | Medium-High | Medium | Real utility, but blocked by #6 as specified; per-call AI cost needs thought regardless of gating |
| "Redesign every screen" (from #5) | Unscoped | High | Not a backlog item as stated — it's a signal to commission a scoped UX audit, not something to size or sequence yet |

**Recommended sequencing:**

1. **Do now (high/med impact, low risk, no blockers):** known-word counter, label/icon fixes; ~~#1 (translate infinitive), #2 (jump to example)~~ — both shipped and promoted to prod 2026-07-02; ~~streaks~~ — shipped 2026-07-08, see status notes below
2. **Near-term, needs one small decision first:** verb illustration images — settle sourcing approach, then scope
3. **Big bets — scope before committing:** #6 (premium mechanism) is the real fork in the road here, since it gates both #3 and #4. Worth a short scoping spike (separate deployment vs. entitlement flag, Play Billing vs. Stripe) before estimating either downstream item. Consider whether #4 (spaced repetition) could ship as a free feature first, independent of #6 — the user's request for it doesn't inherently require a paywall, that framing came from the product side, not the feedback itself.
4. **Parked:** "redesign everything" — flag for a future scoped UX audit, not on this backlog as-is.

No premium/paywall mechanism currently exists in the codebase — #3 and #4 both assume one, which is why #6 sits ahead of them despite being newer.

**Combined lowest-risk queue (including carried-over engineering items from #7):** admin inline-`style=` cleanup is the single lowest-risk item in the whole backlog — no behavior change, no tests, one file surface, admin-only. Right behind it: the form-row Examples button (#2), since its design is already fully specced. Both can run ahead of anything premium/#6-dependent with no sequencing conflicts.

---

## 2026-07-09 update

### Item 5 (Streaks) -- SHIPPED 2026-07-08

Practice day-streak, from the 2026-07-02 session's "New requests" list and the prioritization table's top "Do now" item.

- **Shipped:** consecutive-day tracking on session completion, stored per-language in localStorage (`practice_streak:{lang}`) and mirrored server-side on `user_practice` (`streak_last_day`/`streak_len`). Merge logic (`core/progress/streak.py` + `app/static/streak.js`, kept in sync and covered by a Node/Python parity test) never shrinks a legitimate streak: same day keeps the max length, consecutive days extend, a gap of 2+ days lets the later day win. `POST /api/progress/practice` returns the server-merged streak so the wrap-up modal never under-counts on a lagging device. 🔥 chip renders in the verbs-page practice panel (LTR+RTL, hidden when the streak is dead); wrap-up modal shows the current streak. Localized label added to all four locales (`practice.streak`). 47 new tests. Manual QATP in `QATP_streak_manual.md`; core cases confirmed on stage incl. next-day increment.
- **Follow-up fix (2026-07-09):** mobile practice-bar layout -- Skip and Abandon shared one crowded row on narrow screens; reordered via CSS `flex`/`order` so Skip sits full-width directly under the counter and Abandon sits below Skip (user feedback from stage testing).

### New item: in-app "help" affordance design -- NEEDS DISCUSSION

Triggered by the streak chip: on touch devices its "Day streak" label is invisible (hover-tooltip only), so a mobile user tapping the chip gets nothing. A ui-ux review (2026-07-09) recommended against a "?" glyph (crowds the tightest header row in the app; no existing "?" idiom anywhere in the product) and instead proposed making the chip itself a link to the About page's streak paragraph (span -> anchor, `/about?ui_language=...#about-streaks`, enlarged tap target, focus ring, zero visual change). Full spec is preserved in that review; anchor ids on the About paragraphs are the only template change needed.

Decision deliberately deferred: instead of a one-off fix for the chip, design help/discoverability as ONE consistent pattern across product spots that currently explain themselves poorly, e.g.:

- Streak chip 🔥 (what does the number mean, how do I keep it)
- The "learned/выучила" star button (already flagged as confusing in the 2026-07-02 user feedback, item 5)
- Practice panel controls (session size pills, listens-per-verb stepper)
- Jump-to-example 🔎 button on conjugation rows
- Translation toggle button

**To settle in discussion (PM + ui-ux):** which spots get an affordance at all; one idiom for all of them (tappable element itself vs. dedicated hint style vs. first-run hints); whether the target is the About page (deep-linked anchors) or inline micro-explanations; how it stays out of the way for returning users (stateless/frictionless principle).

- **Size:** design discussion first (small); implementation per-spot is trivial-to-small once the idiom is chosen
- **Blocks:** nothing; the streak chip stays as-is (title + screen-reader label) until decided

---

## 2026-07-10 session -- backlog review + new proposals

### A. Status audit of everything currently open

**Shipped and closed (no action):** translate infinitive (#1), jump-to-example (#2), streaks, admin inline-style cleanup, all architect MEDIUM items.

**Still open, carried forward:**

| Item | Origin | Status |
|---|---|---|
| Google Play submission, steps 5.1-5.8 | `GOOGLE_PLAY_CHECKLIST.md` (supersedes `instructions.txt`) | The single biggest open product thread. **Timeline changed 2026-07-23**: Google now requires a closed test with >=12 opted-in testers for 14 continuous days before production access unlocks (new personal-account policy, confirmed live in Play Console; https://support.google.com/googleplay/android-developer/answer/14151465) -- this is a hard minimum-14-day wait baked into the middle of the sequence (checklist step 5.6b), not a same-week launch. Recruiting testers is the human-side long pole. All remaining steps are human-side Play Console work except 5.5 (assetlinks fingerprint update, done in-session once the SHA-256 is pasted). Everything code-side is done and verified. |
| Known-word counter | 2026-07-02 #5 | Top of the "Do now" tier since 2026-07-02, still unbuilt. Data already tracked; display-only work. |
| Label/icon fixes (Abandon wording, learned-star clarity, snail icon) | 2026-07-02 #5 | Unbuilt. Cheap; the learned-star confusion also feeds the help-affordance discussion below. |
| In-app help affordance (one idiom across streak chip, learned star, practice controls, 🔎, translation toggle) | 2026-07-09 | Awaiting PM + ui-ux discussion. Design-first, implementation trivial per spot. |
| Verb illustration images | 2026-07-02 #5 | Blocked on a sourcing decision (stock vs AI-gen vs hand-picked). |
| #6 Premium mechanism | 2026-07-02 | Unscoped. Note a new wrinkle: the Play listing is planned as Paid $0.99 (`instructions.txt` 5.2), which partially answers "how do users pay" for the app itself but not per-feature entitlement. |
| #3 On-demand example generation | 2026-07-02 | Blocked on #6. Dependency on form/example association is now satisfied by shipped #2. |
| #4 Spaced repetition | 2026-07-02 | Blocked on #6 only by product framing; technically independent. Still the highest-value learning-outcome ask on the books. |
| "Redesign every screen" | 2026-07-02 #5 | Parked; future scoped UX audit. |
| Engineering: admin/JWT secret split; JS link-building consolidation; Firestore fake seam; DI container | architect reviews | All deliberately deferred; none urgent. The secret split should ride along with the next infra/deploy pass rather than get its own. |

**Consistency note:** the draft Play listing copy promises "no gamification pressure" while the product now has streaks and badges and this backlog leans further that way (counters, spaced repetition). Not a blocker, but the listing copy or the framing of future gamified features should be reconciled before 5.4.

### B. New feature proposals (2026-07-10)

Impact = retention/learning outcomes/revenue/reach. Risk = scope, unknowns, external dependencies.

| # | Proposal | Impact | Risk | Rationale |
|---|---|---|---|---|
| N1 | **Verb of the day** on home page: one featured verb per day per language, deep-link to /learn | Medium-High | Low | Creates a daily reason to open the app; pairs directly with the streak mechanic. Pure display work over existing data; deterministic pick (date-hash over verb list) needs no new storage. |
| N2 | **Streak grace / freeze**: one missed day does not kill the streak (or: 1 freeze earned per N completed sessions) | Medium | Low | Streak loss is the #1 churn moment in every streak product; merge logic is already centralized in `streak.js`/`streak.py` with parity tests, so the change is contained. Decide the rule before touching code. |
| N3 | **Weak-forms insight**: surface which conjugation forms the user replays most / jump-to-example misses, as a personal "focus on these" hint | Medium | Medium | First feature to close the loop on data already collected (audio plays, `form_signal` demand). Needs a per-user aggregation decision (client-side localStorage counts vs server), so scope before building. |
| N4 | **Anki/CSV export of known verbs** | Medium | Low | The power user who drove the 2026-07-02 feedback named Anki explicitly. Cheap goodwill for the exact audience most likely to churn to Anki; also a natural premium-tier candidate later. Client-side generation, no new backend. |
| N5 | **Fifth language (e.g. FR or DE)** | High | Medium | Plugin architecture, AI generation pipeline, TTS, and translation routing all exist; marginal cost of a language is prompt tuning + voice selection + content QA. Biggest lever for Play Store reach. Real risk is content quality review bandwidth, not code. |
| N6 | **Practice reminder via web push** (PWA/TWA notification when streak is about to lapse) | High | High | Strongest retention lever after spaced repetition, but web push is new infra (subscription storage, a send mechanism, permission UX) and intersects the stateless/frictionless principle. Scope only after Play launch proves an installed-app audience exists. |
| N7 | **Post-practice rating prompt**: after the Nth completed session in the TWA, trigger the Play in-app review API | Medium | Low-Med | Store rating velocity matters most in the first weeks after launch; the trigger point (session completion) already exists. Only meaningful once the app is live on Play, and needs a "never nag twice" guard. |
| N8 | **Nightly auto-generation of candidates from top demand signals** (admin efficiency, not user-facing) | Medium | Medium | Turns the demand pipeline from pull to push: top-N unresolved signals become draft candidates awaiting review. Human review/promote step stays. Needs a scheduled job (Cloud Scheduler) and cost guardrails on AI spend. |

### C. Recommended priority (combined queue)

**P0, mostly human-side, now spans >=2 weeks not "this week":** finish Google Play submission (5.1-5.8). The 14-day closed-testing gate (step 5.6b, new as of 2026-07-23) means the earliest possible production submission is ~2 weeks out even with testers recruited immediately -- recruiting >=12 opted-in testers is the critical-path task, start it as soon as internal testing (5.3) and store setup (5.4/5.6) are done. Everything else in this backlog compounds only after the app is discoverable. Reconcile the "no gamification pressure" listing copy at step 5.4. Code-side involvement: fingerprint swap at 5.5.

**P1, quick wins, no blockers, do in any order alongside P0:**
1. Known-word counter (oldest unshipped "Do now" item, trivially small)
2. Label/icon fixes from user feedback
3. N1 Verb of the day
4. N2 Streak grace (settle the rule first, one-line design decision)
5. N4 Anki/CSV export

**P2, needs one decision each, then small-medium:**
1. Help-affordance idiom (PM + ui-ux discussion already queued; fold the learned-star confusion into it)
2. Verb illustration sourcing decision
3. N7 rating prompt (after Play approval)
4. N3 weak-forms insight (decide client vs server aggregation)

**P3, big bets, scope before committing:**
1. **Spaced repetition (#4), recommended as the next big bet, and recommended free.** It is the strongest learning-outcome feature requested, and unbundling it from premium removes its only blocker. Premium can later gate depth (custom intervals, per-form scheduling) rather than the feature itself.
2. N5 fifth language, high reach, mostly content risk
3. #6 premium mechanism scoping spike, sharpened by the paid-listing decision: is the $0.99 Play price the monetization, or is there a subscription tier on top? Answer determines whether #3/#6 stay coupled.
4. N6 push reminders, revisit once Play install numbers exist
5. N8 nightly auto-candidates, whenever admin review time becomes the bottleneck

**Engineering hygiene track (background, not user-visible):** JS link-building consolidation remains the biggest test-simplification lever and should be its own deliberate project; admin/JWT secret split rides with the next infra pass; Firestore fake seam and DI container stay parked.

---

## 2026-07-12 session -- premium mechanism (#6) DEFINED

Product owner decision. Supersedes the open questions in the 2026-07-02 #6 entry and the "premium scoping spike" in the 2026-07-10 P3 list.

### The definition

> **Naming/domain update, later on 2026-07-12:** the premium edition deploys at **plus.verbboard.com** -- the same Docker image as the free app, with premium config. "Ver2" below is the earlier working name for what is now the **Plus** edition; read them as the same thing.

Premium = **VerbBoard ver2**, a second version of the same app:

- **Ver2 features at launch:** on-demand example generation (#3); Italian and French as study languages (in addition to the existing four); UI languages EN / RU / HE / ES
- **Ver1 change:** remove **Hebrew from the UI language options** (Hebrew stays as a study language; only the interface localization is withdrawn)
- **Ongoing policy:** new features go to ver2 from now on; ver1 is effectively feature-frozen except fixes
- **Pricing:** ver2 priced higher than ver1 (ver1 planned at $0.99 per `instructions.txt` 5.2)

### What this resolves from #6's open questions

- Separate deployment + separate Google Play listing: **confirmed** (matches the original rough shape)
- Entitlement mechanism: **owning the ver2 app is the entitlement.** No server-side per-feature entitlement checks, no Play Billing receipt validation, no Stripe. This deletes the hardest part of the old #6 scope.
- #3 (on-demand example generation) is now unblocked as a ver2 launch feature
- #4 (spaced repetition) and all other future features (N1-N8 above where still open) now target **ver2** by policy

### Still open (decisions needed before ver2 build starts)

1. **Exact pricing model:** higher one-time price vs subscription. Affects nothing in code if one-time; subscription would reintroduce Play Billing complexity that this definition otherwise avoids. Recommend one-time to keep the "owning the app = entitlement" simplicity.
2. **Codebase strategy: SETTLED 2026-07-12** (owner constraint: code must never diverge; concern that separate hosting forces a separate stage). Resolution:
   - **One repo, one Docker image.** Both editions deploy the *same image digest* from the same `git push`. Ver1 vs ver2 is env config only (feature flags, study-language list, UI-language list, manifest app name). Divergence is structurally impossible; editions can differ only in declarative config.
   - **No second stage.** Ver2 is a strict superset, so the single existing stage runs in ver2 config and exercises all code paths. Ver1-mode behavior ("flag actually hides X") is covered by env-var-driven tests at the unit/TestClient layer. Occasional ver1 eyeballing on real infra = temporarily flip one env var on stage.
   - **Deploy matrix: 3 targets** (stage, prod-v1, prod-v2), one build, one test suite, one SW cache version discipline.
   - **Rejected alternative:** one prod service switching edition by Host header. It avoids the second service but breaks the frozen `load_settings()` startup pattern (edition would become per-request state threaded through routes/templates) and the 60s verb cache would need per-edition keys or Hebrew UI could leak between editions. Cheap declarative infra duplication beats a cross-cutting request-scoped refactor.
   - **Acknowledged, accepted:** a separate URL does not technically gate access (plus.verbboard.com is browsable without paying; the paid Play listing gates only the Android shell). This is the same soft-enforcement model ver1 already uses with its $0.99 listing + public site -- consistent, but a conscious choice.
   - **Hostname: SETTLED 2026-07-12 -- `plus.verbboard.com`.** Subdomain of the existing domain; concrete deployment consequences to carry into the Plus infra work item:
     1. **Firebase Auth:** add `plus.verbboard.com` to the Firebase project's authorized domains, and mint a per-edition web-config secret (pattern already exists: `verbboard-firebase-web-config` / `-stage`; add a `-plus` variant with `authDomain: "plus.verbboard.com"`).
     2. **Hosting/routing:** a Firebase Hosting site (or Cloud Run domain mapping) for `plus.verbboard.com` pointing at the Plus Cloud Run service; DNS is one CNAME on the existing zone.
     3. **Play/TWA:** the Plus Android listing needs its own package name, so `/.well-known/assetlinks.json` served at `plus.verbboard.com` must carry the Plus app's fingerprint (env-driven, same `well_known.py` code path).
3. **Progress data carryover:** if ver2 shares the same Firebase project/Firestore, a user's progress follows their Google account into ver2 automatically (`user_progress`/`user_practice` are keyed by uid, not by app). Recommend same project: carryover becomes an upgrade selling point for free.
4. **Timing of the ver1 Hebrew-UI removal:** at ver2 launch (Hebrew UI becomes an upgrade driver, current Hebrew-UI users lose nothing until an alternative exists) vs now. Needs an explicit call; see risk table.

### New work items with risk/impact

| Item | Impact | Risk | Notes |
|---|---|---|---|
| Ver2 infra: second prod Cloud Run service (same image) + hosting site + Play listing ($ higher) | High (unlocks revenue) | Low-Medium | Same image digest deployed twice from one push; no second stage (shared stage runs ver2 config); Play listing process will already have been exercised by ver1 launch |
| Italian + French language plugins | High | Medium | Plugin architecture, AI generation, TTS, translation routing all generalize; risk is content QA bandwidth per language, not code (same assessment as N5, which this supersedes) |
| On-demand example generation (#3) | Medium-High | Medium | Now unblocked; per-call AI cost still needs a guardrail (rate limit per user/day) even without entitlement checks |
| Env-driven feature/language config (prerequisite for single-repo strategy) | Medium (enabler) | Low-Medium | Extends `load_settings()`; needs the [[feedback_state_propagation_audit]] treatment for the UI-language list since `ui_language` travels through every link |
| Ver1 Hebrew-UI removal | Low | Low code / **Medium product if done early** | Small change (drop `he` from the UI-language selector; keep the locale file for ver2). If done before ver2 exists, current Hebrew-UI users lose it with nothing to buy; recommend bundling with ver2 launch |

### Priority impact

- 2026-07-10 **P3.1 (spaced repetition free)** is overruled: it targets ver2, per the new-features-go-to-ver2 policy.
- 2026-07-10 **P3.2 (N5 fifth language)** is superseded: ver2 ships Italian AND French.
- 2026-07-10 **P3.3 (premium scoping spike)** is done; this session is its output.
- **P0 is unchanged:** ver1 Play submission still comes first; it exercises the exact Play Console path ver2 will reuse and establishes the free-tier funnel.
- **New P3 head item: ver2 build**, in order: (a) settle the four open decisions above, (b) env-driven config, (c) IT/FR plugins + content, (d) on-demand generation, (e) second deployment + listing, (f) ver1 Hebrew-UI removal at ver2 launch.

### Plus edition -- implementation checklist (recorded 2026-07-12 for future implementation)

Consolidated from the decisions above. Not started; execute in this order when the Plus build begins (after ver1 Play launch).

1. **Env-driven edition config** (code, prerequisite for everything else)
   - Extend `load_settings()` with edition-controlled fields: feature flags (on-demand example generation), study-language list, app/manifest name, assetlinks fingerprint
   - UI-language list is NOT edition config -- identical EN/RU/HE/ES in both editions (2026-07-15 ruling); free edition config = exactly today's behavior
   - Tests: unit/TestClient coverage for both edition configs via env vars; no new stage
2. **Italian + French language plugins** (`core/languages/it`, `core/languages/fr`)
   - Plugin + prompts in `settings_ai.py` + TTS voices in `tts.py` + translation routing; content generation + QA per language is the real effort
3. **On-demand example generation** (premium flag)
   - New endpoint: user picks a form with no example -> generate via existing AI pipeline -> persist to the verb doc (never regenerated)
   - Rate-limit per user/day as the AI-cost guardrail; no entitlement check needed (edition flag gates it)
4. **GCP/Firebase infra for plus.verbboard.com**
   - Secret `verbboard-firebase-web-config-plus` (authDomain `plus.verbboard.com`); add domain to Firebase authorized domains
   - Second prod Cloud Run service deploying the **same image digest** in the same push (extend cloudbuild); Hosting site or domain mapping + DNS CNAME
   - Same Firebase project/Firestore: progress carries over by uid (upgrade selling point)
5. **Play listing for Plus** -- lessons from the base-app launch (2026-07-23/24), to go faster this time:
   - Own package name; PWABuilder against the Plus host; higher price (one-time recommended; subscription would reintroduce Play Billing)
   - Plus fingerprint served in assetlinks.json at the plus host (env-driven `well_known.py`)
   - **Likely one-time per developer account, not per app:** the 12-tester/14-day closed-testing gate for new personal accounts unlocks "production access" at the *account* level (Play Console's "Apply for production access" lives on the account Dashboard, not per-app). If so, Plus -- published from the same account that already cleared this gate -- should skip straight to a normal review timeline (hours-to-days) with no multi-week wait. **Confirm this against the Play Console UI when Plus launch starts** before assuming it's skippable.
   - **PWABuilder's "Package ID" field silently defaults** to `com.<name>.twa`, not whatever you decided -- it does NOT read from the site's manifest `id` or anything else. Always explicitly overwrite that exact field before generating, and verify the real result by inspecting the compiled `AndroidManifest.xml` inside the generated AAB directly (`unzip -p file.aab base/manifest/AndroidManifest.xml | strings | grep <package>`) -- don't trust the bundled `assetlinks.json` or the form alone as proof.
   - **Binary secrets in GCP Secret Manager must be read back with `gcloud secrets versions access ... --out-file=PATH`**, never a shell pipe/redirect -- stdout text-mode encoding silently corrupts non-UTF-8 bytes (keystore files). Verify with a SHA-256 comparison against the source before trusting any backup.
   - Closed Testing requires the app "finished set up" (store listing + content declarations) first; Internal Testing has zero requirements and is the right first upload target (also what triggers Play App Signing / the real fingerprint).
   - The manifest/PWA enrichment work (categories, shortcuts, `display_override`, `dir`, `related_applications`, `launch_handler`, offline fallback page) lives in the shared codebase, so Plus inherits all of it automatically -- nothing to redo there.
   - `.gitignore` already blocks keystore/AAB/APK/`key.properties` from ever being committed -- inherited automatically, but generate Plus's keystore backup into GCP Secret Manager under its own secret names (don't reuse `verbboard-play-signing-*`).
   - New for Plus, not yet encountered: **paid listing requires a Google Payments merchant account** -- set that up as its own step, not covered by anything done for the free base app.
6. **Stage runs Plus config** from step 1 onward (superset; covers both editions' code paths)
7. ~~At Plus launch: remove Hebrew from the free edition's UI-language options~~ -- **dropped 2026-07-15**: Hebrew UI stays in the free edition (see addendum)

Standing rules: one repo, one image; editions differ only in env config; new user-visible features default to Plus.

### 2026-07-12 addendum -- Hebrew stays a FREE study language (DECIDED)

Owner considered removing Hebrew as a *study* language from the free edition on cost grounds (Hebrew is the most expensive language to generate: Sonnet with max_tokens=4096 vs 2048, and Claude instead of Gemini for example/lemma translations). Decision: **keep Hebrew as a free study language.**

Reasoning, for the record:
- The cost rationale did not survive scrutiny. Generation cost is one-time per verb (roughly 2x a Russian/Spanish verb, i.e. cents), amortized across all users of both editions forever, and spent only when the owner acts on a demand signal in the admin flow -- there is no per-user or auto-triggered AI spend for free Hebrew learners.
- Hebrew is the most differentiated study language (thin competition for Hebrew conjugation + audio -> likely the strongest acquisition keyword for the free listing), and the owner has a known warm audience interested in Hebrew -- exactly the early installs/reviews a new free listing needs.
- Deciding principle, stated by owner: **engagement is more important than money.**

Consequences:
- The free edition's study languages remain EN / RU / HE / ES; the Play listing copy "Supports Spanish, Russian, Hebrew, and English" stays true.
- Unchanged from the main ruling: Hebrew *UI localization* still moves to Plus at Plus launch (checklist step 7).
- **Fallback kept in reserve (not scheduled):** if Hebrew generation spend ever becomes uncomfortable, "freeze, don't remove" -- free keeps the existing Hebrew catalog, new Hebrew verbs generate into Plus only (per-edition content gate; reversible). Nothing decided today forecloses this.

### 2026-07-12 addendum -- pricing DECIDED + Plus hostname handling

**Base app pricing: launch Paid at $0.99, flip to Free later.** Owner decision, superseding the discussed launch-free option. Rationale:
- (a) **Practice all the motions:** a paid listing exercises the Google merchant account + paid-app Console flow end to end -- exactly the machinery the Plus listing ($1.99) will reuse.
- (b) **PR beat:** the later "VerbBoard is now free" flip is an announcement in its own right. Suggested (not decided) timing: pair the free-flip with the Plus launch for a combined story ("base now free, Plus available").
- Play mechanics that make this safe: paid-to-free is allowed (the reverse is not); early $0.99 buyers simply keep the app after the flip, no refund handling.
- `instructions.txt` step 5.2 (Paid / $0.99) is therefore **correct as written** -- do not change it.

**Plus pricing: $1.99 at launch.** Can be raised for new buyers later; the on-record recommendation to consider $2.99-$4.99 (or treat $1.99 as an introductory price) stands as a future option, not a blocker.

**Plus hostname: stored in GCP Secret Manager, not committed to the repo.** Owner decision ("plusxxx"-style secret) to avoid accidental free distribution of the Plus URL. Consequences:
- Earlier references to `plus.verbboard.com` in this session should be read as "the Plus hostname (from GSM)"; the literal subdomain is not fixed in this document or in code.
- Checklist step 4 gains a hostname secret alongside the `-plus` Firebase web-config secret; authorized-domain, hosting/DNS, and assetlinks steps all consume the GSM value.
- Honest scope, accepted: this prevents *accidental/casual* discovery. TLS certificate-transparency logs and the Plus Android package metadata can still reveal the hostname to a determined user -- consistent with the already-accepted soft-enforcement model.

### 2026-07-15 addendum -- base app launches FREE (supersedes the $0.99-then-flip decision)

Owner decision after further consideration: the base app (everything shipped as of today, Hebrew study included) launches on Google Play as **Free** from day one. This supersedes the 2026-07-12 "launch Paid $0.99, flip Free later" ruling.

- Forfeited, knowingly: the paid-listing practice run (the merchant-account and paid-app motions now get exercised for the first time at Plus launch) and the "VerbBoard is now free" PR beat.
- One-way door, now taken for real: a free listing can never become paid. Accepted; monetization lives entirely in Plus.
- `GOOGLE_PLAY_CHECKLIST.md` step 5.2 updated to Free; the post-launch "price flip" item removed.
- Plus pricing unchanged: $1.99 at launch, raise-later option open.

**Same day, second ruling: Hebrew UI STAYS in the free edition.** Supersedes the 2026-07-12 "Hebrew UI moves to Plus at Plus launch" ruling ("doesn't really matter" -- differentiation value judged marginal). Consequences:
- UI languages are identical in both editions: EN / RU / HE / ES.
- Plus implementation checklist step 7 (free-edition Hebrew-UI removal at Plus launch) is **dropped**; step 1 gets simpler -- the UI-language list no longer needs to be edition-config, and the `ui_language` state-propagation audit for removal is no longer needed.

**Same day, confirmation of the edition split:**
- The free edition releases **exactly as it is today** -- nothing added, nothing removed (Hebrew study stays, Hebrew UI stays, all current features stay). Nothing currently shipped is ever taken away; the app is free.
- Plus at launch = the free app + **Italian and French study languages + on-demand example generation** (launch scope unchanged from the 2026-07-12 definition).
- P1/P2 quick wins from 2026-07-10 remain valid but should be re-read against the ver2 policy: anything user-visible and new belongs in ver2; ver1 keeps fixes and already-promised items (known-word counter and label fixes predate the policy; owner may choose to grandfather them into ver1 or move them).

### 2026-07-23 addendum -- Web Push flagged as a future Plus feature candidate (not launch scope)

Raised during Google Play submission prep (PWABuilder report-card review). Owner wants this kept in mind for Plus, not built now.

- **Not in Plus launch scope** -- Plus at launch stays as defined above (Italian/French + on-demand examples). Push is a candidate for *after* Plus launch, not part of it.
- Natural trigger would be streak-reminder nudges ("your streak is about to break"), which directly collides with the unreconciled "no gamification pressure" line in the free app's store listing copy (flagged 2026-07-10, still open) -- if push moves forward, that copy tension needs resolving first, and the free/Plus copy split may need to diverge (free stays low-pressure, Plus opts into push).
- Real implementation cost when it's picked up: VAPID keys, a push-subscription store (Firestore, per-uid), a server-side trigger to decide when to send (streak-expiry check), and a permission-prompt UX -- not a manifest-only change.

---

## 2026-07-27 session -- small UI fix + flagged issue

### Correction: "Known-word counter" (2026-07-02 #5) was already shipped -- not a real backlog item

Turns out this has existed since 2026-05-18 (commit touching `progress-star`), predating the 2026-07-02 session that (re-)requested it -- an oversight in that session, never caught until re-scoping it today. The verbs page already shows known-count / total via a live progress bar: `.progress-star ★` + `.progress-count` / `.progress-total` + `.progress-fill` in `app/templates/verbs.html` (`.vb-progress-static` block, ~line 148-160), kept live by `app/static/verbs_filters.js`'s `updateProgress` (wired from `app/static/verbs_page.js`). No work needed. Removed from the "P1 quick wins" queue; every prioritization table above that still lists it as open/unbuilt is stale on this one point.

### Feedback page poll question spacing -- SHIPPED 2026-07-27
`.question-title` (the poll question, e.g. "What would you like to see next?") had zero CSS anywhere, so it sat flush against the answer pills below it. Fixed in `app/static/feedback.css`: `margin-bottom: 10px`, `font-weight: 600`, `font-size: 0.94rem`, `color: var(--text-body)` -- matches the label-above-pills spacing/weight convention used elsewhere (`.search-row-header` in `common.css`). Verified via Playwright screenshot at desktop + 375px mobile, LTR and Hebrew RTL.

### Feedback page mobile header crowding -- SHIPPED 2026-07-27
At 375px, the "Feedback" `<h1>` heading crowded the "Back" pill in `.topbar-nav` on `/feedback`. Root cause: feedback.html inverts the shared `.topbar-nav` pattern (heading on the left instead of a compact Back pill), and `.topbar-nav`'s `justify-content: space-between` had no `gap`/wrap to absorb overflow -- in ES this wasn't just crowding, it pushed the "Iniciar sesión" login pill off the right edge of the viewport entirely.

Fixed scoped to `app/static/feedback.css` (`.card-nav` rule, which only applies where `.topbar-nav` + `.card-nav` co-occur, i.e. feedback.html only): `flex-wrap: wrap` + `row-gap`/`column-gap` on `.card-nav`, `flex: 1 1 auto; min-width: 0` on the `h1` so it can shrink/wrap, `flex-shrink: 0` on `.topbar-nav-right` so Back/Login are never compressed off-screen again. `common.css` and `feedback.html` untouched -- `.topbar-nav` is shared by verbs/board/home and those pages' content is already compact on both sides, so the fix was deliberately scoped rather than changing the shared component. Verified via Playwright at 375px across EN/RU/ES/HE (RTL), plus regression-checked `/verbs`, `/`, `/learn` at 375px for pixel-identical output (no shared-component impact).

### New proposal: guaranteed repetition quota for seen-but-not-known verbs

Practice session pool selection (`buildPool()` in `app/static/practice_loop.js`) currently pulls all non-known verbs (seen and never-seen mixed together undifferentiated), shuffles, and slices to session size (`startPractice()`). There's no guarantee a session actually re-surfaces verbs the user has already been exposed to but hasn't marked known -- a session could easily be 100% brand-new verbs, or 100% previously-seen ones, purely by chance.

Proposal: reserve ~25-30% of each session's slots for the seen-but-not-known subset (`seen()` minus `known()`, both already-existing localStorage sets -- see `progress.js`), filling the remainder from the rest of the non-known pool as today.

- **Depends on:** nothing new -- `seen()`/`known()` sets already exist client-side (`storage.readSet`); this is a sampling-ratio change inside the existing pool-building logic, not a new data model
- **Size:** small -- contained to `buildPool()`/`startPractice()` in one file; no server or storage-schema change
- **Risk:** Low -- purely client-side session composition; existing pool/shuffle mechanism is reused, just partitioned before the shuffle
- **Impact:** Medium-High -- a light-weight repetition lever for retention ahead of full spaced repetition (#4, which is scoped to Plus); directly answers the "seen it once, never came back to it" gap without new infra
- **Open question before building:** exact quota (25% vs 30%, fixed vs range) and behavior when the seen-but-not-known pool is smaller than the quota (pad from elsewhere, same pattern `buildPool()` already uses for the known-verb padding case)

#### Implementation scope (2026-07-27)

Confirmed by re-reading `buildPool()`/`startPractice()`: `startPractice()` re-shuffles and slices whatever `buildPool()` returns down to `activePracticeSize` (`const shuffled = [...pool].sort(random); picked = shuffled.slice(0, size)`). That means a naive fix -- e.g. just concatenating a "reserved" quota into the pool array `buildPool()` returns today -- would NOT actually guarantee the quota survives: `startPractice()`'s own reshuffle+slice would still pick the final `size` items uniformly at random from the whole (typically much larger) pool, silently defeating the guarantee.

**The actual fix has to make `buildPool()` selection-complete** -- i.e. when the quota path applies, it must return exactly `size` verbs already, not an oversized pool for `startPractice()` to sample from. Once `buildPool()` returns exactly `size` items, `startPractice()`'s existing reshuffle+slice(0, size) becomes a harmless no-op on the selection (still useful for randomizing display order) -- so `startPractice()` needs zero changes. All the work is inside `buildPool()`.

```js
// PracticeSessionSize is 3/6/9 only (core/progress/models.py PracticeSessionSize) --
// a lookup table lands closer to the 25-30% target than a generic round(size * ratio)
// (round() pushes all three sizes to ~33%; table below: 1/3=33%, 2/6=33%, 2/9=22%,
// tune to taste -- open decision, not settled here).
const REPEAT_QUOTA = { 3: 1, 6: 2, 9: 2 };

function shuffle(arr) {
  return [...arr].sort(function () { return Math.random() - 0.5; }); // matches startPractice's existing pattern
}

function buildPool(size) {
  const knownSet = known();
  const nonKnown = verbs.filter(v => !knownSet.has(v.id));

  if (nonKnown.length < size) {
    // Unchanged: not enough non-known verbs -- pad with known ones.
    const knownVerbs = verbs.filter(v => knownSet.has(v.id));
    return [...nonKnown, ...knownVerbs];
  }

  const seenSet = seen();
  const seenNotKnown = nonKnown.filter(v => seenSet.has(v.id));
  const quota = Math.min(seenNotKnown.length, REPEAT_QUOTA[size] || 0);

  if (quota === 0) {
    // Unchanged: no seen-not-known verbs to reserve, or size not in the table.
    return nonKnown;
  }

  const reserved = shuffle(seenNotKnown).slice(0, quota);
  const reservedIds = new Set(reserved.map(v => v.id));
  const rest = shuffle(nonKnown.filter(v => !reservedIds.has(v.id))).slice(0, size - quota);

  return [...reserved, ...rest]; // exactly `size` long -- startPractice's reshuffle+slice is now a no-op on selection
}
```

- **Unaffected by this change:** the `nonKnown.length < size` pad-with-known branch, `needsMixIn()`'s "Start (includes known)" warning label, and every other size/quota=0 fallback -- all identical to current behavior, so no regression risk there.
- **Test plan:** `buildPool()` is currently untested (no unit test file for `practice_loop.js` pool logic). Given the quota-selection logic is now a small pure function of `(verbs, knownSet, seenSet, size)`, consider extracting it so it can run through the same Node-harness pattern already used for `tests/test_streak_merge.py` (single subprocess, no browser) rather than requiring a full Playwright e2e test just to check a sampling ratio -- cases: quota fully satisfiable, quota larger than available seen-not-known pool (degrades to `Math.min`), quota=0 (empty seen-not-known pool), pad-with-known branch untouched.
- **Still open before implementing:** confirm the `REPEAT_QUOTA` table values (1/2/2 above is a starting guess, not decided) and whether this ships free-tier or also gets swept into the Plus-only framing now applied to spaced repetition/streak-grace (see below) -- unlike streak-grace, this one has no existing free-tier behavior to protect, so there's no urgency forcing that call the way there was for streak-grace.

### Streak grace/freeze (N2) -- rule DECIDED, scope moved to Plus, ✅ SHIPPED 2026-07-27

Rule decided: **one free miss per streak** -- a single missed day never breaks the current streak (no matter how long it's been running); the grace resets (becomes available again) only when the streak itself resets to length 1. Simpler than a redeemable "freeze balance" (N2's original alternate framing); no separate resource to display or manage.

**Scope: Plus-only, not free tier** (owner call, 2026-07-27) -- superseded the earlier framing of this as a plain P1 free-tier quick win.

**Update: shipped later the same day, commit `1797077`** ("Add streak grace/freeze (N2): one free miss per streak, Plus-gated"), once the env-driven edition config item below landed and unblocked it. Gated by `Settings.streak_grace_enabled`, strict no-op with the flag off, JS/Python parity maintained per the existing `streak.js`/`streak.py` convention. The paragraphs below describe the pre-implementation blocker and data-path audit -- preserved for history, no longer the current state.

**~~Not implemented this session.~~ Was** blocked on a real prerequisite gap: no edition/feature-flag config exists anywhere in the codebase yet -- the "env-driven edition config" item in the Plus checklist (2026-07-12 session) is explicitly step 1, not started. Rather than invent a one-off flag shape for this single feature (which would likely mismatch whatever the real edition-config system ends up looking like), the owner chose to hold off entirely until Plus edition-config work actually starts.

**Data-path audit already done (2026-07-27), preserved here so re-scoping is cheap when Plus work begins:**
- `StreakRecord` needs a third field, `grace_used: bool`, alongside existing `last_day`/`len`
- Server-side files touched: `core/progress/streak.py` (`merge_streak` gap-of-2 branch), `core/progress/progress_repository.py` (`_read_streak`, `save_practice_progress`), `core/progress/progress_service.py` (`record_practice_progress` param passthrough), `core/progress/models.py` (`PracticeProgress.streak_grace_used`), `app/routes/api_progress.py` (`PracticeProgressRequest` field, GET/POST streak dict shape)
- Client-side files touched: `app/static/streak.js` (`bump`/`merge`/`displayLen`, plus a new `daysBetween` helper generalizing the existing `isNextDay`), `app/static/learn_practice.js` (POST body + serverStreak construction around line 222-260), `app/static/practice_loop.js` (`savePracticeBadgesToServer`/`syncPracticeBadgesFromServer` around line 108-193)
- Test file: `tests/test_streak_merge.py` -- the JS/Python parity harness and its `_py_bump`/`_py_display_len` mirror functions need the grace branch added in lockstep with the real implementations, plus new dedicated grace-path cases (gap-of-2 with grace available vs. already used, reset behavior)
- Decision NOT yet made: exact gating mechanism (single narrow settings flag vs. folding into whatever the real edition-config system becomes) -- revisit when Plus edition-config work starts

### Env-driven edition config (Plus checklist step 1) -- IMPLEMENTED 2026-07-27

Landed the prerequisite the streak-grace item above was blocked on: `Settings` now carries `edition` (`EDITION` env var, default `free`), `study_languages` (defaults per edition via `default_study_languages()` in `core/languages/config.py`), `app_name`/`app_short_name`, `android_package_name`/`android_cert_fingerprints` (feeds `/.well-known/assetlinks.json`), and `on_demand_examples_enabled` (defaults to `edition == "plus"`, independently overridable as an AI-cost kill switch). Free/local with zero env vars set is a strict no-op vs. pre-change behavior (verified). `core/editions.py` (new) exposes `active_study_plugins()`/`is_study_language()`, consumed by `home.py`/`verbs.py`/`api_preferences.py` instead of raw `all_plugins()`. Stage now deploys with `EDITION=plus` (Makefile + `cloudbuild.stage.yaml`); prod deploys with `EDITION=free` explicit (not relying on the default, so a future default change can't silently flip prod). `UI_LANGUAGES` split out from `LANGUAGE` in `core/languages/config.py` to defuse a latent bug: `LANGUAGE.keys()` was doing double duty as both the UI-language allowlist and study-language display metadata, which would have let a Plus-only study language (e.g. `it`) silently pass UI-language validation once that plugin existed.

Also decided/done in this pass: `PRACTICE_LOOP_ENABLED` (module-level flag, `true` in every deployed environment, only `false` locally) deleted outright rather than migrated into `Settings` -- owner call, it was a finished rollout with no live toggle use, and its only effect had been hiding a shipped feature from local dev.

**Entitlement model clarification (owner, 2026-07-27) -- narrows the 2026-07-12 "owning the app is the entitlement" ruling:** for study-language gating specifically (i.e. IT/FR once those plugins exist), the owner wants real per-user enforcement, not just soft URL-level separation: **anonymous users get no access to Plus-only study languages at all; logged-in users must be checked against a paid/free status.** This is a materially different mechanism than "owning the Plus app is the entitlement, no server-side per-feature checks" -- it requires an actual per-user entitlement record (a `status` field keyed by uid, populated from something -- manual admin flag initially, Play Billing/subscription webhook later) and route-level checks in `learn.py`/`audio.py`, none of which exist yet.

**Explicitly out of scope for this session's edition-config work** (owner-confirmed, 2026-07-27): no auth/entitlement code was touched. `core/registry.get()` (used by `learn.py`, `audio.py`, `admin_candidates.py`) stays unfiltered by edition for now -- once IT/FR plugins are registered, they'd technically be reachable on the free host by a hand-typed URL until the entitlement check above is built. Recorded here as the next real gap to close, not forgotten: **before IT/FR plugins ship, this entitlement check needs its own ticket** (per-user status field/source, `learn.py`/`audio.py` gating, and reconciling with the existing "owning the app is the entitlement" language elsewhere in this doc, which this decision supersedes for study-language access specifically).

### Entitlement mechanism -- design DONE 2026-07-27, phased rollout DECIDED, pricing model changes as a consequence

Design memo produced (senior-architect, 2026-07-27) answering the open question from the "Entitlement model clarification" note above: can a Google Play Store install itself set a server-visible "this user paid" flag?

**Verdict: no.** Google provides no API to verify "this account paid for a paid app listing" -- that resource doesn't exist. The only mechanisms available: **Play Integrity API** (proves a genuine, untampered Play install -- not payment -- Android-only, no web binding, would require hand-maintaining a custom TWA shell instead of regenerating one from tooling, no refund/cancellation notifications), or **Play Billing via the Digital Goods API** (full server-side verification through the Android Publisher API, real-time notifications for renewals/cancellations/refunds via Pub/Sub RTDN, works from the same web codebase running inside the installed TWA) -- **but this only works if the app is free to install**, with the paywall as an in-app purchase or subscription. Google's own TWA billing docs recommend exactly this (free app + IAP) over a paid listing for this reason. Install Referrer API carries no payment information at all. Full technical detail (Firestore schema, exact enforcement points, fail-open/fail-closed policy, the discovery that `/learn` currently has no way to identify a signed-in user on a plain page load since `__session` is already claimed by admin auth) lives in this session's conversation record, not reproduced here -- re-derive via a fresh senior-architect design pass if this doc's summary isn't enough when implementation starts.

**Phased rollout DECIDED (owner, 2026-07-27):**
- **Phase 1 (build first, no billing/Play Console work needed):** entitlement source is a flag the owner sets manually from the admin console. This builds the *entire* enforcement path end to end -- `user_entitlements/{uid}` in Firestore, the session-cookie rework needed to identify a signed-in user on `/learn` (currently impossible), the `can_study()`-style gate in `learn.py`/`audio.py` -- and lets the owner dogfood/validate the whole anon-blocked/logged-in-checked flow immediately.
- **Phase 2 (later):** entitlement source becomes a verified in-app subscription purchase (Digital Goods API + Play Billing + RTDN sync). This phase only swaps *where the flag comes from* -- the enforcement code from Phase 1 is not touched again.

**Pricing consequence, supersedes the 2026-07-12 addendum's "$1.99 paid listing" decision:** since Phase 2 requires Play Billing, and Play Billing requires a free-to-install listing, **Plus now launches free-to-install, monetized entirely through an in-app subscription (or one-time in-app purchase, still open) rather than a paid Play listing.** The $1.99 paid-listing plan, the "paid listing practice run" rationale, and the associated Google Payments merchant-account-for-a-paid-listing framing in the 2026-07-12 addenda are superseded by this. One-time-purchase vs. subscription for the in-app product itself remains an open call, deferred to Phase 2 -- doesn't block Phase 1.

**Why:** the owner asked directly whether an app-store install could set the flag automatically; the honest answer forced the pricing-model question, since the only mechanism that gives genuine server-side verification requires flipping the monetization model.

**Update: Phase 1 ✅ SHIPPED 2026-07-28, commit `ed6f2d7`** ("Add Phase 1 entitlement mechanism: manual admin-set Plus gating"). Built the full enforcement path: `user_entitlements/{uid}` in Firestore, `core/entitlements.py` (`can_study`, fail-open on transient errors), gates on `/learn`, `/verbs` (page + API), `/audio`, both search endpoints, `/api/preferences`; manual grant/revoke via `/admin/entitlements`. Zero production effect yet since `FREE_STUDY_LANGUAGES` still covers every registered plugin at ship time -- becomes load-bearing once Italian/French are reachable. Phase 2 (swap the manual flag for a verified in-app purchase) is unchanged, still not started.

**~~How to apply: Phase 1 work (admin-set entitlement + session cookie + route gating) is unblocked and can start~~** without any Play Console/merchant-account/pricing work -- superseded by the shipped note above. Do not build IT/FR plugins live on the Plus host before Phase 1's gate exists, or they become reachable on the free host by hand-typed URL (registry is edition-unfiltered by design, see the entitlement clarification note above). Do not schedule Play listing/merchant-account work (checklist item 5) against the old $1.99 paid-listing assumption -- it now needs a free listing + in-app product setup instead.

### On-demand example generation (#3) -- attempted 2026-07-27, blocked on a real gap, not scheduling gate

Went to start this (next item after edition config in the "PM, propose 3 next items" queue) and found the checklist's one-line scope ("user picks a form with no example -> generate via existing AI pipeline -> persist") assumes a form<->example association that doesn't actually exist. What's shipped (item #2 above, "Jump to example") is a **superficial match**: client-side substring search of the conjugated form's surface text against already-rendered example sentences (`app/static/learn.js`), not a real grammatical link (person/number/tense/aspect) between a form and an example. "No match" today just means "the substring search failed," not "no example uses this form" -- the two are different failure modes and the UI/signal-logging can't currently tell them apart.

Building real per-form generation on top of this would either (a) generate against the same shaky substring signal, meaning some "missing" forms flagged for generation already have a matching example the search just missed, or (b) require building the real grammatical association first (which form -> which example, structurally) -- a bigger, separate piece of work than "one endpoint + a rate limit."

**Not scheduled yet.** Owner's call to make: whether the substring-match approach is good enough to build on now (accept some false "missing" positives, ship a v1), or whether the real grammatical association needs to be built first as its own item. Also still unresolved from the entitlement design memo above: whether this feature needs real entitlement gating (architect's recommendation) or the original checklist's "edition flag + no entitlement check" framing still holds -- that question is independent of the matching-model question and can be decided separately.

**Other prerequisite gaps found while scoping (not blockers, just not yet built):** no rate-limiting primitive exists anywhere in the codebase (would need one, e.g. a Firestore per-user daily counter -- `core/analytics/daily_counters.py` despite the name is just a language-code validator, not reusable); the `Example` data model has a legacy `src`/`dst` naming inconsistency across raw Firestore docs vs. the loaded dataclass (called out in `admin_candidates.py`'s own comments) that would need reconciling before writing new generated examples into it.

### Jump to example (#2): kill switch shipped 2026-07-28, real design still owed

The superficial-match finding above (client-side substring search, no real grammatical link) got a live-data audit once Italian shipped -- 20 real verbs with a compound `passato_prossimo` tense (e.g. "ho parlato", two tokens, unlike every other language's single-token forms), a real stress test for the matching logic.

**Audit verdict (2026-07-28, senior-architect, traced against real Firestore data + live production signals -- not just code reading):**

1. **Italian compound tense: NOT broken today.** Ported the JS matcher to Python, ran it against all 20 live Italian verbs -- zero cases where an example contains the participle but the `passato_prossimo` row fails to match. Latent fragility exists (adverb insertion like "Ho **già** parlato" breaks it; essere-verb participle agreement like "è andat**a**" vs the stored "andato" breaks it) but doesn't manifest in the current clean, textbook-style seed examples. Not urgent, doesn't justify flipping the kill switch.

2. **Real problem #1 -- silent false positives across ALL five languages, not just Italian.** Homograph rate (a normalized form string shared by another row on the same board, so a match can land on the wrong grammatical form with no indication anything's off): it 18%, es 21%, he 22%, **en 58%**. Diacritic-stripping collisions verified live: Italian "è" (lui/lei presente of essere) normalizes to "e" and matches the conjunction "e" ("...gentile con gli altri **e** riceverai..."); Spanish "está"→"esta" matches the demonstrative; Hebrew nikud-stripping merges `past_2msg`/`past_2fsg` into the same normalized string despite the board rendering them as distinct rows. Only ~25-42% of form rows are matchable at all per language (5-6 examples vs 25-30 rows) -- most magnifier buttons are dead by construction, not by bug.

3. **Real problem #2 -- HIGH severity, already caused production damage.** The lemma/infinitive row also gets a magnifier button (`core/render.py`'s `NO_AUDIO_ROW_KEYS` exclusion list doesn't cover it), and it is a **guaranteed miss** (the infinitive essentially never appears verbatim in an example sentence) -- 275 buttons across the catalog whose only possible outcome is a false demand signal. Confirmed live in Firestore: 33 `source="form_jump"` signals exist, and **13 of them are already mislabeled as real candidates** (`status: candidate` in `demand_signal_labels`) despite being inflected forms of verbs already in the catalog (e.g. `he_מְאַחֲרִים`, `he_קָרָאתָ` -- conjugations of `he_lakhr`, already live). The admin review UI (`app/routes/admin_signals.py`) doesn't surface `source`/`verb_id`, so these are indistinguishable from genuine unknown-verb searches to a reviewing human. `classify_signal_group` can create a `verb_candidates` stub keyed `f"{language}_{query}"` -- for `it`+`parlare` that's literally `it_parlare`, the real verb's own id (a collision hazard, not yet triggered but the code path is live). `/api/learn/form_signal` itself is also unauthenticated, unvalidated, and has no dedupe/rate-limit (one verified case of the same signal logged 3x from one session).

**Decision (2026-07-28, owner override): flipped `JUMP_TO_EXAMPLE_ENABLED=false` in stage and prod (live via `gcloud run services update`, and persisted into `cloudbuild.stage.yaml` + `Makefile`'s `gcp-deploy-stage`/`gcp-promote-stage-to-prod` targets so the next deploy doesn't silently re-enable it). Owner chose to disable rather than accept the false-positive rate the audit found (problem #2 below already caused mislabeled demand signals in production), overriding the audit's own "leave it on" recommendation. Re-enable only after the three patches below (or the real fix) land.**

**Recommendation (audit's, not actioned -- superseded by the decision above): leave `JUMP_TO_EXAMPLE_ENABLED=true`, do NOT start the grammatical-link redesign yet. Three ordered patches first:**
1. Stop rendering the magnifier on the lemma/infinitive row (`core/render.py:65` -- new exclusion set, do NOT extend `NO_AUDIO_ROW_KEYS`, that also gates the audio button). One line, kills 275 guaranteed-false signals across the catalog.
2. Get `form_jump` signals out of the verb-demand review queue: surface `source`/`verb_id` in `admin_signals.py`, default-filter `form_jump` out of candidate review (or route to a separate collection), clean up the 13 already-mislabeled Hebrew entries in `demand_signal_labels`. This is the fix with real, already-realized consequences.
3. Move matching server-side into `core/render.py` (which already has both `board.sections` and `board.verb.examples` in scope) -- render the magnifier only on rows that will actually hit. Removes ~75% of dead buttons, removes the toast UX, removes the demand-signal write path for misses entirely.

Only after those three does the "real fix" (backlog item below) become cheap: once matching is a single Python function instead of client-side JS, swapping substring-match for a stored `form -> example index` association (built at generation time -- the prompt already emits one example per tense, asking Claude to also tag which form each example demonstrates is close to free) is a local change, not a rewrite.

**Not yet done:** none of the three patches above are implemented. This is the next concrete work item, not just a design question anymore.

**Shipped ahead of the audit landing, as insurance, not as a fix:** `Settings.jump_to_example_enabled` (env `JUMP_TO_EXAMPLE_ENABLED`, defaults `true` -- a kill switch, not edition-gated, current behavior unchanged unless explicitly flipped off). Wired through `core/render.py` (`render_board_html`'s `jump_to_example_enabled` param gates only the 🔎 button itself, nothing else on the row) and `app/routes/learn.py`. Lets the feature be disabled instantly via env var, no redeploy, no code change, if the audit finds it materially broken for a shipped language -- without pre-judging what that audit concludes.

**TODO, not started -- design the real fix:** a genuine grammatical/structural link between a conjugated form and the example that demonstrates it, replacing (or supplementing) the substring heuristic. This is the same underlying gap the on-demand-generation item above is blocked on -- fixing it properly likely unblocks both. Needs: (a) the audit's severity verdict first, (b) a decision on whether the fix is a stored association (built at generation time, form -> example index) vs. a smarter runtime match (e.g. tokenizing compound forms instead of whole-string search), (c) whether existing verbs (en/ru/he/es/it) need a backfill or only new generations get the real link.

**Why:** shipping the kill switch now means "the feature might be broken" and "we've fixed it properly" are decoupled -- the first is a one-line env change, the second is real design work that shouldn't be rushed just because a quick mitigation exists.

**How to apply:** don't start the real fix until the audit's findings are recorded here. If the audit finds en/ru/he/es genuinely fine and only Italian's compound tense is at risk, the fix might be narrower (special-case multi-word forms) than a full redesign.

### Italian conjugation correctness -- linguist-agent audit (2026-07-28)

Separate from the jump-to-example matching audit above, this is a direct grammatical audit of the 20 live Italian verbs' stored conjugation data, cross-checked against a regular-verb-ending reference (https://www.thoughtco.com/tables-of-regular-italian-verb-endings-4088101) and standard Italian grammar.

**Confirmed correct:** regular -are/-ere conjugations (presente/imperfetto/futuro/passato_prossimo) including orthographic rules (mangiare -> mangerò, no double-i); irregular verbs (essere/avere/andare/fare/dare/stare/dire/venire/bere/sapere) including irregular participles and futuro consonant doubling (verrò/berrò); passato_prossimo avere-vs-essere auxiliary selection across all 20 verbs; example sentences (natural, idiomatic, each demonstrates its labeled form).

**Real bug found:** `it_dovere` and `it_potere`'s formal (Lei) imperative use presente indicativo ("deve", "può") instead of the grammatically correct congiuntivo presente ("debba", "possa") -- 18 of 20 verbs derive Lei-imperative correctly, these two don't. `_PROMPT_IT` in `core/settings_ai.py` doesn't spell out the congiuntivo-derivation rule the way RU's prompt does for its imperative. Needs a prompt fix + regeneration of these two verbs.

**Real (small) bug found:** `core/languages/it/plugin.py`'s passato_prossimo section reuses the shared `board.tense_preterite` locale key, which Spanish's plugin uses correctly for a true simple-past preterite. Passato prossimo is a compound perfect, not a preterite -- mislabeling risk for a learner comparing tenses cross-language. Fix: new locale key (e.g. `board.tense_perfect`) across all 4 locale files.

**Documented, not a bug:** passato_prossimo participle agreement is deliberately masculine-singular-only per `_PROMPT_IT` (e.g. "sono andato" regardless of speaker gender) -- a real simplification with a real learner-facing cost, not a silent defect. Product call on whether ver2 wants gendered variants.

**Coverage gap, not yet a documented decision:** board has no congiuntivo (subjunctive) or condizionale (conditional) -- mirrors Spanish's exact scope, so likely an intentional cross-Romance-language v1 boundary, but no record of that decision was found for either language. Condizionale ("vorrei un caffè") is arguably as important as futuro for a learner. Passato remoto's omission is fine (literary/regional register).

**Not yet tested live:** no regular -ire verb and no -isc- infix verb (e.g. finire, capire) exists in the current 20-verb catalog -- that ending class (io capisco, noi capiamo) is the one Italian regular-conjugation pattern with a stem-insertion irregularity, untested against real generated data.

**Not actioned yet** -- this is an audit record, not a fix. Next owner call: whether to prompt-fix + regenerate dovere/potere now, and whether to scope congiuntivo/condizionale for ver2 Italian or leave both Romance languages at the current tense set.

### French language plugin -- ✅ SHIPPED 2026-07-28

Second Plus-only Romance study language, alongside Italian (`PLUS_EXTRA_STUDY_LANGUAGES = ("it", "fr")` in `core/languages/config.py` already anticipated both). Built the same way Italian was: `core/languages/fr/plugin.py` (présent/passé composé/imparfait/futur/impératif/gérondif/participe passé board), a French generation prompt in `core/settings_ai.py` (explicit avoir-vs-être auxiliary + masculine-singular participle-agreement default for passé composé, mirroring the Italian prompt's approach), Edge TTS voices in `core/tts.py` (`fr-FR-DeniseNeural`/`fr-FR-HenriNeural`), registered in `app/main.py` and `tools/check_plugins.py`, `"fr": "French"` added to `core/translation_service.py`'s `_LANG_NAMES`. `tests/test_editions.py` and `tests/test_nav_links.py` updated (both previously asserted "fr" plugin doesn't exist yet). Full suite green (859 passed) after wiring.

`tools/seed_fr_verbs.py` used the real Claude generation pipeline to write the 30 most common French verbs into the live `verbs` Firestore collection (same one-off-script pattern as `tools/seed_it_verbs.py`) -- all 30 succeeded, no skips. `tools/prewarm_fr_audio.py` pre-generated both-voice TTS audio for all 30 verbs into **both** `verbboard-audio-stage` and `verbboard-audio-prod` GCS buckets. `tools/backfill_fr_translations.py` backfilled inline example + lemma translations for all 30 verbs across en/ru/he/es.

**Bug found and fixed during audio prewarm:** `core/settings.py` calls `load_dotenv(override=True)`, so a shell-inline `AUDIO_BUCKET=verbboard-audio-prod` env var was silently overridden by `.env`'s `AUDIO_BUCKET=verbboard-audio-stage` -- the first "prod" prewarm run actually re-uploaded to the stage bucket a second time without erroring. Caught by checking each run's own printed target-bucket line, not by a crash. Fixed by temporarily editing `.env` itself (no local dev server running at the time) rather than relying on inline env vars, since `override=True` always wins. Not a code bug worth fixing in `core/settings.py` itself (the override behavior is relied on elsewhere for local dev convenience) -- just a footgun for any future one-off script that tries to target a non-default bucket via inline env var. Worth remembering next time a script needs a non-`.env` bucket/project value.

**Update: linguist-agent audit done later the same day** -- see "French conjugation correctness -- linguist-agent audit (2026-07-28)" below. One real bug found and fixed.

### cache_audio.py augmented for it/fr + --both-buckets (2026-07-28)

`tools/cache_audio.py` (the general-purpose, repeatable audio-caching tool -- as opposed to the one-off `seed_*`/`prewarm_*` scripts above) registered the `it`/`fr` plugins and expanded its `--language` choices (including `all`) to cover Plus-only study languages, and gained a `--both-buckets` shorthand for `--bucket verbboard-audio-stage --bucket verbboard-audio-prod`.

**Real gap found by this augmentation:** a `--language it --both-buckets --dry-run` run showed **0 items cached in the prod bucket for Italian** -- `tools/prewarm_it_audio.py` (the one-off script used at Italian's original ship time) only ever wrote to whichever bucket `.env`'s `AUDIO_BUCKET` pointed at (stage), and was never run a second time against prod. Backfilled via `cache_audio.py --language it --both-buckets` for real: 1478/1478 generated, 0 failures, both buckets now fully covered (confirmed via a follow-up dry-run showing 0 remaining). Also used to complete French's prod coverage cleanly (`--language fr --both-buckets`: 2158/2158, 0 failures), sidestepping the `load_dotenv(override=True)` footgun noted above entirely, since `--bucket`/`--both-buckets` are explicit CLI args, not env vars.

**Why:** the one-off per-language prewarm scripts (`prewarm_it_audio.py`, `prewarm_fr_audio.py`) duplicate logic `cache_audio.py` already had (existing-key listing, hashed-key generation, multi-bucket writes) but without the `--bucket`/multi-target support that would have caught the Italian prod gap immediately. `cache_audio.py` is now the actual general tool for this; the one-off scripts stay checked in as historical record of what was run at each language's ship time, but future audio work (including any regeneration-driven re-warm) should prefer `cache_audio.py --both-buckets`.

### French conjugation correctness -- linguist-agent audit (2026-07-28)

Same treatment as the Italian audit above, run against all 30 live French verbs, cross-checked against standard French grammar (regular -er/-re conjugation rules, the passé composé avoir/être auxiliary list, the tu-imperative -s-drop rule for -er verbs, elision).

**Confirmed correct:** regular -er conjugations (10 verbs) and regular -re conjugations (2 verbs) across présent/imparfait/futur; all tested irregular verbs (être, avoir, faire, aller, dire, voir, savoir, pouvoir, vouloir, venir, devoir, prendre, tenir, sortir, vivre, mettre, connaître) including tricky suppletive/irregular forms (aller → futur "j'irai", dire → "vous dites", connaître's circumflex before t/dropped before s); passé composé auxiliary selection (avoir vs être) correct for all 30, including the 6 être-verbs (aller/arriver/passer/rester/sortir/venir) and correct number-agreement on the participle for all 6; the -s-drop tu-imperative rule for -er verbs, applied correctly across all 12 relevant verbs with zero exceptions; elision (je → j'), checked across all 120 je-slot forms in the catalog, zero mismatches; example sentence quality (idiomatic, agreement-consistent with stored forms, correct French-specific syntax like futur-after-"dès que").

**Real bug found and fixed:** `fr_pouvoir`'s `imperatif` (`{tu: "peux", nous: "pouvons", vous: "pouvez"}`) was fabricated -- pouvoir is grammatically defective in the imperative mood in standard French (no genuine command form exists), but generation had copied the présent forms in as if they were valid. Evidence the model itself sensed the defectiveness: pouvoir was the only one of 30 verbs with 5 examples instead of 6, and the only one with no impératif example -- the structured `forms` field fabricated an answer where free-text example generation correctly declined to. Fixed: `_PROMPT_FR` in `core/settings_ai.py` now has an explicit rule (return `imperatif: {}` rather than copying présent for defective verbs), and `tools/fix_fr_pouvoir_imperative.py` (new, mirrors `tools/fix_it_modal_imperative.py`) regenerated `fr_pouvoir`'s forms -- confirmed `imperatif` is now `{}`, board correctly omits the Impératif section for this verb, audio re-warmed to both buckets.

**Not fixed, lower priority:** two verbs have grammatically valid `imperatif` forms but no example sentence actually demonstrating the mood -- `fr_devoir` (all 6 examples are présent-indicatif, none is a real command) and `fr_connaître` (the "impératif" example is actually a présent-indicatif question, not a command). Content-quality gap, not a forms-accuracy bug.

**Coverage gaps, shared with Italian's audit, still undocumented decisions:** no conditionnel (French's "je voudrais" is arguably more load-bearing for a beginner than futur, same undocumented-gap pattern as Italian's missing congiuntivo/condizionale); no regular 2nd-group -ir/-iss- verb (e.g. finir: je finis, nous finissons) tested against real generated data, mirroring Italian's untested -isc- infix class.

**Not actioned:** the two milder example-completeness gaps and the coverage-gap product decisions, same as Italian's equivalent open items.
