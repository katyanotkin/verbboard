document.addEventListener("DOMContentLoaded", function () {
  var btn = document.getElementById("delete-account-btn");
  if (!btn) return;

  var UI = window.UI || {};

  function refreshVisibility() {
    var signedIn = !!(window.VerbBoardAuth && window.VerbBoardAuth.currentUser());
    btn.classList.toggle("hidden", !signedIn);
  }

  if (window.VerbBoardAuth) {
    window.VerbBoardAuth.ready().then(refreshVisibility);
  }
  window.addEventListener("vb:progress-hydrated", refreshVisibility);
  window.addEventListener("vb:auth-signed-out", refreshVisibility);

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
