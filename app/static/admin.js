/* global ADMIN_ROOT */
'use strict';

const ROOT = window.ADMIN_ROOT;

// ── state ────────────────────────────────────────────────────────────────────
let feedbackData  = [];
let signalsData   = [];   // raw signal docs
let labelsData    = [];   // label docs
let candidatesData = [];  // verb_candidates docs

let signalsLoaded    = false;
let candidatesLoaded = false;
let sigView          = 'aggr';
let hideProcessed    = false;
let processedLoaded  = false;

const extractsCache = {};

const statusOrder = {
  candidate:       0,
  in_set:          1,
  __unclassified__: 2,
  garbage:         3,
};


// ── nav ───────────────────────────────────────────────────────────────────────
function showPanel(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  document.querySelector(`[data-panel="${name}"]`).classList.add('active');
  location.hash = name;
  if (name === 'signals'    && !signalsLoaded)    loadSignals();
  if (name === 'candidates' && !candidatesLoaded) loadCandidates();
}

// ── view toggle ───────────────────────────────────────────────────────────────
function setSigView(v) {
  sigView = v;
  document.getElementById('sig-aggr-view').style.display = v === 'aggr' ? '' : 'none';
  document.getElementById('sig-raw-view').style.display  = v === 'raw'  ? '' : 'none';
  document.getElementById('btn-view-aggr').classList.toggle('active', v === 'aggr');
  document.getElementById('btn-view-raw').classList.toggle('active',  v === 'raw');
  renderActiveSignalView();
}

function renderActiveSignalView() {
  if (sigView === 'aggr') renderAggr();
  else renderRaw();
}

// ── feedback ──────────────────────────────────────────────────────────────────
async function loadFeedback() {
  try {
    const res = await fetch(`${ROOT}/api/feedback`);
    if (!res.ok) throw new Error(await res.text());
    feedbackData = (await res.json()).feedback;
    populateFilter('fb-filter-lang',   [...new Set(feedbackData.map(f => f.language).filter(Boolean))].sort());
    populateFilter('fb-filter-source', [...new Set(feedbackData.map(f => f.source).filter(Boolean))].sort());
    updateFeedbackStats();
    renderFeedback();
  } catch (e) {
    document.getElementById('fb-body').innerHTML =
      `<tr><td colspan="6" class="error-msg">Error: ${e.message}</td></tr>`;
  }
}

function updateFeedbackStats() {
  document.getElementById('fb-total').textContent        = feedbackData.length;
  document.getElementById('fb-with-comment').textContent = feedbackData.filter(f => f.comment?.trim()).length;
  document.getElementById('fb-langs').textContent        = new Set(feedbackData.map(f => f.language).filter(Boolean)).size;
}

function renderFeedback() {
  const lang   = document.getElementById('fb-filter-lang').value;
  const source = document.getElementById('fb-filter-source').value;
  let rows = feedbackData;
  if (lang)   rows = rows.filter(f => f.language === lang);
  if (source) rows = rows.filter(f => f.source === source);

  const tbody = document.getElementById('fb-body');
  if (!rows.length) { tbody.innerHTML = '<tr class="empty"><td colspan="6">No entries</td></tr>'; return; }

  tbody.innerHTML = rows.map(f => {
    const date      = f.created_at ? f.created_at.slice(0, 10) : '';
    const isGarbage = !f.comment || f.comment.trim().length < 2;
    return `<tr id="fb-${f.id}">
      <td><span class="comment ${isGarbage ? 'garbage' : ''}">${esc(f.comment || '(empty)')}</span></td>
      <td>${f.language ? `<span class="pill pill-lang">${esc(f.language)}</span>` : ''}</td>
      <td><span style="color:var(--muted);font-size:12px">${esc(f.page)}</span></td>
      <td>${f.source ? `<span class="pill pill-src">${esc(f.source)}</span>` : ''}</td>
      <td style="color:var(--muted);font-size:12px;white-space:nowrap">${date}</td>
      <td><button class="btn-del" title="Delete" onclick="deleteFeedback('${f.id}', this)">✕</button></td>
    </tr>`;
  }).join('');
}

