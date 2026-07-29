(function () {
  let authReadyResolve;

  const authReadyPromise = new Promise(function (resolve) {
    authReadyResolve = resolve;
  });

  let currentUser = null;
  let signInInProgress = false;

  // sessionStorage key used to detect sign-out across page navigations.
  // Set to the uid on login; removed on sign-out.  sessionStorage persists
  // within a browser tab across navigations but is cleared when the tab closes,
  // so it correctly tracks per-tab auth state.
  var SESSION_UID_KEY = 'vb:uid';

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

  function isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches
      || window.navigator.standalone === true;
  }

  function isMobile() {
    // Popups become full tabs on mobile and lose window.opener, breaking
    // Firebase's popup auth flow. Use UA only -- maxTouchPoints fires on
    // touchscreen laptops and window.innerWidth on narrow desktop windows,
    // both of which should keep the popup flow.
    return /Mobi|Android|iPhone|iPad|Opera Mini/i.test(navigator.userAgent);
  }

  async function signIn() {
    if (signInInProgress) return;
    signInInProgress = true;
    try {
      const provider = new firebase.auth.GoogleAuthProvider();
      // Always show the account chooser, even when the browser has a cached
      // Google session -- prevents silent single-account auto-sign-in.
      provider.setCustomParameters({ prompt: 'select_account' });
      if (isStandalone()) {
        // Standalone PWA: opening a browser tab crosses the PWA/browser
        // boundary and focuses the new tab. Firebase syncs auth state back
        // to the PWA shell via IndexedDB once sign-in completes.
        window.open('/auth/signin', '_blank');
      } else if (isMobile()) {
        // Mobile browser: window.open(_blank) opens in the background on
        // Chrome Android (no focus switch). Navigate the current page to the
        // sign-in page instead; it redirects back via return_to after success.
        var returnTo = encodeURIComponent(location.pathname + location.search);
        window.location.href = '/auth/signin?return_to=' + returnTo;
      } else {
        await firebase.auth().signInWithPopup(provider);
      }
    } finally {
      signInInProgress = false;
    }
  }

  async function signOut() {
    // Clear the uid claim from the __session cookie before Firebase signs the
    // user out client-side, so a stale cookie doesn't keep the server treating
    // this browser as the previous user (e.g. for entitlement checks on a
    // plain page-load GET) after sign-out completes. Awaited -- unlike other
    // non-critical fire-and-forget calls in this file -- because the user may
    // navigate away immediately after clicking sign-out.
    try {
      await fetch('/api/analytics/session/clear', { method: 'POST' });
    } catch (_) {}
    await firebase.auth().signOut();
  }

  // Remove all user-specific progress keys from localStorage across all
  // languages.  Called by auth.js on sign-out so cleanup happens even if the
  // user navigates to a different page before signing out.
  function clearProgressLocalStorage() {
    var toRemove = [];
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      if (k && (
        k.startsWith('known:') ||
        k.startsWith('seen:') ||
        k.startsWith('practice_badges:') ||
        k.startsWith('practice_session:') ||
        k.startsWith('practice_wrapup:') ||
        k.startsWith('audio_plays:')
      )) {
        toRemove.push(k);
      }
    }
    toRemove.forEach(function (k) { localStorage.removeItem(k); });
  }

  function mountAuthButton() {
    // Prefer the dedicated auth slot (verbs page) so the button lands in the
    // right layout position.  Fall back to the generic header targets on pages
    // that don't have an explicit slot.
    const target =
      document.getElementById("auth-slot") ||
      document.querySelector(".page-header") ||
      document.querySelector(".topbar-actions");

    if (!target) return;

    let existing = document.getElementById("auth-btn");

    if (existing) {
      existing.remove();
    }

    // Read localized labels from window.UI (set by each page's server render).
    // Fall back to English strings so the button is always usable even on pages
    // that don't (yet) expose window.UI.
    var _ui = window.UI || {};
    var loginLabel = _ui['auth.login'] || 'Login';
    var logoutLabel = _ui['auth.logout'] || 'Logout';

    const button = document.createElement("button");

    button.id = "auth-btn";
    button.className = "btn-secondary auth-btn";
    button.type = "button";

    const snailIcon = document.createElement("img");
    snailIcon.src = "/static/snail-logo.svg";
    snailIcon.alt = "";
    snailIcon.setAttribute("aria-hidden", "true");
    snailIcon.className = "auth-brand-icon";
    snailIcon.width = 14;
    snailIcon.height = 14;
    button.appendChild(snailIcon);

    if (currentUser) {
      const photoURL = currentUser.photoURL;

      if (photoURL) {
        const img = document.createElement("img");
        img.src = photoURL;
        img.alt = "";
        img.className = "auth-avatar";
        // referrerpolicy required for Google profile image URLs to load
        // correctly when the page origin differs from accounts.google.com.
        img.referrerPolicy = "no-referrer";
        img.onerror = function () { this.remove(); };
        button.appendChild(img);
      }

      button.appendChild(document.createTextNode(logoutLabel));

      button.addEventListener("click", async function () {
        await signOut();
      });
    } else {
      button.appendChild(document.createTextNode(loginLabel));

      button.addEventListener("click", async function () {
        try {
          await signIn();
        } catch (err) {
          if (err.code === 'auth/cancelled-popup-request') return;
          console.error('VB sign-in error:', err);
          alert('Sign-in error: ' + (err.message || err.code || err));
        }
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

    if (!language && window.VB_LANGUAGE) {
      language = window.VB_LANGUAGE;
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

    // Track which verbs the server considers known so we can upload the diff.
    const serverKnownIds = new Set();

    for (const [verbId, state] of Object.entries(verbs)) {
      if (state.seen) {
        seen.add(verbId);
      }

      if (state.known) {
        known.add(verbId);
        serverKnownIds.add(verbId);
      }
      // No delete: local knowledge is preserved. Pre-login learned verbs
      // are not on the server yet -- union wins here.
    }

    localStorage.setItem(
      seenKey,
      JSON.stringify(Array.from(seen))
    );

    localStorage.setItem(
      knownKey,
      JSON.stringify(Array.from(known))
    );

    // Upload any locally-known verbs the server doesn't have yet.
    const toUpload = Array.from(known).filter(function (id) {
      return !serverKnownIds.has(id);
    });
    if (toUpload.length > 0) {
      toUpload.forEach(function (verbId) {
        fetch('/api/progress/known', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: 'Bearer ' + token,
          },
          body: JSON.stringify({ language: language, verb_id: verbId, known: true }),
        }).catch(function () {});
      });
    }

    window.dispatchEvent(
      new CustomEvent('vb:progress-hydrated', { detail: { language } })
    );
  }

  async function applyPreferences() {
    if (!currentUser) return;
    const token = await getIdToken();
    if (!token) return;

    const currentUiLang = document.documentElement.lang || '';
    const langSelect = document.querySelector('select[name="language"]');
    const currentLearningLang = langSelect ? langSelect.value : (window.VB_LANGUAGE || '');
    const onHome = window.location.pathname === '/';
    const urlParams = new URLSearchParams(window.location.search);
    const explicitUiLang = urlParams.has('ui_language');
    const explicitLearningLang = urlParams.has('language');

    try {
      const resp = await fetch('/api/preferences', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) return;

      const prefs = await resp.json();
      const toSave = {};

      // UI language: if the user just explicitly switched (ui_language in URL),
      // their choice is authoritative — save it to the server.
      // Otherwise only save when the server has no preference yet.
      if (currentUiLang && (explicitUiLang || !prefs.ui_language) && prefs.ui_language !== currentUiLang) {
        toSave.ui_language = currentUiLang;
      }

      // Learning language: same pattern — explicit switch is authoritative.
      if (currentLearningLang && (explicitLearningLang || !prefs.learning_language) && prefs.learning_language !== currentLearningLang) {
        toSave.learning_language = currentLearningLang;
      }

      if (Object.keys(toSave).length) {
        await fetch('/api/preferences', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify(toSave),
        });
      }

      // Apply — redirect to server preferences only when the user did not just
      // explicitly switch (otherwise we'd immediately undo their choice).
      const url = new URL(window.location.href);
      let needsRedirect = false;

      if (!explicitUiLang && prefs.ui_language && currentUiLang && prefs.ui_language !== currentUiLang) {
        url.searchParams.set('ui_language', prefs.ui_language);
        needsRedirect = true;
      }

      if (onHome && !explicitLearningLang && prefs.learning_language && currentLearningLang && prefs.learning_language !== currentLearningLang) {
        url.searchParams.set('language', prefs.learning_language);
        needsRedirect = true;
      }

      if (needsRedirect) {
        window.location.replace(url.toString());
        return;
      }

      // Apply practice session size from server profile.
      const serverSize = prefs.practice_session_size;
      if (serverSize) {
        const lang = currentLearningLang;
        if (lang) localStorage.setItem(`practice_size:${lang}`, String(serverSize));
        const loop = window.VerbBoardPracticeLoopInstance;
        if (loop && loop.setSize) loop.setSize(serverSize);
      }
    } catch (_) {}
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
        // Record that this tab has an authenticated session.
        sessionStorage.setItem(SESSION_UID_KEY, currentUser.uid);

        // Attach UID to the analytics session once per browser-session per login.
        if (!sessionStorage.getItem('vb:session_uid_sent')) {
          sessionStorage.setItem('vb:session_uid_sent', '1');
          getIdToken().then(function (token) {
            if (!token) return;
            fetch('/api/analytics/session', {
              method: 'POST',
              headers: { Authorization: 'Bearer ' + token },
            }).catch(function () {});
          });
          // Enrich session with the language the user is actually seeing.
          const language = new URLSearchParams(location.search).get('language') || '';
          const uiLang = new URLSearchParams(location.search).get('ui_language') || document.documentElement.lang || '';
          if (language || uiLang) {
            fetch('/api/analytics/enrich', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ language, ui_lang: uiLang }),
            }).catch(function () {});
          }
        }

        await hydrateProgress();
        await applyPreferences();
      } else {
        // Detect sign-out by checking whether we had a uid recorded.
        // This works across page navigations (sessionStorage persists within
        // the tab), unlike a JS variable which resets on each page load.
        var wasAuthenticated = !!sessionStorage.getItem(SESSION_UID_KEY);
        sessionStorage.removeItem(SESSION_UID_KEY);
        sessionStorage.removeItem('vb:session_uid_sent');

        if (wasAuthenticated) {
          // Clear all user-specific progress from localStorage across all
          // languages before notifying pages, so they re-render cleanly
          // even if the user navigated away from the page that had listeners.
          clearProgressLocalStorage();
          window.dispatchEvent(new CustomEvent('vb:auth-signed-out'));
        }
        // If wasAuthenticated is false the user was never logged in during
        // this tab session -- do not clear anonymous localStorage progress.
      }

      authReadyResolve();
    });
  }

  // Called directly from the bottom-nav Profile tab so the user's tap is the
  // trusted gesture -- programmatic .click() on the auth button loses isTrusted,
  // which causes window.open() to be blocked by popup blockers in standalone mode.
  async function tapProfile() {
    try {
      if (currentUser) {
        await signOut();
      } else {
        await signIn();
      }
    } catch (err) {
      if (err.code === 'auth/cancelled-popup-request') return;
      console.error('VB tapProfile error:', err);
      alert('Sign-in error: ' + (err.message || err.code || err));
    }
  }

  window.VerbBoardAuth = {
    ready: function () {
      return authReadyPromise;
    },

    signIn: signIn,
    signOut: signOut,
    tapProfile: tapProfile,

    getIdToken: getIdToken,

    currentUser: function () {
      return currentUser;
    },
  };

  initializeFirebase();
})();
