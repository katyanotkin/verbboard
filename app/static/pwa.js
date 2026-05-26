if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/sw.js");
}

let _installPrompt = null;

window.addEventListener("beforeinstallprompt", e => {
  e.preventDefault();
  _installPrompt = e;
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
