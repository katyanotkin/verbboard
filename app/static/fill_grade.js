// Pure grading for the "fill the form" drill. No DOM access.
// grade() returns 'correct' | 'accent' | 'wrong' | 'empty'; 'correct' and
// 'accent' both score as right, 'accent' means the typed text only matched
// after ignoring accents/diacritics, so the page shows the exact answer.
(function () {
  'use strict';

  var root = typeof window !== 'undefined' ? window : globalThis;

  var FRENCH_PRONOUN = /^(?:(?:je|tu|il|elle|on|nous|vous|ils|elles) +|j')(?=\S)/;
  var LATIN_ACCENT_FOLD_EXCLUDED = { ru: true, he: true };

  function lowerCase(language, text) {
    if (language === 'tr') {
      text = text.replace(/I/g, 'ı').replace(/İ/g, 'i');
    }
    return text.toLowerCase();
  }

  function normalize(language, text) {
    var s = String(text == null ? '' : text).normalize('NFC');
    s = s.replace(/[’‘ʼ]/g, "'");
    s = s.replace(/\s+/g, ' ').trim();
    s = lowerCase(language, s);
    if (language === 'he') {
      s = s.replace(/[֑-ׇ]/g, '');
    } else if (language === 'ru') {
      s = s.replace(/ё/g, 'е').replace(/́/g, '');
    }
    return s.normalize('NFC');
  }

  function foldAccents(language, normalized) {
    if (LATIN_ACCENT_FOLD_EXCLUDED[language]) return normalized;
    var s = normalized.normalize('NFD').replace(/[̀-ͯ]/g, '');
    return s.replace(/ı/g, 'i').normalize('NFC');
  }

  function splitAnswers(answer, alternatives) {
    var out = [];
    [answer].concat(alternatives || []).forEach(function (entry) {
      String(entry == null ? '' : entry).split('/').forEach(function (part) {
        if (part.trim()) out.push(part);
      });
    });
    return out;
  }

  function typedVariants(language, typedNormalized) {
    var variants = [typedNormalized];
    if (language === 'fr') {
      var stripped = typedNormalized.replace(FRENCH_PRONOUN, '');
      if (stripped && stripped !== typedNormalized) variants.push(stripped);
    }
    return variants;
  }

  function grade(language, typed, answer, alternatives) {
    var typedNormalized = normalize(language, typed);
    if (!typedNormalized) return 'empty';

    var accepted = splitAnswers(answer, alternatives).map(function (a) {
      return normalize(language, a);
    });
    var variants = typedVariants(language, typedNormalized);

    for (var i = 0; i < variants.length; i += 1) {
      if (accepted.indexOf(variants[i]) !== -1) return 'correct';
    }

    var foldedAccepted = accepted.map(function (a) {
      return foldAccents(language, a);
    });
    for (var j = 0; j < variants.length; j += 1) {
      if (foldedAccepted.indexOf(foldAccents(language, variants[j])) !== -1) return 'accent';
    }
    return 'wrong';
  }

  var api = { normalize: normalize, grade: grade };
  root.VerbBoardFillGrade = api;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})();
