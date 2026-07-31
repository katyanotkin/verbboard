document.addEventListener("DOMContentLoaded", function () {
  var btn = document.getElementById("delete-account-btn");
  if (!btn) return;

  var UI = window.UI || {};

  var disabledTitle = UI["privacy.delete_account_disabled_title"] ||
    "Sign in with Google to delete your account";

  function refreshEnabled() {
    var signedIn = !!(window.VerbBoardAuth && window.VerbBoardAuth.currentUser());
    btn.disabled = !signedIn;
    if (signedIn) {
      btn.removeAttribute("title");
    } else {
      btn.title = disabledTitle;
    }
  }

  if (window.VerbBoardAuth) {
    window.VerbBoardAuth.ready().then(refreshEnabled);
  }
  window.addEventListener("vb:progress-hydrated", refreshEnabled);
  window.addEventListener("vb:auth-signed-out", refreshEnabled);

  btn.addEventListener("click", async function () {
    var confirmMsg = UI["privacy.delete_account_confirm"] ||
      "This will permanently delete your account and all data (progress, practice history). This cannot be undone. Continue?";
    if (!window.confirm(confirmMsg)) return;

    btn.disabled = true;
    try {
      await window.VerbBoardAuth.deleteAccount();
      alert(UI["privacy.delete_account_success"] || "Your account and data have been deleted.");
      window.location.href = "/";
    } catch (err) {
      alert(UI["privacy.delete_account_error"] || "Something went wrong. Please try again, or email us.");
      btn.disabled = false;
    }
  });
});