async function deleteFeedback(id, btn) {
  btn.disabled = true;
  try {
    const res = await fetch(`${ROOT}/api/feedback/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    feedbackData = feedbackData.filter(f => f.id !== id);
    document.getElementById(`fb-${id}`)?.remove();
    updateFeedbackStats();
    if (!document.querySelector('#fb-body tr:not(.empty)')) renderFeedback();
  } catch (e) {
    btn.disabled = false;
    alert('Delete failed: ' + e.message);
  }
}

// ── signals — load ────────────────────────────────────────────────────────────
async function loadSignals() {
  signalsLoaded = true;
  try {
    const [sigRes, lblRes] = await Promise.all([
      fetch(`${ROOT}/api/signals`),
      fetch(`${ROOT}/api/signal_labels`),
    ]);
    if (!sigRes.ok) throw new Error(await sigRes.text());
    if (!lblRes.ok) throw new Error(await lblRes.text());

    signalsData = (await sigRes.json()).signals;
    labelsData  = (await lblRes.json()).labels;

    const langs = [...new Set(signalsData.map(s => s.language).filter(Boolean))];
    await Promise.all(langs.map(loadExtracts));

    populateFilter('sig-filter-lang', langs.sort());
    updateSignalStats();
    renderAggr();
  } catch (e) {
    document.getElementById('sig-aggr-body').innerHTML =
      `<tr><td colspan="5" class="error-msg">Error: ${e.message}</td></tr>`;
  }
}

async function loadExtracts(language) {
  if (extractsCache[language]) return;
  try {
    const res = await fetch(`${ROOT}/api/verbs/search_extracts?language=${encodeURIComponent(language)}`);
    if (!res.ok) return;
    extractsCache[language] = new Set((await res.json()).extracts);
  } catch (_) {
    extractsCache[language] = new Set();
  }
}

// ── signals — classify ────────────────────────────────────────────────────────
function classifyRaw(signal) {
  const extracts = extractsCache[signal.language];
  if (extracts && extracts.has(signal.query.toLowerCase())) return 'in_set';
  const label = labelsData.find(l => l.query === signal.query && l.language === signal.language);
  if (label) return label.status;
  return null;
}

function classifyAggr(query, language) {
  const extracts = extractsCache[language];
  if (extracts && extracts.has(query.toLowerCase())) return 'in_set';
  const label = labelsData.find(l => l.query === query && l.language === language);
  return label ? label.status : null;
}

// ── signals — trash heuristic ─────────────────────────────────────────────────
const LANG_SCRIPTS = {
  en: /^[a-zA-Z\u00C0-\u024F\s'\-]+$/,
  es: /^[a-zA-Z\u00C0-\u024F\s'\-]+$/,
  ru: /^[\u0400-\u04FF\s'\-]+$/,
  he: /^[\u05B0-\u05EA\s'\-]+$/,
};

function trashScore(query, language) {
  if (!query) return 'empty';
  if (query.length > 50) return 'too long';
  if (query.length < 2)  return 'too short';
  const alpha = query.replace(/[^a-zA-Z\u00C0-\u05FF]/g, '');
  if (alpha.length / query.length < 0.5) return 'mostly non-alpha';
  const pattern = LANG_SCRIPTS[language];
  if (pattern && !pattern.test(query)) return 'wrong script';
  return null;
}

// ── signals — stats ───────────────────────────────────────────────────────────
function updateSignalStats() {
  const unprocessed = signalsData.filter(s => s.status !== 'processed');
  document.getElementById('sig-total').textContent  = unprocessed.length + labelsData.length;
  document.getElementById('sig-unique').textContent =
    new Set([
      ...unprocessed.map(s => s.query),
      ...labelsData.map(l => l.query),
    ]).size;
  document.getElementById('sig-langs').textContent  =
    new Set([
      ...unprocessed.map(s => s.language),
      ...labelsData.map(l => l.language),
    ].filter(Boolean)).size;
}

// ── signals — helpers ─────────────────────────────────────────────────────────
function statusPill(status) {
  const map = {
    garbage:   ['Likely garbage', 'garbage'],
    candidate: ['Candidate verb', 'candidate'],
    in_set:    ['Already in set', 'in_set'],
  };
  if (!status || !map[status]) return `<span class="status-pill unset">Unclassified</span>`;
  const [label, cls] = map[status];
  return `<span class="status-pill ${cls}">${label}</span>`;
}

function aggrClassifySelect(query, language, currentStatus) {
  const opts = [
    ['', currentStatus ? '— change —' : '— classify —'],
    ['candidate', 'Candidate verb'],
    ['garbage',   'Likely garbage'],
  ].map(([v, label]) => `<option value="${v}">${label}</option>`).join('');
  return `<select class="status-select"
    onchange="classifyGroup('${esc(query)}','${esc(language)}',this)">${opts}</select>`;
}

// ── signals — aggregated view ─────────────────────────────────────────────────
function aggrRows() {
  const langFilter   = document.getElementById('sig-filter-lang').value;
  const statusFilter = document.getElementById('sig-filter-status').value;

  const labeled = new Map();
  for (const l of labelsData) {
    if (langFilter && l.language !== langFilter) continue;
    const status = classifyAggr(l.query, l.language);
    if (hideProcessed && status === 'processed') continue;
    if (statusFilter) {
      if (statusFilter === '__unclassified__' && status !== null) continue;
      if (statusFilter !== '__unclassified__' && status !== statusFilter) continue;
    }
    labeled.set(`${l.language}\x00${l.query}`, {
      query: l.query, language: l.language,
      count: l.count, last_ts: l.last_ts,
      status, labelId: `${l.language}_${l.query}`,
    });
  }

  const raw = new Map();
  for (const s of signalsData) {
    if (s.status === 'processed') continue;
    if (langFilter && s.language !== langFilter) continue;
    const status = classifyAggr(s.query, s.language);
    if (statusFilter) {
      if (statusFilter === '__unclassified__' && status !== null) continue;
      if (statusFilter !== '__unclassified__' && status !== statusFilter) continue;
    }
    const key = `${s.language}\x00${s.query}`;
    if (labeled.has(key)) continue;
    if (!raw.has(key)) raw.set(key, { query: s.query, language: s.language, count: 0, last_ts: '', status, labelId: null, trashReason: trashScore(s.query, s.language) });
    const entry = raw.get(key);
    entry.count++;
    if (!entry.last_ts || s.ts > entry.last_ts) entry.last_ts = s.ts;
  }

  return [...labeled.values(), ...raw.values()];
}

async function loadOrToggleProcessed() {
  const btn = document.getElementById('btn-hide-processed');
  if (!processedLoaded) {
    btn.disabled = true;
    btn.textContent = 'Loading…';
    try {
      const res = await fetch(`${ROOT}/api/signals?include_processed=true`);
      if (!res.ok) throw new Error(await res.text());
      const all = (await res.json()).signals;
      const existingIds = new Set(signalsData.map(s => s.id));
      for (const s of all) {
        if (!existingIds.has(s.id)) signalsData.push(s);
      }
      processedLoaded = true;
      hideProcessed = false;
    } catch (e) {
      btn.disabled = false;
      btn.textContent = 'Load processed';
      alert('Failed: ' + e.message);
      return;
    }
  } else {
    hideProcessed = !hideProcessed;
  }
  btn.disabled = false;
  btn.textContent = hideProcessed ? 'Show processed' : 'Hide processed';
  btn.classList.toggle('active', !hideProcessed);
  renderRaw();
}

function renderAggr() {
  const sortBy = document.getElementById('sig-sort').value;
  let rows = aggrRows();

  if (sortBy === 'count') {
    rows.sort((a, b) => b.count - a.count);
  } else if (sortBy === 'last') {
    rows.sort((a, b) => b.last_ts.localeCompare(a.last_ts));
  } else if (sortBy === 'status') {
    rows.sort((a, b) => {
      const aS = statusOrder[a.status ?? '__unclassified__'] ?? 999;
      const bS = statusOrder[b.status ?? '__unclassified__'] ?? 999;
      if (aS !== bS) return aS - bS;
      if (a.count !== b.count) return b.count - a.count;
      if (a.last_ts !== b.last_ts) return b.last_ts.localeCompare(a.last_ts);
      return a.query.localeCompare(b.query);
    });
  } else {
    rows.sort((a, b) => a.query.localeCompare(b.query));
  }

  const tbody = document.getElementById('sig-aggr-body');
  if (!rows.length) { tbody.innerHTML = '<tr class="empty"><td colspan="5">No signals</td></tr>'; return; }

  tbody.innerHTML = rows.map(a => {
    const last        = a.last_ts ? a.last_ts.slice(0, 10) : '';
    const canClassify = a.status !== 'in_set';
    const isTrash     = !a.labelId && !a.status && a.trashReason;
    let actionCell;
    if (a.labelId) {
      actionCell = `<span style="display:flex;align-items:center;gap:6px">
          ${statusPill(a.status)}
          <button class="btn-del" title="Undo classification"
            onclick="undoLabel('${esc(a.labelId)}',this)">↩</button>
        </span>`;
    } else if (isTrash) {
      actionCell = `<span style="display:flex;align-items:center;gap:6px">
          <span class="trash-hint" title="${esc(a.trashReason)}">${esc(a.trashReason)}</span>
          <button class="btn-confirm-trash" onclick="quickTrash('${esc(a.query)}','${esc(a.language)}',this)">Mark garbage</button>
        </span>`;
    } else if (canClassify) {
      actionCell = aggrClassifySelect(a.query, a.language, a.status);
    } else {
      actionCell = statusPill(a.status);
    }
    const rowClass = isTrash ? 'trash-candidate' : '';
    return `<tr class="${rowClass}">
      <td><span class="mono">${esc(a.query)}</span></td>
      <td>${a.language ? `<span class="pill pill-lang">${esc(a.language)}</span>` : ''}</td>
      <td><span class="cnt">${a.count}</span></td>
      <td style="color:var(--muted);font-size:12px">${last}</td>
      <td>${actionCell}</td>
    </tr>`;
  }).join('');
}


async function classifyGroup(query, language, selectEl) {
  const status = selectEl.value;
  if (!status) return;
  selectEl.disabled = true;

  const matching = signalsData.filter(
    s => s.query === query && s.language === language && s.status == null
  );
  const count = matching.length;
  const last_ts = matching.reduce(
    (best, s) => (!best || s.ts > best ? s.ts : best),
    '',
  );

  try {
    const res = await fetch(`${ROOT}/api/signal_labels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, language, status, count, last_ts }),
    });
    if (!res.ok) throw new Error(await res.text());

    signalsData
      .filter(s => s.query === query && s.language === language && s.status == null)
      .forEach(s => { s.status = status; });

    const existing = labelsData.findIndex(
      l => l.query === query && l.language === language,
    );
    const labelDoc = { id: `${language}_${query}`, query, language, status, count, last_ts };
    if (existing >= 0) labelsData[existing] = labelDoc;
    else labelsData.push(labelDoc);

    updateSignalStats();
    renderAggr();
  } catch (e) {
    selectEl.disabled = false;
    alert('Classify failed: ' + e.message);
  }
}

