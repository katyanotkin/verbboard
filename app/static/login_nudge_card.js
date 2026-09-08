'use strict';

// Threshold-crossed login nudge: a dismissible inline card at the top of
// /verbs (see #vb-login-nudge-slot in verbs.html). This is the fallback
// surface for an engaged browse-and-star user who never finishes a practice
// session (the badge-earned surface lives in practice_loop.js's
// showWrapUp() instead) -- see login_nudge.js for the shared scoring logic,
// the whenAuthReady() helper, and the CTA builder both surfaces use.
//
// Uses whenAuthReady() rather than calling window.VerbBoardAuth.ready()
// directly: verbs.html's body scripts, including this one, are plain
// (non-deferred) <script> tags that run inline during parse, before auth.js
// (deferred) has executed, so window.VerbBoardAuth may not exist yet at the
// moment this file's top-level code runs.
//
// Ordering vs. the badge-earned surface: verbs_page.js's synchronous
// practiceLoop.maybeShowWrapUp() call (script order: practice_loop.js,
// verbs_page.js, verbs_export.js, then this file) registers its own
// whenAuthReady() callback before this file's init() runs. Both resolve via
// the same window.VerbBoardAuth.ready() promise, and same-event listeners /
// .then() callbacks fire in the order they were registered, so the badge
// path's shouldShowThresholdCard()-relevant markShown() call (if it fires)
// is guaranteed to complete before this file's own shouldShowThresholdCard()
// check runs -- the two surfaces never race for the same page load.
(function () {
  function init() {
    if (!window.VerbBoardLoginNudge) return;

    window.VerbBoardLoginNudge.whenAuthReady(function () {
      if (!window.VerbBoardLoginNudge.shouldShowThresholdCard()) return;

      var slot = document.getElementById('vb-login-nudge-slot');
      if (!slot) return;

      var ui = window.UI || {};
      var copy =
        ui['login_nudge.progress'] ||
        "Don't lose your progress. Sign in to keep it if you switch devices.";

      var cta = window.VerbBoardLoginNudge.buildCta(copy);
      cta.classList.add('vb-login-nudge--card');
      slot.appendChild(cta);
      window.VerbBoardLoginNudge.markShown();
    });
  }

  init();
})();
