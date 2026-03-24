document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById('search-input');
  const searchButton = document.getElementById('search-btn');
  const learnButton = document.getElementById('learn-btn');
  const verbSelect = document.getElementById('verb-select');

  function updatePrimaryAction() {
    if (!searchInput || !searchButton || !learnButton) return;

    const hasText = searchInput.value.trim().length > 0;

    searchButton.classList.toggle('is-primary', hasText);
    learnButton.classList.toggle('is-primary', !hasText);
    learnButton.style.opacity = hasText ? '0.75' : '1';
  }

  function markSeenVerbs() {
    if (!verbSelect) return;

    const languageSelect = document.querySelector('select[name="language"]');
    if (!languageSelect) return;

    const language = languageSelect.value;
    const storageKey = `seen:${language}`;
    const seen = new Set(JSON.parse(localStorage.getItem(storageKey) || "[]"));

    for (const option of verbSelect.options) {
      const baseLabel = option.textContent.replace(/^✓\s+/, '');
      option.textContent = seen.has(option.value)
        ? `✓ ${baseLabel}`
        : baseLabel;
    }
  }

  if (searchInput) {
    searchInput.addEventListener('input', updatePrimaryAction);
  }

  updatePrimaryAction();
  markSeenVerbs();
});
