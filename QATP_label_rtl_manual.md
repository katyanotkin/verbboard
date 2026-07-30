# QATP: Label copy rename + RTL known-button fix (manual)

Commit: `359eee1`. Run against stage after deploy. Covers what automated tests don't: real visual rendering across viewports/RTL on live stage data.

Automated coverage already in place (do not re-test manually): i18n key parity across all 4 locales (`tests/test_i18n.py`), SW cache version bump (`tests/test_safe_return_and_privacy.py`).

**Setup:** `https://stage.verbboard.com`, any verb with a board page, in each of en/ru/es/he.

---

## A. "Discard practice" wording

**TC-1:** Start a practice session (any language). Check the abandon button reads:
- EN "Discard practice" / RU "Отменить тренировку" / ES "Descartar práctica" / HE "בטל תרגול"

Click it -- confirm it still exits to `/verbs` without saving progress (behavior unchanged, wording only).

## B. Learned-star copy ("already known regardless of source")

**TC-2:** Open any verb's board (`/learn`) page. Caption next to the star button should read:
- EN "Already know this" / RU "Уже знаю" / ES "Ya lo sé" / HE "מוכר"

Click the star to toggle. Expected: caption text stays the same in both states (intentional -- single static string now), but the star visually fills/unfills gold.

## C. RTL known-button overflow (the real bug fixed here)

**TC-3:** `he` UI language (`?ui_language=he`), any verb's board page, at 375px width (or a real phone). Confirm the star button + caption are fully on-screen -- not cut off past the right edge.

This was broken before this fix: `.func-panel`'s RTL rule fought its own column layout and pushed the whole control off-canvas for every Hebrew user. If it's still off-canvas, this is a real regression, not a pre-existing known issue.

## D. LTR regression check

**TC-4:** Same board page in en/ru/es. Confirm layout is pixel-identical to before -- voice toggle + star button still stacked, no shift, no wrap.

---

Not testable in-app: the Play-listing copy change ("no gamification pressure" -> "no pressure to log in daily") is docs-only (`GOOGLE_PLAY_CHECKLIST.md`), nothing in the running app to check.

---

# QATP addendum: self-serve account deletion + practice-panel help link (manual)

Commits: `fe506c8`..`c45ea41`. Covers self-serve account deletion (a real, irreversible action -- test with a throwaway/test account, not your main one, unless you're intentionally deleting it) and the new "PRACTICE ?" help affordance.

Automated coverage already in place (do not re-test manually): route auth/success/failure paths, deletion-order pinning, per-module repository/entitlement/session unit tests (`tests/test_account_api.py`, `tests/test_account_deletion.py`, plus additions to `test_progress_repository.py`/`test_entitlements.py`/`test_session_tracker.py`).

## E. Self-serve account deletion

**TC-5:** Sign in with a real Google account you're OK deleting data for. Use the app a bit (mark a verb known, do a practice session) so there's real data to delete. Go to `/privacy`, confirm the "Delete my account and data" button is visible (only when signed in -- sign out and reload to confirm it disappears, sign back in to confirm it reappears).

**TC-6:** Click the delete button. Expected: a confirm() dialog with unambiguous "permanent, cannot be undone" wording in your current UI language. Cancel it -- nothing should happen. Click it again and confirm -- expected: success alert, then signed out automatically. Sign back in with the same account: progress/known-verbs/badges should all be gone (fresh account state).

**TC-7 (regression):** On `/privacy`, confirm there's no leftover mention of emailing for deletion -- the button is now the only path described.

## F. Practice-panel "PRACTICE ?" help link

**TC-8:** On `/verbs`, in the practice panel, the "PRACTICE" title should now read "PRACTICE ?" with a small de-emphasized question mark (not a circular badge, shouldn't look like a 3rd medal next to the streak-badge row). Click anywhere on "PRACTICE" (the whole label, not just the "?") -- expected: navigates to `/about` and jumps straight to the Practice section (heading "Тренировка" in Russian, matching the body text -- not "Практика"), not just the top of the page.

**TC-9:** Start a practice session so the panel is in the "in progress" state (shows X/Y visited count instead of the size/listens pickers). Confirm "PRACTICE ?" is still there and still links correctly in this state too (this was inconsistent before the fix -- only the picker state had it).

**TC-10:** Check at 375px and in Hebrew (RTL) -- confirm no layout shift/overflow, and the "?" sits naturally next to the label in both directions.

Not testable in-app: package/Play Console submission status (steps 5.4-5.8) has no in-app surface to check.
