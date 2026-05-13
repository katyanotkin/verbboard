(function () {
  function readSet(storageKey) {
    try {
      return new Set(JSON.parse(localStorage.getItem(storageKey) || "[]"));
    } catch (_) {
      return new Set();
    }
  }

  function writeSet(storageKey, valueSet) {
    localStorage.setItem(storageKey, JSON.stringify(Array.from(valueSet)));
  }

  function storageKeys(language) {
    return {
      seenKey: `seen:${language}`,
      knownKey: `known:${language}`,
    };
  }

  async function apiPost(path, payload) {
    if (!window.VerbBoardAuth || !window.VerbBoardAuth.getIdToken) {
      return false;
    }

    const token = await window.VerbBoardAuth.getIdToken();
    if (!token) return false;

    const response = await fetch(path, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    return response.ok;
  }

  async function markSeen(language, verbId) {
    const keys = storageKeys(language);
    const seen = readSet(keys.seenKey);

    if (!seen.has(verbId)) {
      seen.add(verbId);
      writeSet(keys.seenKey, seen);
    }

    await apiPost("/api/progress/seen", {
      language: language,
      verb_id: verbId,
    });
  }

  async function setKnown(language, verbId, known) {
    const keys = storageKeys(language);
    const knownSet = readSet(keys.knownKey);

    if (known) {
      knownSet.add(verbId);
    } else {
      knownSet.delete(verbId);
    }

    writeSet(keys.knownKey, knownSet);

    await apiPost("/api/progress/known", {
      language: language,
      verb_id: verbId,
      known: known,
    });
  }

  function isKnown(language, verbId) {
    const keys = storageKeys(language);
    return readSet(keys.knownKey).has(verbId);
  }

  window.VerbBoardProgress = {
    readSet: readSet,
    writeSet: writeSet,
    markSeen: markSeen,
    setKnown: setKnown,
    isKnown: isKnown,
  };
})();