async function quickTrash(query, language, btn) {
  btn.disabled = true;

  const matching = signalsData.filter(
    s => s.query === query && s.language === language && s.status == null
  );
  const count = matching.length;
  const last_ts = matching.reduce(
    (best, s) => (!best || s.ts > best ? s.ts : best),
    '',
  );

  try {
    const res = await fetch(`${ROOT}/api/signal_labels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, language, status: 'garbage', count, last_ts }),
    });
    if (!res.ok) throw new Error(await res.text());

    signalsData
      .filter(s => s.query === query && s.language === language && s.status == null)
      .forEach(s => { s.status = 'garbage'; });

    const existing = labelsData.findIndex(
      l => l.query === query && l.language === language,
    );
    const labelDoc = {
      id: `${language}_${query}`,
      query,
      language,
      status: 'garbage',
      count,
      last_ts,
    };
    if (existing >= 0) labelsData[existing] = labelDoc;
    else labelsData.push(labelDoc);

    updateSignalStats();
    renderAggr();
  } catch (e) {
    btn.disabled = false;
    alert('Failed: ' + e.message);
  }
}	

async function undoLabel(labelId, btn) {
  btn.disabled = true;
  try {
    const res = await fetch(`${ROOT}/api/signal_labels/${encodeURIComponent(labelId)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());

    const label = labelsData.find(l => l.id === labelId);
    if (label) {
      signalsData.filter(s => s.query === label.query && s.language === label.language && s.status === 'processed')
        .forEach(s => s.status = null);
    }
    labelsData = labelsData.filter(l => l.id !== labelId);

    updateSignalStats();
    renderAggr();
  } catch (e) {
    btn.disabled = false;
    alert('Undo failed: ' + e.message);
  }
}

// ── signals — raw view ────────────────────────────────────────────────────────
function rawRows() {
  const langFilter   = document.getElementById('sig-filter-lang').value;
  const statusFilter = document.getElementById('sig-filter-status').value;
  return signalsData.filter(s => {
    if (hideProcessed && s.status === 'processed') return false;
    if (langFilter && s.language !== langFilter) return false;
    const status = classifyRaw(s);
    if (statusFilter === '__unclassified__' && status !== null) return false;
    if (statusFilter && statusFilter !== '__unclassified__' && status !== statusFilter) return false;
    return true;
  });
}

function renderRaw() {
  const rows  = rawRows();
  const tbody = document.getElementById('sig-body');
  if (!rows.length) { tbody.innerHTML = '<tr class="empty"><td colspan="4">No signals</td></tr>'; return; }

  tbody.innerHTML = rows.map(s => {
    const ts     = s.ts ? s.ts.slice(0, 19).replace('T', ' ') : '';
    const status = classifyRaw(s);
    return `<tr id="sig-${s.id}">
      <td><span class="mono">${esc(s.query)}</span></td>
      <td>${s.language ? `<span class="pill pill-lang">${esc(s.language)}</span>` : ''}</td>
      <td style="color:var(--muted);font-size:12px;white-space:nowrap">${ts}</td>
      <td>${statusPill(status)}</td>
    </tr>`;
  }).join('');
}

// ── candidates ────────────────────────────────────────────────────────────────

const candStatusOrder = {
  needs_generation: 0,
  pending: 1,
  to_be_fixed: 2,
  duplicate: 3,
  promoted: 4,
};

async function loadCandidates() {
  candidatesLoaded = true;
  try {
    const res = await fetch(`${ROOT}/api/candidates`);
    if (!res.ok) throw new Error(await res.text());
    candidatesData = (await res.json()).candidates;
    const langs = [...new Set(candidatesData.map(c => c.language).filter(Boolean))].sort();
    populateFilter('cand-filter-lang', langs);
    updateCandidateStats();
    renderCandidates();
  } catch (e) {
    document.getElementById('cand-body').innerHTML =
      `<tr><td colspan="8" class="error-msg">Error: ${e.message}</td></tr>`;
  }
}

function updateCandidateStats() {
  document.getElementById('cand-stat-pending').textContent =
    candidatesData.filter(c => c.status === 'pending' || c.status === 'needs_generation').length;
  document.getElementById('cand-stat-promoted').textContent =
    candidatesData.filter(c => c.status === 'promoted').length;
  document.getElementById('cand-stat-fix').textContent =
    candidatesData.filter(c => c.status === 'to_be_fixed').length;
}

function candStatusPill(status) {
  const map = {
    needs_generation: ['Needs generation', 'unset'],
    pending: ['Pending', 'candidate'],
    to_be_fixed: ['Needs fix', 'garbage'],
    duplicate: ['Duplicate', 'garbage'],
    promoted: ['Promoted', 'in_set'],
  };
  const [label, cls] = map[status] ?? [status, 'unset'];
  return `<span class="status-pill ${cls}">${label}</span>`;
}

function renderFormsTable(forms) {
  if (!forms || !Object.keys(forms).length) return '<em style="color:var(--muted)">—</em>';
  const rows = Object.entries(forms)
    .map(([k, v]) => `<tr>
      <td style="color:var(--muted);padding-right:8px;white-space:nowrap;font-size:11px">${esc(k)}</td>
      <td class="mono" style="font-size:11px">${esc(Array.isArray(v) ? v.join(', ') : String(v))}</td>
    </tr>`)
    .join('');
  return `<table style="border-collapse:collapse">${rows}</table>`;
}

function renderExamplesList(examples) {
  if (!examples || !examples.length) return '<em style="color:var(--muted)">—</em>';
  return examples
    .map((ex, i) => `<div style="font-size:12px;padding:2px 0">
      <span style="color:var(--muted);margin-right:4px">${i + 1}.</span>${esc(ex.dst ?? ex)}
    </div>`)
    .join('');
}

function renderCandidates() {
  const langFilter = document.getElementById('cand-filter-lang').value;
  const statusFilter = document.getElementById('cand-filter-status').value;
  const sortBy = document.getElementById('cand-sort').value;

  let rows = candidatesData.filter(c => {
    if (langFilter && c.language !== langFilter) return false;
    if (statusFilter) {
      const allowed = statusFilter.split(',');
      if (!allowed.includes(c.status)) return false;
    }
    return true;
  });

  if (sortBy === 'created') {
    rows = [...rows].sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''));
  } else if (sortBy === 'status') {
    rows = [...rows].sort((a, b) => {
      const aS = candStatusOrder[a.status] ?? 99;
      const bS = candStatusOrder[b.status] ?? 99;
      if (aS !== bS) return aS - bS;
      if (a.language !== b.language) return a.language.localeCompare(b.language);
      return a.query.localeCompare(b.query);
    });
  } else {
    rows = [...rows].sort((a, b) => {
      if (a.language !== b.language) return a.language.localeCompare(b.language);
      return a.query.localeCompare(b.query);
    });
  }

  const tbody = document.getElementById('cand-body');
  if (!rows.length) {
    tbody.innerHTML = '<tr class="empty"><td colspan="8">No candidates</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(c => {
    const isPromoted = c.status === 'promoted';
    const needsGen = c.status === 'needs_generation';
    const isDuplicate = c.status === 'duplicate';
    const canPromote = c.status === 'pending' || c.status === 'to_be_fixed';
    const canNeedsFix = c.status === 'pending';
    const canReopen = c.status === 'to_be_fixed' || c.status === 'duplicate';
    const canGenerate =
      c.status === 'needs_generation' ||
      c.status === 'pending' ||
      c.status === 'to_be_fixed';

    const actionBtns = [];

    if (canPromote) {
      actionBtns.push(
        `<button class="btn-promote" onclick="promoteCandidate('${esc(c.verb_id)}',this)">▲ Promote</button>`
      );
    }

    if (canNeedsFix) {
      actionBtns.push(
        `<button class="btn-needs-fix" onclick="setCandidateStatus('${esc(c.verb_id)}','to_be_fixed',this)">⚑ Needs fix</button>`
      );
    }

    if (canReopen) {
      actionBtns.push(
        `<button class="btn-reopen" onclick="setCandidateStatus('${esc(c.verb_id)}','pending',this)">↩ Reopen</button>`
      );
    }

    if (canGenerate) {
      const label = needsGen ? '⚡ Generate' : '⟳ Regen';
      actionBtns.push(
        `<button class="btn-regen" onclick="regenSingle('${esc(c.verb_id)}',this)">${label}</button>`
      );
    }

    if (isDuplicate) {
      actionBtns.push(
        `<button class="btn-del" onclick="deleteCandidate('${esc(c.verb_id)}',this)">🗑 Delete</button>`
      );
    }

    const formsCell = needsGen
      ? '<em style="color:var(--muted);font-size:12px">—</em>'
      : `<details><summary class="expand-summary">Forms</summary>
           <div class="expand-body">${renderFormsTable(c.forms)}</div>
         </details>`;

    const examplesCell = needsGen
      ? '<em style="color:var(--muted);font-size:12px">—</em>'
      : `<details><summary class="expand-summary">Examples</summary>
           <div class="expand-body">${renderExamplesList(c.examples)}</div>
         </details>`;

    return `<tr id="cand-row-${esc(c.verb_id)}" class="${isPromoted ? 'row-promoted' : ''}">
      <td><span class="mono">${esc(c.query)}</span></td>
      <td><span class="mono" style="color:var(--muted)">${c.lemma ? esc(c.lemma) : '—'}</span></td>
      <td><span class="pill pill-lang">${esc(c.language)}</span></td>
      <td style="color:var(--muted);font-size:12px">${c.rank ?? '—'}</td>
      <td>${candStatusPill(c.status)}</td>
      <td class="cell-expand">${formsCell}</td>
      <td class="cell-expand">${examplesCell}</td>
      <td>
        <div style="display:flex;flex-direction:column;gap:4px;align-items:flex-start">
          ${actionBtns.join('')}
        </div>
      </td>
    </tr>`;
  }).join('');
}

