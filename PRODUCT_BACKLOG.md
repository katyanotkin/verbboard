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
| Google Play submission, steps 5.1-5.8 | `instructions.txt` | The single biggest open product thread. All remaining steps are human-side Play Console work except 5.5 (assetlinks fingerprint update, done in-session once the SHA-256 is pasted). Everything code-side is done and verified. |
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

**P0, this week, mostly human-side:** finish Google Play submission (5.1-5.8). Everything else in this backlog compounds only after the app is discoverable. Reconcile the "no gamification pressure" listing copy at step 5.4. Code-side involvement: fingerprint swap at 5.5.

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
5. **Play listing for Plus**
   - Own package name; PWABuilder against plus.verbboard.com; higher price (one-time recommended; subscription would reintroduce Play Billing)
   - Plus fingerprint served in assetlinks.json at the plus host (env-driven `well_known.py`)
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
