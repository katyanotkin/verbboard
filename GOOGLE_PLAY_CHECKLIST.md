# VerbBoard -- Google Play Launch Checklist

Single tracking doc for getting VerbBoard onto the Google Play Store as a TWA,
while keeping the existing FastAPI/PWA architecture.

> **Supersedes** (2026-07-15): `instructions.txt` (execution steps, 2026-06-29)
> and `VerbBoard_Google_Play_Checklist.docx` (planning checklist) -- both merged
> here and removed. References elsewhere (e.g. `PRODUCT_BACKLOG.md`) to
> "instructions.txt step 5.x" map to the same step numbers in this file.

**Pricing (decided 2026-07-15, supersedes the 2026-07-12 $0.99-then-flip plan;
see `PRODUCT_BACKLOG.md`):** the base app launches **Free** from day one.
A free listing can never become paid -- accepted; monetization lives entirely
in the future Plus app ($1.99).

---

## DONE -- foundation work (verified live)

- [x] **Product readiness** -- mobile UX, PWA install, login, progress sync, practice flows stable on prod
- [x] **authDomain fix** -- prod `verbboard.com`, stage `stage.verbboard.com`; `/auth/signin` + `/__/auth/handler` verified live
- [x] **assetlinks.json infrastructure** -- served as static file from `public/.well-known/`; `firebase-deploy-hosting` wired into CI/CD (`cloudbuild.stage.yaml` + Makefile); `roles/firebasehosting.admin` granted; fingerprint JSON verified on prod + stage (placeholder fingerprint until step 5.5)
- [x] **Practice localization** -- `practice.size_unit` / `practice.listens_unit` in all locales; Hebrew RTL bidi fix; 12 regression tests; verified on prod
- [x] **Auth verified end to end** -- desktop + mobile browser + installed PWA on verbboard.com
- [x] **Privacy policy** -- live at https://verbboard.com/privacy (covers login, progress tracking, analytics, feedback)
- [x] **Firebase authorized domains** -- login flows verified from the domains above

## TODO -- prerequisites

- [x] **P1. Google Play developer account** -- registered, $25 fee paid, identity verified (2026-07-23)
- [x] **P2. Package name decision** -- `com.verbboard.app` (decided 2026-07-23). Set at packaging time (step 5.1); cannot change after first upload. Note: the future Plus app will need its own, different package name.

## TODO -- submission steps (execute in order)

### Step 5.1: Generate TWA package [YOU DO THIS]

Go to https://www.pwabuilder.com > enter `https://verbboard.com` >
Package for stores > Android > Download zip.

Inside the zip:
- `verbboard.aab` -- upload to Play Console
- `signing.keystore` -- KEEP SAFE, needed for every future update
- `key.properties` -- alias/passwords

- [ ] Package generated
- [ ] **Keystore backed up** -- encrypted local backup + copy in GCP Secret Manager (alias + passwords too). Losing this means losing the ability to update the app.

### Step 5.2: Create app in Play Console [YOU DO THIS]

play.google.com/console > Create app
- App name: `VerbBoard`
- Default language: English (United States)
- App or game: App
- Free or paid: **Free** (decided 2026-07-15; a free listing can never become paid -- accepted, Plus carries monetization)
- Accept policies > Create

- [ ] App created

### Step 5.3: Upload AAB to Internal Testing [YOU DO THIS]

