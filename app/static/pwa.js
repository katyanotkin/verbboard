var VB_SW_UPDATE_STRINGS = {
  en: { text: "A new version is available", button: "Update", close: "Close" },
  ru: { text: "Доступна новая версия", button: "Обновить", close: "Закрыть" },
  es: { text: "Hay una nueva versión disponible", button: "Actualizar", close: "Cerrar" },
  he: { text: "גרסה חדשה זמינה", button: "עדכון", close: "סגירה" },
};
var VB_SW_UPDATE_INTERVAL_MS = 60 * 60 * 1000;

// "New version available" banner. The SW skips waiting but never claims open
// pages, so a page keeps its old cached JS/CSS until it is reloaded; this tells
// the user. Never reloads by itself (the user may be mid-answer or mid-practice).
function vbShowUpdateBanner() {
  if (document.getElementById("vb-update-banner")) return;
  var lang = String(window.VB_UI_LANG || document.documentElement.lang || "en")
    .toLowerCase()
    .split("-")[0];
  var strings = VB_SW_UPDATE_STRINGS[lang] || VB_SW_UPDATE_STRINGS.en;

  var banner = document.createElement("div");
  banner.id = "vb-update-banner";
  banner.className = "vb-update-banner";
  banner.setAttribute("role", "status");
  banner.setAttribute("aria-live", "polite");
  if (lang === "he") banner.setAttribute("dir", "rtl");

  var text = document.createElement("span");
  text.className = "vb-update-text";
  text.textContent = strings.text;

  var update = document.createElement("button");
  update.type = "button";
  update.className = "vb-update-btn";
  update.id = "vb-update-reload";
  update.textContent = strings.button;
  update.addEventListener("click", function () {
    location.reload();
  });

  var dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.className = "vb-update-dismiss";
  dismiss.id = "vb-update-dismiss";
  dismiss.setAttribute("aria-label", strings.close);
  dismiss.textContent = "×";
  dismiss.addEventListener("click", function () {
    banner.remove();
  });

  banner.appendChild(text);
  banner.appendChild(update);
  banner.appendChild(dismiss);
  document.body.appendChild(banner);
}

window.VerbBoardUpdate = { show: vbShowUpdateBanner, check: function () {} };

if ("serviceWorker" in navigator) {
  // Only an already-controlled page can be "outdated"; the first install is not.
  var vbHadController = !!navigator.serviceWorker.controller;

  navigator.serviceWorker.register("/sw.js").then(function (registration) {
    function watch(worker) {
      if (!worker) return;
      worker.addEventListener("statechange", function () {
        if (
          worker.state === "activated" && vbHadController
        ) {
          vbShowUpdateBanner();
        }
      });
    }

    registration.addEventListener("updatefound", function () {
      watch(registration.installing);
    });
    // The update may already be under way / done before register() resolved.
    if (registration.waiting && vbHadController) vbShowUpdateBanner();
    watch(registration.installing);

    var lastCheck = Date.now();
    function checkForUpdate() {
      lastCheck = Date.now();
      registration.update().catch(function () {});
    }
    document.addEventListener("visibilitychange", function () {
      if (
        document.visibilityState === "visible" &&
        Date.now() - lastCheck >= VB_SW_UPDATE_INTERVAL_MS
      ) {
        checkForUpdate();
      }
    });
    setInterval(function () {
      if (document.visibilityState === "visible") checkForUpdate();
    }, VB_SW_UPDATE_INTERVAL_MS);

    window.VerbBoardUpdate.check = checkForUpdate;
  }).catch(function () {});
}

// Show the Google Play link on Android browsers (not the installed app, not
// embedded WebViews, whose UA carries "; wv)"). Hidden everywhere else: iOS
// has no app, desktop has the browser's own install icon.
(function () {
  var link = document.getElementById("play-link");
  if (!link) return;

  var ua = navigator.userAgent;
  var isAndroidBrowser = /Android/i.test(ua) && !/; wv\)/.test(ua);
  var isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;

  if (isAndroidBrowser && !isStandalone) link.removeAttribute("hidden");
})();

// "Rate us on Google Play" line (About / Feedback). Shown on Android browsers
// AND the installed Android app (TWA, standalone), but not in WebViews
// ("; wv)"). Nothing for iOS/desktop. A tap sends a set-once beacon; keepalive
// because the link navigates away immediately.
function vbShowRateLink(doc, nav) {
  var line = doc.getElementById("rate-line");
  if (!line) return;
  var ua = nav.userAgent || "";
  if (!(/Android/i.test(ua) && !/; wv\)/.test(ua))) return;
  line.removeAttribute("hidden");
  var link = doc.getElementById("rate-link");
  if (!link) return;
  link.addEventListener("click", function () {
    try {
      fetch("/api/analytics/rate_clicked", { method: "POST", keepalive: true }).catch(function () {});
    } catch (_) {}
  });
}
vbShowRateLink(document, navigator);
