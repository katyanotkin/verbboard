'use strict';

const CANDIDATES_ROOT = window.ADMIN_ROOT || "/admin";

async function loadCandidates() {
  candidatesLoaded = true;

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
      `<tr><td colspan="6" class="error-msg">Error: ${esc(error.message)}</td></tr>`;
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


function setCandSort(field) {
  if (candSortBy === field) {
    candSortDir = candSortDir === 'asc' ? 'desc' : 'asc';
  } else {
    candSortBy = field;
    candSortDir = 'asc';
  }
  renderCandidates();
}

function renderCandidates() {
  const languageFilter = document.getElementById('cand-filter-lang').value;
  const statusFilter = document.getElementById('cand-filter-status').value;

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

  if (candSortBy === 'status') {
    rows = [...rows].sort((a, b) => {
      const aStatus = candStatusOrder[a.status] ?? 99;
      const bStatus = candStatusOrder[b.status] ?? 99;
      const diff = candSortDir === 'asc' ? aStatus - bStatus : bStatus - aStatus;
      if (diff !== 0) return diff;
      if (a.language !== b.language) return a.language.localeCompare(b.language);
      return a.query.localeCompare(b.query);
    });
  } else {
    rows = [...rows].sort((a, b) => {
      if (a.language !== b.language) {
        return candSortDir === 'asc'
          ? a.language.localeCompare(b.language)
          : b.language.localeCompare(a.language);
      }
      return candSortDir === 'asc'
        ? a.query.localeCompare(b.query)
        : b.query.localeCompare(a.query);
    });
  }

  updateSortHeaders('cth', candSortBy, candSortDir, {
    query: 'Raw query', status: 'Status',
  });

  const tbody = document.getElementById('cand-body');
  if (!rows.length) {
    tbody.innerHTML = '<tr class="empty"><td colspan="6">No candidates</td></tr>';
    return;
  }

  tbody.innerHTML = rows
    .map((item) => {
      const isPromoted = item.status === 'promoted';
      const needsGeneration = item.status === 'needs_generation';
      const isDuplicate = item.status === 'duplicate';

      const canPromote = item.status === 'pending';
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
          `<a class="btn-preview" href="/learn?language=${esc(item.language)}&verb_id=${esc(item.verb_id)}&source=candidate&ui_language=en" target="_blank">👁 Preview</a>`,
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
          `<button class="btn-del" onclick="deleteCandidate('${esc(item.verb_id)}',this)">🗑</button>`,
        );
      }

      const lemmaDisplay = item.lemma
        ? `<span class="cand-lemma">${esc(item.lemma)}</span>`
        : '<em style="color:var(--muted)">—</em>';

      return `<tr id="cand-row-${esc(item.verb_id)}" class="${isPromoted ? 'row-promoted' : ''}">
      <td><span class="mono">${esc(item.query)}</span></td>
      <td>${lemmaDisplay}</td>
      <td><span class="pill pill-lang">${esc(item.language)}</span></td>
      <td style="color:var(--muted);font-size:12px">${item.rank ?? '—'}</td>
      <td>${candStatusPill(item.status)}</td>
      <td>
        <div class="btn-row">
          ${actionButtons.join('')}
        </div>
      </td>
    </tr>`;
    })
    .join('');
}

async function regenSingle(verbId, button) {
  button.disabled = true;
  const originalText = button.textContent;
  button.textContent = '⟳ Generating…';

  try {
    const response = await fetch(
      `${CANDIDATES_ROOT}/api/candidates/${encodeURIComponent(verbId)}/generate`,
      { method: 'POST' },
    );

    if (response.status === 409) {
      const conflict = await response.json().catch(() => ({}));

      // generate_candidate deletes the candidate doc before raising 409 — remove it locally
      candidatesData = candidatesData.filter((item) => item.verb_id !== verbId);

      const statusFilter = document.getElementById('cand-filter-status');
      if (statusFilter && statusFilter.value === 'needs_generation,pending,to_be_fixed') {
        statusFilter.value = '';
      }

      updateCandidateStats();
      renderCandidates();

      alert(conflict.detail || conflict.message || 'Already in live verbs. Candidate removed.');

      return;
    }

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorPayload.detail ?? response.statusText);
    }

    const doc = await response.json();
    delete doc.old_id;
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
    button.textContent = originalText;
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

    if (response.status === 404) {
      // Already gone from Firestore (e.g. deleted server-side on a prior 409) — clean up locally
      candidatesData = candidatesData.filter((item) => item.verb_id !== verbId);
      updateCandidateStats();
      renderCandidates();
      return;
    }

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
