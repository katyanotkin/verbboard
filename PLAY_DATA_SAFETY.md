# VerbBoard -- Google Play Data Safety Worksheet

Reference doc for filling out Play Console > Policy > App content > Data safety.
Derived from actual code (grepped, not guessed) as of 2026-07-31. Linked from
`GOOGLE_PLAY_CHECKLIST.md` step 5.6. Re-verify against the code if a data
type is added/removed before you re-submit this form.

---

## Step 3: Data types -- category-by-category selections

### Personal info -- select 4 (Name, Email address, User IDs, Other info)

**Name** (Google display name)
- Collected: Yes / Shared: No / Processed ephemerally: No / Required: only if user signs in (optional feature)
- Purposes: App functionality, Account management
- Description: "Your display name is stored when you sign in with Google so we can identify your account and sync your learning progress across devices."

**Email address**
- Collected: Yes / Shared: No / Ephemeral: No / Required: only if signing in
- Purposes: App functionality, Account management
- Description: "Your email address is stored when you sign in with Google, used to identify your account and, if you contact us via the feedback form, to reply to you."
- Note: "Developer communications" deliberately NOT checked -- no code sends unsolicited emails/newsletters.

**User IDs** (Firebase `uid`)
- Collected: Yes / Shared: No / Ephemeral: No / Required: only if signing in
- Purposes: App functionality, Account management
- Description: "A unique account identifier is used internally to store and retrieve your learning progress, practice badges, and (if applicable) subscription entitlement."

**Other info** (Google account profile picture URL)
- Collected: Yes / Shared: No / Ephemeral: No / Required: only if signing in
- Purposes: App functionality, Account management
- Description: "If you sign in with Google, we store a link to your Google profile picture to display it in the app. We never download or store the image itself -- it's rendered directly from Google's servers (`referrerPolicy=no-referrer`)."
- Not filed under "Photos and videos": that category covers photos/videos your app collects from the device camera/gallery or that users upload. This is a pass-through URL to an image Google already hosts -- no image bytes ever touch VerbBoard's servers.

### App activity -- select 3 of 5

**App interactions** -- Yes
- Collected: Yes / Shared: No / Ephemeral: No / Required: Yes (automatic, not user-optional)
- Purposes: Analytics, App functionality
- Description: "We log which pages are visited (home, verb list, learn, feedback) and device type to understand app usage and improve performance. This is anonymous unless you're signed in, in which case your account ID may be attached to that day's session."
- Source: `app/main.py` `_PageViewMiddleware`, `core/analytics/session_tracker.py` -- writes to Firestore `analytics_sessions`.

**In-app search history** -- Yes
- Collected: Yes / Shared: No / Ephemeral: No / Required: Yes (automatic on a failed search)
- Purposes: Analytics, App functionality
- Description: "When a search doesn't match an existing verb, the search term is logged (without any account link) so we know which verbs to prioritize adding next. Successful searches are not logged."
- Source: `core/admin_logging.py` `log_missing_verb_search()` -- writes to Firestore `demand_signal`.

**Other user-generated content** (feedback comment + poll answer) -- Yes
- Collected: Yes / Shared: No / Ephemeral: No / Required: No (voluntary submission)
- Purposes: App functionality, Analytics (poll)
- Description: "If you submit feedback, the comment text and poll answer you provide are stored to help us improve the app. This is not linked to your account unless you include identifying information in the message or reply-to email."
- Source: `app/routes/feedback.py`, `core/feedback_store.py` -- writes to Firestore `feedback`.

**Installed apps** -- No. No `PackageManager`/`getInstalledPackages` code anywhere (grep-confirmed).

**Other actions** -- No. No generic click/action telemetry beyond what's covered above. (Known/seen verb marks and practice badges exist but are already disclosed under Personal info as account-linked progress data, not filed here.)

Across all three collected App activity types: **Advertising or marketing**, **Fraud prevention/security/compliance**, and **Personalization** were deliberately left unchecked -- no ad SDK, no marketing pixel, no abuse-detection system, and nothing currently tailors content based on this data.

### Everything else on Step 3 -- all unchecked (0)

| Category | Why not |
|---|---|
| Financial info (0/4) | `core/entitlements.py` has a billing-fields schema (`product_id`/`purchase_token`/`order_id`/`expires_at`) but it's Phase 1 -- manual admin-only grants, those fields are always seeded `None`. No live Play Billing integration yet. **Revisit when Plus billing ships.** |
| Health and fitness (0/2) | No matches beyond the unrelated `/health` liveness route. |
| Messages (0/3) | No chat/messaging feature. |
| Photos and videos (0/2) | See "Other info" above -- URL only, no image bytes collected. |
| Audio files (0/3) | All audio is server-generated TTS, cached in GCS. No microphone access, no user-uploaded audio. |
| Files and docs (0/1) | No file-upload input anywhere. |
| Calendar (0/1) | No calendar code. |
| Contacts (0/1) | No contacts API usage. |
| Web browsing (0/1) | `document.referrer` checks are internal-only (deciding back-button behavior from `/learn` or `/feedback`), not a log of external sites visited. |
| App info and performance (0/3: Crash logs, Diagnostics, Other) | No Crashlytics, Sentry, GA4/gtag, or any crash/diagnostics SDK in client or server code. |
| Device or other IDs (0/1) | No FCM registration ID, no Android Advertising ID, no persistent device identifier. `firebase_web_config_json` is Auth-config only (apiKey/authDomain/projectId), not a device ID. |

---

## Notes

- Update this doc (and re-check the code) before resubmitting the Data Safety
  form if: Plus billing goes live (Financial info), a crash-reporting SDK is
  added (App info and performance), or any new client-side data collection
  is introduced.
- Cross-reference: `https://verbboard.com/privacy` should stay consistent
  with whatever is declared here -- it currently covers login data, progress
  tracking, anonymous analytics, and feedback, which matches this worksheet.
