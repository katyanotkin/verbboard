if ("serviceWorker" in navigator) {
  // Register from /sw.js (root path, Service-Worker-Allowed: / header) so the
  // SW scope covers all pages, not just /static/*.
  navigator.serviceWorker.register("/sw.js");
}

let _installPrompt = null;

window.addEventListener("beforeinstallprompt", e => {
  e.preventDefault();
  _installPrompt = e;
  // Shown on all screen sizes while testing the install flow.
  // Restrict back to mobile-only once verified: wrap in matchMedia("(max-width:767px)").
  document.getElementById("install-btn")?.removeAttribute("hidden");
});

window.addEventListener("appinstalled", () => {
  document.getElementById("install-btn")?.setAttribute("hidden", "");
  _installPrompt = null;
});

window.vbInstall = async () => {
  if (!_installPrompt) return;
  _installPrompt.prompt();
  const { outcome } = await _installPrompt.userChoice;
  if (outcome === "accepted") _installPrompt = null;
};
