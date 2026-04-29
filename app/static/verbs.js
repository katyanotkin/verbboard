'use strict';

(function () {
  const lang     = window.VB_LANGUAGE;
  const returnTo = encodeURIComponent(`/verbs?language=${lang}`);
  const verbs    = window.VB_VERBS;  // [{id, lemma, rank}, ...] pre-sorted by rank
  const recentSet = new Set(window.VB_RECENT_IDS || []);

  const searchEl = document.getElementById('vb-search');
  const listEl   = document.getElementById('vb-list');
  const countEl  = document.getElementById('vb-count');
  const toggleEl = document.getElementById('vb-filter-toggle');
  const sortEl   = document.getElementById('vb-sort');

  let activeFilter = 'new';
  let activeSort   = 'rank';
  let searchQuery  = '';

  // ── localStorage ──────────────────────────────────────────────────────────
  function readSet(key) {
    try { return new Set(JSON.parse(localStorage.getItem(key) || '[]')); }
    catch (_) { return new Set(); }
  }
  function known() { return readSet(`known:${lang}`); }
  function seen()  { return readSet(`seen:${lang}`);  }

  // ── filter + sort ──────────────────────────────────────────────────────────
  function visibleVerbs() {
    const knownSet = known();
    const seenSet  = seen();
    const q        = searchQuery.trim().toLowerCase();

    let rows = verbs.filter(v => {
      if (activeFilter === 'new'  && (knownSet.has(v.id) || seenSet.has(v.id))) return false;
      if (activeFilter === 'seen' && (knownSet.has(v.id) || !seenSet.has(v.id))) return false;
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

  // ── render ─────────────────────────────────────────────────────────────────
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

    // Recent strip: shown on 'all' or 'new' filter, not during search
    const showRecent = !searchQuery.trim() && (activeFilter === 'all' || activeFilter === 'new');
    const recentRows = showRecent ? rows.filter(v => recentSet.has(v.id)) : [];
    const mainRows   = showRecent ? rows.filter(v => !recentSet.has(v.id)) : rows;

    let html = '';
    if (recentRows.length) {
      html += `<div class="vb-section-label">${esc(UI['verbs.filter_recent'] || 'Recently added')}</div>`;
      html += recentRows.map(v => renderItem(v, knownSet, seenSet)).join('');
      if (mainRows.length) {
        html += `<div class="vb-section-divider"></div>`;
      }
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
    render();
  });

  // ── sort ───────────────────────────────────────────────────────────────────
  sortEl.addEventListener('change', function () {
    activeSort = sortEl.value;
    render();
  });

  // ── search ─────────────────────────────────────────────────────────────────
  searchEl.addEventListener('input', function () {
    searchQuery = searchEl.value;
    render();
  });

  // ── escape ─────────────────────────────────────────────────────────────────
  function esc(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  render();
})();
