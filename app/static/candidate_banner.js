async function candidateAction(verbId, action) {
  const banner = document.getElementById('candidate-banner');
  const adminHref = banner && banner.dataset.adminHref;
  if (!adminHref) return;
  const apiBase = adminHref.split('#')[0];  // strip #candidates for API calls

  if (action === 'promote') {
    const r = await fetch(`${apiBase}/api/candidates/${encodeURIComponent(verbId)}/promote`, {method: 'POST'});
    if (r.ok) {
      banner.innerHTML = `<span style="color:#3a7a5a;font-weight:600">✓ Promoted</span> <a href="${adminHref}" class="cand-nav-btn">← Admin</a>`;
    } else {
      alert('Promote failed: ' + (await r.json()).detail);
    }
  } else if (action === 'fix') {
    const r = await fetch(`${apiBase}/api/candidates/${encodeURIComponent(verbId)}/status`, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status: 'to_be_fixed'}),
    });
    if (r.ok) {
      banner.innerHTML = `<span style="color:#b8860b;font-weight:600">⚑ Marked for fix</span> <a href="${adminHref}" class="cand-nav-btn">← Admin</a>`;
    } else {
      alert('Failed: ' + (await r.json()).detail);
    }
  } else if (action === 'regen') {
    banner.innerHTML = `<span style="color:#555;font-weight:500">⟳ Regenerating… this takes ~15 s</span>`;
    const r = await fetch(`${apiBase}/api/candidates/${encodeURIComponent(verbId)}/generate`, {method: 'POST'});
    if (r.ok) {
      window.location.reload();
    } else {
      const err = await r.json().catch(() => ({detail: r.statusText}));
      const detail = String(err.detail || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      banner.innerHTML = `<span style="color:#b00;font-weight:600">⚠ Regen failed: ${detail}</span> <a href="${adminHref}" class="cand-nav-btn">← Admin</a>`;
    }
  }
}
