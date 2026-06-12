'use strict';

(function () {
  function esc(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function createVerbFilters(config) {
    const {
      lang,
      verbs,
      recentSet,
      listEl,
      searchEl,
      sortEl,
      toggleEl,
      progressFillEl,
      progressCountEl,
      loadMoreWrapEl,
      displayBatch,
      ui,
    } = config;

    const storage = window.VerbBoardStorage;

    const stateKey = `vb-ui:${lang}`;
    const displayCountKey = `vb-display-count:${lang}`;
    const batch = displayBatch || 20;

    const navType = (performance.getEntriesByType('navigation')[0] || {}).type;
    const isBackNav = navType === 'back_forward' ||
      (!!document.referrer && (
        document.referrer.includes('/learn') ||
        document.referrer.includes('/feedback')
      ));
    const savedCount = isBackNav ? parseInt(sessionStorage.getItem(displayCountKey) || '0', 10) : 0;
    let displayCount = (savedCount >= batch) ? savedCount : batch;

    function readHash() {
      const params = new URLSearchParams(window.location.hash.slice(1));

      return {
        filter: params.get('filter'),
        sort: params.get('sort'),
      };
    }

    function readStorageState() {
      return storage.readJson(stateKey, {
        filter: null,
        sort: null,
      });
    }

    const fromHash = readHash();
    const fromStorage = readStorageState();

    const VALID_SORTS = new Set(['alpha', 'newest']);

    let activeFilter = fromHash.filter || fromStorage.filter || 'all';
    let activeSort = fromHash.sort || fromStorage.sort || 'alpha';
    if (!VALID_SORTS.has(activeSort)) {
      activeSort = 'alpha';
    }
    let searchQuery = (searchEl && searchEl.value) ? searchEl.value.trim() : '';

    function writeState() {
      const params = new URLSearchParams();

      params.set('filter', activeFilter);
      params.set('sort', activeSort);

      history.replaceState(null, '', '#' + params.toString());

      storage.writeJson(stateKey, {
        filter: activeFilter,
        sort: activeSort,
      });
    }

    function known() {
      return storage.readSet(`known:${lang}`);
    }

    function seen() {
      return storage.readSet(`seen:${lang}`);
    }

    function visibleVerbs() {
      const knownSet = known();
      const seenSet = seen();
      const query = searchQuery.trim().toLowerCase();

      let rows = verbs.filter(function (verb) {
        if (activeFilter === 'new' && (knownSet.has(verb.id) || seenSet.has(verb.id))) {
          return false;
        }

        if (activeFilter === 'seen' && (knownSet.has(verb.id) || !seenSet.has(verb.id))) {
          return false;
        }

        if (activeFilter === 'known' && !knownSet.has(verb.id)) {
          return false;
        }

        if (query && !verb.lemma.toLowerCase().includes(query)) {
          return false;
        }

        return true;
      });

      if (activeSort === 'alpha') {
        rows = [...rows].sort(function (left, right) {
          return left.lemma.localeCompare(right.lemma, lang);
        });
      } else if (activeSort === 'newest') {
        rows = [...rows].sort(function (left, right) {
          return (right.created_at || '').localeCompare(left.created_at || '');
        });
      }

      return rows;
    }

    function renderItem(verb, knownSet, seenSet) {
      const isKnown = knownSet.has(verb.id);
      const isSeen = !isKnown && seenSet.has(verb.id);

      const badge = isKnown
        ? '<span class="vb-badge known">★</span>'
        : '';

      const className = isKnown
        ? ' is-known'
        : isSeen
          ? ' is-seen'
          : '';

      const uiLang = window.VB_UI_LANG || '';
      const uiParam = uiLang ? ('&ui_language=' + encodeURIComponent(uiLang)) : '';
      const returnTo = encodeURIComponent('/verbs?language=' + lang + uiParam);

      return `
        <a
          class="vb-item${className}"
          href="/learn?language=${encodeURIComponent(lang)}&verb_id=${encodeURIComponent(verb.id)}&return_to=${returnTo}${uiParam}"
        >
          <span class="vb-lemma">${esc(verb.lemma)}</span>${badge}
        </a>
      `;
    }

    function render() {
      const knownSet = known();
      const seenSet = seen();
      const rows = visibleVerbs();
      const shownRows = rows.slice(0, displayCount);

      if (!shownRows.length) {
        listEl.innerHTML = `
          <div class="vb-empty">
            ${ui['verbs.empty_state'] || 'No verbs match'}
          </div>
        `;

        if (loadMoreWrapEl) loadMoreWrapEl.style.display = 'none';
        return;
      }

      const showRecent = !searchQuery.trim() && activeSort === 'alpha' && (
        activeFilter === 'all' || activeFilter === 'new'
      );

      const recentRows = showRecent
        ? shownRows.filter(v => recentSet.has(v.id))
        : [];

      const mainRows = showRecent
        ? shownRows.filter(v => !recentSet.has(v.id))
        : shownRows;

      let html = '';

      if (recentRows.length) {
        html += `
          <div class="vb-section-label">
            ${esc(ui['verbs.filter_recent'] || 'Recently added')}
          </div>
        `;

        html += recentRows
          .map(v => renderItem(v, knownSet, seenSet))
          .join('');

        if (mainRows.length) {
          html += '<div class="vb-section-divider"></div>';
        }
      }

      html += mainRows
        .map(v => renderItem(v, knownSet, seenSet))
        .join('');

      if (isFinite(displayCount)) {
        sessionStorage.setItem(displayCountKey, String(displayCount));
      }
      listEl.innerHTML = html;

      if (loadMoreWrapEl) {
        var clientHasMore = displayCount < rows.length;
        var serverHasMore = window.VB_VERBS && window.VB_VERBS.length < (window.VB_VERBS_TOTAL || 0);
        loadMoreWrapEl.style.display = (clientHasMore || serverHasMore) ? '' : 'none';
      }
    }

    function updateProgress() {
      const total = (window.VB_VERBS_TOTAL > 0 ? window.VB_VERBS_TOTAL : verbs.length);

      if (!total) {
        return;
      }

      const count = known().size;
      const percent = (count / total) * 100;

      if (progressFillEl) {
        progressFillEl.style.width = `${percent}%`;
      }

      if (progressCountEl) {
        progressCountEl.textContent = String(count);
      }

      // progress-total span is server-rendered static HTML -- do not overwrite
    }

    function applyFilter(newFilter, init) {
      activeFilter = newFilter;
      if (!init) displayCount = batch;

      if (toggleEl.tagName === 'SELECT') {
        toggleEl.value = newFilter;
      } else {
        toggleEl.querySelectorAll('.vb-ftbtn').forEach(function (node) {
          node.classList.toggle('active', node.dataset.filter === newFilter);
        });
      }

      writeState();
      render();
    }

    function showMore() {
      displayCount += batch;
      render();
    }

    function showAll() {
      displayCount = verbs.length;
      render();
    }

    function hasMoreToShow() {
      return displayCount < visibleVerbs().length;
    }

    function bindEvents() {
      sortEl.value = activeSort;

      applyFilter(activeFilter, true);

      if (toggleEl.tagName === 'SELECT') {
        toggleEl.addEventListener('change', function () {
          applyFilter(toggleEl.value);
        });
      } else {
        toggleEl.addEventListener('click', function (event) {
          const button = event.target.closest('.vb-ftbtn');

          if (!button) {
            return;
          }

          applyFilter(button.dataset.filter);
        });
      }

      sortEl.addEventListener('change', function () {
        activeSort = sortEl.value;
        displayCount = batch;

        writeState();
        render();
      });

      var searchTimer;
      searchEl.addEventListener('input', function () {
        searchQuery = searchEl.value;
        displayCount = batch;
        clearTimeout(searchTimer);
        searchTimer = setTimeout(render, 150);
      });

      const prefetched = new Set();

      listEl.addEventListener('pointerover', function (event) {
        const item = event.target.closest('.vb-item[href]');

        if (!item || prefetched.has(item.href)) {
          return;
        }

        prefetched.add(item.href);

        const link = document.createElement('link');

        link.rel = 'prefetch';
        link.href = item.href;

        document.head.appendChild(link);
      }, { passive: true });
    }

    bindEvents();
    writeState();

    return {
      render,
      updateProgress,
      known,
      seen,
      showMore,
      showAll,
      hasMoreToShow,
    };
  }

  window.VerbBoardVerbFilters = {
    createVerbFilters,
  };
})();
