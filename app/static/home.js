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
    if (!searchInput || !searchButton) return;
    const hasText = searchInput.value.trim().length > 0;
    searchButton.classList.toggle("is-primary", hasText);
    searchButton.disabled = !hasText;
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

    window.location = `/learn?language=${encodeURIComponent(language)}&verb_id=${encodeURIComponent(verbId)}`;
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
});
