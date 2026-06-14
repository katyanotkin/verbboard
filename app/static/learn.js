document.addEventListener("DOMContentLoaded", function () {
  const knownButton = document.getElementById("known-btn");
  const pageRoot = document.getElementById("learn-page");

  if (!knownButton || !pageRoot) return;

  const language = pageRoot.dataset.language;
  const verbId = pageRoot.dataset.verbId;

  if (!language || !verbId) return;

  const progress = window.VerbBoardProgress;
  if (!progress) return;

  const audioPlaysKey = `audio_plays:${language}`;
  const heardSrcsKey = `audio_heard_srcs:${language}`;

  function _readHeardSrcs() {
    try { return JSON.parse(localStorage.getItem(heardSrcsKey) || '{}'); } catch (_) { return {}; }
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

      window.dispatchEvent(new CustomEvent('vb:learn-audio-played'));
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

});
