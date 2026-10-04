(function () {
  "use strict";

  var config = document.getElementById("admin-report-config");
  if (!config) return;
  var apiUrl = config.dataset.apiUrl;
  var SINCE_KEY = "admin_report_invite_date";
  var DEFAULT_SINCE = "2026-10-01"; // first closed-testing invite

  var fromInput = document.getElementById("report-from");
  var toInput = document.getElementById("report-to");
  var sinceInput = document.getElementById("report-since");
  var compareInput = document.getElementById("report-compare");
  var errorBox = document.getElementById("report-error");
  var body = document.getElementById("report-body");

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function isoDaysAgo(days) {
    var d = new Date(Date.now() - days * 86400000);
    return d.toISOString().slice(0, 10);
  }

  function readSince() {
    try { return localStorage.getItem(SINCE_KEY) || DEFAULT_SINCE; } catch (_) { return DEFAULT_SINCE; }
  }

  function saveSince(value) {
    try {
      if (value) localStorage.setItem(SINCE_KEY, value);
      else localStorage.removeItem(SINCE_KEY);
    } catch (_) {}
  }

  function deltaHtml(report, key, isPct) {
    if (!report.deltas || !report.deltas[key]) return "";
    var d = report.deltas[key];
    var sign = d.delta > 0 ? "+" : "";
    var cls = d.delta > 0 ? "delta-up" : (d.delta < 0 ? "delta-down" : "delta-flat");
    var unit = isPct ? " pp" : "";
    return '<div class="stat-delta ' + cls + '">' + escapeHtml(sign + d.delta + unit) +
      " vs " + escapeHtml(d.previous + (isPct ? "%" : "")) + "</div>";
  }

  function tile(label, value, sub, delta) {
    return '<div class="stat"><div class="stat-label">' + escapeHtml(label) + "</div>" +
      '<div class="stat-val">' + escapeHtml(value) + "</div>" +
      '<div class="cell-meta">' + escapeHtml(sub) + "</div>" + delta + "</div>";
  }

  function trendSvg(daily) {
    var width = 640, height = 140, pad = 4;
    var max = 1;
    daily.forEach(function (row) { max = Math.max(max, row.sessions); });
    var slot = (width - pad * 2) / Math.max(daily.length, 1);
    var barWidth = Math.max(slot - 2, 1);
    var bars = daily.map(function (row, i) {
      var x = pad + i * slot;
      function bar(count, cls) {
        var h = (count / max) * (height - 20);
        return '<rect class="' + cls + '" x="' + x.toFixed(1) + '" y="' + (height - 16 - h).toFixed(1) +
          '" width="' + barWidth.toFixed(1) + '" height="' + h.toFixed(1) + '"><title>' +
          escapeHtml(row.date + ": " + row.sessions + " sessions, " + row.registered + " registered, " + row.twa + " TWA") +
          "</title></rect>";
      }
      return bar(row.sessions, "trend-bar-all") + bar(row.registered, "trend-bar-registered") + bar(row.twa, "trend-bar-twa");
    }).join("");
    var first = daily.length ? daily[0].date : "";
    var last = daily.length ? daily[daily.length - 1].date : "";
    return '<svg class="trend-svg" viewBox="0 0 ' + width + " " + height + '" role="img" aria-label="Daily sessions">' + bars +
      '<text class="trend-axis" x="' + pad + '" y="' + (height - 3) + '">' + escapeHtml(first) + "</text>" +
      '<text class="trend-axis" text-anchor="end" x="' + (width - pad) + '" y="' + (height - 3) + '">' + escapeHtml(last) + "</text></svg>" +
      '<div class="cell-meta"><span class="legend-all">all sessions</span> <span class="legend-registered">registered</span> <span class="legend-twa">TWA</span> (peak ' + escapeHtml(max) + ")</div>";
  }

  function table(headers, rows) {
    return "<table><thead><tr>" + headers.map(function (h) { return "<th>" + escapeHtml(h) + "</th>"; }).join("") +
      "</tr></thead><tbody>" + rows.map(function (r) {
        return "<tr>" + r.map(function (c) { return "<td>" + escapeHtml(c) + "</td>"; }).join("") + "</tr>";
      }).join("") + "</tbody></table>";
  }

  function engagementLabel(flag) {
    return flag.replace(/_/g, " ");
  }

  function render(report) {
    var reg = report.registered, twa = report.twa;
    var html = '<div class="card card-body"><div class="cell-meta">' +
      escapeHtml(report.range.date_from + " to " + report.range.date_to + " (" + report.range.days + " days)") +
      " &middot; " + escapeHtml(report.non_bot_sessions) + " non-bot sessions, " + escapeHtml(report.bot_sessions) +
      " bot sessions excluded</div></div>";

    html += '<div class="stats stats-4">' +
      tile("Registered sessions", reg.sessions_with_uid + " (" + reg.pct + "%)",
        reg.distinct_users + " distinct users, " + reg.new_registrations + " new registrations",
        deltaHtml(report, "registered.sessions_with_uid", false)) +
      tile("TWA (Play app) sessions", twa.sessions + " (" + twa.pct + "%)",
        twa.signed_in_users + " signed-in users",
        deltaHtml(report, "twa.sessions", false)) +
      tile("Legacy TWA (approx.)", String(twa.legacy_approximate_sessions),
        "before the twa flag existed", deltaHtml(report, "twa.legacy_approximate_sessions", false)) +
      tile("Non-bot sessions", String(report.non_bot_sessions), "denominator for percentages",
        deltaHtml(report, "non_bot_sessions", false)) +
      "</div>";

    html += '<div class="card card-body"><p class="cell-meta">' + escapeHtml(twa.note) +
      " Tracking since " + escapeHtml(twa.tracking_since) + ".</p></div>";

    html += '<div class="card card-body"><h2>Daily trend</h2>' + trendSvg(report.daily) + "</div>";

    var engagementRows = Object.keys(report.engagement).map(function (flag) {
      return [engagementLabel(flag), report.engagement[flag]];
    });
    var deviceRows = Object.keys(report.by_device).sort().map(function (name) {
      return [name, report.by_device[name]];
    });
    html += '<div class="card card-body"><h2>Engagement (sessions)</h2>' + table(["Signal", "Sessions"], engagementRows) + "</div>";
    html += '<div class="card card-body"><h2>Devices</h2>' + table(["Device", "Sessions"], deviceRows) + "</div>";
    body.innerHTML = html;
  }

  function run() {
    errorBox.hidden = true;
    var params = new URLSearchParams({
      date_from: fromInput.value,
      date_to: toInput.value,
      compare: compareInput.checked ? "true" : "false",
    });
    body.innerHTML = '<p class="text-muted">Loading...</p>';
    fetch(apiUrl + "?" + params.toString(), { headers: { Accept: "application/json" } })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          if (!res.ok) throw new Error(data.detail || ("HTTP " + res.status));
          return data;
        });
      })
      .then(render)
      .catch(function (err) {
        body.innerHTML = "";
        errorBox.textContent = String(err && err.message ? err.message : err);
        errorBox.hidden = false;
      });
  }

  function applyPreset(preset) {
    toInput.value = isoDaysAgo(0);
    if (preset === "since") {
      if (!sinceInput.value) {
        errorBox.textContent = "Set a Since date first.";
        errorBox.hidden = false;
        return;
      }
      fromInput.value = sinceInput.value;
    } else {
      fromInput.value = isoDaysAgo(Number(preset) - 1);
    }
    run();
  }

  fromInput.value = config.dataset.defaultFrom;
  toInput.value = config.dataset.defaultTo;
  sinceInput.value = readSince();
  sinceInput.addEventListener("change", function () { saveSince(sinceInput.value); });
  compareInput.addEventListener("change", run);
  document.getElementById("report-run").addEventListener("click", run);
  Array.prototype.forEach.call(document.querySelectorAll("[data-preset]"), function (btn) {
    btn.addEventListener("click", function () { applyPreset(btn.dataset.preset); });
  });
  run();
})();
