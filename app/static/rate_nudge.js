'use strict';

// One-time "Rate on Google Play" row in the practice wrap-up modal (issue #24).
// A plain TWA cannot call the Play in-app review API, so this is a plain link
// to the store listing, shown only on Android (browser or installed app, never
// a WebView). Rules: after the 2nd completed practice, asked once per device
// (never nag twice), no incentive, not gated on sentiment.
//
// localStorage keys:
//   rate_nudge_completed -- completed practice sessions counted on this device
//   rate_nudge_done      -- '1' once the row was shown (never shown again)
(function () {
  var COMPLETED_KEY = 'rate_nudge_completed';
  var DONE_KEY = 'rate_nudge_done';
  var MIN_COMPLETED = 2;
  var PLAY_URL =
    'https://play.google.com/store/apps/details?id=com.verbboard.app' +
    '&referrer=utm_source%3Dverbboard_web%26utm_medium%3Dpractice_nudge';

  function read(key) {
    try { return localStorage.getItem(key); } catch (_) { return null; }
  }
  function write(key, value) {
    try { localStorage.setItem(key, value); } catch (_) {}
  }

  function isAndroidBrowser(ua) {
    ua = ua || '';
    return /Android/i.test(ua) && !/; wv\)/.test(ua);
  }

  function isDone() {
    return read(DONE_KEY) === '1';
  }

  // Call once per completed practice. True when this completion should carry
  // the rate row.
  function recordCompleted() {
    var count = (parseInt(read(COMPLETED_KEY), 10) || 0) + 1;
    write(COMPLETED_KEY, String(count));
    return count >= MIN_COMPLETED && !isDone() && isAndroidBrowser(navigator.userAgent);
  }

  // Live check at render time (the wrap-up payload can outlive its page).
  function canShow() {
    return !isDone() && isAndroidBrowser(navigator.userAgent);
  }

  function markShown() {
    write(DONE_KEY, '1');
  }

  function buildCta(copyText, linkLabel) {
    var wrap = document.createElement('div');
    wrap.className = 'vb-login-nudge vb-rate-nudge';

    var text = document.createElement('span');
    text.className = 'vb-login-nudge-text';
    text.textContent = copyText;
    wrap.appendChild(text);

    var actions = document.createElement('div');
    actions.className = 'vb-login-nudge-actions';

    var link = document.createElement('a');
    link.className = 'vb-login-nudge-signin btn-pill-navy';
    link.href = PLAY_URL;
    link.rel = 'noopener';
    link.textContent = linkLabel;
    link.addEventListener('click', function () {
      try {
        fetch('/api/analytics/rate_clicked', { method: 'POST', keepalive: true }).catch(function () {});
      } catch (_) {}
      wrap.remove();
    });

    var dismiss = document.createElement('button');
    dismiss.type = 'button';
    dismiss.className = 'vb-login-nudge-dismiss';
    var ui = window.UI || {};
    dismiss.setAttribute('aria-label', ui['home.install_hint_dismiss'] || 'Dismiss');
    dismiss.textContent = '×';
    dismiss.addEventListener('click', function () { wrap.remove(); });

    actions.appendChild(link);
    actions.appendChild(dismiss);
    wrap.appendChild(actions);
    return wrap;
  }

  window.VerbBoardRateNudge = {
    recordCompleted: recordCompleted,
    canShow: canShow,
    markShown: markShown,
    buildCta: buildCta,
    isAndroidBrowser: isAndroidBrowser,
  };
})();
