(function () {
  "use strict";

  var config = document.getElementById("audio-reports-config");
  if (!config) return;
  var apiUrl = config.dataset.apiUrl;
  var body = document.getElementById("audio-reports-body");
  var hint = document.getElementById("audio-reports-hint");
  var languageSelect = document.getElementById("audio-reports-language");
  var status = "open";

  var HINTS = {
    open: "Most reported first. A new report on a resolved clip reopens it.",
    confirmed: "Publicly flagged on the verb page, newest confirmation first. Reports keep counting while confirmed.",
    resolved: "Fixed or dismissed. Votes were released and counters restarted."
  };
  var REASON_LABELS = {
    wrong_form: "different form", stress: "stress/vowel", glitch: "cut off/noisy", other: "other"
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatTime(iso) {
    return (iso || "").slice(0, 16).replace("T", " ");
  }

  function reasonChips(reasons) {
    return Object.keys(reasons || {})
      .sort(function (a, b) { return reasons[b] - reasons[a]; })
      .map(function (key) {
        return '<span class="cell-meta">' + escapeHtml(REASON_LABELS[key] || key) + " " + escapeHtml(reasons[key]) + "</span>";
      }).join(" ");
  }

  function actionButtons(report) {
    function btn(action, label) {
      return '<button type="button" class="btn-primary" data-action="' + escapeHtml(action) +
        '" data-id="' + escapeHtml(report.id) + '">' + escapeHtml(label) + "</button> ";
    }
    if (report.status === "open") return btn("confirm", "Confirm") + btn("resolve", "Resolve");
    if (report.status === "confirmed") return btn("resolve", "Resolve") + btn("unconfirm", "Unconfirm");
    return "";
  }

  function render(reports) {
    if (!reports.length) {
      body.innerHTML = '<p class="text-muted">Nothing here.</p>';
      return;
    }
    var rows = reports.map(function (r) {
      var comments = (r.comments || []).map(function (c) {
        return '<div class="cell-meta">&ldquo;' + escapeHtml(c) + "&rdquo;</div>";
      }).join("");
      var since = r.status === "confirmed" && r.reports_since_confirm > 0
        ? ' <span class="cell-meta">+' + escapeHtml(r.reports_since_confirm) + " since confirmed</span>" : "";
      var lastCol = r.status === "confirmed" ? r.confirmed_at : (r.status === "resolved" ? r.resolved_at : r.last_at);
      return "<tr>" +
        '<td><a href="' + escapeHtml(r.learn_url) + '" target="_blank" rel="noopener">' +
        escapeHtml(r.verb_id) + "</a></td>" +
        "<td>" + escapeHtml(r.text) + '<div class="cell-meta">' + escapeHtml(r.row_kind) + "</div>" + comments + "</td>" +
        "<td>" + escapeHtml(r.voice) + "</td>" +
        "<td>" + reasonChips(r.reasons) + "</td>" +
        "<td>" + escapeHtml(r.count) + since + "</td>" +
        "<td>" + escapeHtml(formatTime(r.last_at)) + "</td>" +
        "<td>" + escapeHtml(formatTime(lastCol)) + "</td>" +
        "<td>" + actionButtons(r) + "</td>" +
        "</tr>";
    }).join("");
    var lastHeader = status === "confirmed" ? "Confirmed" : (status === "resolved" ? "Resolved" : "Last reported");
    body.innerHTML = "<table><thead><tr><th>Verb</th><th>Form text</th><th>Voice</th><th>Reasons</th>" +
      "<th>Reports</th><th>Last reported</th><th>" + escapeHtml(lastHeader) + "</th><th></th></tr></thead><tbody>" +
      rows + "</tbody></table>";
  }

  function load() {
    hint.textContent = HINTS[status];
    Array.prototype.forEach.call(document.querySelectorAll("[data-status]"), function (btn) {
      btn.setAttribute("aria-pressed", btn.dataset.status === status ? "true" : "false");
      btn.style.opacity = btn.dataset.status === status ? "1" : "0.6";
    });
    var query = "?status=" + encodeURIComponent(status) + "&language=" + encodeURIComponent(languageSelect.value);
    fetch(apiUrl + query, { headers: { Accept: "application/json" } })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) { render(data.reports || []); })
      .catch(function (err) {
        body.innerHTML = '<p class="error-msg">' + escapeHtml(err && err.message ? err.message : err) + "</p>";
      });
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-status]"), function (btn) {
    btn.addEventListener("click", function () { status = btn.dataset.status; load(); });
  });
  languageSelect.addEventListener("change", load);

  body.addEventListener("click", function (event) {
    var btn = event.target.closest("[data-action]");
    if (!btn) return;
    btn.disabled = true;
    fetch(apiUrl + "/" + encodeURIComponent(btn.dataset.id) + "/" + encodeURIComponent(btn.dataset.action), {
      method: "POST"
    })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        load();
      })
      .catch(function () { btn.disabled = false; load(); });
  });

  load();
})();
