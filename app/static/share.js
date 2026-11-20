// Share a study language with a friend (issue #128). Mobile uses the native share sheet,
// everything else copies the link. The beacon is set-once per session-day and fire-and-forget.
(function () {
  'use strict';

  var beaconSent = false;
  var statusTimer = null;

  function beacon() {
    if (beaconSent) return;
    beaconSent = true;
    try {
      fetch('/api/analytics/practice_event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event: 'share_tapped' }),
        keepalive: true
      }).catch(function () {});
    } catch (e) { /* analytics must never block sharing */ }
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var field = document.createElement('textarea');
      field.value = text;
      field.setAttribute('readonly', '');
      field.style.position = 'fixed';
      field.style.opacity = '0';
      document.body.appendChild(field);
      field.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      document.body.removeChild(field);
      if (ok) resolve(); else reject(new Error('copy failed'));
    });
  }

  function showStatus(message) {
    var status = document.getElementById('vb-share-status');
    if (!status) return;
    status.textContent = message;
    if (statusTimer) clearTimeout(statusTimer);
    statusTimer = setTimeout(function () { status.textContent = ''; }, 2500);
  }

  // When even copying fails (insecure context, some in-app browsers) show the link itself so it can be copied by hand.
  function copyOrShow(url, copiedLabel) {
    copyText(url).then(function () { showStatus(copiedLabel); }).catch(function () { showStatus(url); });
  }

  function onShareClick(event) {
    var btn = event.currentTarget;
    var url = btn.getAttribute('data-share-url') || '';
    var text = btn.getAttribute('data-share-text') || '';
    var title = btn.getAttribute('data-share-title') || '';
    var copiedLabel = btn.getAttribute('data-copied-label') || '';
    if (!url) return;
    beacon();

    if (navigator.share) {
      // AbortError = the user closed the sheet; anything else falls back to copying.
      navigator.share({ title: title, text: text, url: url }).catch(function (err) {
        if (err && err.name === 'AbortError') return;
        copyOrShow(url, copiedLabel);
      });
      return;
    }
    copyOrShow(url, copiedLabel);
  }

  function init() {
    var btn = document.getElementById('vb-share-btn');
    if (btn) btn.addEventListener('click', onShareClick);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
}());
