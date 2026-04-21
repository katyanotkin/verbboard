(function () {
  const configElement = document.getElementById("admin-feedback-config");
  if (!configElement) {
    return;
  }

  const feedbackApiBase = configElement.dataset.feedbackApiBase;
  if (!feedbackApiBase) {
    return;
  }

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
    if (!selectElement) {
      return;
    }

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
    const response = await fetch(`${feedbackApiBase}/facets`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error("Failed to load feedback facets");
    }

    const payload = await response.json();
    populateSelect("page", "All pages", payload.pages || []);
    populateSelect("language", "All languages", payload.languages || []);
    populateSelect("source", "All sources", payload.sources || []);
  }

  function renderFeedback(feedbackRows) {
    const feedbackList = document.getElementById("feedback-list");
    if (!feedbackList) {
      return;
    }

    if (!feedbackRows.length) {
      feedbackList.innerHTML = `
        <div class="card" style="padding:24px;color:#6b7280;">
          No feedback found.
        </div>
      `;
      return;
    }

    feedbackList.innerHTML = feedbackRows
      .map((feedbackRow) => {
        const hiddenBadge = feedbackRow.hidden
          ? '<span style="display:inline-flex;align-items:center;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;background:#f3f4f6;color:#4b5563;">hidden</span>'
          : "";

        const actionButton = feedbackRow.hidden
          ? `<button type="button" data-action="unhide" data-id="${escapeHtml(feedbackRow.id)}">Unhide</button>`
          : `<button type="button" data-action="hide" data-id="${escapeHtml(feedbackRow.id)}">Hide</button>`;

        return `
          <div class="card" style="padding:14px 16px;margin-bottom:12px;">
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px;">
              <div style="font-size:12px;color:#6b7280;line-height:1.5;overflow-wrap:anywhere;display:flex;gap:6px;flex-wrap:wrap;">
                <span>${escapeHtml(feedbackRow.created_at || "-")}</span>
                <span>·</span>
                <span>${escapeHtml(feedbackRow.source || "-")}</span>
                <span>·</span>
                <span>${escapeHtml(feedbackRow.page || "-")}</span>
                <span>·</span>
                <span>${escapeHtml(feedbackRow.language || "-")}</span>
                <span>·</span>
                <span>${escapeHtml(feedbackRow.verb_id || "-")}</span>
                ${hiddenBadge}
              </div>

              <div style="flex-shrink:0;">
                ${actionButton}
              </div>
            </div>

            <div style="white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;line-height:1.55;color:#111827;">
              ${escapeHtml(feedbackRow.comment || "")}
            </div>
          </div>
        `;
      })
      .join("");
  }

  async function loadFeedback() {
    const queryString = buildQueryString();
    updateUrl();

    const url = queryString ? `${feedbackApiBase}?${queryString}` : feedbackApiBase;

    const response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error("Failed to load feedback");
    }

    const payload = await response.json();
    renderFeedback(payload.feedback || []);
  }

  async function moderateFeedback(feedbackId, action) {
    const response = await fetch(
      `${feedbackApiBase}/${encodeURIComponent(feedbackId)}/${action}`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to ${action} feedback`);
    }

    await loadFeedback();
  }

  const filtersForm = document.getElementById("filters");
  if (filtersForm) {
    filtersForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      await loadFeedback();
    });

    for (const selectElement of filtersForm.querySelectorAll("select")) {
      selectElement.addEventListener("change", async () => {
        await loadFeedback();
      });
    }
  }	

  document.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    const action = target.dataset.action;
    const feedbackId = target.dataset.id;

    if (!action || !feedbackId) {
      return;
    }

    await moderateFeedback(feedbackId, action);
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
	    ${escapeHtml(error.message || "Failed to load feedback admin page.")}
	  </div>
      `;
    }
  });
})();
