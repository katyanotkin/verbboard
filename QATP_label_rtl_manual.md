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
