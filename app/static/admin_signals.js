'use strict';

const SIGNALS_ROOT = window.ADMIN_ROOT || "/admin";

const LANG_SCRIPTS = {
  en: /^[a-zA-Z\u00C0-\u024F\s'\-]+$/,
  es: /^[a-zA-Z\u00C0-\u024F\s'\-]+$/,
  ru: /^[\u0400-\u04FF\s'\-]+$/,
  he: /^[\u05B0-\u05EA\s'\-]+$/,
};

async function loadSignals() {
  window.signalsLoaded = true;

  try {
    const [signalsResponse, labelsResponse] = await Promise.all([
      fetch(`${SIGNALS_ROOT}/api/signals`),
      fetch(`${SIGNALS_ROOT}/api/signal_labels`),
    ]);

    if (!signalsResponse.ok) throw new Error(await signalsResponse.text());
    if (!labelsResponse.ok) throw new Error(await labelsResponse.text());

    signalsData = (await signalsResponse.json()).signals;
    labelsData = (await labelsResponse.json()).labels;

    const languages = [...new Set(signalsData.map(item => item.language).filter(Boolean))];
    await Promise.all(languages.map(loadExtracts));

    populateFilter('sig-filter-lang', languages.sort());
    updateSignalStats();
    renderActiveSignalView();
  } catch (error) {
    document.getElementById('sig-aggr-body').innerHTML =
      `<tr><td colspan="5" class="error-msg">Error: ${error.message}</td></tr>`;
  }
}

async function loadExtracts(language) {
  if (extractsCache[language]) return;

  try {
    const response = await fetch(
      `${SIGNALS_ROOT}/api/verbs/search_extracts?language=${encodeURIComponent(language)}`,
    );
    if (!response.ok) return;

    extractsCache[language] = new Set((await response.json()).extracts);
  } catch (_) {
    extractsCache[language] = new Set();
  }
}

function classifyRaw(signal) {
  const extracts = extractsCache[signal.language];
  if (extracts && extracts.has(signal.query.toLowerCase())) return 'in_set';

  const label = labelsData.find(
    item => item.query === signal.query && item.language === signal.language,
  );
  if (label) return label.status;

  return signal.status ?? null;
}

function classifyAggr(query, language) {
  const extracts = extractsCache[language];
  if (extracts && extracts.has(query.toLowerCase())) return 'in_set';

  const label = labelsData.find(
    item => item.query === query && item.language === language,
  );
  if (label) return label.status;

  return null;
}

function trashScore(query, language) {
  if (!query) return 'empty';
  if (query.length > 50) return 'too long';
  if (query.length < 2) return 'too short';

  const alphaOnly = query.replace(/[^a-zA-Z\u00C0-\u05FF]/g, '');
  if (alphaOnly.length / query.length < 0.5) return 'mostly non-alpha';

  const pattern = LANG_SCRIPTS[language];
  if (pattern && !pattern.test(query)) return 'wrong script';

  return null;
}

function updateSignalStats() {
  const unclassifiedOrClassified = signalsData.filter(item => item.status !== 'duplicate');
  document.getElementById('sig-total').textContent =
    unclassifiedOrClassified.length + labelsData.length;
  document.getElementById('sig-unique').textContent =
    new Set([
      ...unclassifiedOrClassified.map(item => item.query),
      ...labelsData.map(item => item.query),
    ]).size;
  document.getElementById('sig-langs').textContent =
    new Set([
      ...unclassifiedOrClassified.map(item => item.language),
      ...labelsData.map(item => item.language),
    ].filter(Boolean)).size;
}

function statusPill(status) {
  const map = {
    garbage: ['Likely garbage', 'garbage'],
    candidate: ['Candidate verb', 'candidate'],
    in_set: ['Already in set', 'in_set'],
  };

  if (!status || !map[status]) {
    return `<span class="status-pill unset">Unclassified</span>`;
  }

  const [label, cssClass] = map[status];
  return `<span class="status-pill ${cssClass}">${label}</span>`;
}

function aggrClassifySelect(query, language, currentStatus) {
  const options = [
    ['', currentStatus ? '— change —' : '— classify —'],
    ['candidate', 'Candidate verb'],
    ['garbage', 'Likely garbage'],
  ]
    .map(([value, label]) => `<option value="${value}">${label}</option>`)
    .join('');

  return `<select class="status-select"
    onchange="classifyGroup('${esc(query)}','${esc(language)}',this)">${options}</select>`;
}

function aggrRows() {
  const languageFilter = document.getElementById('sig-filter-lang').value;
  const statusFilter = document.getElementById('sig-filter-status').value;

  const labeled = new Map();
  for (const label of labelsData) {
    if (label.hidden) continue;
    if (languageFilter && label.language !== languageFilter) continue;

    const status = classifyAggr(label.query, label.language);
    if (statusFilter) {
      if (statusFilter === '__unclassified__' && status !== null) continue;
      if (statusFilter !== '__unclassified__' && status !== statusFilter) continue;
    }

    labeled.set(`${label.language}\x00${label.query}`, {
      id: label.id,
      query: label.query,
      language: label.language,
      count: label.count,
      last_ts: label.last_ts,
      status,
      hidden: !!label.hidden,
      labelId: label.id || `${label.language}_${label.query}`,
      trashReason: status === 'garbage' ? trashScore(label.query, label.language) : null,
    });
  }

  const raw = new Map();
  for (const signal of signalsData) {
    if (languageFilter && signal.language !== languageFilter) continue;

    const status = classifyAggr(signal.query, signal.language);
    if (statusFilter) {
      if (statusFilter === '__unclassified__' && status !== null) continue;
      if (statusFilter !== '__unclassified__' && status !== statusFilter) continue;
    }

    const key = `${signal.language}\x00${signal.query}`;
    if (labeled.has(key)) continue;

    if (!raw.has(key)) {
      raw.set(key, {
        id: null,
        query: signal.query,
        language: signal.language,
        count: 0,
        last_ts: '',
        status,
        hidden: false,
        labelId: null,
        trashReason: trashScore(signal.query, signal.language),
      });
    }

    const entry = raw.get(key);
    entry.count += 1;
    if (!entry.last_ts || signal.ts > entry.last_ts) {
      entry.last_ts = signal.ts;
    }
  }

  return [...labeled.values(), ...raw.values()];
}

async function loadOrToggleProcessed() {
  const button = document.getElementById('btn-hide-processed');

  if (!processedLoaded) {
    button.disabled = true;
    button.textContent = 'Loading…';
    try {
      const response = await fetch(`${SIGNALS_ROOT}/api/signals?include_processed=true`);
      if (!response.ok) throw new Error(await response.text());

      const allSignals = (await response.json()).signals;
      const existingIds = new Set(signalsData.map(item => item.id));
      for (const signal of allSignals) {
        if (!existingIds.has(signal.id)) signalsData.push(signal);
      }

      processedLoaded = true;
      hideProcessed = false;
    } catch (error) {
      button.disabled = false;
      button.textContent = 'Load processed';
      alert('Failed: ' + error.message);
      return;
    }
  } else {
    hideProcessed = !hideProcessed;
  }

  button.disabled = false;
  button.textContent = hideProcessed ? 'Show processed' : 'Hide processed';
  button.classList.toggle('active', !hideProcessed);
  renderActiveSignalView();
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
      const aStatus = statusOrder[a.status ?? '__unclassified__'] ?? 999;
      const bStatus = statusOrder[b.status ?? '__unclassified__'] ?? 999;
      if (aStatus !== bStatus) return aStatus - bStatus;
      if (a.count !== b.count) return b.count - a.count;
      if (a.last_ts !== b.last_ts) return b.last_ts.localeCompare(a.last_ts);
      return a.query.localeCompare(b.query);
    });
  } else {
    rows.sort((a, b) => a.query.localeCompare(b.query));
  }

  const tbody = document.getElementById('sig-aggr-body');
  if (!rows.length) {
    tbody.innerHTML = '<tr class="empty"><td colspan="5">No signals</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(item => {
    const last = item.last_ts ? item.last_ts.slice(0, 10) : '';
    const canClassify = item.status !== 'in_set';
    const isTrash = !item.labelId && !item.status && item.trashReason;

    let actionCell;

    if (item.labelId) {
      const hideAction =
        item.status === 'garbage'
          ? (
              item.hidden
                ? `<button class="btn-del" title="Unhide"
                    onclick="unhideSignalLabel('${esc(item.labelId)}',this)">Unhide</button>`
                : `<button class="btn-del" title="Hide"
                    onclick="hideSignalLabel('${esc(item.labelId)}',this)">Hide</button>`
            )
          : '';

      if (item.status === 'in_set') {
        actionCell = `<span style="display:flex;align-items:center;gap:6px">
            ${statusPill(item.status)}
          </span>`;
      } else if (item.status === 'garbage') {
        const reasonHint = item.trashReason
          ? `<span class="trash-hint" title="${esc(item.trashReason)}">${esc(item.trashReason)}</span>`
          : '';

        actionCell = `<span style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
            ${statusPill(item.status)}
            ${reasonHint}
            <button class="btn-del" title="Undo classification"
              onclick="undoLabel('${esc(item.labelId)}',this)">↩</button>
            ${hideAction}
          </span>`;
      } else {
        actionCell = `<span style="display:flex;align-items:center;gap:6px">
            ${statusPill(item.status)}
            <button class="btn-del" title="Undo classification"
              onclick="undoLabel('${esc(item.labelId)}',this)">↩</button>
          </span>`;
      }
    } else if (isTrash) {
      actionCell = `<span style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
          <span class="trash-hint" title="${esc(item.trashReason)}">${esc(item.trashReason)}</span>
          <button class="btn-confirm-trash" onclick="quickTrash('${esc(item.query)}','${esc(item.language)}',this)">Mark garbage</button>
          <button class="btn-del" onclick="quickHideTrash('${esc(item.query)}','${esc(item.language)}',this)">Hide</button>
        </span>`;
    } else if (canClassify) {
      actionCell = aggrClassifySelect(item.query, item.language, item.status);
    } else {
      actionCell = statusPill(item.status);
    }

    const rowClass = isTrash ? 'trash-candidate' : '';
    return `<tr class="${rowClass}">
      <td><span class="mono">${esc(item.query)}</span></td>
      <td>${item.language ? `<span class="pill pill-lang">${esc(item.language)}</span>` : ''}</td>
      <td><span class="cnt">${item.count}</span></td>
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
    item => item.query === query && item.language === language && item.status == null,
  );
  const count = matching.length;
  const lastTs = matching.reduce(
    (best, item) => (!best || item.ts > best ? item.ts : best),
    '',
  );

  try {
    const response = await fetch(`${SIGNALS_ROOT}/api/signal_labels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, language, status, count, last_ts: lastTs }),
    });
    if (!response.ok) throw new Error(await response.text());

    await loadSignals();
  } catch (error) {
    selectEl.disabled = false;
    alert('Classify failed: ' + error.message);
  }
}

