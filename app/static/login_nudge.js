'use strict';

// Anonymous-only login-nudge scoring + shared CTA builder.
//
// One localStorage counter (`login_nudge_score`) is incremented by three
// signals, each weighted by how strongly it signals engagement:
//   - a verb page view (/learn loads)         -- +1  (learn.js)
//   - a verb marked known (star toggle)        -- +3  (learn.js)
//   - a completed practice session (badge)     -- +10 (learn_practice.js)
// Tracking only ever happens while anonymous -- once
// window.VerbBoardAuth.currentUser() is truthy, every function in this file
// is a no-op, so the whole mechanism goes permanently dormant for that
// browser without needing to clear any of the keys below.
//
// Two delivery surfaces share this one mechanism (see practice_loop.js's
// showWrapUp() and login_nudge_card.js):
//   - badge-earned: always fires the prompt immediately, regardless of the
//     running score -- the only thing that can suppress it is the lifetime
//     show cap (deliberately does NOT respect the dismissal cooldown below;
//     it's the strongest signal and is allowed to re-ask after a dismiss,
//     up to the lifetime cap).
//   - score crossing LOGIN_NUDGE_THRESHOLD: fires the inline /verbs card,
//     but only if nothing has already shown this same page load (see
//     shownThisPageLoad below) and the dismissal cooldown has elapsed.
//
// localStorage keys (anonymous-only, never written once signed in):
//   login_nudge_score              -- running weighted engagement score (int)
//   login_nudge_shows_count        -- lifetime count of prompts actually
//                                      shown, across both surfaces combined
//                                      (int, capped at LOGIN_NUDGE_LIFETIME_CAP)
//   login_nudge_dismissed_at_score -- score value at the moment of the most
//                                      recent dismissal; the threshold-card
//                                      surface stays quiet until the running
//                                      score reaches roughly double this
//                                      (badge-earned ignores this key)
(function () {
  var SCORE_KEY = 'login_nudge_score';
  var SHOWS_KEY = 'login_nudge_shows_count';
  var DISMISSED_AT_KEY = 'login_nudge_dismissed_at_score';

  var WEIGHT_VERB_VIEW = 1;
  var WEIGHT_KNOWN_MARKED = 3;
  var WEIGHT_BADGE_EARNED = 10;

  var THRESHOLD = 12;
  var LIFETIME_SHOW_CAP = 5;

  // Set in-memory (not persisted) the first time a nudge surface actually
  // renders during this page's lifetime, so the badge-earned wrap-up CTA
  // and the /verbs threshold card never both fire for the same page load.
  // Resets naturally on every navigation/reload.
  var shownThisPageLoad = false;

  function isAnonymous() {
    return !(window.VerbBoardAuth && window.VerbBoardAuth.currentUser());
  }

  // Synchronously claims the "one nudge per page load" slot, independent of
  // script order or promise/microtask timing. showWrapUp() (practice_loop.js)
  // calls this synchronously, during initial parse, before it ever awaits
  // whenAuthReady() -- so by the time the /verbs threshold card's own
  // shouldShowThresholdCard() check runs (also gated behind whenAuthReady()),
  // shownThisPageLoad is already reserved if the badge path is in play at
  // all, regardless of which of the two async callbacks happens to resolve
  // first. Deliberately does not touch SHOWS_KEY/the lifetime-cap counter --
  // that only advances via markShown(), once a surface is actually rendered
  // (the badge path may still end up not rendering, e.g. if the live
  // isAnonymous() check fails after whenAuthReady() resolves).
  function reserveThisPageLoad() {
    shownThisPageLoad = true;
  }

  // Safely wait for Firebase auth to have resolved at least once before
  // trusting isAnonymous(), regardless of how/when the calling script runs.
  // auth.js is always `defer`red, so a *non*-deferred caller (verbs.html's
  // body scripts, e.g. practice_loop.js/login_nudge_card.js, run inline
  // during HTML parsing) can execute before window.VerbBoardAuth even
  // exists yet -- calling window.VerbBoardAuth.ready() directly at that
  // point would throw. Waiting for DOMContentLoaded first (deferred scripts
  // always finish before it fires) sidesteps that without callers needing
  // to know which loading strategy they were included with.
  function whenAuthReady(callback) {
    function run() {
      if (window.VerbBoardAuth && window.VerbBoardAuth.ready) {
        window.VerbBoardAuth.ready().then(callback);
      } else {
        // auth.js didn't load at all (shouldn't happen -- it's included on
        // every page) -- fail open rather than never calling back.
        callback();
      }
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', run, { once: true });
    } else {
      run();
    }
  }

  function readScore() {
    return parseInt(localStorage.getItem(SCORE_KEY), 10) || 0;
  }

  function readShowsCount() {
    return parseInt(localStorage.getItem(SHOWS_KEY), 10) || 0;
  }

  function bump(weight) {
    if (!isAnonymous()) return readScore();
    var next = readScore() + weight;
    localStorage.setItem(SCORE_KEY, String(next));
    return next;
  }

  function recordVerbView() {
    return bump(WEIGHT_VERB_VIEW);
  }

  function recordKnownMarked() {
    return bump(WEIGHT_KNOWN_MARKED);
  }

  function lifetimeCapReached() {
    return readShowsCount() >= LIFETIME_SHOW_CAP;
  }

  function inDismissalCooldown() {
    var raw = localStorage.getItem(DISMISSED_AT_KEY);
    if (raw === null) return false;
    var dismissedScore = parseInt(raw, 10) || 0;
    return readScore() < dismissedScore * 2;
  }

  function hasCrossedThreshold() {
    return readScore() >= THRESHOLD;
  }

  // Badge-earned is the strongest, most natural stop-and-look moment: it
  // always fires regardless of the running score and regardless of any
  // prior dismissal -- the lifetime cap is the only thing that can stop it.
  // Still gated on anonymity so a signed-in user never sees or accrues this.
  function recordBadgeEarned() {
    bump(WEIGHT_BADGE_EARNED);
    return isAnonymous() && !lifetimeCapReached();
  }

  function shouldShowThresholdCard() {
    return (
      isAnonymous() &&
      !lifetimeCapReached() &&
      !inDismissalCooldown() &&
      !shownThisPageLoad &&
      hasCrossedThreshold()
    );
  }

  // Call exactly once, right when a nudge surface is actually inserted into
  // the DOM (not merely decided-eligible) -- counts against the lifetime cap
  // and blocks the other surface from also firing this same page load.
  function markShown() {
    shownThisPageLoad = true;
    localStorage.setItem(SHOWS_KEY, String(readShowsCount() + 1));
  }

  function markDismissed() {
    localStorage.setItem(DISMISSED_AT_KEY, String(readScore()));
  }

  // Shared DOM builder for both surfaces (wrap-up modal CTA row + /verbs
  // inline card). Built with createElement/textContent rather than
  // innerHTML template literals -- copyText comes from window.UI (server
  // -rendered i18n JSON), which is already safe, but this keeps the pattern
  // identical to showWrapUp()'s existing per-verb-label handling in
  // practice_loop.js, so there is exactly one HTML-building convention for
  // this file to reason about.
  function buildCta(copyText) {
    var ui = window.UI || {};

    var wrap = document.createElement('div');
    wrap.className = 'vb-login-nudge';

    var text = document.createElement('span');
    text.className = 'vb-login-nudge-text';
    text.textContent = copyText;
    wrap.appendChild(text);

    var actions = document.createElement('div');
    actions.className = 'vb-login-nudge-actions';

    var signInBtn = document.createElement('button');
    signInBtn.type = 'button';
    signInBtn.className = 'vb-login-nudge-signin btn-pill-navy';
    signInBtn.textContent = ui['auth.login'] || 'Login';
    signInBtn.addEventListener('click', function () {
      if (window.VerbBoardAuth && window.VerbBoardAuth.signIn) {
        window.VerbBoardAuth.signIn().catch(function (err) {
          if (err && err.code === 'auth/cancelled-popup-request') return;
          console.error('VB login-nudge sign-in error:', err);
        });
      }
    });

    var dismissBtn = document.createElement('button');
    dismissBtn.type = 'button';
    dismissBtn.className = 'vb-login-nudge-dismiss';
    var dismissLabel = ui['home.install_hint_dismiss'] || 'Dismiss';
    dismissBtn.setAttribute('aria-label', dismissLabel);
    dismissBtn.textContent = '×';
    dismissBtn.addEventListener('click', function () {
      markDismissed();
      wrap.remove();
    });

    actions.appendChild(signInBtn);
    actions.appendChild(dismissBtn);
    wrap.appendChild(actions);

    // If the user signs in (via this CTA or any other path, e.g. the bottom
    // nav) while this element is still on the page, remove it -- the whole
    // mechanism is dormant once signed in, so a leftover "sign in" prompt
    // right after signing in would look broken. vb:progress-hydrated only
    // ever fires post sign-in (hydrateProgress() returns early while
    // anonymous), so this never fires spuriously for an anonymous viewer.
    window.addEventListener(
      'vb:progress-hydrated',
      function () {
        wrap.remove();
      },
      { once: true }
    );

    return wrap;
  }

  window.VerbBoardLoginNudge = {
    recordVerbView: recordVerbView,
    recordKnownMarked: recordKnownMarked,
    recordBadgeEarned: recordBadgeEarned,
    shouldShowThresholdCard: shouldShowThresholdCard,
    markShown: markShown,
    markDismissed: markDismissed,
    reserveThisPageLoad: reserveThisPageLoad,
    buildCta: buildCta,
    isAnonymous: isAnonymous,
    whenAuthReady: whenAuthReady,
  };
})();
