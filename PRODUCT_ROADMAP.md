# Product Roadmap

Point-in-time triage snapshot derived from `PRODUCT_BACKLOG.md`, generated 2026-07-28, last updated 2026-07-29. `PRODUCT_BACKLOG.md` remains the source of truth and historical record for decisions, rationale, and dates -- this file is a scannable "what's left" view on top of it, not a replacement. Re-derive this file from the backlog periodically rather than editing it as a second log.

Classification grounds "Free" vs "Plus" in `core/languages/config.py` (`FREE_STUDY_LANGUAGES` vs `PLUS_EXTRA_STUDY_LANGUAGES = ("it", "fr")`) and the backlog's own 2026-07-12 ruling: **all new user-visible features default to Plus** unless explicitly grandfathered into the free edition (known-word counter and label fixes are the two named exceptions, per the 2026-07-15 addendum). Items the backlog itself leaves genuinely open are marked "(ambiguous, defaulted to Plus per policy)".

---

## Done

- **Translate verb infinitive** -- lemma translation using the existing `Example.translations` mechanism (`translate_lemma()`, `lemma_translations` field, backfilled across 384 verbs). See PRODUCT_BACKLOG.md "2026-07-02 session" #1.
- **Jump to example from a conjugation form** -- 🔎 button per form row, client-side substring match, demand-signal logging on miss. Shipped, but **currently disabled** (kill switch flipped off 2026-07-28 after an audit found a high false-positive rate; real fix tracked in Plus TODO). See "2026-07-02 session" #2 and "2026-07-28 session".
- ~~**Practice day streak**~~ -- shipped 2026-07-08, **removed entirely 2026-07-29** (owner call, "not my game"). See "2026-07-29 session" removal record.
- **Admin inline-`style=` cleanup** -- inline styles in admin JS/templates extracted to CSS classes, no behavior change. See "2026-07-10 session" status audit.
- **Architect MEDIUM engineering items** (temperature=0 on LLM calls, pydantic validation, rank-scan fix, Gemini retry) -- closed as a batch. See "2026-07-10 session" status audit.
- **Known-word counter** -- turned out to already exist since 2026-05-18 (`.progress-star`/`.progress-count` on the verbs page); the 2026-07-02 request was a duplicate ask, not a real gap. See "2026-07-27 session" correction.
- **Feedback page poll question spacing** -- `.question-title` styling fix. See "2026-07-27 session".
- **Feedback page mobile header crowding** -- `.card-nav` flex-wrap fix, scoped to `feedback.css`. See "2026-07-27 session".
- **Env-driven edition config** (Plus checklist step 1) -- `Settings.edition`, `study_languages`, `app_name`, Android fingerprints, `on_demand_examples_enabled`; `core/editions.py`; stage runs `EDITION=plus`, prod runs `EDITION=free` explicitly. Prerequisite for everything Plus-scoped below. See "2026-07-27 session".
- ~~**Streak grace/freeze (N2)**~~ -- shipped commit `1797077`, **removed along with the base streak feature, 2026-07-29**. See "2026-07-29 session" removal record.
- **Italian language plugin** -- base catalog of 20 verbs live (`core/languages/it`), Plus-only study language, linguist-audited and both bugs found (Lei-imperative congiuntivo derivation, `board.tense_perfect` mislabel) fixed same day. See "2026-07-28 session" Italian audit. Remaining open item (congiuntivo/condizionale coverage decision) tracked in Plus TODO.
- **Entitlement mechanism, Phase 1** -- manual admin-set Plus gating: `user_entitlements/{uid}` in Firestore, `core/entitlements.py` (`can_study`, fail-open on transient errors), gates `/learn`, `/verbs`, `/audio`, both search endpoints, `/api/preferences`; grant/revoke via `/admin/entitlements`. Zero production effect today (free study languages cover every currently-reachable plugin). Shipped commit `ed6f2d7`. See "2026-07-27 session" entitlement design memo (backlog text refreshed 2026-07-28 to reflect ship status).
- **French language plugin** -- catalog of 30 verbs live (`core/languages/fr`), Plus-only study language, same shape as Italian (présent/passé composé/imparfait/futur/impératif/gérondif/participe passé). Audio cached to both `verbboard-audio-stage` and `verbboard-audio-prod`; translations backfilled across en/ru/he/es; linguist-audited same day, one real bug found (`fr_pouvoir`'s fabricated imperatif) and fixed. See "2026-07-28 session" French audit. Remaining open items (two milder example-completeness gaps, conditionnel coverage decision) tracked in Plus TODO.
- **`cache_audio.py` augmented for it/fr + `--both-buckets`** -- surfaced and fixed a real gap: Italian's original prewarm script never wrote to the prod bucket at all (0 cached, silently). Both languages backfilled to full coverage in both buckets, verified via dry-run. See "2026-07-28 session".
- **Jump-to-example kill switch** (`Settings.jump_to_example_enabled`) -- shipped as insurance ahead of the audit, then actually used: flipped off in stage/prod same day once the audit found real false-positive damage. See "2026-07-28 session".
- **Google Play submission infra prerequisites** -- manifest/PWA enrichment (categories, shortcuts, offline fallback), assetlinks fingerprint pipeline, `GOOGLE_PLAY_CHECKLIST.md` tracking doc. The submission itself is still open (Free TODO below); only the code-side groundwork is done.
- **"No gamification pressure" store-listing copy tension** -- resolved by rewording to "no pressure to log in daily" (`GOOGLE_PLAY_CHECKLIST.md`), a precise claim consistent with shipped badges rather than a blanket claim badges would contradict. See "2026-07-29 session".

---

## Free TODO

Ordered roughly by how actionable each item is right now.

1. **Google Play submission (base app), steps 5.1-5.8.** The single biggest open thread. Blocked on human-side work: recruiting >=12 opted-in closed testers for a 14-continuous-day gate (new personal-account Play policy, confirmed live 2026-07-23) before production access unlocks. All code-side work is done (assetlinks fingerprint swap at 5.5). See "2026-07-10 session" A, "2026-07-23" checklist note, `GOOGLE_PLAY_CHECKLIST.md`.
2. **Label/icon fixes** from real user feedback -- **in progress 2026-07-29**: "Abandon" -> "Discard practice" (en/ru/es/he) and the learned-star copy reworked to a non-committal "already known regardless of source" framing ("Already know this" / "Уже знаю" / "Ya lo sé" / "מוכר", single static string covering both toggle states) shipped; mobile-fit check on the English string pending. Snail icon and the `/verbs` filter chip wording explicitly left unchanged (owner decision). See "2026-07-02 session" #5, "2026-07-15 addendum", "2026-07-29 session" label-copy record.
3. **In-app help/discoverability affordance** -- one consistent idiom (tappable element vs. hint style vs. first-run hints) for the learned-star button, practice-panel controls, translation toggle, and (once re-enabled) the jump-to-example button. Idiom decided 2026-07-29: tappable element itself (control links/expands to an explanation on tap). Per-control design (target anchor/text) not yet done. See "2026-07-09 update".
4. **Nightly auto-generation of candidates from top demand signals (N8).** Admin efficiency, not user-facing -- turns the review pipeline from pull to push. Needs a Cloud Scheduler job and AI-spend guardrails; human promote/review step stays. See "2026-07-10 session" N8.
5. **"Redesign every screen"** -- one user's open-ended instinct that the whole UI needs a professional pass. Not a scoped item; parked pending a dedicated UX audit, not something to size yet. See "2026-07-02 session" #5.

**Engineering hygiene (background, not user-visible, applies to the shared codebase both editions run):**
- Admin password and JWT signing key share the same secret -- deferred to the next dedicated infra/Secret Manager pass.
- Consolidate JS link-building (`verbs_filters.js`, `practice_loop.js`, `home.js`, `learn_practice.js`, `auth.js` each hand-append `language`/`ui_language`/`return_to`) into server-rendered construction -- biggest lever for e2e-test simplification, needs a full caller/invariant audit first.
- Firestore fake/mock seam for `session_tracker.py`, `admin_feedback_service.py`, `verb_repository.py` write paths -- no emulator/fake exists, so these paths have no unit coverage.
- DI container to remove monkeypatch drag in tests -- not urgent, maintainability risk only.

See PRODUCT_BACKLOG.md "2026-07-02 session" #7 for all four.

---

## Plus TODO

Ordered roughly by how actionable each item is right now (clear next step first, aspirational asks last).

1. **Jump-to-example real fix, three ordered patches** (currently disabled via kill switch pending these): (a) stop rendering the magnifier on the lemma/infinitive row -- one line, kills 275 guaranteed-false signals; (b) get `form_jump` signals out of the admin candidate-review queue and clean up the 13 already-mislabeled Hebrew entries; (c) move matching server-side into `core/render.py` so the button only renders on rows that will actually hit. See "2026-07-28 session" jump-to-example audit.
2. **Real grammatical form<->example association** -- replace the substring-match heuristic with a stored `form -> example` link (built at generation time) or a smarter runtime match. Becomes cheap only after patch (c) above lands; also unblocks item 3. Open: whether existing verbs need a backfill or only new generations get the real link. See same audit.
3. **On-demand example generation (#3)** -- Plus launch feature. Attempted 2026-07-27, blocked on the association gap above (not a scheduling gate). Also needs: a rate-limiting primitive (none exists -- `core/analytics/daily_counters.py` despite its name is not reusable for this), reconciling the `Example` model's legacy `src`/`dst` naming, and a decision on whether it needs real entitlement gating or the original "edition flag only" framing. See "2026-07-12 session" checklist step 3, "2026-07-27 session".
4. **French example-completeness gaps** -- `fr_devoir` and `fr_connaître` both have grammatically valid `imperatif` forms but no example sentence that actually demonstrates the mood (both are présent-indicatif sentences, one a question). Content-quality gap, not a forms-accuracy bug; low priority. See "2026-07-28 session" French audit.
5. **Entitlement Phase 1 loose end** -- the uid session cookie can go stale past its 12h max-age if a tab stays open without re-triggering the write path (fails closed, not a security issue, flagged as a fast-follow to land before Plus-only content is actually reachable by a free user). See "2026-07-28 session" entitlement commit note.
6. **Italian/French tense-coverage decision** -- neither has congiuntivo/condizionale (subjunctive/conditional); mirrors Spanish's current scope but no language has a recorded decision that this was deliberate. Also untested in both: no regular stem-insertion verb class exists in either catalog yet (Italian's `-isc-` infix e.g. finire/capire; French's `-iss-` 2nd-group `-ir` verbs e.g. finir/choisir). See "2026-07-28 session" Italian and French audits.
7. **Entitlement Phase 2** -- swap the manual admin-set flag for a verified in-app purchase (Digital Goods API + Play Billing + Real-Time Developer Notifications). One-time purchase vs. subscription is still an open call, deferred to this phase. See "2026-07-27 session" entitlement design memo.
8. **Ver2/Plus infra**: second prod Cloud Run service (same image digest as free), Hosting site/DNS, Play listing at the Plus host (hostname itself lives in GCP Secret Manager, never committed). Now needs a **free-to-install listing + in-app product** setup, not the earlier $1.99 paid-listing plan (superseded by the Phase 2 pricing consequence). See "2026-07-12 session" checklist steps 4-5, "2026-07-27 session" pricing consequence.
9. **Guaranteed repetition quota for seen-but-not-known verbs** -- implementation plan and code sketch are fully scoped (`buildPool()` in `practice_loop.js`); not yet built. Open: exact `REPEAT_QUOTA` values and *(ambiguous, defaulted to Plus per the "all new features -> Plus" policy -- the backlog itself flags this as unresolved and unforced)*. See "2026-07-27 session".
10. **Spaced repetition (#4)** -- Anki-style resurfacing of learned/practiced verbs after N days. Explicitly Plus-only per the 2026-07-12 "new features -> ver2" ruling. Large: new per-verb due-date scheduling model + practice-loop integration. See "2026-07-02 session" #4.
11. **Verb illustration images** -- meaning-linked art per verb (not generic icons). Blocked on a sourcing decision (stock vs. AI-generated vs. hand-picked) before it can be sized. *(ambiguous, defaulted to Plus per the "all new features -> Plus" policy -- proposed 2026-07-02, predates the policy, not one of the two named grandfather exceptions.)* See "2026-07-02 session" #5.
12. **Verb of the day (N1)** -- one featured verb per day per language on the home page, deep-linked to `/learn`. Low risk, display-only, deterministic date-hash pick, no new storage. New user-visible feature -> Plus per the 2026-07-15 re-read of the 2026-07-10 quick-win queue against the ver2 policy. See "2026-07-10 session" N1.
13. **Anki/CSV export of known verbs (N4)** -- client-side generation, no new backend. The backlog's own rationale already frames this as "a natural premium-tier candidate later." See "2026-07-10 session" N4.
14. **Weak-forms insight (N3)** -- surface which conjugation forms a user replays or misses most, as a personal "focus on these" hint. Needs a client-vs-server aggregation decision before scoping. See "2026-07-10 session" N3.
15. **Post-practice rating prompt (N7)** -- trigger the Play in-app review API after the Nth completed practice session in the TWA. Needs a "never nag twice" guard; only meaningful once an app is live on Play. See "2026-07-10 session" N7.
16. **Web push notifications (N6)** -- originally scoped as streak-about-to-lapse reminders; that specific trigger no longer applies now that the day-streak feature is removed (2026-07-29), so this item needs a new rationale/trigger (e.g. a general "come back and practice" nudge) before it's picked up. Explicitly flagged 2026-07-23 as a *future* Plus candidate, not launch scope. Real cost when picked up: VAPID keys, a push-subscription Firestore store, a server-side send trigger, permission-prompt UX. Collides with the still-open "no gamification pressure" free-listing copy tension if it moves forward. See "2026-07-23 addendum".

---

**Not on this roadmap by design:** the "redesign every screen" ask and the web-push copy tension are both flagged above as *signals*, not scoped items -- don't size them without a prerequisite decision first (a UX audit; a copy reconciliation, respectively).
