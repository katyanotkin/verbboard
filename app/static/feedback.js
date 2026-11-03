document.addEventListener("DOMContentLoaded", function () {
  var emailInput = document.querySelector('input[name="contact_email"]');
  if (!emailInput || !window.VerbBoardAuth) return;

  function prefillEmail() {
    var user = window.VerbBoardAuth.currentUser();
    if (user && user.email && !emailInput.value) emailInput.value = user.email;
  }

  window.VerbBoardAuth.ready().then(prefillEmail);
  window.addEventListener("vb:progress-hydrated", prefillEmail);
});
