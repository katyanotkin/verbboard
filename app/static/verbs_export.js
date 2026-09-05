'use strict';

// Client-side CSV export of a user's known verbs for the current language,
// in a plain "front,back" shape Anki's CSV importer reads directly. No
// server-side export endpoint: fetches the full verb catalog page-by-page
// from the existing /api/verbs endpoint, then filters to the known set
// already in localStorage.
(function () {
  function csvEscape(value) {
    var s = value == null ? '' : String(value);
    // Neutralize spreadsheet formula injection (Excel/Numbers, not Anki) if
    // this CSV is ever opened outside Anki: a value starting with one of
    // these is otherwise interpreted as a formula on open.
    if (/^[=+\-@\t\r]/.test(s)) {
      s = "'" + s;
    }
    if (/[",\r\n]/.test(s)) {
      s = '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  function fetchAllVerbs(language, uiLang) {
    var all = [];
    var limit = 100;

    function fetchPage(offset) {
      return fetch(
        '/api/verbs?language=' + encodeURIComponent(language) +
          '&ui_language=' + encodeURIComponent(uiLang) +
          '&include_translations=1' +
          '&offset=' + offset +
          '&limit=' + limit,
        { credentials: 'same-origin' }
      )
        .then(function (res) {
          if (!res.ok) return null;
          return res.json();
        })
        .then(function (data) {
          if (!data) return all;
          all = all.concat(data.verbs || []);
          if (data.has_more) return fetchPage(offset + limit);
          return all;
        });
    }

    return fetchPage(0);
  }

  function downloadCsv(filename, csvText) {
    var blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('vb-export-btn');
    if (!btn || !window.VerbBoardStorage) return;

    var lang = window.VB_LANGUAGE;
    var uiLang = window.VB_UI_LANG || 'en';

    function updateVisibility() {
      var knownSet = window.VerbBoardStorage.readSet('known:' + lang);
      btn.hidden = knownSet.size === 0;
    }

    // Known-verb data can arrive after DOMContentLoaded: hydrateProgress()
    // (auth.js) merges the server's known-verb list into localStorage
    // asynchronously on login and fires vb:progress-hydrated when done --
    // the most common case for a returning power user on a new
    // device/session, who is exactly who this feature is for.
    updateVisibility();
    window.addEventListener('vb:progress-hydrated', updateVisibility);

    btn.addEventListener('click', function () {
      if (btn.disabled) return;
      var knownSet = window.VerbBoardStorage.readSet('known:' + lang);
      if (!knownSet.size) return;

      btn.disabled = true;
      var originalText = btn.textContent;
      btn.textContent = '…';

      fetchAllVerbs(lang, uiLang)
        .then(function (allVerbs) {
          var lines = allVerbs
            .filter(function (v) { return knownSet.has(v.id); })
            .map(function (v) { return csvEscape(v.lemma) + ',' + csvEscape(v.translation || ''); });
          downloadCsv('verbboard_' + lang + '_known.csv', lines.join('\r\n'));
        })
        .catch(function (err) {
          console.error('Verb export failed:', err);
        })
        .finally(function () {
          btn.disabled = false;
          btn.textContent = originalText;
        });
    });
  });
})();
