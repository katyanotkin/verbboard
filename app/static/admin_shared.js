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

const extractsCache = {};

const statusOrder = {
  candidate: 0,
  in_set: 1,
  __unclassified__: 2,
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
    .replace(/"/g, '&quot;');
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
  document.querySelectorAll('.panel').forEach(panel => panel.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));

  document.getElementById('panel-' + name).classList.add('active');
  document.querySelector(`[data-panel="${name}"]`).classList.add('active');

  location.hash = name;

  if (name === 'signals' && !signalsLoaded) loadSignals();
  if (name === 'candidates' && !candidatesLoaded) loadCandidates();
}

function setSigView(viewName) {
  sigView = viewName;
  document.getElementById('sig-aggr-view').style.display = viewName === 'aggr' ? '' : 'none';
  document.getElementById('sig-raw-view').style.display = viewName === 'raw' ? '' : 'none';
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
