(function () {
  let authReadyResolve;

  const authReadyPromise = new Promise(function (resolve) {
    authReadyResolve = resolve;
  });

  let currentUser = null;

  function config() {
    return window.FIREBASE_WEB_CONFIG || null;
  }

  function hasFirebaseConfig() {
    const cfg = config();
    return cfg && cfg.apiKey;
  }

  async function getIdToken() {
    if (!currentUser) return "";
    return await currentUser.getIdToken();
  }

  async function signIn() {
    const provider = new firebase.auth.GoogleAuthProvider();
    await firebase.auth().signInWithPopup(provider);
  }

  async function signOut() {
    await firebase.auth().signOut();
  }

  function mountAuthButton() {
    const target =
      document.querySelector(".page-header") ||
      document.querySelector(".topbar-actions");

    if (!target) return;

    let existing = document.getElementById("auth-btn");

    if (existing) {
      existing.remove();
    }

    const button = document.createElement("button");

    button.id = "auth-btn";
    button.className = "btn-secondary auth-btn";

    if (currentUser) {
      button.textContent = "Logout";

      button.addEventListener("click", async function () {
        await signOut();
      });
    } else {
      button.textContent = "Login";

      button.addEventListener("click", async function () {
        await signIn();
      });
    }

    target.appendChild(button);
  }

  async function hydrateProgress() {
    if (!currentUser) return;

    const token = await getIdToken();

    if (!token) return;

    const languageSelect = document.querySelector(
      'select[name="language"]'
    );

    const pageRoot = document.getElementById("learn-page");

    let language = "";

    if (languageSelect) {
      language = languageSelect.value;
    }

    if (!language && pageRoot) {
      language = pageRoot.dataset.language || "";
    }

    if (!language) return;

    const response = await fetch(
      `/api/progress?language=${encodeURIComponent(language)}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!response.ok) return;

    const payload = await response.json();
    const verbs = payload.verbs || {};

    const seenKey = `seen:${language}`;
    const knownKey = `known:${language}`;

    let seen;
    let known;

    try {
      seen = new Set(
        JSON.parse(localStorage.getItem(seenKey) || "[]")
      );
    } catch (_) {
      seen = new Set();
    }

    try {
      known = new Set(
        JSON.parse(localStorage.getItem(knownKey) || "[]")
      );
    } catch (_) {
      known = new Set();
    }

    for (const [verbId, state] of Object.entries(verbs)) {
      if (state.seen) {
        seen.add(verbId);
      }

      if (state.known) {
        known.add(verbId);
      }
    }

    localStorage.setItem(
      seenKey,
      JSON.stringify(Array.from(seen))
    );

    localStorage.setItem(
      knownKey,
      JSON.stringify(Array.from(known))
    );
  }

  function initializeFirebase() {
    if (!hasFirebaseConfig()) {
      authReadyResolve();
      return;
    }

    firebase.initializeApp(config());

    firebase.auth().onAuthStateChanged(async function (user) {
      currentUser = user;

      mountAuthButton();

      if (currentUser) {
        await hydrateProgress();
      }

      authReadyResolve();
    });
  }

  window.VerbBoardAuth = {
    ready: function () {
      return authReadyPromise;
    },

    signIn: signIn,
    signOut: signOut,

    getIdToken: getIdToken,

    currentUser: function () {
      return currentUser;
    },
  };

  initializeFirebase();
})();
