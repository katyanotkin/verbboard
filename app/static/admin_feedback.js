(function () {
  const configElement = document.getElementById("admin-feedback-config");
  if (!configElement) return;

  const feedbackApiBase = configElement.dataset.feedbackApiBase;
  if (!feedbackApiBase) return;

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function buildQueryString() {
    const form = document.getElementById("filters");
    const formData = new FormData(form);
    const searchParams = new URLSearchParams();

    for (const [key, value] of formData.entries()) {
      const normalizedValue = String(value).trim();
      if (normalizedValue !== "") {
        searchParams.set(key, normalizedValue);
      }
    }

    return searchParams.toString();
  }

  function updateUrl() {
    const queryString = buildQueryString();
    const nextUrl = queryString
      ? `${window.location.pathname}?${queryString}`
      : window.location.pathname;

    window.history.replaceState(null, "", nextUrl);
  }

  function readInitialFilters() {
    const searchParams = new URLSearchParams(window.location.search);

    for (const element of document.querySelectorAll("#filters [name]")) {
      const value = searchParams.get(element.name);
      if (value !== null) {
        element.value = value;
      }
    }
  }

  function populateSelect(selectId, allLabel, values) {
    const selectElement = document.getElementById(selectId);
    if (!selectElement) return;

    const currentValue = selectElement.value;
    selectElement.innerHTML = "";

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = allLabel;
    selectElement.appendChild(defaultOption);

    for (const value of values) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      selectElement.appendChild(option);
    }

    selectElement.value = values.includes(currentValue) ? currentValue : "";
  }

  async function loadFacetValues() {
    const response = await fetch(`${feedbackApiBase}/facets`);
    if (!response.ok) throw new Error("Failed to load feedback facets");

    const payload = await response.json();
    populateSelect("page", "All pages", payload.pages || []);
    populateSelect("language", "All languages", payload.languages || []);
    populateSelect("source", "All sources", payload.sources || []);
  }

  function answerLabel(answer, pollMeta) {
    const options = pollMeta?.options || [];
    const found = options.find(o => o.value === answer);
    return found ? found.label : (answer || "-");
  }

  // For future yes/no/no_preference polls -- not used by the current poll.
  function renderYesNoPollSummary(filtered, pollLabel) {
    const yes = filtered.filter(r => r.poll_answer === "yes").length;
    const no = filtered.filter(r => r.poll_answer === "no").length;
    const noPref = filtered.filter(r => r.poll_answer === "no_preference").length;
    const total = yes + no + noPref;
    if (!total) return "";
    const yesPct = Math.round((yes / total) * 100);
    const noPct = Math.round((no / total) * 100);
    const noPrefPct = Math.round((noPref / total) * 100);
    return `
      <div class="card" style="padding:14px 16px;margin-bottom:12px;background:#f8fafc;">
        <div style="font-weight:700;margin-bottom:6px;">Poll: ${escapeHtml(pollLabel)}</div>
        <div style="font-size:13px;color:#374151;">
          Answers: ${total} ·
          Yes: ${yes} (${yesPct}%) ·
          No: ${no} (${noPct}%) ·
          No preference: ${noPref} (${noPrefPct}%)
        </div>
      </div>
    `;
  }

  function renderPollSummary(rows, pollMeta) {
    const activePollId = pollMeta?.poll_id || "";
    const options = pollMeta?.options || [];
    const validValues = new Set(options.map(o => o.value));
    const filtered = rows.filter(
      (r) => r.poll_id === activePollId && validValues.has(r.poll_answer)
    );

    const total = filtered.length;
    if (!total) return "";

    const counts = {};
    for (const opt of options) counts[opt.value] = 0;
    for (const r of filtered) if (r.poll_answer in counts) counts[r.poll_answer]++;

    const breakdown = options.map(opt => {
      const count = counts[opt.value] || 0;
      const pct = Math.round((count / total) * 100);
      return `${escapeHtml(opt.label)}: ${count} (${pct}%)`;
    }).join(" · ");

    const pollLabel = pollMeta?.question_en || "";

    return `
      <div class="card" style="padding:14px 16px;margin-bottom:12px;background:#f8fafc;">
        <div style="font-weight:700;margin-bottom:6px;">
          Poll: ${escapeHtml(pollLabel)}
        </div>
        <div style="font-size:13px;color:#374151;">
          Answers: ${total} · ${breakdown}
        </div>
      </div>
    `;
  }

  function renderUsageSummary(deviceMix) {
    const dims = [
      { label: "Devices",          data: deviceMix?.by_device   || {} },
      { label: "OS",               data: deviceMix?.by_os       || {} },
      { label: "Language studied", data: deviceMix?.by_language || {} },
      { label: "UI language",      data: deviceMix?.by_ui_lang  || {} },
    ];

    const totalSessions = deviceMix?.total_sessions ?? 0;
    if (!totalSessions) return "";

    const u = deviceMix?.users || {};
    const pr = deviceMix?.practice || {};
    const loggedIn = deviceMix?.logged_in_sessions ?? null;
    const anon = loggedIn != null ? totalSessions - loggedIn : null;
    const loginPct = totalSessions && loggedIn != null ? Math.round((loggedIn / totalSessions) * 100) : "—";

    function dimTable(data) {
      const sorted = Object.entries(data).sort((a, b) => b[1] - a[1]);
      const total = sorted.reduce((s, [, n]) => s + n, 0);
      const rows = sorted.map(([key, n]) => {
        const pct = total ? Math.round((n / total) * 100) : 0;
        return `<tr>
          <td style="padding:1px 8px 1px 0;color:#374151;">${escapeHtml(key)}</td>
          <td style="padding:1px 8px 1px 0;text-align:right;color:#374151;">${n}</td>
          <td style="padding:1px 0;color:#6b7280;">${pct}%</td>
        </tr>`;
      }).join("");
      return `<table style="border-collapse:collapse;font-size:12px;">${rows}</table>`;
    }

    function statRow(label, value) {
      return `<tr>
        <td style="padding:1px 8px 1px 0;color:#374151;">${label}</td>
        <td style="padding:1px 0;text-align:right;color:#374151;">${value}</td>
      </tr>`;
    }

    const usersTable = `<table style="border-collapse:collapse;font-size:12px;">
      ${statRow("Total registered", u.total ?? "—")}
      ${statRow("New (60d)", u.new_last_60d ?? "—")}
      ${statRow("Active (7d)", u.active_last_7d ?? "—")}
      ${statRow("Active (60d)", u.active_last_60d ?? "—")}
      ${statRow("Sessions logged-in", loggedIn != null ? `${loggedIn} (${loginPct}%)` : "—")}
      ${statRow("Sessions anon", anon != null ? anon : "—")}
    </table>`;

    const practiceSection = pr.practice_users_total != null ? `
      <div>
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;margin-bottom:4px;">Practice users</div>
        <table style="border-collapse:collapse;font-size:12px;">
          ${statRow("Total ever", pr.practice_users_total ?? "—")}
          ${Object.entries(pr.practice_by_language || {}).sort((a, b) => b[1] - a[1]).map(([lang, n]) => statRow(lang, n)).join("")}
        </table>
      </div>
    ` : "";

    const sections = dims.map(({ label, data }) => `
      <div>
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;margin-bottom:4px;">${label}</div>
        ${dimTable(data)}
      </div>
    `).join("");

    return `
      <div class="card" style="padding:14px 16px;margin-bottom:12px;background:#f1f5f9;">
        <div style="font-weight:700;margin-bottom:10px;">
          Usage summary · last ${escapeHtml(String(deviceMix.days || 60))} days · ${escapeHtml(String(totalSessions))} sessions
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(80px,auto));gap:16px 24px;align-items:start;">
          <div>
            <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;margin-bottom:4px;">Users</div>
            ${usersTable}
          </div>
          ${sections}
          ${practiceSection}
        </div>
      </div>
    `;
  }

  function renderFeedback(rows, pollRows, pollMeta, deviceMix) {
    const feedbackList = document.getElementById("feedback-list");
    if (!feedbackList) return;

    if (!rows.length) {
      feedbackList.innerHTML = `
        <div class="card" style="padding:24px;color:#6b7280;">
          No feedback found.
        </div>
      `;
      return;
    }

    const pollSummary = renderPollSummary(pollRows, pollMeta);
    const deviceSummary = renderUsageSummary(deviceMix);

    feedbackList.innerHTML =
      deviceSummary +
      pollSummary +
      rows.map(row => {
        const hiddenBadge = row.hidden
          ? '<span style="font-size:11px;background:#eee;padding:2px 6px;border-radius:6px;">hidden</span>'
          : "";

	const actionButton = row.hidden
  	  ? `<button type="button" data-action="unhide" data-id="${escapeHtml(row.id)}">Unhide</button>`
  	  : `<button type="button" data-action="hide" data-id="${escapeHtml(row.id)}">Hide</button>`;

        const pollBadge = row.poll_answer
          ? `<span style="font-size:11px;color:#374151;">poll: ${escapeHtml(answerLabel(row.poll_answer))}</span>`
          : "";

        const pollRaw = row.poll_question
          ? `<div style="margin-top:6px;font-size:12px;color:#374151;">
               <b>Poll:</b> ${escapeHtml(row.poll_question)}<br>
               <b>Answer:</b> ${escapeHtml(answerLabel(row.poll_answer))}
             </div>`
          : "";

        return `
	  <div class="card" style="padding:14px;margin-bottom:12px;">
	    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px;">
	      <div style="font-size:12px;color:#6b7280;line-height:1.5;overflow-wrap:anywhere;">
		${escapeHtml(row.created_at || "-")} ·
		${escapeHtml(row.source || "-")} ·
		${escapeHtml(row.page || "-")} ·
		${escapeHtml(row.language || "-")} ·
		${escapeHtml(row.verb_id || "-")}
		${pollBadge ? " · " + pollBadge : ""}
		${hiddenBadge}
	      </div>

	      <div style="flex-shrink:0;">
		${actionButton}
	      </div>
	    </div>

	    <div style="white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;line-height:1.55;color:#111827;">
	      ${escapeHtml(row.comment || "")}
	    </div>

	    ${pollRaw}
	  </div>
	`;
      }).join("");
  }

  async function loadFeedback() {
    const queryString = buildQueryString();
    updateUrl();

    const url = queryString ? `${feedbackApiBase}?${queryString}` : feedbackApiBase;

    const response = await fetch(url);
    if (!response.ok) throw new Error("Failed to load feedback");

    const payload = await response.json();

    renderFeedback(
      payload.feedback || [],
      payload.poll_feedback || [],
      payload.poll_meta || {},
      payload.device_mix || {}
    );
  }

  document.getElementById("filters")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    await loadFeedback();
  });

  document.addEventListener("click", async (event) => {
    const el = event.target;
    if (!(el instanceof HTMLElement)) return;

    const action = el.dataset.action;
    const id = el.dataset.id;
    if (!action || !id) return;

    await fetch(`${feedbackApiBase}/${id}/${action}`, { method: "POST" });
    await loadFeedback();
  });

  (async function init() {
    readInitialFilters();
    await loadFacetValues();
    await loadFeedback();
  })().catch((error) => {
    const feedbackList = document.getElementById("feedback-list");
    if (feedbackList) {
      feedbackList.innerHTML = `
        <div class="card" style="padding:24px;color:#b91c1c;">
          ${escapeHtml(error.message)}
        </div>
      `;
    }
  });
})();
