/* global ADMIN_ROOT */
'use strict';

const ROOT = window.ADMIN_ROOT;

// shared state
let feedbackData = [];
let signalsData = [];
let labelsData = [];
let candidatesData = [];

let signalsLoaded = false;
let candidatesLoaded = false;
let sigView = 'aggr';
let hideProcessed = false;
let processedLoaded = false;

let sigSortBy = 'count';
let sigSortDir = 'desc';
let candSortBy = 'query';
let candSortDir = 'asc';

const extractsCache = {};

const statusOrder = {
  candidate: 0,
  in_set: 2,
  __unclassified__: 1,
  garbage: 3,
};

const candStatusOrder = {
  needs_generation: 0,
  pending: 1,
  to_be_fixed: 2,
  duplicate: 3,
  promoted: 4,
};

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function populateFilter(selectId, values) {
  const select = document.getElementById(selectId);
  const firstOption = select.options[0];
  select.innerHTML = '';
  select.appendChild(firstOption);

  values.forEach(value => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
}

function showPanel(name) {
  const panel = document.getElementById('panel-' + name);
  if (!panel) return;

  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));

  panel.classList.add('active');
  const navItem = document.querySelector(`[data-panel="${name}"]`);
  if (navItem) navItem.classList.add('active');

  location.hash = name;

  if (name === 'signals' && !signalsLoaded) loadSignals();
  if (name === 'candidates' && !candidatesLoaded) loadCandidates();
}

function setSigView(viewName) {
  sigView = viewName;
  document.getElementById('sig-aggr-view').classList.toggle('hidden', viewName !== 'aggr');
  document.getElementById('sig-raw-view').classList.toggle('hidden', viewName !== 'raw');
  document.getElementById('btn-view-aggr').classList.toggle('active', viewName === 'aggr');
  document.getElementById('btn-view-raw').classList.toggle('active', viewName === 'raw');
  renderActiveSignalView();
}

function renderActiveSignalView() {
  if (sigView === 'aggr') {
    renderAggr();
  } else {
    renderRaw();
  }
}

// Updates sortable column headers: sets label + ▲/▼ indicator on the active column.
// idPrefix: e.g. 'sth' → looks for ids sth-{field}; labels: { field: 'Label', ... }
function updateSortHeaders(idPrefix, sortBy, sortDir, labels) {
  for (const [field, label] of Object.entries(labels)) {
    const th = document.getElementById(`${idPrefix}-${field}`);
    if (!th) continue;
    if (field === sortBy) {
      th.textContent = `${label} ${sortDir === 'asc' ? '▲' : '▼'}`;
      th.classList.add('sort-active');
    } else {
      th.textContent = label;
      th.classList.remove('sort-active');
    }
  }
}
