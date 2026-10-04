// Report a problem with one audio clip (issue #71). One delegated click listener
// drives every .audio-report-btn on the board and one shared #audio-report-pop.
// The clip is identified by the sibling <audio> src (/audio/{lang}/{verb}/{voice}/{form_key}.mp3);
// the server resolves the spoken text itself. Signed-in users only.
(function () {
  "use strict";

  var NOTE_MAX = 200;
  var page = document.getElementById("learn-page");
  var pop = document.getElementById("audio-report-pop");
  if (!page || !pop) return;
  document.body.appendChild(pop); // absolute positioning against the document, not a page container

  var UI = window.UI || {};
  var language = page.dataset.language;
  var storageKey = "audio_reported:" + language;
  var noteLink = pop.querySelector(".audio-report-note-link");
  var noteWrap = pop.querySelector(".audio-report-note");
  var noteInput = pop.querySelector(".audio-report-note-input");
  var sendBtn = pop.querySelector(".audio-report-send");
  var reasonBtns = Array.prototype.slice.call(pop.querySelectorAll(".audio-report-reason"));
  var activeBtn = null;
  var activeClip = null;
  var selectedReason = "";
  var sending = false;

  function toast(message) {
    if (window.vbShowToast) window.vbShowToast(message);
  }

  function parseClip(btn) {
    var cell = btn.closest("td");
    var audio = cell && cell.querySelector("audio");
    var src = audio && (audio.getAttribute("src") || "");
    var match = /^\/audio\/([^/]+)\/([^/]+)\/([^/]+)\/([^/]+)\.mp3$/.exec(src || "");
    if (!match) return null;
    return {
      language: decodeURIComponent(match[1]),
      verb_id: decodeURIComponent(match[2]),
      voice: decodeURIComponent(match[3]),
      form_key: decodeURIComponent(match[4]),
    };
  }

  function clipId(clip) {
    return clip.verb_id + ":" + clip.voice + ":" + clip.form_key;
  }

  function reportedSet() {
    return window.VerbBoardStorage ? window.VerbBoardStorage.readSet(storageKey) : new Set();
  }

  function markReported(clip) {
    if (!window.VerbBoardStorage) return;
    var set = reportedSet();
    set.add(clipId(clip));
    try { window.VerbBoardStorage.writeSet(storageKey, set); } catch (_) {}
    if (activeBtn) activeBtn.setAttribute("aria-pressed", "true");
  }

  function paintReported() {
    var set = reportedSet();
    Array.prototype.forEach.call(document.querySelectorAll(".audio-report-btn"), function (btn) {
      var clip = parseClip(btn);
      if (clip && set.has(clipId(clip))) btn.setAttribute("aria-pressed", "true");
    });
  }

  function resetPop() {
    selectedReason = "";
    reasonBtns.forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
    noteWrap.hidden = true;
    noteLink.hidden = false;
    noteLink.setAttribute("aria-expanded", "false");
    noteInput.value = "";
  }

  function closePop(returnFocus) {
    if (pop.hidden) return;
    pop.hidden = true;
    pop.removeAttribute("role");
    var btn = activeBtn;
    if (btn) btn.setAttribute("aria-expanded", "false");
    activeBtn = null;
    activeClip = null;
    resetPop();
    if (returnFocus && btn) btn.focus();
  }

  function placePop(btn) {
    var rect = btn.getBoundingClientRect();
    var margin = 12;
    var half = pop.offsetWidth / 2;
    var center = rect.left + rect.width / 2;
    var clamped = Math.min(Math.max(center, margin + half), document.documentElement.clientWidth - margin - half);
    pop.style.left = clamped + "px";
    pop.style.top = rect.bottom + window.scrollY + 8 + "px";
  }

  function openPop(btn, clip) {
    closePop(false);
    activeBtn = btn;
    activeClip = clip;
    btn.setAttribute("aria-expanded", "true");
    pop.setAttribute("role", "dialog"); // only while open: a hidden dialog would still count as one on the page
    pop.hidden = false;
    placePop(btn);
    reasonBtns[0].focus();
  }

  function signedInUser() {
    var auth = window.VerbBoardAuth;
    if (!auth || !auth.ready) return Promise.resolve(null);
    var timeout = new Promise(function (resolve) { setTimeout(function () { resolve(null); }, 1500); });
    var resolved = auth.ready().then(function () { return auth.currentUser(); }).catch(function () { return null; });
    return Promise.race([resolved, timeout]);
  }

  function promptSignIn() {
    toast(UI["audio_report.sign_in"] || "Sign in to report an audio problem.");
    var auth = window.VerbBoardAuth;
    if (auth && auth.signIn) {
      try { auth.signIn(); } catch (_) {}
    }
  }

  function send(reason) {
    if (sending || !activeClip) return;
    var clip = activeClip;
    var note = noteWrap.hidden ? "" : noteInput.value.trim().slice(0, NOTE_MAX);
    sending = true;
    var tokenPromise = window.VerbBoardAuth && window.VerbBoardAuth.getIdToken
      ? window.VerbBoardAuth.getIdToken()
      : Promise.resolve(null);
    tokenPromise.then(function (token) {
      if (!token) { closePop(true); promptSignIn(); return null; }
      return fetch("/api/audio_report", {
        method: "POST",
        keepalive: true,
        headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json" },
        body: JSON.stringify({
          language: clip.language,
          verb_id: clip.verb_id,
          voice: clip.voice,
          form_key: clip.form_key,
          reason: reason,
          comment: note || null,
          ui_language: window.VB_UI_LANG || null,
        }),
      }).then(function (res) {
        if (res.status === 401) { closePop(true); promptSignIn(); return; }
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json().then(function (data) {
          markReported(clip);
          closePop(true);
          toast(data && data.duplicate
            ? (UI["audio_report.already"] || "Already reported")
            : (UI["audio_report.thanks"] || "Thanks, report sent."));
        });
      });
    }).catch(function () {
      toast(UI["audio_report.error"] || "Could not send. Try again later.");
    }).then(function () { sending = false; });
  }

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest(".audio-report-btn");
    if (trigger) {
      if (activeBtn === trigger) { closePop(true); return; }
      var clip = parseClip(trigger);
      if (!clip) return;
      if (trigger.getAttribute("aria-pressed") === "true") {
        toast(UI["audio_report.already"] || "Already reported");
        return;
      }
      signedInUser().then(function (user) {
        if (!user) { promptSignIn(); return; }
        openPop(trigger, clip);
      });
      return;
    }
    if (pop.hidden) return;
    if (!pop.contains(event.target)) { closePop(false); return; }

    var reasonBtn = event.target.closest(".audio-report-reason");
    if (reasonBtn) {
      if (noteWrap.hidden) {
        send(reasonBtn.dataset.reason);
      } else {
        selectedReason = reasonBtn.dataset.reason;
        reasonBtns.forEach(function (b) { b.setAttribute("aria-pressed", b === reasonBtn ? "true" : "false"); });
      }
    } else if (event.target.closest(".audio-report-note-link")) {
      noteWrap.hidden = false;
      noteLink.hidden = true;
      noteLink.setAttribute("aria-expanded", "true");
      noteInput.focus();
    } else if (event.target.closest(".audio-report-send")) {
      send(selectedReason || "other");
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closePop(true);
  });

  window.addEventListener("resize", function () { if (activeBtn && !pop.hidden) placePop(activeBtn); });

  // Dim the flags until a clip has been played (CSS keys off this class).
  function markPlayed() { page.classList.add("audio-played"); }
  window.addEventListener("vb:learn-audio-played", markPlayed);
  Array.prototype.forEach.call(document.querySelectorAll("audio"), function (audio) {
    audio.addEventListener("play", markPlayed);
  });

  paintReported();
  window.addEventListener("pageshow", paintReported);
})();
