(function () {
  "use strict";

  var config = document.getElementById("admin-personas-config");
  if (!config) return;
  var apiUrl = config.dataset.apiUrl;
  var errorBox = document.getElementById("personas-error");
  var body = document.getElementById("personas-body");
  var ISSUES_URL = "https://github.com/katyanotkin/verbboard/issues/";

  var STATUS_LABEL = { assumed: "Assumed", observed: "Observed", refuted: "Refuted" };

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function chip(status) {
    var key = Object.prototype.hasOwnProperty.call(STATUS_LABEL, status) ? status : "unknown";
    var label = STATUS_LABEL[key] || String(status || "-");
    return '<span class="status-pill persona-chip persona-chip--' + key + '">' + esc(label) + "</span>";
  }

  function openReviewHtml(review) {
    if (!review) return "";
    var window_ = review.window || {};
    return '<section class="card persona-section persona-open-review">' +
      "<h2>Open review: " + esc(review.date) + "</h2>" +
      '<p class="text-muted">Window ' + esc(window_.date_from) + " to " + esc(window_.date_to) + ".</p>" +
      '<pre class="persona-figures">' + esc(review.body || "(no figures stored)") + "</pre>" +
      '<div class="form-actions"><button type="button" class="btn-primary persona-done-btn" ' +
      'data-act="persona-done" data-a1="' + esc(review.date) + '">Mark done</button></div>' +
      "</section>";
  }

  function claimsTable(claims) {
    if (!claims || !claims.length) return '<p class="text-muted">No claims.</p>';
    var rows = claims.map(function (claim) {
      return "<tr><td>" + esc(claim.claim) + "</td><td>" + chip(claim.status) + "</td><td>" +
        esc(claim.evidence) + "</td><td>" + esc(claim.n) + "</td><td>" + esc(claim.last_checked) + "</td></tr>";
    }).join("");
    return '<div class="persona-table-wrap"><table class="tbl persona-claims"><thead><tr>' +
      "<th>Claim</th><th>Status</th><th>Evidence</th><th>n</th><th>Last checked</th>" +
      "</tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function personasHtml(snapshot) {
    if (!snapshot) {
      return '<section class="persona-section"><h2>Personas now</h2>' +
        '<p class="text-muted">No snapshot yet. Run <code>make persona-publish</code>.</p></section>';
    }
    var head = '<p class="text-muted">Last review ' + esc(snapshot.last_review || "-") +
      ", next review " + esc(snapshot.next_review || "-") +
      ". Snapshot " + esc(snapshot.date) + (snapshot.commit ? " (commit " + esc(snapshot.commit) + ")" : "") + ".</p>";
    var cards = (snapshot.personas || []).map(function (persona) {
      return '<div class="card persona-card"><h3>' + esc(persona.name) + "</h3>" +
        (persona.summary ? "<p>" + esc(persona.summary) + "</p>" : "") +
        (persona.next_test ? '<p class="text-muted"><strong>Next test:</strong> ' + esc(persona.next_test) + "</p>" : "") +
        claimsTable(persona.claims) + "</div>";
    }).join("");
    return '<section class="persona-section"><h2>Personas now</h2>' + head + cards + "</section>";
  }

  function eventText(event) {
    var who = esc(event.persona);
    var claim = esc(event.claim);
    switch (event.kind) {
      case "status":
        return who + ": " + claim + ": " + chip(event.from) + " &rarr; " + chip(event.to);
      case "added":
        return who + ": new claim " + claim + " " + chip(event.to);
      case "removed":
        return who + ": claim removed, " + claim + " (was " + chip(event.from) + ")";
      case "evidence":
        return who + ": " + claim + ": evidence updated " + chip(event.to);
      case "persona_added":
        return "New persona: " + who;
      default:
        return who + ": " + claim;
    }
  }

  function evolutionHtml(evolution) {
    var html = '<section class="persona-section"><h2>Evolution</h2>';
    if (!evolution || !evolution.length) {
      return html + '<p class="text-muted">No snapshots yet. Run <code>make persona-publish</code>.</p></section>';
    }
    if (evolution.length === 1) {
      html += '<p class="text-muted">No changes yet. Evolution appears after the next review publishes a new snapshot.</p>';
    }
    html += '<ol class="persona-timeline">' + evolution.map(function (entry, index) {
      var isBaseline = index === evolution.length - 1;
      var items;
      if (isBaseline) items = "<li>Baseline</li>";
      else if (!entry.events || !entry.events.length) items = '<li class="text-muted">No changes</li>';
      else items = entry.events.map(function (event) { return "<li>" + eventText(event) + "</li>"; }).join("");
      return '<li class="persona-timeline-item"><div class="persona-timeline-date">' + esc(entry.date) +
        (entry.commit ? ' <span class="pill pill-lang">' + esc(entry.commit) + "</span>" : "") +
        "</div><ul>" + items + "</ul></li>";
    }).join("") + "</ol></section>";
    return html;
  }

  function historyHtml(reviews) {
    var html = '<section class="persona-section"><h2>Review history</h2>';
    if (!reviews || !reviews.length) {
      return html + '<p class="text-muted">No reviews yet.</p></section>';
    }
    var rows = reviews.map(function (review) {
      var window_ = review.window || {};
      var done = review.status === "done";
      var issue = review.issue_number
        ? '<a href="' + ISSUES_URL + encodeURIComponent(review.issue_number) +
          '" target="_blank" rel="noopener">#' + esc(review.issue_number) + "</a>"
        : "-";
      return "<tr><td>" + esc(review.date) + "</td><td>" + esc(window_.date_from) + " to " + esc(window_.date_to) +
        '</td><td><span class="status-pill ' + (done ? "in_set" : "candidate") + '">' + (done ? "Done" : "Open") +
        "</span></td><td>" + issue + "</td></tr>";
    }).join("");
    return html + '<div class="card persona-table-wrap"><table class="tbl"><thead><tr>' +
      "<th>Date</th><th>Window</th><th>Status</th><th>Issue</th></tr></thead><tbody>" + rows +
      "</tbody></table></div></section>";
  }

  function render(data) {
    body.innerHTML = openReviewHtml(data.open_review) + personasHtml(data.snapshot) +
      evolutionHtml(data.evolution) + historyHtml(data.reviews);
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = !message;
  }

  function load() {
    return fetch(apiUrl, { credentials: "same-origin" })
      .then(function (response) {
        if (!response.ok) throw new Error("Request failed (" + response.status + ")");
        return response.json();
      })
      .then(function (data) { showError(""); render(data); })
      .catch(function (error) { showError(error.message); });
  }

  function markDone(reviewDate, button) {
    button.disabled = true;
    fetch(apiUrl + "/reviews/" + encodeURIComponent(reviewDate) + "/done", {
      method: "POST",
      credentials: "same-origin",
    })
      .then(function (response) {
        if (!response.ok) throw new Error("Could not mark done (" + response.status + ")");
        return load();
      })
      .catch(function (error) { showError(error.message); button.disabled = false; });
  }

  var ACTIONS = { "persona-done": markDone };
  document.addEventListener("click", function (event) {
    var el = event.target.closest && event.target.closest("[data-act]");
    if (!el || !Object.prototype.hasOwnProperty.call(ACTIONS, el.dataset.act)) return;
    ACTIONS[el.dataset.act](el.dataset.a1, el);
  });

  load();
})();
