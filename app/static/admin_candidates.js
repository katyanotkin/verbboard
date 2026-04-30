'use strict';

const CANDIDATES_ROOT = window.ADMIN_ROOT || "/admin";

async function loadCandidates() {
  window.candidatesLoaded = true;

  try {
    const response = await fetch(`${CANDIDATES_ROOT}/api/candidates`);
    if (!response.ok) {
      throw new Error(await response.text());
    }

    candidatesData = (await response.json()).candidates || [];

    const languages = [
      ...new Set(candidatesData.map((item) => item.language).filter(Boolean)),
    ].sort();
    populateFilter('cand-filter-lang', languages);

    updateCandidateStats();
    renderCandidates();
  } catch (error) {
    document.getElementById('cand-body').innerHTML =
      `<tr><td colspan="8" class="error-msg">Error: ${error.message}</td></tr>`;
  }
}

function updateCandidateStats() {
  document.getElementById('cand-stat-pending').textContent =
    candidatesData.filter(
      (item) => item.status === 'pending' || item.status === 'needs_generation',
    ).length;

  document.getElementById('cand-stat-promoted').textContent =
    candidatesData.filter((item) => item.status === 'promoted').length;

  document.getElementById('cand-stat-fix').textContent =
    candidatesData.filter((item) => item.status === 'to_be_fixed').length;
}

function candStatusPill(status) {
  const map = {
    needs_generation: ['Needs generation', 'unset'],
    pending: ['Pending', 'candidate'],
    to_be_fixed: ['Needs fix', 'garbage'],
    duplicate: ['Duplicate', 'garbage'],
    promoted: ['Promoted', 'in_set'],
  };

  const [label, cssClass] = map[status] ?? [status, 'unset'];
  return `<span class="status-pill ${cssClass}">${label}</span>`;
}

function renderFormsTable(forms) {
  if (!forms || !Object.keys(forms).length) {
    return '<em style="color:var(--muted)">—</em>';
  }

  const rows = [];

  for (const [section, value] of Object.entries(forms)) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      rows.push(`<tr>
        <td colspan="2" style="color:var(--accent);font-size:10px;padding-top:6px;text-transform:uppercase;letter-spacing:0.05em">${esc(section)}</td>
      </tr>`);

      for (const [key, val] of Object.entries(value)) {
        rows.push(`<tr>
          <td style="color:var(--muted);padding-right:8px;padding-left:8px;white-space:nowrap;font-size:11px">${esc(key)}</td>
          <td class="mono" style="font-size:11px">${esc(Array.isArray(val) ? val.join(', ') : String(val ?? ''))}</td>
        </tr>`);
      }
    } else {
      rows.push(`<tr>
        <td style="color:var(--muted);padding-right:8px;white-space:nowrap;font-size:11px">${esc(section)}</td>
        <td class="mono" style="font-size:11px">${esc(Array.isArray(value) ? value.join(', ') : String(value ?? ''))}</td>
      </tr>`);
    }
  }

  return `<table style="border-collapse:collapse">${rows.join('')}</table>`;
}

function renderExamplesList(examples) {
  if (!examples || !examples.length) {
    return '<em style="color:var(--muted)">—</em>';
  }

  return examples
    .map(
      (example, index) => `<div style="font-size:12px;padding:2px 0">
      <span style="color:var(--muted);margin-right:4px">${index + 1}.</span>${esc(example.dst ?? example)}
    </div>`,
    )
    .join('');
}

