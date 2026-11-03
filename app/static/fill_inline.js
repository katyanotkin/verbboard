// In-place "Fill in the blank" mode on /learn. Rows with a usable example target carry
// data-fill-start/end/label/alts (core/render.py); this swaps the target word for an input,
// grades with VerbBoardFillGrade, then shows the sentence with the form in place and unlocks
// that row's audio (translations follow their own toggle). The mode lives in the URL only (?mode=fill).
(function () {
  'use strict';

  var page = document.getElementById('learn-page');
  var toggle = document.getElementById('fill-toggle');
  var banner = document.getElementById('fill-banner');
  var Grade = window.VerbBoardFillGrade;
  if (!page || !toggle || !Grade) return;

  var language = page.dataset.language;
  var ui = window.UI || {};
  var RECENT_LIMIT = 100;
  var rows = Array.prototype.slice.call(page.querySelectorAll('tr.fill-row'));
  if (!rows.length) return;

  var totals = { answers: 0, correct: 0 };
  var startedBeaconSent = false;
  var sentTotals = { answers: 0, correct: 0 };
  var cachedToken = '';
  var active = false;

  function t(key, vars) {
    var text = ui[key] || '';
    Object.keys(vars || {}).forEach(function (name) {
      text = text.split('{' + name + '}').join(String(vars[name]));
    });
    return text;
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  // One persistent polite live region: text set in a later tick so every answer is announced.
  var live = el('div', 'fill-sr-only');
  live.setAttribute('aria-live', 'polite');
  live.setAttribute('aria-atomic', 'true');
  document.body.appendChild(live);

  function announce(message) {
    live.textContent = '';
    setTimeout(function () {
      live.textContent = message;
    }, 50);
  }

  // ---- per-row model -----------------------------------------------------
  function parseRow(row) {
    var source = row.querySelector('.example-src');
    var text = source ? source.textContent : '';
    // Offsets are code points (Python); JS strings are UTF-16.
    var points = Array.from(text);
    var start = parseInt(row.dataset.fillStart, 10);
    var end = parseInt(row.dataset.fillEnd, 10);
    var alts = [];
    try {
      var parsed = JSON.parse(row.dataset.fillAlts || '[]');
      if (Array.isArray(parsed)) alts = parsed;
    } catch (_) {}
    var valid = start >= 0 && end > start && end <= points.length;
    return {
      row: row,
      source: source,
      text: text,
      valid: valid,
      prefix: valid ? points.slice(0, start).join('') : '',
      answer: valid ? points.slice(start, end).join('') : '',
      suffix: valid ? points.slice(end).join('') : '',
      alts: alts,
      label: row.dataset.fillLabel || '',
      lemma: row.dataset.fillLemma || '',
      index: parseInt(row.dataset.fillIndex, 10) || 0,
      audioCell: row.querySelector('td:last-child'),
      state: '',
      typed: '',
      shown: false,
    };
  }

  var models = rows.map(parseRow).filter(function (m) {
    return m.valid && m.source;
  });
  if (!models.length) return;

  function clearExtras(model) {
    var cell = model.source.parentNode;
    Array.prototype.slice.call(cell.querySelectorAll('.fill-controls, .fill-feedback')).forEach(function (n) {
      n.remove();
    });
  }

  function showPlain(model) {
    clearExtras(model);
    model.source.textContent = model.text;
  }

  function insertAfterSource(model, node) {
    model.source.parentNode.insertBefore(node, model.source.nextSibling);
  }

  // ---- answered view -----------------------------------------------------
  function showAnswered(model) {
    clearExtras(model);
    var state = model.state === 'wrong' ? 'wrong' : model.state;
    model.source.textContent = '';
    model.source.appendChild(document.createTextNode(model.prefix));
    model.source.appendChild(el('mark', 'fill-answer fill-answer--' + state, model.answer));
    model.source.appendChild(document.createTextNode(model.suffix));

    var feedback = el('span', 'fill-feedback fill-feedback--' + state);
    feedback.tabIndex = -1;
    if (state === 'correct') {
      feedback.textContent = t('fill.correct');
    } else if (state === 'accent') {
      feedback.textContent = t('fill.correct_accent', { answer: model.answer });
    } else {
      if (model.typed) {
        feedback.appendChild(el('s', '', model.typed));
        feedback.appendChild(document.createTextNode(' · '));
      }
      feedback.appendChild(document.createTextNode(t('fill.answer_is', { answer: model.answer })));
    }
    insertAfterSource(model, feedback);
    model.feedback = feedback;
    announce(feedback.textContent);
  }

  // ---- unanswered view ---------------------------------------------------
  function showBlank(model) {
    clearExtras(model);
    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'fill-inline-input';
    input.setAttribute('autocapitalize', 'off');
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('autocorrect', 'off');
    input.spellcheck = false;
    input.lang = language;
    input.dir = language === 'he' ? 'rtl' : 'ltr';
    input.setAttribute('aria-label', [model.lemma, model.label].filter(Boolean).join(' · '));
    input.style.inlineSize = Math.max(6, Array.from(model.answer).length + 2) + 'ch';

    var slot = el('span', 'fill-slot');
    slot.appendChild(input);
    model.source.textContent = '';
    model.source.appendChild(document.createTextNode(model.prefix));
    model.source.appendChild(slot);
    model.source.appendChild(document.createTextNode(model.suffix));

    var controls = el('div', 'fill-controls');
    if (model.label) controls.appendChild(el('span', 'fill-chip', model.label));
    var check = el('button', 'btn-secondary fill-check-btn', t('board.fill_check'));
    check.type = 'button';
    var showLink = el('button', 'fill-show-link', t('board.fill_show'));
    showLink.type = 'button';
    controls.appendChild(check);
    controls.appendChild(showLink);
    insertAfterSource(model, controls);

    function submit() {
      var typed = input.value;
      var result = Grade.grade(language, typed, model.answer, model.alts);
      if (result === 'empty') {
        input.focus();
        return;
      }
      finish(model, result, typed);
    }
    check.addEventListener('click', submit);
    showLink.addEventListener('click', function () {
      finish(model, 'wrong', '');
    });
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' && !event.isComposing) {
        event.preventDefault();
        submit();
      }
    });
  }

  function render(model) {
    // Unanswered rows' audio is locked in fill mode: not just dimmed, also out of the tab order.
    if (model.audioCell) model.audioCell.inert = active && !model.state;
    if (!active) {
      showPlain(model);
    } else if (model.state) {
      showAnswered(model);
    } else {
      showBlank(model);
    }
  }

  // ---- results, storage, beacons -------------------------------------------
  function recordRecent(model, ok) {
    var Storage = window.VerbBoardStorage;
    if (!Storage) return;
    try {
      var verbId = page.dataset.verbId;
      var recent = Storage.readJson('fill_recent:' + language, []);
      if (!Array.isArray(recent)) recent = [];
      // Same id shape as /practice/fill items: "{verb_id}:{1-based example index}".
      recent.push({ id: verbId + ':' + model.index, ok: !!ok, ts: Date.now() });
      Storage.writeJson('fill_recent:' + language, recent.slice(-RECENT_LIMIT));
    } catch (_) {}
  }

  function trackStarted() {
    if (startedBeaconSent) return;
    startedBeaconSent = true;
    try {
      fetch('/api/analytics/practice_event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event: 'fill_started' }),
        keepalive: true,
      }).catch(function () {});
    } catch (_) {}
  }

  function finish(model, result, typed) {
    if (model.state) return;
    var ok = result === 'correct' || result === 'accent';
    model.state = result;
    model.typed = typed;
    model.row.classList.add('fill-answered');
    totals.answers += 1;
    if (ok) totals.correct += 1;
    recordRecent(model, ok);
    trackStarted();
    if (model.audioCell) model.audioCell.inert = false;
    showAnswered(model);
    var next = page.querySelector('.fill-row:not(.fill-answered) .fill-inline-input');
    if (next) next.focus({ preventScroll: true });
    else if (model.feedback) model.feedback.focus({ preventScroll: true });
  }

  function auth() {
    return window.VerbBoardAuth || null;
  }

  function refreshToken() {
    var a = auth();
    if (!a || !a.ready || !a.getIdToken) return;
    Promise.resolve(a.ready())
      .then(function () {
        if (!a.currentUser()) return null;
        return a.getIdToken();
      })
      .then(function (token) {
        if (token) cachedToken = token;
      })
      .catch(function () {});
  }

  // On pagehide / tab hidden: send the answers not yet reported (counters are additive, so a later
  // send only carries what was typed since). Totals are marked sent only once a POST is issued.
  // Hidden-tab sends are spaced out so toggling tabs cannot burn the server's rate limit.
  var MIN_HIDDEN_POST_GAP_MS = 30000;
  var lastPostAt = 0;
  var inFlight = false;

  function sendSession(reason) {
    var a = auth();
    var answers = totals.answers - sentTotals.answers;
    var correct = totals.correct - sentTotals.correct;
    if (inFlight || answers < 1 || !a || !a.currentUser || !a.currentUser()) return;
    if (reason !== 'pagehide' && Date.now() - lastPostAt < MIN_HIDDEN_POST_GAP_MS) return;
    var body = JSON.stringify({
      language: language,
      answers: answers,
      correct: correct,
      completed: false,
      mode: 'inline',
    });
    function post(token) {
      inFlight = false;
      if (!token) return;
      sentTotals = { answers: sentTotals.answers + answers, correct: sentTotals.correct + correct };
      lastPostAt = Date.now();
      try {
        fetch('/api/progress/fill_session', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
          body: body,
          keepalive: true,
        }).catch(function () {});
      } catch (_) {}
    }
    if (reason !== 'pagehide' && a.getIdToken) {
      inFlight = true;
      Promise.resolve(a.getIdToken())
        .then(function (token) {
          post(token || cachedToken);
        })
        .catch(function () {
          post(cachedToken);
        });
    } else {
      post(cachedToken);
    }
  }

  // ---- mode switch -----------------------------------------------------------
  function syncVoiceForm() {
    var form = page.querySelector('form.voice-control');
    if (!form) return;
    var existing = form.querySelector('input[name="mode"]');
    if (active && !existing) {
      var hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = 'mode';
      hidden.value = 'fill';
      form.appendChild(hidden);
    } else if (!active && existing) {
      existing.remove();
    }
  }

  function setActive(next, updateUrl) {
    active = next;
    page.classList.toggle('fill-mode', active);
    toggle.setAttribute('aria-pressed', active ? 'true' : 'false');
    if (banner) banner.hidden = !active;
    models.forEach(render);
    syncVoiceForm();
    if (updateUrl) {
      try {
        var url = new URL(window.location.href);
        if (active) url.searchParams.set('mode', 'fill');
        else url.searchParams.delete('mode');
        window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
      } catch (_) {}
    }
    if (active) {
      var first = page.querySelector('.fill-row:not(.fill-answered) .fill-inline-input');
      if (first && updateUrl) first.focus({ preventScroll: true });
    }
  }

  toggle.hidden = false;
  var toggleWrap = document.getElementById('fill-toggle-wrap');
  if (toggleWrap) toggleWrap.hidden = false;
  toggle.addEventListener('click', function () {
    setActive(!active, true);
  });

  window.addEventListener('pagehide', function () {
    sendSession('pagehide');
  });
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') sendSession('hidden');
  });
  refreshToken();
  window.addEventListener('vb:progress-hydrated', refreshToken);
  setInterval(refreshToken, 50 * 60 * 1000);

  var wantsFill = false;
  try {
    wantsFill = new URLSearchParams(window.location.search).get('mode') === 'fill';
  } catch (_) {}
  if (wantsFill) setActive(true, false);
})();
