document.addEventListener("DOMContentLoaded", function () {
  const knownButton = document.getElementById("known-btn");
  const pageRoot = document.getElementById("learn-page");

  if (!knownButton || !pageRoot) return;

  const language = pageRoot.dataset.language;
  const verbId = pageRoot.dataset.verbId;

  if (!language || !verbId) return;

  const progress = window.VerbBoardProgress;
  if (!progress) return;

  const seenKey = `seen:${language}`;
  const audioPlaysKey = `audio_plays:${language}`;
  const sessionKey = `practice_session:${language}`;
  const badgesKey = `practice_badges:${language}`;

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

  // ── audio play tracking ────────────────────────────────────────────────────
  document.querySelectorAll("audio").forEach(function (audio) {
    audio.addEventListener("play", function () {
      let plays;
      try {
        plays = JSON.parse(localStorage.getItem(audioPlaysKey) || "{}");
      } catch (_) {
        plays = {};
      }
      plays[verbId] = (plays[verbId] || 0) + 1;
      localStorage.setItem(audioPlaysKey, JSON.stringify(plays));
    });
  });

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
  const PRACTICE_MIN_PLAYS = 5;

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
    const verbsUrl = `/verbs?language=${encodeURIComponent(language)}`;
    const total = session.ids.length;
    const isLast = idx === total - 1;

    const bar = document.createElement("div");
    bar.className = "practice-bar";

    const prevBtn = document.createElement("button");
    prevBtn.className = "practice-nav-btn";
    prevBtn.textContent = UI["practice.prev"] || "Prev";
    prevBtn.disabled = idx === 0;

    const progressEl = document.createElement("span");
    progressEl.className = "practice-progress";
    progressEl.textContent = `${idx + 1} ${UI["practice.of"] || "of"} ${total}`;

    const nextBtn = document.createElement("button");
    nextBtn.className = "practice-nav-btn";
    nextBtn.textContent = UI["practice.next"] || "Next";
    nextBtn.disabled = isLast;

    const finishBtn = document.createElement("button");
    finishBtn.className = "btn-pill-navy";
    finishBtn.textContent = UI["practice.finish"] || "Finish";

    const abandonBtn = document.createElement("button");
    abandonBtn.className = "practice-abandon-btn";
    abandonBtn.textContent = UI["practice.abandon"] || "Abandon";

    const warnEl = document.createElement("span");
    warnEl.className = "practice-listen-warn";
    warnEl.hidden = true;
    warnEl.textContent = UI["practice.listen_first"] || "Listen to the audio first";

    bar.appendChild(prevBtn);
    bar.appendChild(progressEl);
    bar.appendChild(nextBtn);
    bar.appendChild(finishBtn);
    bar.appendChild(abandonBtn);
    bar.appendChild(warnEl);

    pageRoot.insertBefore(bar, pageRoot.firstChild);

    function navTo(targetId) {
      window.location.href =
        `/learn?language=${encodeURIComponent(language)}` +
        `&verb_id=${encodeURIComponent(targetId)}` +
        `&return_to=${encodeURIComponent(verbsUrl)}`;
    }

    function hasListened() {
      let plays;
      try {
        plays = JSON.parse(localStorage.getItem(audioPlaysKey) || "{}");
      } catch (_) {
        plays = {};
      }
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
      accomplished = session.ids.every(
        (id) => seenSet.has(id) && (plays[id] || 0) >= PRACTICE_MIN_PLAYS
      );
    } catch (_) {}

    if (accomplished) {
      let badges;
      try {
        badges = JSON.parse(localStorage.getItem(badgesKey) || "[]");
      } catch (_) {
        badges = [];
      }
      badges.push(session.size || session.ids.length);
      localStorage.setItem(badgesKey, JSON.stringify(badges));

      if (
	  window.VerbBoardPracticeLoopInstance &&
	  window.VerbBoardPracticeLoopInstance.savePracticeBadgesToServer
	) {
	  await window.VerbBoardPracticeLoopInstance
	    .savePracticeBadgesToServer(badges);
      }

      localStorage.setItem(
        `practice_wrapup:${language}`,
        JSON.stringify({ ids: session.ids, lemmas: session.lemmas || {} })
      );
    }

    localStorage.removeItem(sessionKey);
    window.location.href = `/verbs?language=${encodeURIComponent(language)}`;
  }
});
