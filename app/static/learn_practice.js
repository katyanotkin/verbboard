document.addEventListener("DOMContentLoaded", function () {
  const pageRoot = document.getElementById("learn-page");
  if (!pageRoot) return;

  const language = pageRoot.dataset.language;
  const verbId = pageRoot.dataset.verbId;
  if (!language || !verbId) return;

  const _uiLang = window.VB_UI_LANG || '';
  const _uiSuffix = _uiLang ? '&ui_language=' + encodeURIComponent(_uiLang) : '';
  const _graceEnabled = !!window.VB_STREAK_GRACE_ENABLED;

  const progress = window.VerbBoardProgress;
  if (!progress) return;

  const seenKey = `seen:${language}`;
  const audioPlaysKey = `audio_plays:${language}`;
  const sessionKey = `practice_session:${language}`;
  const badgesKey = `practice_badges:${language}`;

  const _minPlaysRaw = parseInt(localStorage.getItem('practice_min_plays'), 10);
  const PRACTICE_MIN_PLAYS = (_minPlaysRaw >= 1 && _minPlaysRaw <= 12) ? _minPlaysRaw : 5;

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
    const verbsUrl = `/verbs?language=${encodeURIComponent(language)}${_uiSuffix}`;
    const sessionTotal = session.size || session.ids.length;
    const skippedSoFar = sessionTotal - session.ids.length;
    const total = session.ids.length;
    const isLast = idx === total - 1;
    const isRTL = document.documentElement.dir === 'rtl';

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

    const nextBtn = document.createElement("button");
    nextBtn.className = "practice-nav-btn practice-nav-btn--primary";
    nextBtn.textContent = isRTL ? '<' : '>';
    nextBtn.setAttribute('aria-label', UI["practice.next"] || "Next");

    const skipBtn = document.createElement("button");
    skipBtn.className = "practice-skip-btn";
    skipBtn.textContent = UI["practice.skip"] || "Skip & learn";

    const abandonBtn = document.createElement("button");
    abandonBtn.className = "practice-abandon-btn";
    abandonBtn.textContent = UI["practice.abandon"] || "Abandon practice";

    const warnEl = document.createElement("span");
    warnEl.className = "practice-listen-warn";
    warnEl.hidden = true;

    bar.appendChild(prevBtn);
    bar.appendChild(skipBtn);
    bar.appendChild(progressWrapper);
    bar.appendChild(abandonBtn);
    bar.appendChild(nextBtn);
    bar.appendChild(warnEl);

    const topbar = pageRoot.querySelector(".topbar");
    if (topbar && topbar.nextSibling) {
      pageRoot.insertBefore(bar, topbar.nextSibling);
    } else {
      pageRoot.insertBefore(bar, pageRoot.firstChild);
    }

    function navTo(targetId) {
      window.location.href =
        `/learn?language=${encodeURIComponent(language)}` +
        `&verb_id=${encodeURIComponent(targetId)}` +
        `&return_to=${encodeURIComponent(verbsUrl)}` +
        _uiSuffix;
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
      nextBtn.disabled = true;
      prevBtn.disabled = true;
      skipBtn.disabled = true;
      abandonBtn.disabled = true;
      const delay = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 1200;
      setTimeout(function () { _finishPractice(completionSession, progressEl); }, delay);
    }

    window.addEventListener('vb:learn-audio-played', function () {
      audioCounterEl.innerHTML = _audioProgressHtml();
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

    skipBtn.addEventListener("click", async function () {
      await progress.setKnown(language, verbId, true);

      const updatedIds = session.ids.filter(function (id) { return id !== verbId; });

      if (updatedIds.length === 0) {
        localStorage.removeItem(sessionKey);
        window.location.href = verbsUrl;
        return;
      }

      const updatedLemmas = Object.assign({}, session.lemmas || {});
      delete updatedLemmas[verbId];

      const updatedSession = {
        ids: updatedIds,
        lemmas: updatedLemmas,
        size: session.size,
      };
      localStorage.setItem(sessionKey, JSON.stringify(updatedSession));

      const navTarget = Math.min(idx, updatedIds.length - 1);
      // If clamping moved us backwards, every remaining verb was already visited.
      // Finish the session rather than landing on a verb the user already completed.
      if (navTarget < idx) {
        _showCompletionAndRedirect(updatedSession);
        return;
      } else {
        navTo(updatedIds[navTarget]);
      }
    });

    abandonBtn.addEventListener("click", function () {
      localStorage.removeItem(sessionKey);
      window.location.href = verbsUrl;
    });
  }

  async function _finishPractice(session, capsuleEl) {
    let accomplished = false;
    try {
      const seenSet = progress.readSet(seenKey);
      let plays;
      try { plays = JSON.parse(localStorage.getItem(audioPlaysKey) || "{}"); } catch (_) { plays = {}; }
      accomplished = session.ids.every(function (id) {
        if (!seenSet.has(id)) return false;
        return (plays[id] || 0) >= PRACTICE_MIN_PLAYS;
      });
    } catch (_) {}

    if (accomplished) {
      let badges;
      try { badges = JSON.parse(localStorage.getItem(badgesKey) || "[]"); } catch (_) { badges = []; }

      badges.push(session.size || session.ids.length);
      localStorage.setItem(badgesKey, JSON.stringify(badges));

      const streakKey = `practice_streak:${language}`;
      let streak = null;
      let streakDisplayLen = 0;
      if (window.VerbBoardStreak && window.VerbBoardStorage) {
        const streakLib = window.VerbBoardStreak;
        const storage = window.VerbBoardStorage;
        const existingStreak = storage.readJson(streakKey, null);
        streak = streakLib.bump(existingStreak, streakLib.localDay(), _graceEnabled);
        storage.writeJson(streakKey, streak);
        streakDisplayLen = streakLib.displayLen(streak);
      }

      const practicePostBody = { language: language, badges: badges };
      if (streak) {
        practicePostBody.streak_last_day = streak.last_day;
        practicePostBody.streak_len = streak.len;
        practicePostBody.streak_grace_used = !!streak.grace_used;
      }

      if (window.VerbBoardAuth && window.VerbBoardAuth.getIdToken) {
        try {
          const token = await window.VerbBoardAuth.getIdToken();
          if (token) {
            const resp = await fetch("/api/progress/practice", {
              method: "POST",
              headers: {
                Authorization: "Bearer " + token,
                "Content-Type": "application/json",
              },
              body: JSON.stringify(practicePostBody),
            });
            // The server merges against other devices' streaks; adopt its
            // answer so the wrap-up modal never under-counts.
            if (resp.ok && window.VerbBoardStreak && window.VerbBoardStorage) {
              const data = await resp.json().catch(function () { return {}; });
              if (data.streak && data.streak.last_day && data.streak.len) {
                const serverStreak = {
                  last_day: data.streak.last_day,
                  len: data.streak.len,
                  grace_used: !!data.streak.grace_used,
                };
                streak = window.VerbBoardStreak.merge(streak, serverStreak, _graceEnabled);
                window.VerbBoardStorage.writeJson(streakKey, streak);
                streakDisplayLen = window.VerbBoardStreak.displayLen(streak);
              }
            }
          }
        } catch (_) {}
      }

      localStorage.setItem(
        `practice_wrapup:${language}`,
        JSON.stringify({
          ids: session.ids,
          lemmas: session.lemmas || {},
          streakLen: streakDisplayLen,
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
    window.location.href = `/verbs?language=${encodeURIComponent(language)}${_uiSuffix}`;
  }
});
