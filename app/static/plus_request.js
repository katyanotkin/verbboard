/* One-tap Plus access request (/feedback?page=plus) and the Plus notice beacon (/verbs).
   Page-agnostic: one delegated click handler; token/uid/email are taken server-side from the ID token. */
(function () {
  "use strict";

  var PENDING_KEY = "plus_request_pending";
  var BDI_WORDS = /(Plus|Google)/;

  function auth() { return window.VerbBoardAuth || null; }

  // Text with <bdi> around "Plus"/"Google" so they keep their direction inside RTL/LTR text. DOM nodes only, no innerHTML.
  function setText(el, text) {
    el.textContent = "";
    String(text).split(BDI_WORDS).forEach(function (part, i) {
      if (!part) return;
      if (i % 2 === 1) {
        var bdi = document.createElement("bdi");
        bdi.textContent = part;
        el.appendChild(bdi);
      } else {
        el.appendChild(document.createTextNode(part));
      }
    });
  }

  function wrapStaticText(root) {
    root.querySelectorAll("p.plus-request__text, button").forEach(function (el) {
      if (el.children.length === 0 && el.textContent) setText(el, el.textContent);
    });
  }

  function storageGet() {
    try { return sessionStorage.getItem(PENDING_KEY) || ""; } catch (e) { return ""; }
  }
  function storageSet(value) {
    try {
      if (value) sessionStorage.setItem(PENDING_KEY, value);
      else sessionStorage.removeItem(PENDING_KEY);
    } catch (e) { /* storage blocked: sign-in then needs a second tap */ }
  }

  function show(root, state, message) {
    root.querySelectorAll("[data-plus-state]").forEach(function (el) {
      var name = el.getAttribute("data-plus-state");
      if (name === "account") return;
      el.hidden = name !== state;
    });
    if (message !== undefined) {
      var target = root.querySelector('[data-plus-state="' + state + '"]');
      if (target) setText(target, message);
    }
  }

  function showAccount(root, user) {
    var line = root.querySelector('[data-plus-state="account"]');
    if (!line) return;
    if (!user || !user.email) { line.hidden = true; return; }
    var tpl = root.getAttribute("data-account-tpl") || "{email}";
    var pieces = tpl.split("{email}");
    line.textContent = "";
    line.appendChild(document.createTextNode(pieces[0]));
    var bdi = document.createElement("bdi");
    bdi.textContent = user.email;
    line.appendChild(bdi);
    if (pieces.length > 1) line.appendChild(document.createTextNode(pieces.slice(1).join("{email}")));
    line.hidden = false;
  }

  function showDone(root, message) {
    show(root, "done", message);
    var done = root.querySelector('[data-plus-state="done"]');
    if (done) done.focus();
  }

  function api(method, token, language, body) {
    var url = "/api/plus/request" + (method === "GET" ? "?language=" + encodeURIComponent(language) : "");
    var options = { method: method, headers: { Authorization: "Bearer " + token } };
    if (body) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    return fetch(url, options).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        return { ok: resp.ok, data: data };
      });
    });
  }

  function sendRequest(root) {
    var language = root.getAttribute("data-language");
    var button = root.querySelector('[data-plus-act="request"]');
    var A = auth();
    if (!A) return Promise.resolve();
    if (button) { button.disabled = true; button.setAttribute("aria-busy", "true"); }
    return A.getIdToken().then(function (token) {
      if (!token) throw new Error("no token");
      return api("POST", token, language, {
        language: language,
        ui_language: root.getAttribute("data-ui-language") || ""
      });
    }).then(function (result) {
      if (!result.ok || !result.data.ok) throw new Error("request failed");
      showDone(root, root.getAttribute(result.data.duplicate ? "data-already" : "data-done"));
    }).catch(function () {
      show(root, "signed-in");
      var err = root.querySelector('[data-plus-state="error"]');
      if (err) { setText(err, root.getAttribute("data-error")); err.hidden = false; }
    }).then(function () {
      if (button) { button.disabled = false; button.removeAttribute("aria-busy"); }
    });
  }

  var refreshing = false;
  function refresh(root) {
    var A = auth();
    if (!A) { show(root, "signed-out"); return Promise.resolve(); }
    var user = A.currentUser();
    showAccount(root, user);
    if (!user) { show(root, "signed-out"); return Promise.resolve(); }
    if (refreshing) return Promise.resolve();
    refreshing = true;
    var language = root.getAttribute("data-language");
    return A.getIdToken().then(function (token) {
      if (!token) { show(root, "signed-out"); return; }
      return api("GET", token, language).then(function (result) {
        if (result.ok && result.data.requested) {
          storageSet("");
          showDone(root, root.getAttribute("data-already"));
          return;
        }
        show(root, "signed-in");
        if (storageGet() === language) {
          storageSet("");
          return sendRequest(root);
        }
      });
    }).catch(function () {
      show(root, "signed-in");
    }).then(function () { refreshing = false; });
  }

  function initCard(root) {
    wrapStaticText(root);
    var A = auth();
    if (!A) { show(root, "signed-out"); return; }
    A.ready().then(function () { return refresh(root); });
    window.addEventListener("vb:progress-hydrated", function () { refresh(root); });
  }

  document.addEventListener("click", function (event) {
    var control = event.target.closest ? event.target.closest("[data-plus-act]") : null;
    if (!control) return;
    var root = control.closest(".plus-request");
    if (!root) return;
    var act = control.getAttribute("data-plus-act");
    if (act === "signin") {
      if (!auth()) return;
      storageSet(root.getAttribute("data-language"));
      auth().signIn();
    } else if (act === "request") {
      sendRequest(root);
    }
  });

  // Plus notice beacon: set-once session flag, once per page load.
  function beaconNotice() {
    if (!document.querySelector("[data-plus-notice]")) return;
    try {
      fetch("/api/analytics/practice_event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event: "plus_notice_shown" }),
        keepalive: true
      }).catch(function () {});
    } catch (e) { /* analytics only */ }
  }

  function init() {
    var card = document.getElementById("plus-request");
    if (card) initCard(card);
    beaconNotice();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
