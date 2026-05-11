'use strict';

(function () {
  const lang      = window.VB_LANGUAGE;
  const returnTo  = encodeURIComponent(`/verbs?language=${lang}`);
  const verbs     = window.VB_VERBS;   // [{id, lemma, rank}, ...] pre-sorted by rank
  const recentSet = new Set(window.VB_RECENT_IDS || []);

  const searchEl   = document.getElementById('vb-search');
  const listEl     = document.getElementById('vb-list');
  const countEl    = document.getElementById('vb-count');
  const toggleEl   = document.getElementById('vb-filter-toggle');
  const sortEl     = document.getElementById('vb-sort');
  const practiceEl = document.getElementById('practice-panel');

  // ── state persistence via URL hash + localStorage ─────────────────────────
  const _STATE_KEY = `vb-ui:${lang}`;

  function readHash() {
    const p = new URLSearchParams(window.location.hash.slice(1));
    return { filter: p.get('filter'), sort: p.get('sort') };
  }

  function readStorage() {
    try {
      const s = JSON.parse(localStorage.getItem(_STATE_KEY) || '{}');
      return { filter: s.filter || null, sort: s.sort || null };
    } catch (_) { return { filter: null, sort: null }; }
  }

  function writeState() {
    const p = new URLSearchParams();
    p.set('filter', activeFilter);
    p.set('sort',   activeSort);
    history.replaceState(null, '', '#' + p.toString());
    localStorage.setItem(_STATE_KEY, JSON.stringify({ filter: activeFilter, sort: activeSort }));
  }

  const fromHash    = readHash();
  const fromStorage = readStorage();
  let activeFilter  = fromHash.filter || fromStorage.filter || 'new';
  let activeSort    = fromHash.sort   || fromStorage.sort   || 'alpha';
  let searchQuery   = '';

  // Sync DOM to restored state
  sortEl.value = activeSort;
  toggleEl.querySelectorAll('.vb-ftbtn').forEach(b => {
    b.classList.toggle('active', b.dataset.filter === activeFilter);
  });
  writeState();

  // ── localStorage helpers ──────────────────────────────────────────────────
  function readSet(key) {
    try { return new Set(JSON.parse(localStorage.getItem(key) || '[]')); }
    catch (_) { return new Set(); }
  }
  function known() { return readSet(`known:${lang}`); }
  function seen()  { return readSet(`seen:${lang}`); }

  // ── filter + sort ──────────────────────────────────────────────────────────
  function visibleVerbs() {
    const knownSet = known();
    const seenSet  = seen();
    const q        = searchQuery.trim().toLowerCase();

    let rows = verbs.filter(v => {
      if (activeFilter === 'new'   && (knownSet.has(v.id) || seenSet.has(v.id))) return false;
      if (activeFilter === 'seen'  && (knownSet.has(v.id) || !seenSet.has(v.id))) return false;
      if (activeFilter === 'known' && !knownSet.has(v.id)) return false;
      if (q && !v.lemma.toLowerCase().includes(q)) return false;
      return true;
    });

    if (activeSort === 'alpha') {
      rows = [...rows].sort((a, b) => a.lemma.localeCompare(b.lemma));
    }
    return rows;
  }

  const UI = window.UI || {};

  // ── item renderer ──────────────────────────────────────────────────────────
  function renderItem(v, knownSet, seenSet) {
    const isKnown = knownSet.has(v.id);
    const isSeen  = !isKnown && seenSet.has(v.id);
    const badge   = isKnown ? '<span class="vb-badge known">★</span>'
                  : isSeen  ? '<span class="vb-badge seen">✓</span>'
                  : '';
    const cls = isKnown ? ' is-known' : isSeen ? ' is-seen' : '';
    return `<a class="vb-item${cls}"
       href="/learn?language=${encodeURIComponent(lang)}&verb_id=${encodeURIComponent(v.id)}&return_to=${returnTo}">
      <span class="vb-lemma">${esc(v.lemma)}</span>${badge}
    </a>`;
  }

  // ── render verb list ───────────────────────────────────────────────────────
  function render() {
    const knownSet = known();
    const seenSet  = seen();
    const rows     = visibleVerbs();

    countEl.textContent = rows.length
      ? `${rows.length} ${rows.length === 1 ? (UI['verbs.count_one'] || 'verb') : (UI['verbs.count_other'] || 'verbs')}`
      : '';

    if (!rows.length) {
      listEl.innerHTML = `<div class="vb-empty">${UI['verbs.empty_state'] || 'No verbs match'}</div>`;
      return;
    }

    const showRecent = !searchQuery.trim() && (activeFilter === 'all' || activeFilter === 'new');
    const recentRows = showRecent ? rows.filter(v => recentSet.has(v.id)) : [];
    const mainRows   = showRecent ? rows.filter(v => !recentSet.has(v.id)) : rows;

    let html = '';
    if (recentRows.length) {
      html += `<div class="vb-section-label">${esc(UI['verbs.filter_recent'] || 'Recently added')}</div>`;
      html += recentRows.map(v => renderItem(v, knownSet, seenSet)).join('');
      if (mainRows.length) html += `<div class="vb-section-divider"></div>`;
    }
    html += mainRows.map(v => renderItem(v, knownSet, seenSet)).join('');
    listEl.innerHTML = html;
  }

  // ── filter toggle ──────────────────────────────────────────────────────────
  toggleEl.addEventListener('click', function (e) {
    const btn = e.target.closest('.vb-ftbtn');
    if (!btn) return;
    toggleEl.querySelectorAll('.vb-ftbtn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilter = btn.dataset.filter;
    writeState();
    render();
  });

  sortEl.addEventListener('change', function () {
    activeSort = sortEl.value;
    writeState();
    render();
  });

  searchEl.addEventListener('input', function () {
    searchQuery = searchEl.value;
    render();
  });

  // ── escape ─────────────────────────────────────────────────────────────────
  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── hover-prefetch ─────────────────────────────────────────────────────────
  const _prefetched = new Set();
  listEl.addEventListener('pointerover', function (e) {
    const item = e.target.closest('.vb-item[href]');
    if (!item || _prefetched.has(item.href)) return;
    _prefetched.add(item.href);
    const link = document.createElement('link');
    link.rel = 'prefetch';
    link.href = item.href;
    document.head.appendChild(link);
  }, { passive: true });

  // ── practice ───────────────────────────────────────────────────────────────
  const practiceSessionKey = `practice_session:${lang}`;
  const practiceSizeKey    = `practice_size:${lang}`;
  const practiceBadgesKey  = `practice_badges:${lang}`;
  const PRACTICE_SIZES     = [3, 6, 9];
  const PRACTICE_POOL      = 20;   // draw from top-N new verbs before padding with known

  let activePracticeSize = parseInt(localStorage.getItem(practiceSizeKey) || '6', 10);
  if (!PRACTICE_SIZES.includes(activePracticeSize)) activePracticeSize = 6;

  function readPracticeSession() {
    try { return JSON.parse(localStorage.getItem(practiceSessionKey)); }
    catch (_) { return null; }
  }

  function readPracticeBadges() {
    try { return JSON.parse(localStorage.getItem(practiceBadgesKey) || '[]'); }
    catch (_) { return []; }
  }

  // Primary pool: verbs not yet marked known (new + seen), top PRACTICE_POOL by rank.
  // Falls back to known verbs only when the primary pool is exhausted.
  function buildPool(size) {
    const knownSet  = known();
    const nonKnown  = verbs.filter(v => !knownSet.has(v.id)).slice(0, PRACTICE_POOL);
    if (nonKnown.length >= size) return nonKnown;
    const knownVerbs = verbs.filter(v => knownSet.has(v.id));
    return [...nonKnown, ...knownVerbs];
  }

  // True only when known verbs are needed to fill the pool.
  function needsMixIn(size) {
    const knownSet = known();
    return verbs.filter(v => !knownSet.has(v.id)).slice(0, PRACTICE_POOL).length < size;
  }

  function renderPracticePanel() {
    if (!practiceEl) return;

    const session = readPracticeSession();
    const badges  = readPracticeBadges();

    const badgesHtml = badges.length
      ? `<div class="practice-badges">${badges.map(n => `<span class="practice-badge">${n}</span>`).join('')}</div>`
      : '';

    if (session && Array.isArray(session.ids) && session.ids.length > 0) {
      // In-progress state
      const seenSet      = seen();
      const visitedCount = session.ids.filter(id => seenSet.has(id)).length;
      const continueId   = session.ids.find(id => !seenSet.has(id)) || session.ids[session.ids.length - 1];
      const verbsUrl     = `/verbs?language=${encodeURIComponent(lang)}`;
      const continueUrl  =
        `/learn?language=${encodeURIComponent(lang)}` +
        `&verb_id=${encodeURIComponent(continueId)}` +
        `&return_to=${encodeURIComponent(verbsUrl)}`;

      practiceEl.innerHTML = `
        <div class="practice-inprogress">
          <span class="practice-inprogress-label">${esc(UI['practice.in_progress'] || 'In progress')}: ${visitedCount}/${session.ids.length}</span>
          <a href="${continueUrl}" class="btn-pill-navy">${esc(UI['practice.continue'] || 'Continue')}</a>
          <button class="practice-abandon-btn" id="practice-abandon">${esc(UI['practice.abandon'] || 'Abandon')}</button>
        </div>
        ${badgesHtml}
      `;

      document.getElementById('practice-abandon').addEventListener('click', function () {
        localStorage.removeItem(practiceSessionKey);
        renderPracticePanel();
      });

    } else {
      // Fresh-start state
      const mixed      = needsMixIn(activePracticeSize);
      const startLabel = mixed
        ? esc(UI['practice.start_mixed'] || 'Start (includes known)')
        : esc(UI['practice.start'] || 'Start');

      const sizeBtns = PRACTICE_SIZES
        .map(n =>
          `<button class="vb-ftbtn${n === activePracticeSize ? ' active' : ''}" data-size="${n}">${n}</button>`
        ).join('');

      practiceEl.innerHTML = `
        <div class="practice-picker">
          <span class="practice-label">${esc(UI['practice.label'] || 'Practice')}</span>
          <div class="vb-filter-toggle">${sizeBtns}</div>
          <button class="btn-pill-navy" id="practice-start">${startLabel}</button>
        </div>
        ${badgesHtml}
      `;

      practiceEl.querySelectorAll('.vb-ftbtn[data-size]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          activePracticeSize = parseInt(btn.dataset.size, 10);
          localStorage.setItem(practiceSizeKey, String(activePracticeSize));
          renderPracticePanel();   // re-render so start label stays accurate
        });
      });

      document.getElementById('practice-start').addEventListener('click', startPractice);
    }
  }

  function startPractice() {
    const pool     = buildPool(activePracticeSize);
    const shuffled = [...pool].sort(() => Math.random() - 0.5);
    const ids      = shuffled.slice(0, activePracticeSize).map(v => v.id);

    localStorage.setItem(practiceSessionKey, JSON.stringify({ ids, size: activePracticeSize }));

    const verbsUrl = `/verbs?language=${encodeURIComponent(lang)}`;
    window.location.href =
      `/learn?language=${encodeURIComponent(lang)}` +
      `&verb_id=${encodeURIComponent(ids[0])}` +
      `&return_to=${encodeURIComponent(verbsUrl)}`;
  }

  render();
  renderPracticePanel();
})();