async function quickTrash(query, language, button) {
  button.disabled = true;

  const matching = signalsData.filter(
    item => item.query === query && item.language === language && item.status == null,
  );
  const count = matching.length;
  const lastTs = matching.reduce(
    (best, item) => (!best || item.ts > best ? item.ts : best),
    '',
  );

  try {
    const response = await fetch(`${SIGNALS_ROOT}/api/signal_labels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, language, status: 'garbage', count, last_ts: lastTs }),
    });
    if (!response.ok) throw new Error(await response.text());

    await loadSignals();
  } catch (error) {
    button.disabled = false;
    alert('Failed: ' + error.message);
  }
}

async function quickHideTrash(query, language, button) {
  button.disabled = true;

  const matching = signalsData.filter(
    item => item.query === query && item.language === language && item.status == null,
  );
  const count = matching.length;
  const lastTs = matching.reduce(
    (best, item) => (!best || item.ts > best ? item.ts : best),
    '',
  );
  const labelId = `${language}_${query}`;

  try {
    const classifyResponse = await fetch(`${SIGNALS_ROOT}/api/signal_labels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        language,
        status: 'garbage',
        count,
        last_ts: lastTs,
      }),
    });
    if (!classifyResponse.ok) throw new Error(await classifyResponse.text());

    const hideResponse = await fetch(
      `${SIGNALS_ROOT}/api/signal_labels/${encodeURIComponent(labelId)}/hide`,
      { method: 'POST' },
    );
    if (!hideResponse.ok) throw new Error(await hideResponse.text());

    await loadSignals();
  } catch (error) {
    button.disabled = false;
    alert('Hide failed: ' + error.message);
  }
}

