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
  practiceLoop.syncPracticeBadgesFromServer();
})();