function renderCandidates() {
  const languageFilter = document.getElementById('cand-filter-lang').value;
  const statusFilter = document.getElementById('cand-filter-status').value;
  const sortBy = document.getElementById('cand-sort').value;

  let rows = candidatesData.filter((item) => {
    if (languageFilter && item.language !== languageFilter) {
      return false;
    }

    if (statusFilter) {
      const allowed = statusFilter.split(',');
      if (!allowed.includes(item.status)) {
        return false;
      }
    }

    return true;
  });

  if (sortBy === 'created') {
    rows = [...rows].sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''));
  } else if (sortBy === 'status') {
    rows = [...rows].sort((a, b) => {
      const aStatus = candStatusOrder[a.status] ?? 99;
      const bStatus = candStatusOrder[b.status] ?? 99;

      if (aStatus !== bStatus) {
        return aStatus - bStatus;
      }
      if (a.language !== b.language) {
        return a.language.localeCompare(b.language);
      }
      return a.query.localeCompare(b.query);
    });
  } else {
    rows = [...rows].sort((a, b) => {
      if (a.language !== b.language) {
        return a.language.localeCompare(b.language);
      }
      return a.query.localeCompare(b.query);
    });
  }

  const tbody = document.getElementById('cand-body');
  if (!rows.length) {
    tbody.innerHTML = '<tr class="empty"><td colspan="8">No candidates</td></tr>';
    return;
  }

  tbody.innerHTML = rows
    .map((item) => {
      const isPromoted = item.status === 'promoted';
      const needsGeneration = item.status === 'needs_generation';
      const isDuplicate = item.status === 'duplicate';

      const canPromote = item.status === 'pending' || item.status === 'to_be_fixed';
      const canNeedsFix = item.status === 'pending';
      const canReopen = item.status === 'to_be_fixed' || item.status === 'duplicate';
      const canGenerate =
        item.status === 'needs_generation' ||
        item.status === 'pending' ||
        item.status === 'to_be_fixed';

      const actionButtons = [];

      if (canPromote) {
        actionButtons.push(
          `<button class="btn-promote" onclick="promoteCandidate('${esc(item.verb_id)}',this)">▲ Promote</button>`,
        );
      }

      if (item.status === 'pending' || item.status === 'to_be_fixed') {
        actionButtons.push(
          `<a class="btn-preview" href="/learn?language=${esc(item.language)}&verb_id=${esc(item.verb_id)}&source=candidate" target="_blank">👁 Preview</a>`,
        );
      }

      if (canNeedsFix) {
        actionButtons.push(
          `<button class="btn-needs-fix" onclick="setCandidateStatus('${esc(item.verb_id)}','to_be_fixed',this)">⚑ Needs fix</button>`,
        );
      }

      if (canReopen) {
        actionButtons.push(
          `<button class="btn-reopen" onclick="setCandidateStatus('${esc(item.verb_id)}','pending',this)">↩ Reopen</button>`,
        );
      }

      if (canGenerate) {
        const label = needsGeneration ? '⚡ Generate' : '⟳ Regen';
        actionButtons.push(
          `<button class="btn-regen" onclick="regenSingle('${esc(item.verb_id)}',this)">${label}</button>`,
        );
      }

      if (isDuplicate) {
        actionButtons.push(
          `<button class="btn-del" onclick="deleteCandidate('${esc(item.verb_id)}',this)">🗑 Delete</button>`,
        );
      }

      const formsCell = needsGeneration
        ? '<em style="color:var(--muted);font-size:12px">—</em>'
        : `<details><summary class="expand-summary">Forms</summary>
           <div class="expand-body">${renderFormsTable(item.forms)}</div>
         </details>`;

      const examplesCell = needsGeneration
        ? '<em style="color:var(--muted);font-size:12px">—</em>'
        : `<details><summary class="expand-summary">Examples</summary>
           <div class="expand-body">${renderExamplesList(item.examples)}</div>
         </details>`;

      return `<tr id="cand-row-${esc(item.verb_id)}" class="${isPromoted ? 'row-promoted' : ''}">
      <td><span class="mono">${esc(item.query)}</span></td>
      <td><span class="mono" style="color:var(--muted)">${item.lemma ? esc(item.lemma) : '—'}</span></td>
      <td><span class="pill pill-lang">${esc(item.language)}</span></td>
      <td style="color:var(--muted);font-size:12px">${item.rank ?? '—'}</td>
      <td>${candStatusPill(item.status)}</td>
      <td class="cell-expand">${formsCell}</td>
      <td class="cell-expand">${examplesCell}</td>
      <td>
        <div class="btn-col">
          ${actionButtons.join('')}
        </div>
      </td>
    </tr>`;
    })
    .join('');
}

