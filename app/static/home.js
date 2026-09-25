// Persist the studied language across bare '/' visits.
// Firebase Hosting strips all cookies except __session, so the server can't
// read the language cookie on a bare '/' request.  We keep the preference in
// localStorage (readable by JS regardless of Hosting) and redirect before the
// page is shown so the server receives the correct ?language= param.
(function () {
  var params = new URLSearchParams(location.search);
  var lang = params.get('language');
  if (lang) {
    try { localStorage.setItem('vb_language', lang); } catch (e) {}
    return;
  }
  var stored;
  try { stored = localStorage.getItem('vb_language'); } catch (e) {}
  if (stored) {
    params.set('language', stored);
    location.replace('/?' + params);
  }
}());

document.addEventListener("DOMContentLoaded", function () {
  // Fire-and-forget Verb of the Day click beacon. keepalive: the click
  // navigates away immediately, and a plain in-flight fetch can be cancelled
  // by the unload. Must never block or fail the navigation itself.
  const votdHero = document.querySelector(".votd-hero");
  if (votdHero) {
    votdHero.addEventListener("click", function () {
      try {
        fetch("/api/analytics/votd_clicked", { method: "POST", keepalive: true }).catch(function () {});
      } catch (_) {}
    });
  }

  function getLanguage() {
    const languageSelect = document.querySelector('select[name="language"]');
    return languageSelect ? languageSelect.value : "";
  }

  function getUiLang() {
    return new URLSearchParams(location.search).get('ui_language') || document.documentElement.lang || '';
  }

  function reportLanguageChoice() {
    const language = getLanguage();
    const uiLang = getUiLang();
    if (!language && !uiLang) return;
    fetch('/api/analytics/enrich', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ language, ui_lang: uiLang }),
    }).catch(function () {});
  }

  // Analytics: report language choice on intentional actions.
  const languageSelect = document.querySelector('select[name="language"]');
  if (languageSelect) {
    languageSelect.addEventListener('change', reportLanguageChoice);
  }
  ['browse-btn'].forEach(function (id) {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', reportLanguageChoice);
  });
  document.querySelectorAll('.browse-practice-btn').forEach(function (el) {
    el.addEventListener('click', reportLanguageChoice);
  });

  // UI language dropdown
  const uiLangMenu = document.getElementById('ui-lang-menu');
  const uiLangTrigger = document.getElementById('ui-lang-trigger');
  const uiLangDropdown = document.getElementById('ui-lang-dropdown');
  if (uiLangTrigger && uiLangDropdown) {
    uiLangTrigger.addEventListener('click', function (e) {
      e.stopPropagation();
      uiLangTrigger.classList.remove('ui-lang-trigger--highlight');
      const opening = uiLangDropdown.hidden;
      uiLangDropdown.hidden = !opening;
      uiLangTrigger.setAttribute('aria-expanded', String(opening));
    });
    document.addEventListener('click', function (e) {
      if (uiLangMenu && uiLangMenu.contains(e.target)) return;
      uiLangDropdown.hidden = true;
      uiLangTrigger.setAttribute('aria-expanded', 'false');
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !uiLangDropdown.hidden) {
        uiLangDropdown.hidden = true;
        uiLangTrigger.setAttribute('aria-expanded', 'false');
        uiLangTrigger.focus();
      }
    });
  }

  // Highlight globe trigger when browser language differs from the served UI language.
  // After acknowledging (× or picking a language) it stays quiet.
  (function () {
    var SEEN_KEY = 'vb_ui_lang_seen';
    var currentLang = document.documentElement.lang || '';
    var rawBrowser = (navigator.language || '').slice(0, 2).toLowerCase();
    var NORM = { iw: 'he' };
    var browserLang = NORM[rawBrowser] || rawBrowser;

    var seenLang = localStorage.getItem(SEEN_KEY);
    var hasMismatch = !!(browserLang && browserLang !== currentLang);
    // Prompt once for new users (no flag yet) and whenever there's a mismatch
    var shouldHighlight = (!seenLang || hasMismatch) && seenLang !== currentLang + '_m';

    function clearHighlight() {
      if (uiLangTrigger) uiLangTrigger.classList.remove('ui-lang-trigger--highlight');
      localStorage.setItem(SEEN_KEY, currentLang + '_m');
    }

    if (shouldHighlight && uiLangTrigger) {
      // Suppress for logged-in users -- they already chose their language
      var auth = window.VerbBoardAuth;
      if (auth) {
        auth.ready().then(function () {
          if (auth.currentUser()) return;
          uiLangTrigger.classList.add('ui-lang-trigger--highlight');
        });
      } else {
        uiLangTrigger.classList.add('ui-lang-trigger--highlight');
      }
    }

    // × button: dismiss and don't show again for this UI lang
    var hintClose = document.getElementById('ui-lang-hint-close');
    if (hintClose) {
      hintClose.addEventListener('click', function (e) {
        e.stopPropagation();
        clearHighlight();
      });
    }

    // Pre-flag before navigating to a chosen language so the new page stays quiet
    if (uiLangDropdown) {
      uiLangDropdown.querySelectorAll('.ui-lang-option').forEach(function (a) {
        a.addEventListener('click', function () {
          var chosenLang = currentLang;
          try {
            chosenLang = new URL(a.href).searchParams.get('ui_language') || currentLang;
          } catch (_) {}
          // Count deliberate UI-language picks (issue #60); keepalive because the
          // click navigates away immediately. Sent before the localStorage write
          // so a storage failure (private mode) can't suppress it.
          try {
            fetch('/api/analytics/ui_lang_selected', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ ui_lang: chosenLang }),
              keepalive: true,
            }).catch(function () {});
          } catch (_) {}
          try {
            localStorage.setItem(SEEN_KEY, chosenLang + '_m');
          } catch (_) {}
        });
      });
    }
  }());
});
