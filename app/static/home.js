document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("search-input");
  const searchButton = document.getElementById("search-btn");
  const learnButton = document.getElementById("learn-btn");
  const verbSelect = document.getElementById("verb-select");

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
	    countEl.textContent = String(count).padStart(3,"0");
	  }
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

  if (searchInput) {
    searchInput.addEventListener("input", updatePrimaryAction);
  }

  updatePrimaryAction();
  sortAndMarkVerbs();
  updateProgress();
});
