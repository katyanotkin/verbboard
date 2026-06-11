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
  const TOKEN_SPLIT_PATTERN = (function () {
    try {
      new RegExp("\\p{L}", "u");
      return /[^\p{L}\p{N}]+/u;
    } catch (error) {
      return /[^0-9a-zа-яё]+/i;
    }
  })();

  const searchInput = document.getElementById("search-input");
  const searchButton = document.getElementById("search-btn");
  const suggestionsBox = document.getElementById("search-suggestions");
  let blurHideTimer = null;

  function updatePrimaryAction() {
  }

  function getLanguage() {
    const languageSelect = document.querySelector('select[name="language"]');
    return languageSelect ? languageSelect.value : "";
  }

  function hideSuggestions() {
    if (blurHideTimer !== null) {
      window.clearTimeout(blurHideTimer);
      blurHideTimer = null;
    }
    if (!suggestionsBox) return;
    suggestionsBox.innerHTML = "";
    suggestionsBox.classList.remove("is-visible");
  }

  function normalizeText(text) {
    return text.trim().toLowerCase();
  }

  function scoreSuggestion(query, label) {
    const normalizedQuery = normalizeText(query);
    const normalizedLabel = normalizeText(label);

    if (!normalizedQuery || !normalizedLabel) return null;
    if (normalizedQuery === normalizedLabel) return 100;
    if (normalizedLabel.startsWith(normalizedQuery)) return 80;

    const tokens = normalizedLabel.split(TOKEN_SPLIT_PATTERN).filter(Boolean);
    if (tokens.includes(normalizedQuery)) return 70;
    if (tokens.some((token) => token.startsWith(normalizedQuery))) return 60;

    if (
      normalizedQuery.length >= 2 &&
      normalizedLabel.includes(normalizedQuery)
    ) {
      return 50;
    }

    return null;
  }

  function buildSuggestions(query) {
    const verbs = window.VB_VERBS || [];
    const ranked = [];
    for (const verb of verbs) {
      const score = scoreSuggestion(query, verb.label);
      if (score === null) continue;
      ranked.push({ id: verb.id, label: verb.label, score });
    }
    ranked.sort((left, right) => {
      if (left.score !== right.score) return right.score - left.score;
      return left.label.localeCompare(right.label);
    });
    return ranked.slice(0, 8);
  }

  function buildBrowseSuggestions() {
    return (window.VB_VERBS || []).slice(0, 8).map(function (verb) {
      return { id: verb.id, label: verb.label, score: 0 };
    });
  }

  function openVerb(verbId) {
    const language = getLanguage();
    const uiLang = new URLSearchParams(location.search).get('ui_language') || '';
    const uiParam = uiLang ? '&ui_language=' + encodeURIComponent(uiLang) : '';
    window.location = `/learn?language=${encodeURIComponent(language)}&verb_id=${encodeURIComponent(verbId)}${uiParam}`;
  }

  function renderSuggestions(query) {
    if (!suggestionsBox) return;

    if (blurHideTimer !== null) {
      window.clearTimeout(blurHideTimer);
      blurHideTimer = null;
    }

    const trimmedQuery = query.trim();
    let suggestions;

    if (!trimmedQuery) {
      if (document.activeElement !== searchInput) {
        hideSuggestions();
        return;
      }
      suggestions = buildBrowseSuggestions();
    } else {
      suggestions = buildSuggestions(trimmedQuery);
    }

    if (!suggestions.length) {
      hideSuggestions();
      return;
    }

    suggestionsBox.innerHTML = "";

    for (const suggestion of suggestions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "search-suggestion";

      const main = document.createElement("div");
      main.className = "search-suggestion-main";
      main.textContent = suggestion.label;
      button.appendChild(main);

      function pickSuggestion() {
        if (blurHideTimer !== null) {
          window.clearTimeout(blurHideTimer);
          blurHideTimer = null;
        }
        searchInput.value = suggestion.label;
        hideSuggestions();
        openVerb(suggestion.id);
      }

      button.addEventListener("mousedown", function (event) {
        event.preventDefault();
        pickSuggestion();
      });

      suggestionsBox.appendChild(button);
    }

    suggestionsBox.classList.add("is-visible");
  }

  if (searchInput) {
	searchInput.addEventListener("keydown", function (event) {
	  if (event.key !== "Enter") return;

	  const query = searchInput.value.trim();

	  // suggestions visible → take first
	  if (suggestionsBox && suggestionsBox.classList.contains("is-visible")) {
	    const first = suggestionsBox.querySelector(".search-suggestion");
	    if (first) {
	      event.preventDefault();
	      first.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
	      return;
	    }
	  }

	  // text exists → trigger search
	  if (query.length > 0) {
	    event.preventDefault();
	    searchButton.click();
	  }
	});

    searchInput.addEventListener("input", function () {
      updatePrimaryAction();
      renderSuggestions(searchInput.value);
    });

    searchInput.addEventListener("focus", function () {
      renderSuggestions(searchInput.value);
    });

    searchInput.addEventListener("blur", function () {
      blurHideTimer = window.setTimeout(function () {
        blurHideTimer = null;
        hideSuggestions();
      }, 200);
    });
  }

  updatePrimaryAction();

  // Search mode pill toggle
  const searchModePills = document.getElementById("search-mode-pills");
  const sourceLangInput = document.getElementById("source-lang-input");

  if (searchModePills && searchButton) {
    const nativePlaceholder = searchInput ? searchInput.placeholder : "";
    const enPlaceholder = searchInput ? (searchInput.dataset.placeholderEn || "") : "";

    function applyMode(mode) {
      searchModePills.querySelectorAll(".search-mode-pill").forEach(function (p) {
        p.classList.toggle("active", p.dataset.mode === mode);
      });
      if (sourceLangInput) {
        sourceLangInput.value = mode === "native" ? "" : mode;
      }
      searchButton.setAttribute("formaction", mode === "native" ? "/search_verb" : "/search_verb_by_lang");
      if (searchInput) {
        searchInput.placeholder = mode === "en" ? enPlaceholder : nativePlaceholder;
      }
    }

    const initialMode = sourceLangInput && sourceLangInput.value ? sourceLangInput.value : "native";
    applyMode(initialMode);

    searchModePills.querySelectorAll(".search-mode-pill").forEach(function (pill) {
      pill.addEventListener("click", function () {
        applyMode(pill.dataset.mode);
      });
    });
  }

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
          try {
            var chosenLang = new URL(a.href).searchParams.get('ui_language') || currentLang;
            localStorage.setItem(SEEN_KEY, chosenLang + '_m');
          } catch (_) {}
        });
      });
    }
  }());
});
