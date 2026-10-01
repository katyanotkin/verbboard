document.addEventListener("DOMContentLoaded", function () {
  const pageRoot = document.getElementById("learn-page");
  if (!pageRoot) return;

  const language = pageRoot.dataset.language;
  const verbId = pageRoot.dataset.verbId;
  if (!language || !verbId) return;

  // Resolved lazily so a missing helper fails loudly where URLs are built,
  // not at script load.
  function _nav() {
    const nav = window.VerbBoardNav;
    if (!nav) {
      throw new Error('nav_urls.js must be loaded before learn_practice.js');
    }
    return nav;
  }

  const progress = window.VerbBoardProgress;
  if (!progress) return;

  const seenKey = `seen:${language}`;
  const audioPlaysKey = `audio_plays:${language}`;
  const sessionKey = `practice_session:${language}`;
  const badgesKey = `practice_badges:${language}`;

  const _minPlaysRaw = parseInt(localStorage.getItem('practice_min_plays'), 10);
  const PRACTICE_MIN_PLAYS = (_minPlaysRaw >= 1 && _minPlaysRaw <= 12) ? _minPlaysRaw : 5;

  // Fire-and-forget, auth-independent practice engagement beacon (issue
  // #48) -- must never block or fail the actual practice flow, same
  // try/catch + .catch(() => {}) idiom as auth.js's _trackSignInTapped().
  function _trackPracticeEvent(event) {
    try {
      fetch('/api/analytics/practice_event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event: event }),
        keepalive: true,
      }).catch(function () {});
    } catch (_) {}
  }

  function _audioProgressHtml() {
    let plays;
    try { plays = JSON.parse(localStorage.getItem(audioPlaysKey) || '{}'); } catch (_) { plays = {}; }
    return '<span class="practice-note-icon">♪</span> ' + Math.min(plays[verbId] || 0, PRACTICE_MIN_PLAYS) + ' / ' + PRACTICE_MIN_PLAYS;
  }

  let practiceSession;
  try {
    practiceSession = JSON.parse(localStorage.getItem(sessionKey));
  } catch (_) {
    practiceSession = null;
  }

  if (
    practiceSession &&
    Array.isArray(practiceSession.ids) &&
    practiceSession.ids.length > 0
  ) {
    const idx = practiceSession.ids.indexOf(verbId);
    if (idx !== -1) {
      _mountPracticeBar(practiceSession, idx);
    }
  }

  function _mountPracticeBar(session, idx) {
    const UI = window.UI || {};
    const verbsUrl = _nav().verbsUrl(language);
    const sessionTotal = session.size || session.ids.length;
    const skippedSoFar = sessionTotal - session.ids.length;
    const total = session.ids.length;
    const isLast = idx === total - 1;
    const isRTL = document.documentElement.dir === 'rtl';
    // Absent 'modes' map (sessions started before spaced repetition shipped)
    // must fall back to ordinary practice -- see practice_loop.js.
    const mode = (session.modes && session.modes[verbId]) || 'new';
    const isReview = mode === 'review';

    const bar = document.createElement("div");
    bar.className = "practice-bar";

    const prevBtn = document.createElement("button");
    prevBtn.className = "practice-nav-btn";
    prevBtn.textContent = isRTL ? '>' : '<';
    prevBtn.setAttribute('aria-label', UI["practice.prev"] || "Previous");
    prevBtn.disabled = idx === 0;

    const progressEl = document.createElement("span");
    progressEl.className = "practice-progress";
    progressEl.textContent = `${skippedSoFar + idx + 1}/${sessionTotal}`;

    const audioCounterEl = document.createElement("span");
    audioCounterEl.className = "practice-audio-counter";
    audioCounterEl.innerHTML = _audioProgressHtml();

    const progressWrapper = document.createElement("div");
    progressWrapper.className = "practice-progress-wrapper";
    progressWrapper.appendChild(progressEl);
    progressWrapper.appendChild(audioCounterEl);

    const abandonBtn = document.createElement("button");
    abandonBtn.className = "practice-abandon-btn";
    abandonBtn.textContent = UI["practice.abandon"] || "Discard practice";

    const warnEl = document.createElement("span");
    warnEl.className = "practice-listen-warn";
    warnEl.hidden = true;

    // Review verbs: the recall self-report IS the advance action. There is
    // no in-session down-signal at all -- a verb that isn't actually known
    // gets addressed elsewhere (unstarring resets its SRS state; ordinary
    // seen/known repeat-candidate logic resurfaces it), not via a recall
    // button press here.
    //
    // New-mode verbs: nextBtn is the only advance control. There used to
    // also be a "Skip & mark as learned" button that bypassed the listen
    // gate and removed the verb from the session immediately; it was
    // removed entirely (owner decision 2026-09-28) because its wording was
    // confusing next to the star's "known" language and the bypass wasn't
    // worth a dedicated control. Marking a verb known without going through
    // the practice flow is still possible via the star button on the board
    // page itself.
    let nextBtn, recallYesBtn;

    if (isReview) {
      recallYesBtn = document.createElement("button");
      recallYesBtn.className = "practice-recall-btn practice-recall-btn--yes";
      recallYesBtn.textContent = UI["practice.recall_yes"] || "Recalled it";
    } else {
      nextBtn = document.createElement("button");
      nextBtn.className = "practice-nav-btn practice-nav-btn--primary";
      if (isLast) {
        nextBtn.classList.add("practice-nav-btn--finish");
        nextBtn.textContent = "\u2713 " + (UI["practice.finish"] || "Finish");
        nextBtn.setAttribute('aria-label', UI["practice.finish"] || "Finish");
      } else {
        nextBtn.textContent = isRTL ? '<' : '>';
        nextBtn.setAttribute('aria-label', UI["practice.next"] || "Next");
      }
    }

    bar.appendChild(prevBtn);
    bar.appendChild(progressWrapper);
    bar.appendChild(abandonBtn);
    bar.appendChild(isReview ? recallYesBtn : nextBtn);
    bar.appendChild(warnEl);

    const topbar = pageRoot.querySelector(".topbar");
    if (topbar && topbar.nextSibling) {
      pageRoot.insertBefore(bar, topbar.nextSibling);
    } else {
      pageRoot.insertBefore(bar, pageRoot.firstChild);
    }

    function navTo(targetId) {
      window.location.href = _nav().learnUrl(language, targetId, { returnTo: verbsUrl });
    }

    function hasListened() {
      let plays;
      try { plays = JSON.parse(localStorage.getItem(audioPlaysKey) || "{}"); } catch (_) { plays = {}; }
      return (plays[verbId] || 0) >= PRACTICE_MIN_PLAYS;
    }

    function _showCompletionAndRedirect(completionSession) {
      const n = completionSession.size || total;
      progressEl.textContent = `${n}/${n}!`;
      progressEl.classList.add('practice-progress--done');
      progressEl.classList.add('practice-progress--done-pulse');
      prevBtn.disabled = true;
      abandonBtn.disabled = true;
      if (isReview) {
        recallYesBtn.disabled = true;
      } else {
        nextBtn.disabled = true;
      }
      const delay = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 1200;
      setTimeout(function () { _finishPractice(completionSession, progressEl); }, delay);
    }

    // Last new-mode verb: the Finish pill stays dimmed (aria-disabled, not
    // `disabled`, so a tap still shows the listen warning) until the audio
    // goal is met, then eases to full emphasis.
    function syncFinishState() {
      if (!nextBtn || !isLast) return;
      const ready = hasListened();
      nextBtn.setAttribute('aria-disabled', ready ? 'false' : 'true');
      nextBtn.classList.toggle('practice-nav-btn--pending', !ready);
    }
    syncFinishState();

    window.addEventListener('vb:learn-audio-played', function () {
      audioCounterEl.innerHTML = _audioProgressHtml();
      syncFinishState();
    });

    let warnTimer;
    function showWarn() {
      warnEl.textContent = UI["practice.listen_first"] || "Listen to audio";
      warnEl.hidden = false;
      clearTimeout(warnTimer);
      warnTimer = setTimeout(function () { warnEl.hidden = true; }, 2500);
    }

    prevBtn.addEventListener("click", function () {
      if (idx > 0) navTo(session.ids[idx - 1]);
    });

    if (isReview) {
      // Deliberately NOT gated behind hasListened(): this button is a
      // recall self-report on a verb the learner already starred as known,
      // and forcing PRACTICE_MIN_PLAYS audio replays before allowing "Knew
      // it" would force-feed the answer right before asking the learner to
      // self-report whether they already knew it -- backwards for a recall
      // test, unlike the ordinary new-verb Next button below (nextBtn),
      // where forcing repeated listens up front is the actual intended
      // first-exposure drill. Audio stays available as an optional aid
      // (play button unchanged); it just isn't a prerequisite here. (Was
      // gated behind hasListened() pre-2026-09-28; removed after this
      // behaved as an invisible dead end in practice -- no Skip fallback in
      // review mode, so a learner short of the listen count had no way to
      // advance at all except an easy-to-miss warning.)
      //
      // Always applyReview(..., true): "Recalled it" is the only control here
      // (owner decision 2026-09-28, see comment above) -- there is no
      // recalled=false path, by design.
      async function _advanceAfterKnew() {
        if (window.VerbBoardSRS) {
          await window.VerbBoardSRS.applyReview(language, verbId, true);
        }
        if (isLast) {
          _showCompletionAndRedirect(session);
        } else {
          navTo(session.ids[idx + 1]);
        }
      }

      recallYesBtn.addEventListener("click", function () { _advanceAfterKnew(); });
    } else {
      nextBtn.addEventListener("click", async function () {
        if (!hasListened()) {
          showWarn();
          return;
        }
        if (isLast) {
          _showCompletionAndRedirect(session);
          return;
        } else {
          navTo(session.ids[idx + 1]);
        }
      });
    }

    abandonBtn.addEventListener("click", function () {
      localStorage.removeItem(sessionKey);
      window.location.href = verbsUrl;
    });
  }

  async function _finishPractice(session, capsuleEl) {
    if (!localStorage.getItem(sessionKey)) {
      window.location.href = _nav().verbsUrl(language);
      return;
    }
    let accomplished = false;
    try {
      const seenSet = progress.readSet(seenKey);
      let plays;
      try { plays = JSON.parse(localStorage.getItem(audioPlaysKey) || "{}"); } catch (_) { plays = {}; }
      accomplished = session.ids.every(function (id) {
        if (!seenSet.has(id)) return false;
        // Review-mode verbs no longer require PRACTICE_MIN_PLAYS listens to
        // advance (see _advanceAfterKnew above) -- the recall self-report
        // itself is the completion signal for those, so don't also demand
        // the listen count here or badge completion would silently regress
        // for any session containing review verbs.
        const mode = (session.modes && session.modes[id]) || 'new';
        if (mode === 'review') return true;
        return (plays[id] || 0) >= PRACTICE_MIN_PLAYS;
      });
    } catch (_) {}

    if (accomplished) {
      _trackPracticeEvent('completed');

      let badges;
      try { badges = JSON.parse(localStorage.getItem(badgesKey) || "[]"); } catch (_) { badges = []; }

      badges.push(session.size || session.ids.length);
      localStorage.setItem(badgesKey, JSON.stringify(badges));

      // Login-nudge signal: a completed practice session / earned badge is
      // the strongest engagement signal (+10) and, unless the lifetime show
      // cap has already been hit, always fires the prompt -- but the actual
      // wrap-up modal (where the CTA renders) only mounts after the
      // redirect to /verbs below, so the eligibility decision made here has
      // to travel with the wrapup payload (see practice_wrapup below and
      // showWrapUp() in practice_loop.js).
      let showLoginNudge = false;
      if (window.VerbBoardLoginNudge) {
        showLoginNudge = window.VerbBoardLoginNudge.recordBadgeEarned();
      }

      const practicePostBody = { language: language, badges: badges };

      if (window.VerbBoardAuth && window.VerbBoardAuth.getIdToken) {
        try {
          const token = await window.VerbBoardAuth.getIdToken();
          if (token) {
            await fetch("/api/progress/practice", {
              method: "POST",
              headers: {
                Authorization: "Bearer " + token,
                "Content-Type": "application/json",
              },
              body: JSON.stringify(practicePostBody),
            });
          }
        } catch (_) {}
      }

      localStorage.setItem(
        `practice_wrapup:${language}`,
        JSON.stringify({
          ids: session.ids,
          lemmas: session.lemmas || {},
          loginNudge: showLoginNudge,
        })
      );
    } else if (capsuleEl) {
      const UI = window.UI || {};
      capsuleEl.textContent = UI["practice.no_badge"] || "No badge";
      capsuleEl.classList.remove("practice-progress--done-pulse");
      capsuleEl.classList.add("practice-progress--no-badge");
      await new Promise(function (r) { setTimeout(r, 1500); });
    }

    localStorage.removeItem(sessionKey);
    window.location.href = _nav().verbsUrl(language);
  }
});
