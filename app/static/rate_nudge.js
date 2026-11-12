'use strict';

// "Rate on Google Play" link rows (issue #24). A plain TWA cannot call the Play
// in-app review API, so these are plain links to the store listing, shown only
// on Android (browser or installed app, never a WebView). Two occasions, both
// value-neutral (Play policy: no incentive, not gated on sentiment):
//   - practice: the wrap-up modal after the 2nd completed practice
//   - known:    a one-line row on /learn once 5 verbs are starred (the real
//               known-verb count, so star/unstar cannot game it)
// Shared cap per device: at most 2 asks, at least 30 days apart, and never
// again after a tap.
//
// localStorage keys:
//   rate_nudge_completed -- completed practice sessions counted on this device
//   rate_nudge_asks      -- how many times a row was shown
//   rate_nudge_last_at   -- ms timestamp of the last show
//   rate_nudge_tapped    -- '1' once the link was tapped (stop asking)
//   rate_nudge_done      -- legacy single-ask flag, migrated into the keys above
(function () {
  var COMPLETED_KEY = 'rate_nudge_completed';
  var ASKS_KEY = 'rate_nudge_asks';
  var LAST_AT_KEY = 'rate_nudge_last_at';
  var TAPPED_KEY = 'rate_nudge_tapped';
  var LEGACY_DONE_KEY = 'rate_nudge_done';
  var MIN_COMPLETED = 2;
  var MIN_KNOWN = 5;
  var MAX_ASKS = 2;
  var MIN_GAP_MS = 30 * 24 * 60 * 60 * 1000;
  var PLAY_URL_BASE =
    'https://play.google.com/store/apps/details?id=com.verbboard.app' +
    '&referrer=utm_source%3Dverbboard_web%26utm_medium%3D';

  function read(key) {
    try { return localStorage.getItem(key); } catch (_) { return null; }
  }
  function write(key, value) {
    try { localStorage.setItem(key, value); } catch (_) {}
  }
  function readInt(key) {
    return parseInt(read(key), 10) || 0;
  }

  function isAndroidBrowser(ua) {
    ua = ua || '';
    return /Android/i.test(ua) && !/; wv\)/.test(ua);
  }

  // The first version stored a single "asked" flag: count it as one ask now.
  function migrateLegacy() {
    if (read(LEGACY_DONE_KEY) === '1' && !read(ASKS_KEY)) {
      write(ASKS_KEY, '1');
      write(LAST_AT_KEY, String(Date.now()));
    }
  }

  function canAsk() {
    migrateLegacy();
    if (!isAndroidBrowser(navigator.userAgent)) return false;
    if (read(TAPPED_KEY) === '1') return false;
    var asks = readInt(ASKS_KEY);
    if (asks >= MAX_ASKS) return false;
    return asks === 0 || Date.now() - readInt(LAST_AT_KEY) >= MIN_GAP_MS;
  }

  // Call once per completed practice. True when this completion should carry
  // the rate row.
  function recordCompleted() {
    var count = readInt(COMPLETED_KEY) + 1;
    write(COMPLETED_KEY, String(count));
    return count >= MIN_COMPLETED && canAsk();
  }

  // Call after a verb is marked known (not un-marked), with the number of
  // known verbs in that language. True when the row should show now.
  function recordKnownMarked(knownCount) {
    return (knownCount || 0) >= MIN_KNOWN && canAsk();
  }

  // Live check at render time (the wrap-up payload can outlive its page).
  function canShow() {
    return canAsk();
  }

  function markShown() {
    write(ASKS_KEY, String(readInt(ASKS_KEY) + 1));
    write(LAST_AT_KEY, String(Date.now()));
  }

  // source: 'practice' | 'known' (utm_medium and the click beacon's source).
  function buildCta(copyText, linkLabel, source) {
    source = source === 'known' ? 'known' : 'practice';
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
    link.href = PLAY_URL_BASE + source + '_nudge';
    link.rel = 'noopener';
    link.textContent = linkLabel;
    link.addEventListener('click', function () {
      write(TAPPED_KEY, '1');
      try {
        fetch('/api/analytics/rate_clicked', {
          method: 'POST',
          keepalive: true,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source: source }),
        }).catch(function () {});
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

  // The one place a rate row is rendered. Every occasion calls this: it
  // builds the row with the shared (localized) copy, appends it to
  // `container` (before `beforeNode` when given) and counts the ask.
  function show(container, source, beforeNode) {
    if (!container) return false;
    var ui = window.UI || {};
    var row = buildCta(
      ui['rate_nudge.text'] || 'Enjoying VerbBoard? A rating on Google Play helps other learners find it.',
      ui['rate_nudge.cta'] || 'Rate on Google Play',
      source
    );
    container.insertBefore(row, beforeNode || null);
    markShown();
    return true;
  }

  window.VerbBoardRateNudge = {
    show: show,
    recordCompleted: recordCompleted,
    recordKnownMarked: recordKnownMarked,
    canShow: canShow,
    markShown: markShown,
    isAndroidBrowser: isAndroidBrowser,
  };
})();