async function hideSignalLabel(labelId, button) {
  button.disabled = true;

  try {
    const response = await fetch(
      `${SIGNALS_ROOT}/api/signal_labels/${encodeURIComponent(labelId)}/hide`,
      { method: 'POST' },
    );
    if (!response.ok) throw new Error(await response.text());

    await loadSignals();
  } catch (error) {
    button.disabled = false;
    alert('Hide failed: ' + error.message);
  }
}

async function unhideSignalLabel(labelId, button) {
  button.disabled = true;

  try {
    const response = await fetch(
      `${SIGNALS_ROOT}/api/signal_labels/${encodeURIComponent(labelId)}/unhide`,
      { method: 'POST' },
    );
    if (!response.ok) throw new Error(await response.text());

    await loadSignals();
  } catch (error) {
    button.disabled = false;
    alert('Unhide failed: ' + error.message);
  }
}

async function undoLabel(labelId, button) {
  button.disabled = true;

  try {
    const response = await fetch(
      `${SIGNALS_ROOT}/api/signal_labels/${encodeURIComponent(labelId)}`,
      { method: 'DELETE' },
    );
    if (!response.ok) throw new Error(await response.text());

    await loadSignals();
  } catch (error) {
    button.disabled = false;
    alert('Undo failed: ' + error.message);
  }
}

function rawRows() {
  const languageFilter = document.getElementById('sig-filter-lang').value;
  const statusFilter = document.getElementById('sig-filter-status').value;

  return signalsData.filter(item => {
    if (hideProcessed && item.status != null) return false;
    if (languageFilter && item.language !== languageFilter) return false;

    const status = classifyRaw(item);
    if (statusFilter === '__unclassified__' && status !== null) return false;
    if (statusFilter && statusFilter !== '__unclassified__' && status !== statusFilter) {
      return false;
    }

    return true;
  });
}

function renderRaw() {
  const rows = rawRows();
  const tbody = document.getElementById('sig-body');

  if (!rows.length) {
    tbody.innerHTML = '<tr class="empty"><td colspan="4">No signals</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(item => {
    const timestamp = item.ts ? item.ts.slice(0, 19).replace('T', ' ') : '';
    const status = classifyRaw(item);

    return `<tr id="sig-${item.id}">
      <td><span class="mono">${esc(item.query)}</span></td>
      <td>${item.language ? `<span class="pill pill-lang">${esc(item.language)}</span>` : ''}</td>
      <td style="color:var(--muted);font-size:12px;white-space:nowrap">${timestamp}</td>
      <td>${statusPill(status)}</td>
    </tr>`;
  }).join('');
}
