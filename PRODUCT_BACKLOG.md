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
| Streaks (from #5) | High | Low | Direct retention lever, explicitly requested; `user_practice` already has the session history this can be computed from |
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

1. **Do now (high/med impact, low risk, no blockers):** streaks, known-word counter, label/icon fixes; ~~#1 (translate infinitive), #2 (jump to example)~~ — both shipped and promoted to prod 2026-07-02, see status notes above
2. **Near-term, needs one small decision first:** verb illustration images — settle sourcing approach, then scope
3. **Big bets — scope before committing:** #6 (premium mechanism) is the real fork in the road here, since it gates both #3 and #4. Worth a short scoping spike (separate deployment vs. entitlement flag, Play Billing vs. Stripe) before estimating either downstream item. Consider whether #4 (spaced repetition) could ship as a free feature first, independent of #6 — the user's request for it doesn't inherently require a paywall, that framing came from the product side, not the feedback itself.
4. **Parked:** "redesign everything" — flag for a future scoped UX audit, not on this backlog as-is.

No premium/paywall mechanism currently exists in the codebase — #3 and #4 both assume one, which is why #6 sits ahead of them despite being newer.

**Combined lowest-risk queue (including carried-over engineering items from #7):** admin inline-`style=` cleanup is the single lowest-risk item in the whole backlog — no behavior change, no tests, one file surface, admin-only. Right behind it: the form-row Examples button (#2), since its design is already fully specced. Both can run ahead of anything premium/#6-dependent with no sequencing conflicts.
