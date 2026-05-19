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
  const progressTotalEl = document.querySelector('.progress-total');

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
    progressTotalEl,
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

  filters.render();
  filters.updateProgress();

  practiceLoop.renderPracticePanel();
  practiceLoop.maybeShowWrapUp();
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

  // After sign-out: clear this language's localStorage state so stale
  // achievements from the previous user are not shown.
  window.addEventListener('vb:auth-signed-out', function () {
    localStorage.removeItem(`known:${lang}`);
    localStorage.removeItem(`seen:${lang}`);
    localStorage.removeItem(`practice_badges:${lang}`);
    filters.render();
    filters.updateProgress();
    practiceLoop.renderPracticePanel();
  });
})();
