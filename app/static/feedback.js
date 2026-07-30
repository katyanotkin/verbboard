document.addEventListener("DOMContentLoaded", function () {
  var emailInput = document.querySelector('input[name="contact_email"]');
  if (!emailInput || !window.VerbBoardAuth) return;

  window.VerbBoardAuth.ready().then(function () {
    var user = window.VerbBoardAuth.currentUser();
    if (user && user.email && !emailInput.value) {
      emailInput.value = user.email;
    }
  });
});
