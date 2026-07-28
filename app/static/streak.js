'use strict';

// Pure practice-streak helpers, mirrored server-side in core/progress/streak.py
// (merge_streak). Keep the two implementations in sync.
//
// A streak record is { last_day: "YYYY-MM-DD", len: N, grace_used: bool }
// (or null/absent = no streak). "Day" is always the client-local calendar
// day -- the server never computes "today" itself, it only stores/compares
// client-provided day strings.
//
// Streak grace (N2): one free miss per streak -- see core/progress/streak.py
// module docstring for the full rule. `graceEnabled` mirrors
// Settings.streak_grace_enabled; when falsy, bump()/merge() behave exactly
// like the pre-grace implementation (a gap of 2+ days always breaks the
// streak).
(function () {
  function pad2(n) {
    return n < 10 ? '0' + n : String(n);
  }

  // Local calendar day as YYYY-MM-DD. Deliberately NOT toISOString() (UTC).
  function localDay(d) {
    var date = d || new Date();
    return date.getFullYear() + '-' + pad2(date.getMonth() + 1) + '-' + pad2(date.getDate());
  }

  // Number of calendar days between two "YYYY-MM-DD" strings (later - earlier).
  // Computed via Date.UTC so DST transitions never throw off the day count.
  function daysBetween(earlier, later) {
    var a = earlier.split('-').map(Number);
    var b = later.split('-').map(Number);
    var t1 = Date.UTC(a[0], a[1] - 1, a[2]);
    var t2 = Date.UTC(b[0], b[1] - 1, b[2]);
    return Math.round((t2 - t1) / 86400000);
  }

  // True if `later` is exactly one calendar day after `earlier` ("YYYY-MM-DD" strings).
  function isNextDay(earlier, later) {
    return daysBetween(earlier, later) === 1;
  }

  function graceUsed(rec) {
    return !!(rec && rec.grace_used);
  }

  // Bump rule applied when a practice badge is earned.
  //   no record -> {today, 1, grace_used:false}
  //   last_day == today -> unchanged
  //   last_day == yesterday (gap 1) -> {today, len+1, grace_used carried forward}
  //   gap of 2, graceEnabled, grace not yet used -> {today, len+1, grace_used:true}
  //   else -> {today, 1, grace_used:false}
  function bump(rec, todayStr, graceEnabled) {
    var today = todayStr || localDay();
    if (!rec || !rec.last_day) {
      return { last_day: today, len: 1, grace_used: false };
    }
    if (rec.last_day === today) {
      return rec;
    }
    var gap = daysBetween(rec.last_day, today);
    if (gap === 1) {
      return { last_day: today, len: (rec.len || 0) + 1, grace_used: graceUsed(rec) };
    }
    if (gap === 2 && graceEnabled && !graceUsed(rec)) {
      return { last_day: today, len: (rec.len || 0) + 1, grace_used: true };
    }
    return { last_day: today, len: 1, grace_used: false };
  }

  // Merge two streak records without ever shrinking a legitimate streak.
  // Mirrors core/progress/streak.py::merge_streak exactly.
  function merge(a, b, graceEnabled) {
    if (!a) return b || null;
    if (!b) return a;

    if (a.last_day === b.last_day) {
      return { last_day: a.last_day, len: Math.max(a.len, b.len), grace_used: graceUsed(a) || graceUsed(b) };
    }

    var earlier, later;
    if (a.last_day < b.last_day) {
      earlier = a; later = b;
    } else {
      earlier = b; later = a;
    }

    var gap = daysBetween(earlier.last_day, later.last_day);

    if (gap === 1) {
      return {
        last_day: later.last_day,
        len: Math.max(later.len, earlier.len + 1),
        grace_used: graceUsed(earlier) || graceUsed(later),
      };
    }

    if (gap === 2 && graceEnabled && !graceUsed(earlier) && !graceUsed(later)) {
      return { last_day: later.last_day, len: Math.max(later.len, earlier.len + 1), grace_used: true };
    }

    return later;
  }

  // Display rule: only show a streak if it's still "alive" (today or yesterday).
  // Returns 0 (render nothing) once the streak has lapsed. Grace does not
  // change this rule -- a grace-preserved streak already has last_day bumped
  // to today, so it reads as "alive" the normal way.
  function displayLen(rec, todayStr) {
    if (!rec || !rec.last_day) return 0;
    var today = todayStr || localDay();
    if (rec.last_day === today) return rec.len || 0;
    if (isNextDay(rec.last_day, today)) return rec.len || 0;
    return 0;
  }

  window.VerbBoardStreak = {
    localDay: localDay,
    isNextDay: isNextDay,
    daysBetween: daysBetween,
    bump: bump,
    merge: merge,
    displayLen: displayLen,
  };
})();
