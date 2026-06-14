document.addEventListener("DOMContentLoaded", function () {
  const pageRoot = document.getElementById("learn-page");
  if (!pageRoot) return;

  const language = pageRoot.dataset.language;
  const verbId = pageRoot.dataset.verbId;
  if (!language || !verbId) return;

  const _uiLang = window.VB_UI_LANG || '';
  const _uiSuffix = _uiLang ? '&ui_language=' + encodeURIComponent(_uiLang) : '';

  const progress = window.VerbBoardProgress;
  if (!progress) return;

  const seenKey = `seen:${language}`;
  const audioPlaysKey = `audio_plays:${language}`;
  const heardSrcsKey = `audio_heard_srcs:${language}`;
  const sessionKey = `practice_session:${language}`;
  const badgesKey = `practice_badges:${language}`;

  const _minPlaysRaw = localStorage.getItem('practice_min_plays') || '5';
  const PRACTICE_MIN_PLAYS = _minPlaysRaw === 'all' ? 'all' : (parseInt(_minPlaysRaw, 10) || 5);
  const audioTotal = document.querySelectorAll('audio').length;

  function _readHeardSrcs() {
    try { return JSON.parse(localStorage.getItem(heardSrcsKey) || '{}'); } catch (_) { return {}; }
  }

  function _audioProgressText() {
    if (PRACTICE_MIN_PLAYS === 'all') {
      return '♪ ' + (_readHeardSrcs()[verbId] || []).length + ' / ' + audioTotal;
    }
    let plays;
    try { plays = JSON.parse(localStorage.getItem(audioPlaysKey) || '{}'); } catch (_) { plays = {}; }
    return '♪ ' + Math.min(plays[verbId] || 0, PRACTICE_MIN_PLAYS) + ' / ' + PRACTICE_MIN_PLAYS;
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
    const total = session.ids.length;
    const isLast = idx === total - 1;
    const isRTL = document.documentElement.dir === 'rtl';

    if (audioTotal > 0) {
      localStorage.setItem(`audio_total:${language}:${verbId}`, String(audioTotal));
    }

    const bar = document.createElement("div");
    bar.className = "practice-bar";

    const prevBtn = document.createElement("button");
    prevBtn.className = "practice-nav-btn";
    prevBtn.textContent = isRTL ? '>' : '<';
    prevBtn.setAttribute('aria-label', UI["practice.prev"] || "Previous");
    prevBtn.disabled = idx === 0;

    const progressEl = document.createElement("span");
    progressEl.className = "practice-progress";
    progressEl.textContent = `${idx + 1}/${total}`;

    const progressWrapper = document.createElement("div");
    progressWrapper.className = "practice-progress-wrapper";
    progressWrapper.appendChild(progressEl);

    const nextBtn = document.createElement("button");
    nextBtn.className = "practice-nav-btn practice-nav-btn--primary";
    nextBtn.textContent = isRTL ? '<' : '>';
    nextBtn.setAttribute('aria-label', UI["practice.next"] || "Next");

    const skipBtn = document.createElement("button");
    skipBtn.className = "practice-skip-btn";
    skipBtn.textContent = UI["practice.skip"] || "Skip";

    const abandonBtn = document.createElement("button");
    abandonBtn.className = "practice-abandon-btn";
    abandonBtn.textContent = UI["practice.abandon"] || "Abandon";

    const warnEl = document.createElement("span");
    warnEl.className = "practice-listen-warn";
    warnEl.hidden = true;

    const actionsRow = document.createElement("div");
    actionsRow.className = "practice-bar-actions";
    actionsRow.appendChild(skipBtn);
    actionsRow.appendChild(abandonBtn);

    bar.appendChild(prevBtn);
    bar.appendChild(progressWrapper);
    bar.appendChild(nextBtn);
    bar.appendChild(warnEl);
    bar.appendChild(actionsRow);

    pageRoot.insertBefore(bar, pageRoot.firstChild);

    function navTo(targetId) {
      window.location.href =
        `/learn?language=${encodeURIComponent(language)}` +
        `&verb_id=${encodeURIComponent(targetId)}` +
        `&return_to=${encodeURIComponent(verbsUrl)}` +
        _uiSuffix;
    }

    function hasListened() {
      if (PRACTICE_MIN_PLAYS === 'all') {
        return (_readHeardSrcs()[verbId] || []).length >= audioTotal;
      }
      let plays;
      try { plays = JSON.parse(localStorage.getItem(audioPlaysKey) || "{}"); } catch (_) { plays = {}; }
      return (plays[verbId] || 0) >= PRACTICE_MIN_PLAYS;
    }

    if (isLast) {
      window.addEventListener('vb:learn-audio-played', function () {
        if (hasListened()) progressEl.classList.add('practice-progress--done');
      });
    }

    let warnTimer;
    function showWarn() {
      warnEl.textContent = (UI["practice.listen_first"] || "Listen to audio") + ' ' + _audioProgressText();
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
        await _finishPractice(session);
      } else {
        navTo(session.ids[idx + 1]);
      }
    });

    skipBtn.addEventListener("click", function () {
      progress.setKnown(language, verbId, true);

      const updatedIds = session.ids.filter(function (id) { return id !== verbId; });

      if (updatedIds.length === 0) {
        localStorage.removeItem(sessionKey);
        window.location.href = verbsUrl;
        return;
      }

      const updatedLemmas = Object.assign({}, session.lemmas || {});
      delete updatedLemmas[verbId];

      localStorage.setItem(sessionKey, JSON.stringify({
        ids: updatedIds,
        lemmas: updatedLemmas,
        size: session.size,
      }));

      navTo(updatedIds[Math.min(idx, updatedIds.length - 1)]);
    });

    abandonBtn.addEventListener("click", function () {
      localStorage.removeItem(sessionKey);
      window.location.href = verbsUrl;
    });
  }

  async function _finishPractice(session) {
    let accomplished = false;
    try {
      const seenSet = progress.readSet(seenKey);
      let plays;
      try { plays = JSON.parse(localStorage.getItem(audioPlaysKey) || "{}"); } catch (_) { plays = {}; }
      accomplished = session.ids.every(function (id) {
        if (!seenSet.has(id)) return false;
        if (PRACTICE_MIN_PLAYS === 'all') {
          const heardData = _readHeardSrcs();
          const heardCount = (heardData[id] || []).length;
          const storedTotal = parseInt(localStorage.getItem(`audio_total:${language}:${id}`) || '0', 10);
          return storedTotal > 0 && heardCount >= storedTotal;
        }
        return (plays[id] || 0) >= PRACTICE_MIN_PLAYS;
      });
    } catch (_) {}

    if (accomplished) {
      let badges;
      try { badges = JSON.parse(localStorage.getItem(badgesKey) || "[]"); } catch (_) { badges = []; }

      badges.push(session.size || session.ids.length);
      localStorage.setItem(badgesKey, JSON.stringify(badges));

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
              body: JSON.stringify({ language: language, badges: badges }),
            });
          }
        } catch (_) {}
      }

      localStorage.setItem(
        `practice_wrapup:${language}`,
        JSON.stringify({ ids: session.ids, lemmas: session.lemmas || {} })
      );
    }

    localStorage.removeItem(sessionKey);
    window.location.href = `/verbs?language=${encodeURIComponent(language)}${_uiSuffix}`;
  }
});
