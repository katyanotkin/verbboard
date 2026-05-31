if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

let _installPrompt = null;

window.addEventListener("beforeinstallprompt", e => {
  e.preventDefault();
  _installPrompt = e;
  // Hide the manual hint -- native prompt will be used instead.
  document.getElementById("install-hint")?.setAttribute("hidden", "");
});

window.addEventListener("appinstalled", () => {
  document.getElementById("install-btn")?.setAttribute("hidden", "");
  document.getElementById("install-hint")?.setAttribute("hidden", "");
  _installPrompt = null;
});

window.vbInstall = async () => {
  if (_installPrompt) {
    // Browser supports programmatic install -- use it.
    _installPrompt.prompt();
    const { outcome } = await _installPrompt.userChoice;
    if (outcome === "accepted") _installPrompt = null;
  } else {
    // No native prompt (e.g. Opera Android) -- show manual instructions.
    document.getElementById("install-hint")?.removeAttribute("hidden");
  }
};

// Show the Install button on touch devices in browser mode (not yet installed).
// The button always appears; it triggers native install if available, or shows
// step-by-step instructions otherwise. Shown on all screen sizes for now.
(function () {
  var btn = document.getElementById("install-btn");
  if (!btn) return;

  var isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
  var isTouch = window.matchMedia("(pointer: coarse)").matches;

  if (!isStandalone && isTouch) {
    btn.removeAttribute("hidden");
  }

  var closeBtn = document.getElementById("install-hint-close");
  if (closeBtn) {
    closeBtn.addEventListener("click", function () {
      document.getElementById("install-hint")?.setAttribute("hidden", "");
    });
  }
})();
