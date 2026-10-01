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

    // Every verb gets nextBtn (listen-gated, no SRS effect). Review-mode
    // verbs additionally get recallYesBtn, the only control that promotes the
    // SRS box and the visual primary; there, nextBtn is a secondary
    // (outlined) "I'm not sure, let me listen and move on" path. This is
    // deliberately NOT the removed "Show me again" down-signal: it never
    // touches the box. There is still no demote action in-session (unstar to
    // leave the ladder). "Skip & mark as learned" stays removed (2026-09-28).
    let recallYesBtn;

    const nextBtn = document.createElement("button");
    nextBtn.className = "practice-nav-btn" + (isReview ? "" : " practice-nav-btn--primary");
    if (isLast) {
      nextBtn.classList.add("practice-nav-btn--finish");
      nextBtn.textContent = "\u2713 " + (UI["practice.finish"] || "Finish");
      nextBtn.setAttribute('aria-label', UI["practice.finish"] || "Finish");
    } else {
      nextBtn.textContent = isRTL ? '<' : '>';
      nextBtn.setAttribute('aria-label', UI["practice.next"] || "Next");
    }

    if (isReview) {
      recallYesBtn = document.createElement("button");
      recallYesBtn.className = "practice-recall-btn practice-recall-btn--yes";
      recallYesBtn.textContent = UI["practice.recall_yes"] || "Recalled it";
    }

    bar.appendChild(prevBtn);
    bar.appendChild(progressWrapper);
    bar.appendChild(abandonBtn);
    bar.appendChild(nextBtn);
    if (isReview) bar.appendChild(recallYesBtn);
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

    // Set synchronously at the start of every advancing click, before any
    // await, so a second tap (recall twice, or recall then Finish while
    // applyReview is in flight) cannot advance or complete twice.
    let advancing = false;
    // Prev and Abandon stay live so a stalled request can never trap the
    // learner; they are only disabled once completion starts.
    function lockBar() {
      advancing = true;
      nextBtn.disabled = true;
      if (isReview) recallYesBtn.disabled = true;
    }

    // Back from the next verb can restore this page from bfcache with the
    // lock still set; unlock unless a completion is under way.
    window.addEventListener('pageshow', function (event) {
      if (!event.persisted || completionStarted) return;
      advancing = false;
      nextBtn.disabled = false;
      if (isReview) recallYesBtn.disabled = false;
      syncFinishState();
    });

    let completionStarted = false;
    function _showCompletionAndRedirect(completionSession) {
      if (completionStarted) return;
      completionStarted = true;
      const n = completionSession.size || total;
      progressEl.textContent = `${n}/${n}!`;
      progressEl.classList.add('practice-progress--done');
      progressEl.classList.add('practice-progress--done-pulse');
      lockBar();
      prevBtn.disabled = true;
      abandonBtn.disabled = true;
      const delay = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 1200;
      setTimeout(function () { _finishPractice(completionSession, progressEl); }, delay);
    }

    // Last new-mode verb: the Finish pill stays dimmed (aria-disabled, not
    // `disabled`, so a tap still shows the listen warning) until the audio
    // goal is met, then eases to full emphasis.
    function syncFinishState() {
      if (!isLast) return;
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
      // Not gated behind hasListened(): a recall self-report on an already
      // starred verb; forcing replays first would hand over the answer
      // right before the test. Always applyReview(..., true) -- the only
      // path that moves the SRS box. nextBtn below never calls it.
      async function _advanceAfterKnew() {
        if (advancing) return;
        lockBar();
        if (window.VerbBoardSRS) {
          // The local SRS write happens before applyReview's network call, so
          // advancing after a timeout never loses the review.
          await Promise.race([
            window.VerbBoardSRS.applyReview(language, verbId, true),
            new Promise(function (resolve) { setTimeout(resolve, 3000); }),
          ]);
        }
        if (isLast) {
          _showCompletionAndRedirect(session);
        } else {
          navTo(session.ids[idx + 1]);
        }
      }

      recallYesBtn.addEventListener("click", function () { _advanceAfterKnew(); });
    }

    nextBtn.addEventListener("click", function () {
      if (advancing) return;
      if (!hasListened()) {
        showWarn();
        return;
      }
      if (isLast) {
        _showCompletionAndRedirect(session);
      } else {
        navTo(session.ids[idx + 1]);
      }
    });

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
        // Review-mode verbs don't require PRACTICE_MIN_PLAYS listens: the
        // recall button is ungated, and the listen-gated Next has no SRS
        // effect. Demanding the count here would silently cost the badge for
        // any session containing review verbs.
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
