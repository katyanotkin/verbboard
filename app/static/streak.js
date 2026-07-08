'use strict';

// Pure practice-streak helpers, mirrored server-side in core/progress/streak.py
// (merge_streak). Keep the two implementations in sync.
//
// A streak record is { last_day: "YYYY-MM-DD", len: N } (or null/absent = no streak).
// "Day" is always the client-local calendar day -- the server never computes
// "today" itself, it only stores/compares client-provided day strings.
(function () {
  function pad2(n) {
    return n < 10 ? '0' + n : String(n);
  }

  // Local calendar day as YYYY-MM-DD. Deliberately NOT toISOString() (UTC).
  function localDay(d) {
    var date = d || new Date();
    return date.getFullYear() + '-' + pad2(date.getMonth() + 1) + '-' + pad2(date.getDate());
  }

  // True if `later` is exactly one calendar day after `earlier` ("YYYY-MM-DD" strings).
  // Computed via Date.UTC so DST transitions never throw off the day count.
  function isNextDay(earlier, later) {
    var a = earlier.split('-').map(Number);
    var b = later.split('-').map(Number);
    var t1 = Date.UTC(a[0], a[1] - 1, a[2]);
    var t2 = Date.UTC(b[0], b[1] - 1, b[2]);
    return (t2 - t1) === 86400000;
  }

  // Bump rule applied when a practice badge is earned.
  //   no record -> {today, 1}
  //   last_day == today -> unchanged
  //   last_day == yesterday -> {today, len+1}
  //   else -> {today, 1}
  function bump(rec, todayStr) {
    var today = todayStr || localDay();
    if (!rec || !rec.last_day) {
      return { last_day: today, len: 1 };
    }
    if (rec.last_day === today) {
      return rec;
    }
    if (isNextDay(rec.last_day, today)) {
      return { last_day: today, len: (rec.len || 0) + 1 };
    }
    return { last_day: today, len: 1 };
  }

  // Merge two streak records without ever shrinking a legitimate streak.
  // Mirrors core/progress/streak.py::merge_streak exactly.
  function merge(a, b) {
    if (!a) return b || null;
    if (!b) return a;

    if (a.last_day === b.last_day) {
      return { last_day: a.last_day, len: Math.max(a.len, b.len) };
    }

    var earlier, later;
    if (a.last_day < b.last_day) {
      earlier = a; later = b;
    } else {
      earlier = b; later = a;
    }

    if (isNextDay(earlier.last_day, later.last_day)) {
      return { last_day: later.last_day, len: Math.max(later.len, earlier.len + 1) };
    }

    return later;
  }

  // Display rule: only show a streak if it's still "alive" (today or yesterday).
  // Returns 0 (render nothing) once the streak has lapsed.
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
    bump: bump,
    merge: merge,
    displayLen: displayLen,
  };
})();
