// "Fill the form" practice page. Strings come only from data.strings (server
// resolved), grading from fill_grade.js. Nothing is stored server-side for
// anonymous users; signed-in users post one summary when a round ends.
(function () {
  'use strict';

  var RECENT_LIMIT = 100;
  var KNOWN_SEEN_MIN = 5;
  var COMPLETED_MIN_ANSWERS = 5;
  var NEXT_TAP_GUARD_MS = 350;

  function shuffled(list) {
    var copy = list.slice();
    for (var i = copy.length - 1; i > 0; i -= 1) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = copy[i];
      copy[i] = copy[j];
      copy[j] = tmp;
    }
    return copy;
  }

  // Items answered correctly most recently go last; never-seen and recently
  // missed items go first. One item per verb before any verb repeats.
  function drawSession(items, recent, size) {
    var lastById = {};
    (recent || []).forEach(function (entry) {
      if (!entry || !entry.id) return;
      var previous = lastById[entry.id];
      if (!previous || entry.ts >= previous.ts) lastById[entry.id] = entry;
    });
    function rank(item) {
      var entry = lastById[item.id];
      return entry && entry.ok ? entry.ts || 1 : 0;
    }
    var ordered = shuffled(items).sort(function (a, b) {
      return rank(a) - rank(b);
    });
    var picked = [];
    var usedVerbs = {};
    var leftovers = [];
    ordered.forEach(function (item) {
      if (picked.length < size && !usedVerbs[item.verbId]) {
        usedVerbs[item.verbId] = true;
        picked.push(item);
      } else {
        leftovers.push(item);
      }
    });
    leftovers.forEach(function (item) {
      if (picked.length < size) picked.push(item);
    });
    return shuffled(picked);
  }

  function init() {
    var dataEl = document.getElementById('fill-data');
    var card = document.getElementById('fill-card');
    if (!dataEl || !card) return;

    var data;
    try {
      data = JSON.parse(dataEl.textContent);
    } catch (_) {
      return;
    }

    var Grade = window.VerbBoardFillGrade;
    var Storage = window.VerbBoardStorage;
    var language = data.language;
    var strings = data.strings || {};
    var allItems = data.items || [];
    var sessionSize = (data.limits && data.limits.sessionSize) || 8;
    var recentKey = 'fill_recent:' + language;
    var backHref =
      document.getElementById('fill-app').dataset.backHref ||
      (window.VerbBoardNav ? window.VerbBoardNav.verbsUrl(language) : '/');
    var coarsePointer = !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);

    var progressWrap = document.getElementById('fill-progress');
    var progressFill = document.getElementById('fill-progress-fill');
    var progressText = document.getElementById('fill-progress-text');
    var progressBar = progressWrap.querySelector('[role="progressbar"]');
    var poolWrap = document.getElementById('fill-pool');

    var state = {
      pool: 'all',
      session: [],
      index: 0,
      answers: 0,
      correct: 0,
      missed: [],
      answered: false,
      answeredAt: 0,
      hintStage: 0,
      sent: false,
    };
    var startedBeaconSent = false;
    var cachedToken = null;
    var currentAudio = null;

    function t(key, vars) {
      var text = strings['fill.' + key] || '';
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

    function readRecent() {
      var value = Storage ? Storage.readJson(recentKey, []) : [];
      return Array.isArray(value) ? value : [];
    }

    function recordResult(item, ok) {
      var recent = readRecent();
      recent.push({ id: item.id, ok: !!ok, ts: Date.now() });
      try {
        Storage.writeJson(recentKey, recent.slice(-RECENT_LIMIT));
      } catch (_) {}
    }

    function knownSeenIds() {
      var ids = new Set();
      if (!Storage) return ids;
      ['known:', 'seen:'].forEach(function (prefix) {
        Storage.readSet(prefix + language).forEach(function (id) {
          ids.add(id);
        });
      });
      return ids;
    }

    var knownSeen = knownSeenIds();
    var knownItems = allItems.filter(function (item) {
      return knownSeen.has(item.verbId);
    });

    function poolItems() {
      return state.pool === 'known' ? knownItems : allItems;
    }

    function defaultPool() {
      if (data.verbId) return 'all';
      return knownSeen.size >= KNOWN_SEEN_MIN && knownItems.length >= sessionSize ? 'known' : 'all';
    }

    // ---- server sync (signed-in only) -----------------------------------
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

    // Runs synchronously on pagehide (no await before fetch) so keepalive can
    // still fire; other reasons may await a fresh token first.
    async function sendSession(reason) {
      var a = auth();
      if (state.sent || state.answers < 1 || !a || !a.currentUser || !a.currentUser()) return;
      state.sent = true;
      var body = JSON.stringify({
        language: language,
        answers: state.answers,
        correct: state.correct,
        completed: state.answers >= COMPLETED_MIN_ANSWERS,
      });
      var token = cachedToken;
      if (reason !== 'pagehide' && a.getIdToken) {
        try {
          token = (await a.getIdToken()) || token;
        } catch (_) {}
      }
      if (!token) return;
      try {
        fetch('/api/progress/fill_session', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
          body: body,
          keepalive: true,
        }).catch(function () {});
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

    // ---- rendering --------------------------------------------------------
    function stopAudio() {
      if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
      }
    }

    function setProgress(done) {
      var total = state.session.length;
      progressWrap.hidden = false;
      progressFill.style.inlineSize = (total ? (done / total) * 100 : 0) + '%';
      progressBar.setAttribute('aria-valuemax', String(total));
      progressBar.setAttribute('aria-valuenow', String(done));
      progressText.textContent = t('progress', { n: Math.min(done + 1, total), total: total });
    }

    function primaryLabel() {
      if (!state.answered) return t('check');
      return state.index >= state.session.length - 1 ? t('finish') : t('next');
    }

    function renderQuestion() {
      stopAudio();
      var item = state.session[state.index];
      state.answered = false;
      state.hintStage = 0;
      setProgress(state.index);
      card.textContent = '';
      card.className = 'fill-card';

      var sentence = el('p', 'fill-sentence');
      sentence.dir = data.studyDir || 'ltr';
      sentence.lang = language;
      var blank = el('span', 'fill-blank');
      blank.appendChild(el('span', 'fill-sr-only', t('blank_label')));
      sentence.appendChild(document.createTextNode(item.prefix || ''));
      sentence.appendChild(blank);
      sentence.appendChild(document.createTextNode(item.suffix || ''));

      var meta = el('p', 'fill-meta');
      var lemma = el('strong', 'fill-lemma', item.lemma);
      lemma.dir = 'auto';
      lemma.lang = language;
      meta.appendChild(lemma);
      meta.appendChild(el('span', 'fill-label', item.label));

      var input = el('input', 'fill-input');
      input.type = 'text';
      input.id = 'fill-input';
      input.dir = 'auto';
      input.lang = language;
      input.autocomplete = 'off';
      input.spellcheck = false;
      input.placeholder = t('placeholder');
      input.setAttribute('autocapitalize', 'off');
      input.setAttribute('autocorrect', 'off');
      input.setAttribute('enterkeyhint', 'done');
      input.setAttribute('aria-label', t('blank_label'));

      var hintLine = el('p', 'fill-hint-line');
      hintLine.setAttribute('aria-live', 'polite');

      var actions = el('div', 'fill-actions');
      var hintBtn = el('button', 'fill-btn fill-btn--secondary', t('hint'));
      hintBtn.type = 'button';
      var primaryBtn = el('button', 'fill-btn fill-btn--primary', t('check'));
      primaryBtn.type = 'button';
      primaryBtn.id = 'fill-primary';
      actions.appendChild(hintBtn);
      actions.appendChild(primaryBtn);

      var feedback = el('div', 'fill-feedback');
      feedback.id = 'fill-feedback';
      feedback.setAttribute('role', 'status');
      feedback.setAttribute('aria-live', 'polite');

      var reveal = el('div', 'fill-reveal');
      reveal.hidden = true;

      card.appendChild(sentence);
      card.appendChild(meta);
      card.appendChild(input);
      card.appendChild(hintLine);
      card.appendChild(actions);
      card.appendChild(feedback);
      card.appendChild(reveal);

      var ctx = {
        item: item,
        blank: blank,
        input: input,
        hintLine: hintLine,
        hintBtn: hintBtn,
        primaryBtn: primaryBtn,
        feedback: feedback,
        reveal: reveal,
      };

      hintBtn.addEventListener('click', function () {
        if (state.answered) return;
        if (state.hintStage === 0) {
          var firstPart = String(item.answer).split('/')[0].trim();
          var letter = Array.from(firstPart)[0] || '';
          hintLine.textContent = t('hint_first', { letter: letter });
          hintLine.dir = 'auto';
          state.hintStage = 1;
          hintBtn.textContent = t('show_answer');
          input.focus();
        } else {
          finishQuestion(ctx, 'revealed', '');
        }
      });

      primaryBtn.addEventListener('click', function (event) {
        if (state.answered) {
          if (event.detail > 0 && Date.now() - state.answeredAt < NEXT_TAP_GUARD_MS) return;
          advance();
        } else {
          submit(ctx);
        }
      });

      input.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' || event.isComposing) return;
        event.preventDefault();
        if (state.answered) advance();
        else submit(ctx);
      });

      trackStarted();
      if (!coarsePointer || state.index > 0) input.focus();
    }

    function submit(ctx) {
      var typed = ctx.input.value;
      var outcome = Grade.grade(language, typed, ctx.item.answer, ctx.item.alternatives);
      if (outcome === 'empty') {
        ctx.hintLine.textContent = t('empty_input');
        ctx.input.classList.remove('fill-shake');
        void ctx.input.offsetWidth;
        ctx.input.classList.add('fill-shake');
        ctx.input.focus();
        return;
      }
      finishQuestion(ctx, outcome, typed.trim());
    }

    function feedbackLine(icon, text) {
      var line = el('p', 'fill-feedback-line');
      if (icon) line.appendChild(el('span', 'fill-feedback-icon', icon));
      line.appendChild(el('span', 'fill-feedback-text', text));
      return line;
    }

    function finishQuestion(ctx, outcome, typed) {
      var item = ctx.item;
      var ok = outcome === 'correct' || outcome === 'accent';
      state.answered = true;
      state.answeredAt = Date.now();
      state.answers += 1;
      if (ok) state.correct += 1;
      else state.missed.push(item);
      recordResult(item, ok);
      refreshToken();

      var kind = ok ? (outcome === 'accent' ? 'accent' : 'correct') : 'wrong';
      card.classList.add('fill-card--' + kind);

      ctx.input.readOnly = true;
      ctx.hintBtn.hidden = true;
      ctx.hintLine.textContent = '';
      ctx.blank.textContent = item.answer;
      ctx.blank.classList.add('fill-blank--filled', 'fill-blank--' + kind);

      ctx.feedback.className = 'fill-feedback fill-feedback--' + kind;
      ctx.feedback.textContent = '';
      if (outcome === 'correct') {
        ctx.feedback.appendChild(feedbackLine('✓', t('correct')));
      } else if (outcome === 'accent') {
        ctx.feedback.appendChild(feedbackLine('✓', t('correct_accent', { answer: item.answer })));
      } else {
        if (outcome === 'wrong') ctx.feedback.appendChild(feedbackLine('✗', t('wrong')));
        var answerLine = feedbackLine(outcome === 'wrong' ? '' : '✗', t('answer_is', { answer: item.answer }));
        answerLine.dir = 'auto';
        ctx.feedback.appendChild(answerLine);
        if (typed) {
          var attempt = el('p', 'fill-attempt');
          attempt.appendChild(el('span', 'fill-attempt-label', t('your_answer') + ': '));
          var struck = el('s', 'fill-attempt-text', typed);
          struck.dir = 'auto';
          struck.lang = language;
          attempt.appendChild(struck);
          ctx.feedback.appendChild(attempt);
        }
      }

      ctx.reveal.textContent = '';
      if (item.audioSrc) {
        var play = el('button', 'fill-play');
        play.type = 'button';
        play.setAttribute('aria-label', t('play'));
        play.title = t('play');
        play.appendChild(el('span', 'fill-play-icon', '▶\uFE0E'));
        play.appendChild(el('span', 'fill-play-label', t('play')));
        play.addEventListener('click', function () {
          stopAudio();
          currentAudio = new Audio(item.audioSrc);
          currentAudio.play().catch(function () {});
        });
        ctx.reveal.appendChild(play);
      }
      if (item.translation) {
        var translation = el('p', 'fill-translation', item.translation);
        translation.lang = data.uiLanguage || '';
        translation.dir = 'auto';
        ctx.reveal.appendChild(translation);
      }
      ctx.reveal.hidden = ctx.reveal.childNodes.length === 0;

      ctx.primaryBtn.textContent = primaryLabel();
      ctx.primaryBtn.focus();
    }

    function advance() {
      stopAudio();
      state.index += 1;
      if (state.index >= state.session.length) showSummary();
      else renderQuestion();
    }

    function showSummary() {
      setProgress(state.session.length);
      progressText.textContent = t('progress', { n: state.session.length, total: state.session.length });
      card.textContent = '';
      card.className = 'fill-card fill-summary';

      card.appendChild(el('h2', 'fill-summary-title', t('summary_title')));
      var score = el('p', 'fill-score', t('summary', { correct: state.correct, total: state.answers }));
      score.dir = 'ltr';
      score.setAttribute('aria-live', 'polite');
      card.appendChild(score);
      card.appendChild(el('p', 'fill-praise', state.correct === state.answers ? t('praise_all') : t('praise')));

      if (state.missed.length) {
        card.appendChild(el('h3', 'fill-review-title', t('review')));
        var list = el('ul', 'fill-review-list');
        state.missed.forEach(function (item) {
          var row = el('li', 'fill-review-item');
          var form = el('strong', 'fill-review-form', item.answer);
          form.dir = 'auto';
          form.lang = language;
          row.appendChild(form);
          row.appendChild(el('span', 'fill-review-label', item.lemma + ' · ' + item.label));
          list.appendChild(row);
        });
        card.appendChild(list);
      }

      var actions = el('div', 'fill-actions');
      var back = el('a', 'fill-btn fill-btn--secondary', t('back'));
      back.href = backHref;
      var again = el('button', 'fill-btn fill-btn--primary', t('again'));
      again.type = 'button';
      again.id = 'fill-again';
      again.addEventListener('click', function () {
        startSession();
      });
      actions.appendChild(back);
      actions.appendChild(again);
      card.appendChild(actions);

      sendSession('summary');
      if (!coarsePointer) again.focus();
    }

    function showEmptyPool() {
      progressWrap.hidden = true;
      card.textContent = '';
      card.className = 'fill-card fill-empty';
      card.appendChild(el('p', '', state.pool === 'known' ? t('empty_known') : t('empty')));
    }

    function startSession() {
      sendSession('restart');
      stopAudio();
      var items = poolItems();
      state.session = drawSession(items, readRecent(), Math.min(sessionSize, items.length));
      state.index = 0;
      state.answers = 0;
      state.correct = 0;
      state.missed = [];
      state.sent = false;
      if (!state.session.length) {
        showEmptyPool();
        return;
      }
      renderQuestion();
    }

    function syncPoolButtons() {
      poolWrap.querySelectorAll('.fill-pool-btn').forEach(function (btn) {
        var isActive = btn.dataset.pool === state.pool;
        btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        btn.classList.toggle('fill-pool-btn--active', isActive);
        if (btn.dataset.pool === 'known') {
          btn.disabled = knownItems.length === 0;
          btn.title = knownItems.length === 0 ? t('empty_known') : '';
        }
      });
    }

    function setupPool() {
      if (data.verbId) return;
      poolWrap.hidden = false;
      poolWrap.addEventListener('click', function (event) {
        var btn = event.target.closest('.fill-pool-btn');
        if (!btn || btn.disabled || btn.dataset.pool === state.pool) return;
        state.pool = btn.dataset.pool;
        syncPoolButtons();
        startSession();
      });
    }

    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' || !state.answered) return;
      var tag = event.target && event.target.tagName;
      if (tag && tag !== 'BODY') return;
      event.preventDefault();
      advance();
    });

    window.addEventListener('pagehide', function () {
      sendSession('pagehide');
    });

    state.pool = defaultPool();
    setupPool();
    syncPoolButtons();
    refreshToken();
    // Firebase ID tokens last ~1 h; keep the cached one fresh so a pagehide send in a long-open tab still authenticates.
    setInterval(refreshToken, 25 * 60 * 1000);
    startSession();
  }

  window.VerbBoardFillPractice = { drawSession: drawSession };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