**Not Production, and not Closed Testing yet either.** Google requires new
personal developer accounts (created after 2023-11-13, which includes this
one, created 2026-07-23) to complete a closed test before Production or
Pre-registration unlock -- see step 5.6b for that gate. Closed Testing itself
requires "finished setting up your app" (store listing + content
declarations, i.e. steps 5.4 and 5.6) per Play Console's own track
requirements table. Internal Testing has **no requirements**, so it's the
right first upload target: it triggers Play App Signing immediately (needed
for step 5.5's real fingerprint) without waiting on anything else.

Play Console > Test and release > Testing > Internal testing > Create new release
- Upload `.aab` from step 5.1
- Release name: `1.0`
- What's new: `Initial release`
- Save and roll out to internal testing (add yourself as a tester to sanity-check the install)

- [ ] AAB uploaded to internal testing (Play App Signing is enabled automatically on first upload; Google re-signs with its own key -- this is why step 5.5 matters)

### Step 5.4: Complete store listing [YOU DO THIS]

Play Console > Store presence > Main store listing

Short description (80 chars max):
```
Verb conjugation tables, audio, and practice. Spanish, Russian, Hebrew, English.
```

Full description:
```
VerbBoard is a verb-first language learning app. Look up any verb and get
a full conjugation table, native-speaker audio for every form, and real
usage examples. Practice sessions drill the verbs you have seen and mark
them as known when you are ready. Works offline after first load.

Supports Spanish, Russian, Hebrew, and English.
Clean interface, no ads, no gamification pressure.
```

> **Copy check before submitting:** "no gamification pressure" vs the shipped
> streaks/badges -- reconcile the wording or make it a deliberate stance
> (flagged in `PRODUCT_BACKLOG.md`, 2026-07-10 session).

Assets:
- App icon: 512x512 PNG -- use `app/static/icons/icon-512.png`
- Feature graphic: 1024x500 PNG -- app name on clean background
- Phone screenshots (min 2): Chrome DevTools > Pixel 7 (412px wide) > verbboard.com; capture verb list page + learn page (Ctrl+Shift+P > "Capture screenshot")
- Category: Education

- [ ] Listing complete

### Step 5.5: Get real Play App Signing fingerprint [CRITICAL -- TELL CLAUDE]

Play Console > Setup > App signing > App signing key certificate.
Copy the SHA-256 fingerprint (format: `AB:CD:EF:...`).

Paste it in the chat. Claude will:
- Update `public/.well-known/assetlinks.json` (fingerprint line)
- Update `app/routes/well_known.py` (fingerprint constant)
- Commit + push + `make gcp-promote-stage-to-prod` (firebase-deploy-hosting runs automatically)

Verify after deploy:
```
curl https://verbboard.com/.well-known/assetlinks.json
https://digitalassetlinks.googleapis.com/v1/statements:list?source.web.site=https://verbboard.com&relation=delegate_permission/common.handle_all_urls
```
Expected: `linked=true`

- [ ] Fingerprint updated and verified

### Step 5.6: App content declarations [YOU DO THIS]

Play Console > Policy > App content:
- Privacy policy: `https://verbboard.com/privacy`
- Ads: No ads
- Content rating: Education questionnaire (no violence/adult content)
- Target audience: 13+ or All ages
- Data safety: Firebase UID tracked for progress sync

- [ ] Declarations complete

### Step 5.6b: Closed testing gate (REQUIRED, not optional) [YOU DO THIS]

Policy reference: https://support.google.com/googleplay/android-developer/answer/14151465

Confirmed live in Play Console 2026-07-23, Google's own wording: *"If you
have a newly created personal developer account, you must run a closed test
for your app with a minimum of 12 testers who have been opted-in for at
least the last 14 days continuously. When you meet these criteria, you can
apply for production access on the Dashboard."* Production and
Pre-registration stay locked until this is satisfied. Now that store listing
(5.4) and content declarations (5.6) are done, the app is "finished set up"
and Closed Testing is unlocked.

Play Console > Test and release > Testing > Closed testing > Create a track
> Create new release (can reuse the AAB already uploaded in 5.3, or upload
fresh) > roll out to the closed track.

- [ ] Closed testing track created, AAB uploaded
- [ ] Recruit >=12 testers (friends/family/community) willing to opt in and keep the app installed
- [ ] Share the closed-testing opt-in link (Play Console > Testing > Closed testing > your track > "Testers" tab) with all 12+
- [ ] Confirm all 12+ have opted in (Play Console shows opt-in count) -- the 14-day clock only counts while a tester is opted in, not from AAB upload
- [ ] Along the way: verify login, audio, progress sync, and navigation from the installed app -- de-risks the eventual public review too
- [ ] Wait 14 continuous days with >=12 testers opted in
- [ ] Apply for production access: Play Console > Dashboard > "Apply for production access" (answers questions about the app, testing process, production readiness)
- [ ] Production access granted (email/dashboard confirmation)

### Step 5.7: Create production release and submit for review [YOU DO THIS]

Only available once 5.6b's production access is granted.

Play Console > Test and release > Production > Create new release (can reuse
the AAB already uploaded, or upload fresh) > Publishing overview > Send
changes for review. Review takes 3-7 days; email arrives on approval or
change request.

- [ ] Production release created
- [ ] Submitted

### Step 5.8: Post-approval TWA check [YOU DO THIS]

Install from Play Store on Android:
- App must open fullscreen with NO browser address bar. If the address bar is visible, assetlinks verification failed -- recheck step 5.5.
- Sign in with Google inside the app to verify auth end to end.

- [ ] Verified on device

## TODO -- post-launch (ongoing)

- [ ] **Maintenance loop** -- keep keystore backups current; regenerate the TWA wrapper when needed (manifest/icon changes); monitor crashes and user feedback in Play Console
- [ ] **Plus listing (future)** -- reuses this playbook with its own package name, its own keystore, assetlinks served at the Plus hostname (stored in GCP Secret Manager, never committed), and the `-plus` Firebase web-config secret; see `PRODUCT_BACKLOG.md` Plus implementation checklist
