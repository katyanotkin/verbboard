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
  const learnButton = document.getElementById("learn-btn");
  const verbSelect = document.getElementById("verb-select");
  const suggestionsBox = document.getElementById("search-suggestions");
  let blurHideTimer = null;

  function updatePrimaryAction() {
    if (!searchInput || !searchButton || !learnButton) return;

    const hasText = searchInput.value.trim().length > 0;

    searchButton.classList.toggle("is-primary", hasText);
    learnButton.classList.toggle("is-primary", !hasText);
    learnButton.style.opacity = hasText ? "0.75" : "1";
  }

  function getLanguage() {
    const languageSelect = document.querySelector('select[name="language"]');
    return languageSelect ? languageSelect.value : "";
  }

  function readSet(storageKey) {
    return new Set(JSON.parse(localStorage.getItem(storageKey) || "[]"));
  }

  function sortAndMarkVerbs() {
    if (!verbSelect) return;

    const language = getLanguage();
    if (!language) return;

    const seen = readSet(`seen:${language}`);
    const known = readSet(`known:${language}`);
    const selectedValue = verbSelect.value;

    const options = Array.from(verbSelect.options).map((option, originalIndex) => {
      const baseLabel = option.textContent.replace(/^[✓★]\s+/, "");
      const isKnown = known.has(option.value);
      const isSeen = !isKnown && seen.has(option.value);

      let group = 0; // unseen
      if (isSeen) group = 1;
      if (isKnown) group = 2;

      return {
        value: option.value,
        baseLabel,
        group,
        selected: option.value === selectedValue,
        originalIndex,
      };
    });

    options.sort((left, right) => {
      if (left.group !== right.group) {
        return left.group - right.group;
      }
      return left.originalIndex - right.originalIndex;
    });

    verbSelect.innerHTML = "";

    for (const optionData of options) {
      const option = document.createElement("option");
      option.value = optionData.value;

      let prefix = "";
      if (optionData.group === 1) {
        prefix = "✓ ";
      } else if (optionData.group === 2) {
        prefix = "★ ";
      }

      option.textContent = `${prefix}${optionData.baseLabel}`;
      option.selected = optionData.selected;
      verbSelect.appendChild(option);
    }
  }

  function updateProgress() {
    if (!verbSelect) return;

    const options = Array.from(verbSelect.options);
    const total = options.length;

    const count = options.filter((option) =>
      option.textContent.startsWith("★ ")
    ).length;

    const percent = total > 0 ? (count / total) * 100 : 0;

    const fill = document.querySelector(".progress-fill");
    const countEl = document.querySelector(".progress-count");

    if (fill) {
      fill.style.width = `${percent}%`;
    }

    if (countEl) {
      countEl.textContent = String(count).padStart(3, "0");
    }
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

  /** Verb dropdown labels only (infinitive / display lemma). */
  function buildSuggestions(query) {
    if (!verbSelect) return [];

    const options = Array.from(verbSelect.options);
    const ranked = [];

    for (const option of options) {
      const cleanLabel = option.textContent.replace(/^[✓★]\s+/, "");
      const score = scoreSuggestion(query, cleanLabel);
      if (score === null) continue;

      ranked.push({
        id: option.value,
        label: cleanLabel,
        score,
      });
    }

    ranked.sort((left, right) => {
      if (left.score !== right.score) {
        return right.score - left.score;
      }
      return left.label.localeCompare(right.label);
    });

    return ranked.slice(0, 8);
  }

  function buildBrowseSuggestions() {
    if (!verbSelect) return [];

    const options = Array.from(verbSelect.options).slice(0, 8);
    return options.map(function (option) {
      return {
        id: option.value,
        label: option.textContent.replace(/^[✓★]\s+/, ""),
        score: 0,
      };
    });
  }

  function openVerb(verbId) {
    const language = getLanguage();
    const voiceSelect = document.querySelector('select[name="voice"]');
    const voice = voiceSelect ? voiceSelect.value : "female";

    window.location = `/learn?language=${encodeURIComponent(language)}&verb_id=${encodeURIComponent(verbId)}&voice=${encodeURIComponent(voice)}`;
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
  sortAndMarkVerbs();
  updateProgress();
});
