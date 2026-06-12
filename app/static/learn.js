document.addEventListener("DOMContentLoaded", function () {
  const knownButton = document.getElementById("known-btn");
  const pageRoot = document.getElementById("learn-page");

  if (!knownButton || !pageRoot) return;

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
      const data = _readHeardSrcs();
      return '♪ ' + (data[verbId] || []).length + ' / ' + audioTotal;
    }
    let plays;
    try { plays = JSON.parse(localStorage.getItem(audioPlaysKey) || '{}'); } catch (_) { plays = {}; }
    return '♪ ' + Math.min(plays[verbId] || 0, PRACTICE_MIN_PLAYS) + ' / ' + PRACTICE_MIN_PLAYS;
  }

  function updateKnownButton(shouldPop) {
    const isKnown = progress.isKnown(language, verbId);
    const UI = window.UI || {};

    knownButton.classList.toggle("is-active", isKnown);
    knownButton.setAttribute("aria-pressed", isKnown ? "true" : "false");
    knownButton.title = isKnown
      ? (UI["board.known"] || "Learned")
      : (UI["board.mark_known"] || "Mark as learned");

    if (shouldPop && isKnown) {
      knownButton.classList.remove("pop");
      void knownButton.offsetWidth;
      knownButton.classList.add("pop");
    }
  }

  async function toggleKnown() {
    const nextKnown = !progress.isKnown(language, verbId);
    await progress.setKnown(language, verbId, nextKnown);
    await progress.markSeen(language, verbId);
    updateKnownButton(true);
  }

  knownButton.addEventListener("click", function (event) {
    event.preventDefault();
    toggleKnown();
  });

  async function initializeProgress() {
    if (
      window.VerbBoardAuth &&
      window.VerbBoardAuth.ready
    ) {
      await window.VerbBoardAuth.ready();
    }

    await progress.markSeen(language, verbId);

    updateKnownButton(false);
  }

  initializeProgress();

  // If the user logs in while already on this page, hydrateProgress() fires
  // and writes updated known state to localStorage.  Re-read it so the button
  // reflects the server's authoritative value without requiring a page reload.
  window.addEventListener('vb:progress-hydrated', function () {
    updateKnownButton(false);
  });


  // If the user signs out while on this page, auth.js has already cleared
  // all user-specific localStorage keys.  Just update the button.
  window.addEventListener('vb:auth-signed-out', function () {
    updateKnownButton(false);
  });

  // ── audio play tracking ────────────────────────────────────────────────────
  const allAudioEls = Array.from(document.querySelectorAll("audio"));
  allAudioEls.forEach(function (audio) {
    audio.addEventListener("play", function () {
      // Stop any other playing audio
      allAudioEls.forEach(function (other) {
        if (other !== audio && !other.paused) other.pause();
      });

      // Total plays
      let plays;
      try { plays = JSON.parse(localStorage.getItem(audioPlaysKey) || "{}"); } catch (_) { plays = {}; }
      plays[verbId] = (plays[verbId] || 0) + 1;
      localStorage.setItem(audioPlaysKey, JSON.stringify(plays));

      // Per-src tracking (used for 'all' mode)
      const heardData = _readHeardSrcs();
      const srcs = new Set(heardData[verbId] || []);
      srcs.add(audio.currentSrc || audio.src || '');
      heardData[verbId] = Array.from(srcs);
      localStorage.setItem(heardSrcsKey, JSON.stringify(heardData));

      // Live-update progress indicator if bar is mounted
      const progressEl = document.getElementById("practice-audio-progress");
      if (progressEl) progressEl.textContent = _audioProgressText();
    });
  });

  // ── persona / number filter ────────────────────────────────────────────────
  const personaControl = document.getElementById("persona-control");
  if (personaControl) {
    const personaStorageKey = `persona_filter:${language}`;
    const numberStorageKey = `number_filter:${language}`;

    let currentPersona = localStorage.getItem(personaStorageKey) || "all";
    let currentNumber  = localStorage.getItem(numberStorageKey)  || "all";

    function applyFilters() {
      document.querySelectorAll(".conj-table tr").forEach(function (tr) {
        var g = tr.dataset.gender;
        var n = tr.dataset.number;
        var gMatch = !g || currentPersona === "all" || g === currentPersona;
        var nMatch = !n || currentNumber  === "all" || n === currentNumber;
        tr.hidden = !(gMatch && nMatch);
      });
      personaControl.querySelectorAll(".persona-btn").forEach(function (btn) {
        btn.classList.toggle("active", btn.dataset.value === currentPersona);
      });
      personaControl.querySelectorAll(".number-btn").forEach(function (btn) {
        btn.classList.toggle("active", btn.dataset.value === currentNumber);
      });
    }

    personaControl.querySelectorAll(".persona-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        currentPersona = btn.dataset.value;
        localStorage.setItem(personaStorageKey, currentPersona);
        applyFilters();
      });
    });

    personaControl.querySelectorAll(".number-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        currentNumber = btn.dataset.value;
        localStorage.setItem(numberStorageKey, currentNumber);
        applyFilters();
      });
    });

    applyFilters();
  }

  // ── translations toggle ────────────────────────────────────────────────────
  const toggleBtn = document.getElementById("toggle-translations");
  if (toggleBtn) {
    const table = document.querySelector(".examples-table");
    const labelShow = toggleBtn.dataset.labelShow;
    const labelHide = toggleBtn.dataset.labelHide;
    let visible = false;

    toggleBtn.addEventListener("click", function () {
      visible = !visible;
      table.classList.toggle("translations-visible", visible);
      toggleBtn.textContent = visible ? labelHide : labelShow;
    });
  }

  // ── practice session bar ──────────────────────────────────────────────────

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

    // Store audio count for this verb so _finishPractice can verify 'all' mode
    if (audioTotal > 0) {
      localStorage.setItem(`audio_total:${language}:${verbId}`, String(audioTotal));
    }

    const bar = document.createElement("div");
    bar.className = "practice-bar";

    const prevBtn = document.createElement("button");
    prevBtn.className = "practice-nav-btn";
    prevBtn.textContent = UI["practice.prev"] || "Prev";
    prevBtn.disabled = idx === 0;

    const progressEl = document.createElement("span");
    progressEl.className = "practice-progress";
    progressEl.textContent = `${idx + 1} ${UI["practice.of"] || "of"} ${total}`;

    const audioProgressEl = document.createElement("span");
    audioProgressEl.id = "practice-audio-progress";
    audioProgressEl.className = "practice-audio-progress";
    audioProgressEl.textContent = _audioProgressText();

    const nextBtn = document.createElement("button");
    nextBtn.className = "practice-nav-btn";
    nextBtn.textContent = UI["practice.next"] || "Next";
    nextBtn.disabled = isLast;

    const finishBtn = document.createElement("button");
    finishBtn.className = "btn-pill-navy";
    finishBtn.textContent = UI["practice.finish"] || "Finish";
    finishBtn.disabled = !isLast;

    const skipBtn = document.createElement("button");
    skipBtn.className = "practice-skip-btn";
    skipBtn.textContent = UI["practice.skip"] || "Skip";

    const abandonBtn = document.createElement("button");
    abandonBtn.className = "practice-abandon-btn";
    abandonBtn.textContent = UI["practice.abandon"] || "Abandon";

    const warnEl = document.createElement("span");
    warnEl.className = "practice-listen-warn";
    warnEl.hidden = true;
    warnEl.textContent = UI["practice.listen_first"] || "Listen to the audio first";

    bar.appendChild(prevBtn);
    bar.appendChild(progressEl);
    bar.appendChild(audioProgressEl);
    bar.appendChild(nextBtn);
    bar.appendChild(finishBtn);
    bar.appendChild(skipBtn);
    bar.appendChild(abandonBtn);
    bar.appendChild(warnEl);

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

    let warnTimer;
    function showWarn() {
      warnEl.hidden = false;
      clearTimeout(warnTimer);
      warnTimer = setTimeout(function () {
        warnEl.hidden = true;
      }, 2500);
    }

    prevBtn.addEventListener("click", function () {
      if (idx > 0) navTo(session.ids[idx - 1]);
    });

    nextBtn.addEventListener("click", function () {
      if (idx >= total - 1) return;
      if (!hasListened()) {
        showWarn();
        return;
      }
      navTo(session.ids[idx + 1]);
    });

    finishBtn.addEventListener("click", async function () {
      if (!hasListened()) {
        showWarn();
        return;
      }
      _finishPractice(session);
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
      try {
        plays = JSON.parse(localStorage.getItem(audioPlaysKey) || "{}");
      } catch (_) {
        plays = {};
      }
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
      try {
        badges = JSON.parse(localStorage.getItem(badgesKey) || "[]");
      } catch (_) {
        badges = [];
      }

      // Append -- each completed session earns its own entry.
      // Multiple badges of the same size are intentional (shows repeat completions).
      badges.push(session.size || session.ids.length);
      localStorage.setItem(badgesKey, JSON.stringify(badges));

      // Save to server here, on the learn page, before redirecting.
      // VerbBoardPracticeLoopInstance is not available on this page.
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
