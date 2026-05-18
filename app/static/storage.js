'use strict';

(function () {
  function readJson(key, fallback) {
    try {
      return JSON.parse(
        localStorage.getItem(key) || JSON.stringify(fallback)
      );
    } catch (_) {
      return fallback;
    }
  }

  function writeJson(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  function readSet(key) {
    return new Set(readJson(key, []));
  }

  function writeSet(key, setValue) {
    writeJson(key, Array.from(setValue));
  }

  window.VerbBoardStorage = {
    readJson,
    writeJson,
    readSet,
    writeSet,
  };
})();
