'use strict';

const LIVE_ROOT = window.ADMIN_ROOT || '/admin';

async function searchLiveVerbs() {
  const query = document.getElementById('live-search-input').value.trim();
  if (!query) return;

  const language = document.getElementById('live-lang-filter').value;
  const tbody = document.getElementById('live-verbs-body');
  tbody.innerHTML = '<tr><td colspan="8" class="loading">Searching…</td></tr>';

  try {
    const params = new URLSearchParams({ query });
    if (language) params.set('language', language);
    const resp = await fetch(`${LIVE_ROOT}/api/verbs?${params}`);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      tbody.innerHTML = `<tr><td colspan="8" class="error-msg">Error ${resp.status}: ${esc(data.detail || resp.statusText)}</td></tr>`;
      return;
    }
    renderLiveVerbsTable(data.verbs || []);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="error-msg">Error: ${esc(err.message)}</td></tr>`;
  }
}

function renderLiveVerbsTable(verbs) {
  const tbody = document.getElementById('live-verbs-body');
  if (!verbs.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="loading">No results</td></tr>';
    return;
  }

  tbody.innerHTML = verbs.map(verb => {
    const verbId = verb.verb_id || '';
    const safeId = esc(verbId);
    const exampleCount = (verb.examples || []).length;
    const hasPronounForms = verb.pronoun_forms && Object.keys(verb.pronoun_forms).length > 0;
    const updated = (verb.updated_at || '').replace('T', ' ').slice(0, 16);
    const previewHref = `/learn?language=${esc(verb.language || '')}&verb_id=${safeId}&ui_language=en&return_to=${encodeURIComponent('/admin#live_verbs')}`;

    return `<tr id="live-row-${safeId}">
      <td><code>${safeId}</code></td>
      <td>${esc(verb.lemma || '')}</td>
      <td>${esc(verb.language || '')}</td>
      <td>${esc(verb.rank ?? '—')}</td>
      <td>${exampleCount}</td>
      <td>${hasPronounForms ? '✓' : '<span style="color:var(--muted)">—</span>'}</td>
      <td style="font-size:12px;color:var(--muted)">${esc(updated)}</td>
      <td>
        <div class="btn-row">
          <a class="btn-preview" href="${previewHref}" target="_blank">👁 Preview</a>
          <button class="btn-regen" onclick="regenLiveExamples('${safeId}')">⟳ Examples</button>
          <button class="btn-regen" onclick="regenLiveForms('${safeId}')">⟳ Forms</button>
          <button class="btn-needs-fix" onclick="regenLiveFull('${safeId}')">⟳ Full</button>
        </div>
        <span id="regen-status-${safeId}" style="font-size:12px;margin-left:2px"></span>
      </td>
    </tr>`;
  }).join('');
}

async function _liveRegenCall(verbId, path, label) {
  const statusEl = document.getElementById(`regen-status-${verbId}`);
  if (statusEl) statusEl.textContent = `${label}…`;

  try {
    const resp = await fetch(`${LIVE_ROOT}/api/verbs/${encodeURIComponent(verbId)}/${path}`, {
      method: 'POST',
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      if (statusEl) statusEl.textContent = `Error ${resp.status}: ${data.detail || resp.statusText}`;
      return;
    }
    if (statusEl) statusEl.textContent = `Done ${(data.updated_at || '').slice(0, 16)}`;
    refreshLiveVerbRow(verbId);
  } catch (err) {
    if (statusEl) statusEl.textContent = `Error: ${err.message}`;
  }
}

function regenLiveExamples(verbId) {
  _liveRegenCall(verbId, 'regen_examples', 'Regen examples');
}

function regenLiveForms(verbId) {
  _liveRegenCall(verbId, 'regen_forms', 'Regen forms');
}

function regenLiveFull(verbId) {
  if (!confirm(`Regenerate ALL fields for ${verbId}? This replaces forms, examples, and tts_forms.`)) return;
  _liveRegenCall(verbId, 'regenerate', 'Regen full');
}

async function refreshLiveVerbRow(verbId) {
  try {
    const resp = await fetch(`${LIVE_ROOT}/api/verbs/${encodeURIComponent(verbId)}`);
    if (!resp.ok) return;
    const verb = await resp.json();
    const row = document.getElementById(`live-row-${verbId}`);
    if (!row) return;

    const exampleCount = (verb.examples || []).length;
    const hasPronounForms = verb.pronoun_forms && Object.keys(verb.pronoun_forms).length > 0;
    const updated = (verb.updated_at || '').replace('T', ' ').slice(0, 16);

    row.cells[4].textContent = exampleCount;
    row.cells[5].innerHTML = hasPronounForms ? '✓' : '<span style="color:var(--muted)">—</span>';
    row.cells[6].textContent = updated;
  } catch (_) {
    // best-effort refresh
  }
}
