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

  // ── translations toggle (examples + verb infinitive) ───────────────────────
  const toggleBtn = document.getElementById("toggle-translations");
  if (toggleBtn) {
    const labelShow = toggleBtn.dataset.labelShow;
    const labelHide = toggleBtn.dataset.labelHide;
    let visible = false;

    toggleBtn.addEventListener("click", function () {
      visible = !visible;
      pageRoot.classList.toggle("translations-visible", visible);
      toggleBtn.textContent = visible ? labelHide : labelShow;
    });
  }

  // ── jump to example from a conjugation form ─────────────────────────────────
  function vbNormalizeFormText(text) {
    return (text || "")
      .normalize("NFKD")
      .replace(/\p{Mn}/gu, "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function vbFormMatchesText(needle, haystackText) {
    const haystack = vbNormalizeFormText(haystackText);
    if (!haystack || !needle) return false;
    // Word-boundary match, not raw substring: a short form (e.g. a single
    // pronoun-like token) must not false-positive match inside an unrelated
    // longer word that merely shares those letters.
    const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const pattern = new RegExp("(^|[^\\p{L}\\p{N}])" + escaped + "($|[^\\p{L}\\p{N}])", "u");
    return pattern.test(" " + haystack + " ");
  }

  function vbShowToast(message) {
    if (!message) return;
    let toast = document.getElementById("vb-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "vb-toast";
      toast.className = "vb-toast";
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.remove("vb-toast--visible");
    void toast.offsetWidth;
    toast.classList.add("vb-toast--visible");
    clearTimeout(toast._vbHideTimer);
    toast._vbHideTimer = setTimeout(function () {
      toast.classList.remove("vb-toast--visible");
    }, 2200);
  }

  window.vbJumpToExample = function (btn) {
    const tr = btn.closest("tr");
    const formText = tr && tr.dataset.form;
    if (!formText) return;

    const needle = vbNormalizeFormText(formText);
    if (!needle) return;

    const exampleRows = document.querySelectorAll(".examples-table tr");
    let matchRow = null;

    for (const row of exampleRows) {
      const srcEl = row.querySelector(".example-src");
      if (!srcEl) continue;
      if (vbFormMatchesText(needle, srcEl.textContent)) {
        matchRow = row;
        break;
      }
    }

    if (matchRow) {
      matchRow.scrollIntoView({ behavior: "smooth", block: "center" });
      matchRow.classList.remove("example-jump-highlight");
      void matchRow.offsetWidth;
      matchRow.classList.add("example-jump-highlight");
      return;
    }

    const UI = window.UI || {};
    vbShowToast(UI["board.no_example_for_form"] || "No example yet for this form");

    fetch("/api/learn/form_signal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        language: language,
        verb_id: verbId,
        form_text: formText,
      }),
    }).catch(function () {});
  };

});
