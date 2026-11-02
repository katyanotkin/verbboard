document.addEventListener("DOMContentLoaded", function () {
  var emailInput = document.querySelector('input[name="contact_email"]');
  if (!emailInput || !window.VerbBoardAuth) return;

  var form = document.getElementById("feedback-form");
  var isPlus = !!(form && form.dataset.plus === "1");
  var tokenInput = document.getElementById("plus-id-token");
  var submitBtn = document.getElementById("plus-submit");
  var accountLine = document.getElementById("plus-account");
  var signinBox = document.getElementById("plus-signin");

  function refreshPlusState(user) {
    if (!isPlus) return;
    var signedIn = !!user;
    if (submitBtn) submitBtn.disabled = !signedIn;
    if (signinBox) signinBox.hidden = signedIn;
    if (accountLine) {
      accountLine.hidden = !signedIn;
      if (signedIn) {
        accountLine.textContent = (accountLine.dataset.tpl || "{email}").replace("{email}", user.email || "");
      }
    }
  }

  window.VerbBoardAuth.ready().then(function () {
    var user = window.VerbBoardAuth.currentUser();
    if (user && user.email && !emailInput.value) {
      emailInput.value = user.email;
    }
    refreshPlusState(user);
  });

  if (!isPlus) return;

  window.addEventListener("vb:progress-hydrated", function () {
    var user = window.VerbBoardAuth.currentUser();
    if (user && user.email && !emailInput.value) emailInput.value = user.email;
    refreshPlusState(user);
  });

  var signinBtn = document.getElementById("plus-signin-btn");
  if (signinBtn) {
    signinBtn.addEventListener("click", function () {
      window.VerbBoardAuth.signIn();
    });
  }

  // The server verifies this token and takes uid/email from it; never from form fields.
  var submitting = false;
  form.addEventListener("submit", function (event) {
    if (submitting) return;
    event.preventDefault();
    window.VerbBoardAuth.getIdToken().then(function (token) {
      if (!token) {
        var err = document.getElementById("plus-token-error");
        if (err) {
          err.textContent = err.dataset.msg || "";
          err.hidden = false;
        }
        return;
      }
      tokenInput.value = token;
      submitting = true;
      form.submit();
    });
  });
});