async function regenSingle(verbId, button) {
  button.disabled = true;

  try {
    const response = await fetch(
      `${CANDIDATES_ROOT}/api/candidates/${encodeURIComponent(verbId)}/generate`,
      { method: 'POST' },
    );

    if (response.status === 409) {
      const conflict = await response.json().catch(() => ({}));
      const candidate = candidatesData.find((item) => item.verb_id === verbId);

      if (candidate) {
        candidate.status = 'duplicate';
        if (conflict.duplicate_of) {
          candidate.duplicate_of = conflict.duplicate_of;
        }
      }

      const statusFilter = document.getElementById('cand-filter-status');
      if (statusFilter && statusFilter.value === 'needs_generation,pending,to_be_fixed') {
        statusFilter.value = '';
      }

      updateCandidateStats();
      renderCandidates();

      alert(
        conflict.detail ||
          conflict.message ||
          'Duplicate detected. Candidate marked as duplicate.',
      );

      return;
    }

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorPayload.detail ?? response.statusText);
    }

    const doc = await response.json();
    const existingIndex = candidatesData.findIndex(
      (item) => item.verb_id === verbId || item.verb_id === doc.verb_id,
    );

    if (existingIndex >= 0) {
      candidatesData[existingIndex] = doc;
    } else {
      candidatesData.push(doc);
    }

    if (doc.verb_id !== verbId) {
      candidatesData = candidatesData.filter((item) => item.verb_id !== verbId);
    }

    updateCandidateStats();
    renderCandidates();
  } catch (error) {
    button.disabled = false;
    alert('Generate failed: ' + error.message);
  }
}

async function promoteCandidate(verbId, button) {
  button.disabled = true;

  try {
    const response = await fetch(
      `${CANDIDATES_ROOT}/api/candidates/${encodeURIComponent(verbId)}/promote`,
      { method: 'POST' },
    );

    if (response.status === 409) {
      const conflict = await response.json().catch(() => ({}));
      const candidate = candidatesData.find((item) => item.verb_id === verbId);

      if (candidate) {
        candidate.status = 'duplicate';
        if (conflict.duplicate_of) {
          candidate.duplicate_of = conflict.duplicate_of;
        }
      }

      const statusFilter = document.getElementById('cand-filter-status');
      if (statusFilter && statusFilter.value === 'needs_generation,pending,to_be_fixed') {
        statusFilter.value = '';
      }

      updateCandidateStats();
      renderCandidates();

      alert(
        conflict.detail ||
          conflict.message ||
          'Duplicate detected. Candidate marked as duplicate.',
      );

      return;
    }

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorPayload.detail ?? response.statusText);
    }

    const candidate = candidatesData.find((item) => item.verb_id === verbId);
    if (candidate) {
      candidate.status = 'promoted';
    }

    updateCandidateStats();
    renderCandidates();
  } catch (error) {
    button.disabled = false;
    alert('Promote failed: ' + error.message);
  }
}

async function setCandidateStatus(verbId, newStatus, button) {
  button.disabled = true;

  try {
    const response = await fetch(
      `${CANDIDATES_ROOT}/api/candidates/${encodeURIComponent(verbId)}/status`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      },
    );

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorPayload.detail ?? response.statusText);
    }

    const candidate = candidatesData.find((item) => item.verb_id === verbId);
    if (candidate) {
      candidate.status = newStatus;
    }

    updateCandidateStats();
    renderCandidates();
  } catch (error) {
    button.disabled = false;
    alert('Status update failed: ' + error.message);
  }
}

async function deleteCandidate(verbId, button) {
  if (!confirm(`Delete candidate ${verbId}?`)) {
    return;
  }

  button.disabled = true;

  try {
    const response = await fetch(
      `${CANDIDATES_ROOT}/api/candidates/${encodeURIComponent(verbId)}`,
      { method: 'DELETE' },
    );

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorPayload.detail ?? response.statusText);
    }

    candidatesData = candidatesData.filter((item) => item.verb_id !== verbId);
    updateCandidateStats();
    renderCandidates();
  } catch (error) {
    button.disabled = false;
    alert('Delete failed: ' + error.message);
  }
}
