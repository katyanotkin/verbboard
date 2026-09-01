'use strict';

(function () {
  // Mirrors core/progress/progress_repository.py's Leitner logic exactly --
  // keep both in lockstep, see tests/test_srs_merge.py for the parity harness.
  const LEITNER_INTERVAL_DAYS = [1, 3, 7, 16, 35];
  const LEITNER_MAX_BOX = LEITNER_INTERVAL_DAYS.length;
  const DAY_MS = 24 * 60 * 60 * 1000;

  function nextBox(currentBox, recalled) {
    if (recalled) {
      return Math.min(currentBox ? currentBox + 1 : 1, LEITNER_MAX_BOX);
    }
    return 1;
  }

  function dueAtMs(box, fromMs) {
    return fromMs + LEITNER_INTERVAL_DAYS[box - 1] * DAY_MS;
  }

  function srsKey(language) {
    return `srs:${language}`;
  }

  function readSrs(language) {
    return window.VerbBoardStorage.readJson(srsKey(language), {});
  }

  function writeSrs(language, map) {
    window.VerbBoardStorage.writeJson(srsKey(language), map);
  }

  // Local-first optimistic update (local state is correct even if the POST
  // below is slow or fails) + a POST to the server, same pattern as
  // VerbBoardProgress.setKnown in auth.js. Callers still await this whole
  // function, so a slow/flaky network does delay the caller's own advance
  // (see learn_practice.js's _advanceAfterRecall) -- same pre-existing
  // behavior as skipBtn/setKnown, not something this file avoids. If the
  // POST fails (offline), the local state still stands; there is no
  // retry/reconciliation of missed offline reviews in this version -- same
  // scope cut as the existing seen/known/badge POSTs, which are also
  // fire-and-forget with no retry.
  async function applyReview(language, verbId, recalled) {
    const map = readSrs(language);
    const current = map[verbId] || { box: 0 };
    const box = nextBox(current.box || 0, recalled);
    const nowMs = Date.now();
    const nowIso = new Date(nowMs).toISOString();
    const dueIso = new Date(dueAtMs(box, nowMs)).toISOString();

    map[verbId] = { box: box, due_at: dueIso, reviewed_at: nowIso };
    writeSrs(language, map);

    if (window.VerbBoardAuth && window.VerbBoardAuth.getIdToken) {
      try {
        const token = await window.VerbBoardAuth.getIdToken();
        if (token) {
          await fetch('/api/progress/review', {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ language: language, verb_id: verbId, recalled: recalled }),
          });
        }
      } catch (_) {}
    }

    return map[verbId];
  }

  // Merge server SRS state into local on hydrate. Unlike known/seen (which
  // union and never delete), SRS state mutates in both directions -- a
  // verb's box and due date must move, not just accumulate -- so this is a
  // last-write-wins-by-reviewed_at merge, not a union. Missing on one side
  // just means "no data yet there"; the side that has data wins outright.
  function mergeFromServer(language, serverVerbs) {
    const local = readSrs(language);
    let changed = false;

    for (const [verbId, state] of Object.entries(serverVerbs || {})) {
      if (!state || !state.srs_box) continue;

      const serverEntry = {
        box: state.srs_box,
        due_at: state.srs_due_at,
        reviewed_at: state.srs_reviewed_at,
      };
      const localEntry = local[verbId];

      if (!localEntry) {
        local[verbId] = serverEntry;
        changed = true;
        continue;
      }

      const serverTime = serverEntry.reviewed_at ? Date.parse(serverEntry.reviewed_at) : 0;
      const localTime = localEntry.reviewed_at ? Date.parse(localEntry.reviewed_at) : 0;

      if (serverTime > localTime) {
        local[verbId] = serverEntry;
        changed = true;
      }
      // else: local is newer or equal -- keep it. (No re-upload-on-reconnect
      // in this version; see applyReview's fire-and-forget note.)
    }

    if (changed) {
      writeSrs(language, local);
    }

    return local;
  }

  function getDueVerbIds(language, nowMs) {
    const map = readSrs(language);
    const now = nowMs || Date.now();
    return Object.keys(map).filter(function (verbId) {
      const entry = map[verbId];
      return entry && entry.box > 0 && Date.parse(entry.due_at) <= now;
    });
  }

  window.VerbBoardSRS = {
    nextBox,
    readSrs,
    writeSrs,
    applyReview,
    mergeFromServer,
    getDueVerbIds,
  };
})();
