'use strict';

// "Rate on Google Play" link rows (issue #24). A plain TWA cannot call the Play
// in-app review API, so these are plain links to the store listing, shown only
// on Android (browser or installed app, never a WebView). Two occasions, both
// value-neutral (Play policy: no incentive, not gated on sentiment):
//   - practice: the wrap-up modal after the 2nd completed practice
//   - votd:     a one-line row on /learn once the Verb of the Day chip on home
//               has been opened 5 times on this device (any language)
// Shared cap per device: at most 2 asks, at least 30 days apart, and never
// again after a tap.
//
// localStorage keys:
//   rate_nudge_completed -- completed practice sessions counted on this device
//   rate_nudge_votd_opens -- Verb of the Day chip opens counted on this device
//   rate_nudge_votd_baseline -- votd opens at the time of the last ask (never reset to 0)
//   rate_nudge_asks      -- how many times a row was shown
//   rate_nudge_last_at   -- ms timestamp of the last show
//   rate_nudge_tapped    -- '1' once the link was tapped (stop asking)
//   rate_nudge_done      -- legacy single-ask flag, migrated into the keys above
// Signed-in users: syncWithServer() (called from auth.js hydrateProgress()) posts
// this state as absolute values to POST /api/progress/rate_nudge and writes the
// field-wise max (OR for tapped) back, so the state follows the account across
// devices. Every field only grows; anonymous users stay local only.
(function () {
  var COMPLETED_KEY = 'rate_nudge_completed';
  var ASKS_KEY = 'rate_nudge_asks';
  var LAST_AT_KEY = 'rate_nudge_last_at';
  var TAPPED_KEY = 'rate_nudge_tapped';
  var LEGACY_DONE_KEY = 'rate_nudge_done';
  var MIN_COMPLETED = 2;
  var VOTD_KEY = 'rate_nudge_votd_opens';
  var VOTD_BASELINE_KEY = 'rate_nudge_votd_baseline';
  var MIN_VOTD_OPENS = 5;
  var MAX_ASKS = 2;
  var SYNC_TIMEOUT_MS = 4000;
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

  // Call on each click of the Verb of the Day chip on home. Counted across
  // languages; the row itself shows on the /learn page that click opens.
  function recordVotdOpened() {
    write(VOTD_KEY, String(readInt(VOTD_KEY) + 1));
  }

  // True when enough Verb of the Day opens have accrued and an ask is allowed.
  function votdNudgeDue() {
    return readInt(VOTD_KEY) - readInt(VOTD_BASELINE_KEY) >= MIN_VOTD_OPENS && canAsk();
  }

  // Live check at render time (the wrap-up payload can outlive its page).
  function canShow() {
    return canAsk();
  }

  function markShown() {
    write(ASKS_KEY, String(readInt(ASKS_KEY) + 1));
    write(LAST_AT_KEY, String(Date.now()));
    write(VOTD_BASELINE_KEY, String(readInt(VOTD_KEY)));
  }

  // Pure: field-wise max for counts and last_at, OR for tapped. Missing or
  // garbage fields count as 0/false, so merging never lowers anything.
  function mergeState(a, b) {
    a = a || {};
    b = b || {};
    function num(v) { return Math.max(0, Number(v) || 0); }
    var merged = { tapped: a.tapped === true || b.tapped === true };
    ['votd_opens', 'votd_opens_at_last_ask', 'completed', 'asks', 'last_at'].forEach(function (k) {
      merged[k] = Math.max(num(a[k]), num(b[k]));
    });
    return merged;
  }

  function readState() {
    migrateLegacy();
    return {
      votd_opens: readInt(VOTD_KEY),
      votd_opens_at_last_ask: readInt(VOTD_BASELINE_KEY),
      completed: readInt(COMPLETED_KEY),
      asks: readInt(ASKS_KEY),
      last_at: readInt(LAST_AT_KEY),
      tapped: read(TAPPED_KEY) === '1',
    };
  }

  function writeState(state) {
    write(VOTD_KEY, String(state.votd_opens));
    write(VOTD_BASELINE_KEY, String(state.votd_opens_at_last_ask));
    write(COMPLETED_KEY, String(state.completed));
    write(ASKS_KEY, String(state.asks));
    write(LAST_AT_KEY, String(state.last_at));
    if (state.tapped) write(TAPPED_KEY, '1');
  }

  // Signed-in only (auth.js calls this with the Firebase ID token on every
  // hydrateProgress()). Sends absolute local values, stores max(local, server).
  // Any failure keeps the local state untouched.
  async function syncWithServer(token) {
    try {
      if (!token) return false;
      var local = readState();
      // Short timeout: hydrateProgress() awaits this, so a hung request must not
      // hold up the rest of the progress merge.
      var controller = typeof AbortController === 'function' ? new AbortController() : null;
      var timer = controller ? setTimeout(function () { controller.abort(); }, SYNC_TIMEOUT_MS) : null;
      try {
        var response = await fetch('/api/progress/rate_nudge', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
          body: JSON.stringify(local),
          signal: controller ? controller.signal : undefined,
        });
        if (!response.ok) return false;
        writeState(mergeState(readState(), await response.json()));
        return true;
      } finally {
        if (timer) clearTimeout(timer);
      }
    } catch (_) {
      return false;
    }
  }

  // source: 'practice' | 'votd' (utm_medium and the click beacon's source).
  function buildCta(copyText, linkLabel, source) {
    source = source === 'votd' ? 'votd' : 'practice';
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
    recordVotdOpened: recordVotdOpened,
    votdNudgeDue: votdNudgeDue,
    canShow: canShow,
    markShown: markShown,
    mergeState: mergeState,
    syncWithServer: syncWithServer,
    isAndroidBrowser: isAndroidBrowser,
  };
})();
