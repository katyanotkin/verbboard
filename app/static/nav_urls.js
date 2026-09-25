// Single builder for /learn and /verbs URLs constructed in JS.
// Every link carries `language` and (when set) `ui_language`; do not hand-append
// these params elsewhere. Reads window.VB_UI_LANG at call time.
(function () {
  'use strict';

  var root = typeof window !== 'undefined' ? window : globalThis;

  function uiSuffix() {
    var uiLang = root.VB_UI_LANG || '';
    return uiLang ? '&ui_language=' + encodeURIComponent(uiLang) : '';
  }

  function verbsUrl(lang) {
    return '/verbs?language=' + encodeURIComponent(lang) + uiSuffix();
  }

  function learnUrl(lang, verbId, options) {
    var returnTo = options && options.returnTo;
    return (
      '/learn?language=' + encodeURIComponent(lang) +
      '&verb_id=' + encodeURIComponent(verbId) +
      (returnTo ? '&return_to=' + encodeURIComponent(returnTo) : '') +
      uiSuffix()
    );
  }

  var api = { verbsUrl: verbsUrl, learnUrl: learnUrl };
  root.VerbBoardNav = api;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})();
