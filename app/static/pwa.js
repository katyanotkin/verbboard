if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
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
