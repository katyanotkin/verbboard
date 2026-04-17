'use strict';

async function loadFeedback() {
  try {
    const response = await fetch(`${ROOT}/api/feedback`);
    if (!response.ok) throw new Error(await response.text());

    feedbackData = (await response.json()).feedback;

    populateFilter(
      'fb-filter-lang',
      [...new Set(feedbackData.map(item => item.language).filter(Boolean))].sort(),
    );
    populateFilter(
      'fb-filter-source',
      [...new Set(feedbackData.map(item => item.source).filter(Boolean))].sort(),
    );

    updateFeedbackStats();
    renderFeedback();
  } catch (error) {
    document.getElementById('fb-body').innerHTML =
      `<tr><td colspan="6" class="error-msg">Error: ${error.message}</td></tr>`;
  }
}

function updateFeedbackStats() {
  document.getElementById('fb-total').textContent = feedbackData.length;
  document.getElementById('fb-with-comment').textContent =
    feedbackData.filter(item => item.comment?.trim()).length;
  document.getElementById('fb-langs').textContent =
    new Set(feedbackData.map(item => item.language).filter(Boolean)).size;
}

function renderFeedback() {
  const language = document.getElementById('fb-filter-lang').value;
  const source = document.getElementById('fb-filter-source').value;

  let rows = feedbackData;
  if (language) rows = rows.filter(item => item.language === language);
  if (source) rows = rows.filter(item => item.source === source);

  const tbody = document.getElementById('fb-body');
  if (!rows.length) {
    tbody.innerHTML = '<tr class="empty"><td colspan="6">No entries</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(item => {
    const date = item.created_at ? item.created_at.slice(0, 10) : '';
    const isGarbage = !item.comment || item.comment.trim().length < 2;

    return `<tr id="fb-${item.id}">
      <td><span class="comment ${isGarbage ? 'garbage' : ''}">${esc(item.comment || '(empty)')}</span></td>
      <td>${item.language ? `<span class="pill pill-lang">${esc(item.language)}</span>` : ''}</td>
      <td><span style="color:var(--muted);font-size:12px">${esc(item.page)}</span></td>
      <td>${item.source ? `<span class="pill pill-src">${esc(item.source)}</span>` : ''}</td>
      <td style="color:var(--muted);font-size:12px;white-space:nowrap">${date}</td>
      <td><button class="btn-del" title="Delete" onclick="deleteFeedback('${item.id}', this)">✕</button></td>
    </tr>`;
  }).join('');
}

async function deleteFeedback(id, button) {
  button.disabled = true;
  try {
    const response = await fetch(`${ROOT}/api/feedback/${id}`, { method: 'DELETE' });
    if (!response.ok) throw new Error(await response.text());

    feedbackData = feedbackData.filter(item => item.id !== id);
    document.getElementById(`fb-${id}`)?.remove();
    updateFeedbackStats();

    if (!document.querySelector('#fb-body tr:not(.empty)')) {
      renderFeedback();
    }
  } catch (error) {
    button.disabled = false;
    alert('Delete failed: ' + error.message);
  }
}
