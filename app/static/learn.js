document.addEventListener("DOMContentLoaded", function () {
  const knownButton = document.getElementById("known-btn");
  const pageRoot = document.getElementById("learn-page");

  if (!knownButton || !pageRoot) return;

  const language = pageRoot.dataset.language;
  const verbId = pageRoot.dataset.verbId;

  if (!language || !verbId) return;

  const seenKey = `seen:${language}`;
  const knownKey = `known:${language}`;

  function readSet(storageKey) {
    return new Set(JSON.parse(localStorage.getItem(storageKey) || "[]"));
  }

  function writeSet(storageKey, valueSet) {
    localStorage.setItem(storageKey, JSON.stringify(Array.from(valueSet)));
  }

  function markSeen() {
    const seen = readSet(seenKey);
    if (!seen.has(verbId)) {
      seen.add(verbId);
      writeSet(seenKey, seen);
    }
  }

  function updateKnownButton(shouldPop = false) {
	  const known = readSet(knownKey);
	  const isKnown = known.has(verbId);

	  knownButton.classList.toggle("is-active", isKnown);
	  knownButton.setAttribute("aria-pressed", isKnown ? "true" : "false");
	  knownButton.title = isKnown ? "Known" : "Mark as known";

	  if (shouldPop && isKnown) {
	    knownButton.classList.remove("pop");
	    void knownButton.offsetWidth;
	    knownButton.classList.add("pop");
	  }
	}

  function toggleKnown() {
    const known = readSet(knownKey);

    if (known.has(verbId)) {
      known.delete(verbId);
    } else {
      known.add(verbId);
    }

    writeSet(knownKey, known);
    markSeen();
    updateKnownButton(true);
  }

  knownButton.addEventListener("click", function (event) {
    event.preventDefault();
    toggleKnown();
  });

  markSeen();
  updateKnownButton();
});
