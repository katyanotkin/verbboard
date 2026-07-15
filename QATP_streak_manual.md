# QATP: Practice Day-Streak (manual)

Commit: `63ed83e`. Covers what automated tests cannot: real multi-day behavior, live audio sessions, multi-device merge, PWA cache rollover.

Automated coverage already in place (do not re-test manually): merge/bump edge cases incl. month/year/leap boundaries (`tests/test_streak_merge.py`, JS/Python parity), API validation and no-shrink merge (`tests/test_progress_api.py`), legacy-doc defaults (`tests/test_progress_repository.py`).

**Setup:** a device with the app, one language with 3+ unlearned verbs. "Complete a session" = start practice (size 3), play audio the required number of times per verb, press Next through all verbs. To inspect state: DevTools > Application > Local Storage > key `practice_streak:{lang}`.

---

## A. Core flow (single device, anonymous)

**TC-ST1: first session creates streak**
1. Fresh state (no `practice_streak:{lang}` key). Complete a session.
2. Expected: wrap-up modal shows "Day streak: 🔥 1". Back on /verbs, practice panel header shows a small orange 🔥 1 chip next to PRACTICE. localStorage has `{"last_day":"<today>","len":1}`.

**TC-ST2: second session same day does not inflate**
1. Same day, complete another session.
2. Expected: still 🔥 1 everywhere. `len` unchanged in localStorage.

**TC-ST3: next-day session increments** (needs a real overnight, or set device clock +1 day)
1. Complete a session the following day.
2. Expected: 🔥 2 in wrap-up and chip.

**TC-ST4: grace day display**
1. With a streak earned yesterday, open /verbs today WITHOUT practicing.
2. Expected: chip still shows the streak (alive on grace day). It must NOT show 🔥 0.

**TC-ST5: broken streak hides chip**
1. Skip 2+ days (or set `last_day` in localStorage to 3 days ago), reload /verbs.
2. Expected: no chip at all (not 🔥 0). Completing a session then restarts at 🔥 1.

## B. Login and multi-device merge

**TC-ST6: anonymous streak survives sign-in**
1. Earn a streak while logged out. Sign in.
2. Expected: chip value unchanged or higher after hydration, never lower. Firestore doc `user_practice/{uid}/languages/{lang}` gains `streak_last_day`/`streak_len`.

**TC-ST7: streak follows you to a clean device**
1. With a server streak from TC-ST6, open the app on a second device (or incognito), sign in, visit /verbs.
2. Expected: chip appears with the server streak after login without practicing on this device.

**TC-ST8: stale device cannot regress the server**
1. Device A has streak 5 (today). Device B has an old local streak (e.g. len 1, three days ago). Sign in on B.
2. Expected: B shows 5 after sync; Firestore still has 5 afterwards.

**TC-ST9: sign-out clears local streak**
1. Sign out on a device with a visible chip.
2. Expected: chip gone after reload (localStorage key removed), server value intact (verify by signing back in).

## C. Localization and layout

**TC-ST10: label localization**
1. With an alive streak, hover the chip (desktop) in each ui_language: en/ru/he/es.
2. Expected tooltips: "Day streak" / "Дней подряд" / "ימים ברצף" / "Días seguidos". Wrap-up line uses the same label.

**TC-ST11: RTL + 375px**
1. Hebrew UI on a narrow phone (or 375px devtools), alive streak, practice panel with several badges.
2. Expected: chip sits next to תרגול, flame mirrored to the correct side, no horizontal overflow; badges wrap to a second row if tight.

## D. PWA / deploy rollover

**TC-ST12: returning PWA user gets the feature**
1. On a device that had the PREVIOUS version installed as PWA, open the app after this deploy, then close and reopen once (SW cache vb-v21 -> vb-v22 swap).
2. Expected: streak works (complete a session, chip appears). No console errors about `VerbBoardStreak` undefined. This is the failure mode the cache bump exists to prevent.

## E. Robustness spot-checks

**TC-ST13: garbage localStorage does not break the page**
1. Set `practice_streak:{lang}` to `{broken` via DevTools console, reload /verbs.
2. Expected: page renders normally, no chip, no JS errors.

**TC-ST14: abandoned session earns nothing**
1. Start a session, abandon it (or leave audio plays short of the minimum).
2. Expected: no badge, no streak bump, no wrap-up streak line.