async function regenSingle(verbId, btn) {
  btn.disabled = true;
  try {
    const res = await fetch(`${ROOT}/api/candidates/${encodeURIComponent(verbId)}/generate`, {
      method: 'POST',
    });

    if (res.status === 409) {
      const conflict = await res.json().catch(() => ({}));
      const cand = candidatesData.find(c => c.verb_id === verbId);
      if (cand) {
        cand.status = 'duplicate';
        if (conflict.duplicate_of) cand.duplicate_of = conflict.duplicate_of;
      }
      updateCandidateStats();
      renderCandidates();
      return;
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }

    const doc = await res.json();
    const oldIdx = candidatesData.findIndex(
      c => c.verb_id === verbId || c.verb_id === doc.verb_id
    );
    if (oldIdx >= 0) candidatesData[oldIdx] = doc;
    else candidatesData.push(doc);

    if (doc.verb_id !== verbId) {
      candidatesData = candidatesData.filter(c => c.verb_id !== verbId);
    }

    updateCandidateStats();
    renderCandidates();
  } catch (e) {
    btn.disabled = false;
    alert('Generate failed: ' + e.message);
  }
}

async function promoteCandidate(verbId, btn) {
  btn.disabled = true;
  try {
    const res = await fetch(`${ROOT}/api/candidates/${encodeURIComponent(verbId)}/promote`, {
      method: 'POST',
    });

    if (res.status === 409) {
      const conflict = await res.json().catch(() => ({}));
      const cand = candidatesData.find(c => c.verb_id === verbId);
      if (cand) {
        cand.status = 'duplicate';
        if (conflict.duplicate_of) cand.duplicate_of = conflict.duplicate_of;
      }
      updateCandidateStats();
      renderCandidates();
      return;
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }

    const cand = candidatesData.find(c => c.verb_id === verbId);
    if (cand) cand.status = 'promoted';
    updateCandidateStats();
    renderCandidates();
  } catch (e) {
    btn.disabled = false;
    alert('Promote failed: ' + e.message);
  }
}

