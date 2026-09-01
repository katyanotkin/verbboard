# QATP: Anki-style spaced repetition (manual)

Commits: `67a3340`..`cbcdd60`. Run against stage after deploy. Covers what automated tests don't: real cross-device sync behavior, real practice-session flow across languages/RTL, and anything that depends on wall-clock due dates (which the unit/parity tests fake, but a manual pass should see resurface for real at least once).

Automated coverage already in place (do not re-test manually): Leitner box-transition math and its JS/Python parity (`tests/test_srs_merge.py`), the last-write-wins merge logic itself (`test_srs_js_python_parity`/merge cases in the same file), `set_known`/`record_review` Firestore payload shape (`tests/test_progress_repository.py`), the `/api/progress/review` endpoint and extended `GET /api/progress` (`tests/test_progress_api.py`), i18n key parity across all 4 locales, SW cache version bump (`tests/test_safe_return_and_privacy.py`).

**Setup:** `https://stage.verbboard.com`, signed in with a real Google account (SRS state only persists server-side when signed in -- anonymous/local-only use still works but has nothing to cross-device-test). Any study language works for the box-ladder mechanics; test the recall-button copy in each of en/ru/es/he. Chrome DevTools console open throughout -- several test cases need it to fast-forward due dates without waiting real days.

---

## A. Entering the ladder

**TC-1:** Open any verb's board page (`/learn`), tap the learned-star to mark it known. In DevTools console, run `JSON.parse(localStorage.getItem('srs:' + <lang>))` (e.g. `srs:en`) -- confirm the verb's id now has an entry: `{box: 1, due_at: <~tomorrow, ISO>, reviewed_at: <~now, ISO>}`.

**TC-2:** Go to `/verbs`, start a practice session, use "Skip & mark as learned" on a verb instead of the star. Same check as TC-1 -- skip must also start the ladder, not just the star toggle.

**TC-3 (no double-init):** Toggle the same verb's star off then on again. Confirm `box`/`due_at`/`reviewed_at` in localStorage are **unchanged** from before the toggle -- re-marking known must not reset ladder progress.

## B. Due-verb resurfacing in a practice session

Real due dates are 1+ days out, so force it: in DevTools console, pick a verb you've marked known (from TC-1) and backdate it so it's already due --

```js
const lang = 'en'; // or whichever
const key = 'srs:' + lang;
const map = JSON.parse(localStorage.getItem(key));
const id = Object.keys(map)[0]; // or a specific verb id
map[id].due_at = new Date(Date.now() - 60000).toISOString(); // 1 min ago
localStorage.setItem(key, JSON.stringify(map));
```

**TC-4:** Reload `/verbs`. The practice panel should now show a due-count line ("N due for review today" / translated equivalent) that wasn't there before.

**TC-5:** Start a practice session sized 6 or 9 (gives the ~1/3 cap room to include at least one review verb). On the verb you backdated, the practice bar should show **two pill buttons** ("Knew it" / "Show me again" -- translated per UI language) **instead of** the usual ‹ Prev / Skip / › Next row. Confirm `skipBtn` is genuinely gone for this verb, not just relabeled.

**TC-6:** On a different verb in the same session that is *not* due for review, confirm the practice bar looks completely normal (Prev/Skip/Next, no recall buttons) -- mode tagging shouldn't leak across verbs in the same session.

## C. Recall self-report

**TC-7 ("Knew it"):** On the due verb from TC-5, listen to the audio the required number of times (same gate as Next), then tap "Knew it". Confirm it advances to the next verb in the session (same as Next normally would). Check localStorage: `box` incremented by 1 from before, `due_at` moved further out, `reviewed_at` ~now.

**TC-8 ("Show me again"):** Repeat with a different due verb, tap "Show me again" instead. Confirm it *also* advances (does not repeat the verb later in the same session -- this is deliberate, not a bug). Check localStorage: `box` reset to `1`, `due_at` ~tomorrow.

**TC-9 (listen gate applies to both):** On a due verb, tap a recall button *before* listening the required number of times. Confirm it's blocked with the same "Listen to the audio first" warning Next normally shows, and localStorage is unchanged (no review recorded).

## D. Cross-device sync (last-write-wins)

This is the highest-risk piece of the whole feature (SRS state moves in both directions across devices, unlike the rest of progress sync) -- worth the extra care.

**TC-10:** Sign in as the same account in two different browsers (or one normal + one incognito/private window signed in separately). On device A, review a due verb ("Knew it"). Reload `/verbs` on device B. Confirm device B's localStorage for that verb now shows device A's newer `box`/`due_at`/`reviewed_at` (check via the same console snippet as TC-1).

**TC-11 (reverse order doesn't matter):** On device B, review the *same* verb again ("Show me again"). Reload on device A. Confirm device A picks up device B's newer state (box back to 1).

**TC-12 (offline device isn't silently clobbered):** On device A, go offline (DevTools > Network > Offline), review a verb. Confirm the local state still updates immediately (optimistic update) even though the POST can't reach the server. Go back online, reload -- the local review is not retried/re-uploaded (this is a known, deliberate scope cut, not a bug); the point of this case is just confirming the local UI didn't hang or error while offline.

## E. Backward compatibility

**TC-13:** In DevTools console, hand-craft an old-format session (simulating one started before this feature shipped): `localStorage.setItem('practice_session:en', JSON.stringify({ids: ['en_go'], lemmas: {en_go: 'go'}, size: 3}))` -- note, no `modes` key at all. Navigate to `/learn?language=en&verb_id=en_go`. Confirm the practice bar behaves exactly like before this feature (Prev/Skip/Next, no recall buttons, no crash).

## F. Localization + layout

**TC-14:** Repeat TC-5 through TC-8 with `?ui_language=ru`, `?ui_language=es`, and `?ui_language=he`. Confirm recall-button labels are translated (RU: "Помню"/"Не помню", ES: "Lo sabía"/"Muéstramelo otra vez", HE: "ידעתי"/"הראה לי שוב") and the "N due for review today" line is translated and doesn't read grammatically broken for a few different counts (1, 2, 5 due) -- Russian in particular was deliberately phrased to dodge numeral-agreement issues, worth confirming it actually reads naturally rather than just "not crashing."

**TC-15:** Hebrew (`he`) at 375px width, RTL: confirm the two recall pill buttons are mirrored correctly (visually: "Show me again" on the right, "Knew it" on the left, matching RTL reading order) and don't overflow/wrap awkwardly.

**TC-16:** Spanish at 375px: "Muéstramelo otra vez" is the longest of the four languages' button labels -- confirm it fits on one line without clipping or forcing the button row to wrap in a broken way.

---

Not testable in-app: the read-then-write race condition noted in the decision log (`docs/decisions/2026-09-01-spaced-repetition-autonomous-run.md`) requires two genuinely simultaneous requests within the same round-trip window and isn't practically reproducible by hand -- it's a known, accepted, low-severity gap, not something to chase in manual QA.
