if ("serviceWorker" in navigator) {
  // Register from /sw.js (root path, Service-Worker-Allowed: / header) so the
  // SW scope covers all pages, not just /static/*.
  navigator.serviceWorker.register("/sw.js");
}

let _installPrompt = null;

window.addEventListener("beforeinstallprompt", e => {
  e.preventDefault();
  _installPrompt = e;
  document.getElementById("install-btn")?.removeAttribute("hidden");
  // Native prompt available: hide the manual hint so they don't compete.
  document.getElementById("install-hint")?.setAttribute("hidden", "");
});

window.addEventListener("appinstalled", () => {
  document.getElementById("install-btn")?.setAttribute("hidden", "");
  document.getElementById("install-hint")?.setAttribute("hidden", "");
  _installPrompt = null;
});

window.vbInstall = async () => {
  if (!_installPrompt) return;
  _installPrompt.prompt();
  const { outcome } = await _installPrompt.userChoice;
  if (outcome === "accepted") _installPrompt = null;
};

// Fallback manual install hint: show on touch devices in browser mode when
// beforeinstallprompt has not fired and the user hasn't dismissed it before.
(function () {
  var DISMISSED_KEY = "vb_install_hint_dismissed";
  var hint = document.getElementById("install-hint");
  var closeBtn = document.getElementById("install-hint-close");
  if (!hint) return;

  var isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
  var isTouch = window.matchMedia("(pointer: coarse)").matches;
  var isDismissed = localStorage.getItem(DISMISSED_KEY) === "1";

  if (!isStandalone && isTouch && !isDismissed && !_installPrompt) {
    hint.removeAttribute("hidden");
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", function () {
      hint.setAttribute("hidden", "");
      localStorage.setItem(DISMISSED_KEY, "1");
    });
  }
})();