async function setCandidateStatus(verbId, newStatus, btn) {
  btn.disabled = true;
  try {
    const res = await fetch(`${ROOT}/api/candidates/${encodeURIComponent(verbId)}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }
    const cand = candidatesData.find(c => c.verb_id === verbId);
    if (cand) cand.status = newStatus;
    updateCandidateStats();
    renderCandidates();
  } catch (e) {
    btn.disabled = false;
    alert('Status update failed: ' + e.message);
  }
}

async function deleteCandidate(verbId, btn) {
  if (!confirm(`Delete candidate ${verbId}?`)) return;

  btn.disabled = true;
  try {
    const res = await fetch(`${ROOT}/api/candidates/${encodeURIComponent(verbId)}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }

    candidatesData = candidatesData.filter(c => c.verb_id !== verbId);
    updateCandidateStats();
    renderCandidates();
  } catch (e) {
    btn.disabled = false;
    alert('Delete failed: ' + e.message);
  }
}

// ── helpers ───────────────────────────────────────────────────────────────────

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function populateFilter(selectId, values) {
  const sel = document.getElementById(selectId);
  const first = sel.options[0];
  sel.innerHTML = '';
  sel.appendChild(first);
  values.forEach(v => {
    const opt = document.createElement('option');
    opt.value = v;
    opt.textContent = v;
    sel.appendChild(opt);
  });
}

// ── init ──────────────────────────────────────────────────────────────────────

const _initPanel = ['feedback', 'signals', 'candidates'].includes(location.hash.slice(1))
  ? location.hash.slice(1)
  : 'feedback';

showPanel(_initPanel);
loadFeedback();
