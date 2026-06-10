'use strict';

(function () {
  const lang = window.VB_LANGUAGE;

  const verbs = window.VB_VERBS;
  const recentSet = new Set(window.VB_RECENT_IDS || []);

  const ui = window.UI || {};

  const searchEl = document.getElementById('vb-search');
  const listEl = document.getElementById('vb-list');
  const toggleEl = document.getElementById('vb-filter-toggle');
  const sortEl = document.getElementById('vb-sort');
  const practiceEl = document.getElementById('practice-panel');

  const progressFillEl = document.querySelector('.progress-fill');
  const progressCountEl = document.querySelector('.progress-count');

  var _isMobile = window.matchMedia('(any-pointer: coarse)').matches;

  const filters = window.VerbBoardVerbFilters.createVerbFilters({
    lang,
    verbs,
    recentSet,
    listEl,
    searchEl,
    sortEl,
    toggleEl,
    progressFillEl,
    progressCountEl,
    loadMoreWrapEl: document.getElementById('vb-load-more-wrap'),
    displayBatch: window.VB_DISPLAY_BATCH || 20,
    ui,
  });

  const practiceLoop = window.VerbBoardPracticeLoop.createPracticeLoop({
    lang,
    verbs,
    practiceEl,
    ui,
    render: filters.render,
    updateProgress: filters.updateProgress,
  });
  window.VerbBoardPracticeLoopInstance = practiceLoop;

  // Search mode pill toggle
  const vbPills = document.getElementById('vb-search-mode-pills');
  const vbSourceLang = document.getElementById('vb-source-lang-input');
  const vbSubmitBtn = document.getElementById('vb-search-submit-btn');

  if (vbPills && vbSubmitBtn) {
    const nativePlaceholder = searchEl ? searchEl.placeholder : '';
    const enPlaceholder = searchEl ? (searchEl.dataset.placeholderEn || '') : '';

    function applyVbMode(mode) {
      vbPills.querySelectorAll('.search-mode-pill').forEach(function (p) {
        p.classList.toggle('active', p.dataset.mode === mode);
      });
      if (vbSourceLang) vbSourceLang.value = mode === 'native' ? '' : mode;
      vbSubmitBtn.setAttribute('formaction', mode === 'native' ? '/search_verb' : '/search_verb_by_lang');
      if (searchEl) searchEl.placeholder = mode === 'en' ? enPlaceholder : nativePlaceholder;
    }

    // Restore mode from server state (e.g. after failed translated search)
    const initialVbMode = (vbSourceLang && vbSourceLang.value) ? vbSourceLang.value : 'native';
    applyVbMode(initialVbMode);

    vbPills.querySelectorAll('.search-mode-pill').forEach(function (pill) {
      pill.addEventListener('click', function () {
        applyVbMode(pill.dataset.mode);
      });
    });
  }

  // Clear no-match notice on first keystroke
  const vbNotice = document.getElementById('vb-notice');
  if (vbNotice && searchEl) {
    searchEl.addEventListener('input', function () {
      vbNotice.style.display = 'none';
    }, { once: true });
  }

  filters.render();
  filters.updateProgress();

  practiceLoop.renderPracticePanel();
  practiceLoop.maybeShowWrapUp();

  if (window.location.hash === '#practice-panel' && practiceEl) {
    // Delay until after layout is stable -- low-end Android can take 150-300ms
    // from DOMContentLoaded to first paint. Double rAF inside setTimeout ensures
    // the scroll fires after the browser has committed the layout.
    setTimeout(function () {
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          practiceEl.scrollIntoView({ block: 'start' });
        });
      });
    }, 200);
  }

  // W2: keep Practice bottom-nav tab active while hash == #practice-panel
  (function () {
    var practiceTab = document.querySelector('.bottom-nav .bnav-tab[href*="#practice-panel"]');
    var browseTab = document.querySelector('.bottom-nav .bnav-tab[href*="/verbs"]:not([href*="#"])');
    function syncBnavPractice() {
      var on = location.hash === '#practice-panel';
      if (practiceTab) {
        practiceTab.classList.toggle('bnav-tab--active', on);
        practiceTab.setAttribute('aria-current', on ? 'page' : 'false');
      }
      if (browseTab) {
        browseTab.classList.toggle('bnav-tab--active', !on);
        browseTab.setAttribute('aria-current', on ? 'false' : 'page');
      }
    }
    syncBnavPractice();
    window.addEventListener('hashchange', syncBnavPractice);
  })();
  // NOTE: syncPracticeBadgesFromServer() is intentionally NOT called here.
  // auth.js is deferred, so window.VerbBoardAuth does not exist yet at this
  // point. The call is made inside the vb:progress-hydrated handler below,
  // which fires only after Firebase auth has resolved and a token is available.

  // After Firebase auth resolves and localStorage is hydrated from the server:
  // re-render the verb list, progress bar, and fetch+render badges.
  // NOTE: this fires once per page load. Changes made on another device while
  // this page is open are not reflected until the next navigation.
  window.addEventListener('vb:progress-hydrated', function () {
    filters.render();
    filters.updateProgress();
    practiceLoop.syncPracticeBadgesFromServer();
    // syncPracticeBadgesFromServer fetches badges and calls renderPracticePanel()
    // itself on success, so no separate renderPracticePanel() call needed here.
  });

  // After sign-out: auth.js has already cleared all user-specific localStorage
  // keys across all languages.  Just re-render so the UI reflects empty state.
  window.addEventListener('vb:auth-signed-out', function () {
    filters.render();
    filters.updateProgress();
    practiceLoop.renderPracticePanel();
  });

  // Mobile: show all pre-loaded verbs at once (no display-batch cap). If there are
  // more verbs beyond VERBS_PAGE_LIMIT, the show-more button fetches them on demand.
  (function () {
    if (!_isMobile) return;
    filters.showAll();
  }());

  // Desktop back-nav: re-fetch verbs that were previously loaded but are absent
  // after page reload (VB_VERBS only contains the server-rendered page-limit batch).
  (function () {
    if (_isMobile) return;

    var navType = (performance.getEntriesByType('navigation')[0] || {}).type;
    if (navType !== 'back_forward') return;

    var needed = parseInt(sessionStorage.getItem('vb-display-count:' + lang) || '0', 10) - window.VB_VERBS.length;
    if (!(needed > 0)) return;
    if (window.VB_VERBS.length >= (window.VB_VERBS_TOTAL || 0)) return;

    fetch(
      '/api/verbs?language=' + encodeURIComponent(lang) +
      '&offset=' + window.VB_VERBS.length +
      '&limit=' + Math.min(needed, 100)
    )
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        data.verbs.forEach(function (v) { window.VB_VERBS.push(v); });
        window.VB_VERBS_TOTAL = data.total;
        filters.render();
      })
      .catch(function () {});
  }());

  // Load-more: client-side batch first, then server fetch when pre-loaded verbs exhausted
  (function () {
    var btnEl = document.getElementById('vb-load-more');
    if (!btnEl) return;

    var batchSize = window.VB_DISPLAY_BATCH || 20;
    var loadMoreLabel = (window.UI && window.UI['verbs.load_more']) || 'Show more verbs';

    btnEl.addEventListener('click', function () {
      if (filters.hasMoreToShow()) {
        filters.showMore();
        return;
      }

      var offset = window.VB_VERBS.length;
      btnEl.disabled = true;
      btnEl.textContent = '…';

      fetch(
        '/api/verbs?language=' + encodeURIComponent(lang) +
        '&offset=' + offset +
        '&limit=' + batchSize
      )
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (data) {
          data.verbs.forEach(function (v) { window.VB_VERBS.push(v); });
          window.VB_VERBS_TOTAL = data.total;
          filters.showMore();
          btnEl.disabled = false;
          btnEl.textContent = loadMoreLabel;
        })
        .catch(function () {
          btnEl.disabled = false;
          btnEl.textContent = loadMoreLabel;
        });
    });
  }());
})();
