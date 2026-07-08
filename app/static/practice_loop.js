'use strict';

(function () {
  function createPracticeLoop(config) {
    const {
      lang,
      verbs,
      practiceEl,
      ui,
      render,
      updateProgress,
    } = config;

    const storage = window.VerbBoardStorage;

    const _uiLang = window.VB_UI_LANG || '';
    const _uiSuffix = _uiLang ? '&ui_language=' + encodeURIComponent(_uiLang) : '';

    const practiceSessionKey = `practice_session:${lang}`;
    const practiceSizeKey = `practice_size:${lang}`;
    const practiceBadgesKey = `practice_badges:${lang}`;
    const practiceWrapupKey = `practice_wrapup:${lang}`;
    const practiceStreakKey = `practice_streak:${lang}`;
    const practiceMinPlaysKey = 'practice_min_plays';
    const LISTENS_MIN = 1;
    const LISTENS_MAX = 12;

    const SIZE_THREE = 3;
    const SIZE_SIX = 6;
    const SIZE_NINE = 9;
    const PRACTICE_SIZES = [SIZE_THREE, SIZE_SIX, SIZE_NINE];
    // Initial non-known pool size before mix-in warning is shown.
    const PRACTICE_POOL_INIT = 20;
    // Display threshold: below this count show one medal per session;
    // at or above, switch to compact "N× size" grouped view.
    const BADGE_COMPACT_THRESHOLD = window.VB_BADGE_COMPACT_THRESHOLD || 400;

    let activePracticeSize = parseInt(
      localStorage.getItem(practiceSizeKey) || String(SIZE_THREE),
      10
    );

    if (!PRACTICE_SIZES.includes(activePracticeSize)) {
      activePracticeSize = SIZE_THREE;
    }

    const _storedListens = parseInt(localStorage.getItem(practiceMinPlaysKey), 10);
    let activeListens = (_storedListens >= LISTENS_MIN && _storedListens <= LISTENS_MAX) ? _storedListens : 5;

    function known() {
      return storage.readSet(`known:${lang}`);
    }

    function seen() {
      return storage.readSet(`seen:${lang}`);
    }

    function readPracticeSession() {
      return storage.readJson(practiceSessionKey, null);
    }

    function readPracticeBadges() {
      return storage.readJson(practiceBadgesKey, []);
    }

    function readPracticeStreak() {
      return storage.readJson(practiceStreakKey, null);
    }

    function streakChipHtml() {
      const streakLib = window.VerbBoardStreak;
      if (!streakLib) return '';
      const rec = readPracticeStreak();
      const len = streakLib.displayLen(rec);
      if (!len) return '';
      const label = ui['practice.streak'] || 'Day streak';
      return (
        `<span class="practice-streak" title="${label}">` +
        `<span class="practice-streak-flame" aria-hidden="true">\u{1F525}</span>` +
        `<span class="practice-streak-num" aria-hidden="true">${len}</span>` +
        `<span class="vb-sr-only">${label}: ${len}</span>` +
        `</span>`
      );
    }

    async function saveKnownVerbToServer(verbId, isKnown) {
      if (!window.VerbBoardAuth || !window.VerbBoardAuth.getIdToken) {
        return;
      }

      const token = await window.VerbBoardAuth.getIdToken();
      if (!token) return;

      await fetch('/api/progress/known', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          language: lang,
          verb_id: verbId,
          known: isKnown,
        }),
      });
    }

    async function savePracticeBadgesToServer(badges, streak) {
      if (!window.VerbBoardAuth || !window.VerbBoardAuth.getIdToken) {
        return;
      }

      const token = await window.VerbBoardAuth.getIdToken();

      if (!token) {
        return;
      }

      const body = { language: lang, badges };
      if (streak) {
        body.streak_last_day = streak.last_day;
        body.streak_len = streak.len;
      }

      await fetch('/api/progress/practice', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });
    }

    async function syncPracticeBadgesFromServer() {
      if (!window.VerbBoardAuth || !window.VerbBoardAuth.getIdToken) {
        return;
      }

      const token = await window.VerbBoardAuth.getIdToken();

      if (!token) {
        return;
      }

      const response = await fetch(
        `/api/progress/practice?language=${encodeURIComponent(lang)}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        return;
      }

      const payload = await response.json();

      if (!Array.isArray(payload.badges)) {
        return;
      }

      // Merge strategy: server is authoritative when it has more badges (new
      // device / clean local state). Keep local when it has more badges --
      // protects against a silent server-save failure on _finishPractice losing
      // locally-earned badges on the next sync. Also upload local-only badges
      // so pre-login earned badges are persisted to the server on first sign-in.
      const localBadges = storage.readJson(practiceBadgesKey, []);
      const badgesToStore = payload.badges.length >= localBadges.length
        ? payload.badges
        : localBadges;

      // Streak merge: never regress a legitimate streak on either device.
      const streakLib = window.VerbBoardStreak;
      const localStreak = readPracticeStreak();
      const serverStreak = payload.streak || null;
      const mergedStreak = streakLib ? streakLib.merge(localStreak, serverStreak) : (serverStreak || localStreak);
      if (mergedStreak) {
        storage.writeJson(practiceStreakKey, mergedStreak);
      }

      // Upload when local badges are ahead OR the merged streak advances the
      // server's -- the two mechanisms sync independently.
      const streakDiffers = mergedStreak && (
        !serverStreak ||
        mergedStreak.last_day !== serverStreak.last_day ||
        mergedStreak.len !== serverStreak.len
      );
      if (localBadges.length > payload.badges.length || streakDiffers) {
        savePracticeBadgesToServer(badgesToStore, mergedStreak);
      }
      storage.writeJson(practiceBadgesKey, badgesToStore);

      renderPracticePanel();
    }

    function buildPool(size) {
      const knownSet = known();
      const nonKnown = verbs.filter(v => !knownSet.has(v.id));

      if (nonKnown.length >= size) {
        return nonKnown;
      }

      // Not enough non-known verbs -- pad with known ones.
      const knownVerbs = verbs.filter(v => knownSet.has(v.id));
      return [...nonKnown, ...knownVerbs];
    }

    function needsMixIn(size) {
      const nonKnownCount = verbs.filter(v => !known().has(v.id)).length;
      // Warn when non-known pool is smaller than the minimum or the session size.
      return nonKnownCount < Math.max(size, PRACTICE_POOL_INIT);
    }

    function renderPracticePanel() {
      if (!practiceEl) {
        return;
      }

      const session = readPracticeSession();
      const badges = readPracticeBadges();

      const ghostBadge = '<span class="practice-badge practice-badge--ghost"><span class="practice-badge-ribbon"></span></span>';
      let badgesHtml;
      if (badges.length >= BADGE_COMPACT_THRESHOLD) {
        // At or above threshold: compact grouped view, no ghost slots needed.
        const counts = {};
        badges.forEach(function (n) { counts[n] = (counts[n] || 0) + 1; });
        const inner = Object.keys(counts)
          .map(Number)
          .sort(function (a, b) { return a - b; })
          .map(function (size) {
            return `<span class="practice-badge-group">` +
              `<span class="practice-badge-count">${counts[size]}</span>` +
              `<span class="practice-badge-times">×</span>` +
              `<span class="practice-badge"><span class="practice-badge-ribbon"></span>${size}</span>` +
              `</span>`;
          })
          .join('');
        badgesHtml = `<div class="practice-badges">${inner}</div>`;
      } else {
        // Below threshold: fill earned badges left-to-right, ghosts fill remaining slots up to 5.
        const earned = badges
          .map(function (n) { return `<span class="practice-badge"><span class="practice-badge-ribbon"></span>${n}</span>`; })
          .join('');
        const ghosts = ghostBadge.repeat(Math.max(0, 5 - badges.length));
        badgesHtml = `<div class="practice-badges">${earned}${ghosts}</div>`;
      }

      if (session && Array.isArray(session.ids) && session.ids.length > 0) {
        const seenSet = seen();

        const visitedCount = session.ids.filter(function (id) {
          return seenSet.has(id);
        }).length;

        const continueId = session.ids.find(function (id) {
          return !seenSet.has(id);
        }) || session.ids[session.ids.length - 1];

        const verbsUrl = `/verbs?language=${encodeURIComponent(lang)}${_uiSuffix}`;

        const continueUrl =
          `/learn?language=${encodeURIComponent(lang)}` +
          `&verb_id=${encodeURIComponent(continueId)}` +
          `&return_to=${encodeURIComponent(verbsUrl)}` +
          _uiSuffix;

        practiceEl.innerHTML = `
          <div class="practice-panel-card">
            <div class="practice-card-header">
              <span class="practice-label">${ui['practice.label'] || 'Practice'}</span>
              ${streakChipHtml()}
              ${badgesHtml}
            </div>
            <div class="practice-inprogress">
              <span class="practice-inprogress-label">
                ${ui['practice.in_progress'] || 'In progress'}:
                ${visitedCount}/${session.ids.length}
              </span>

              <a href="${continueUrl}" class="btn-pill-navy">
                ${ui['practice.continue'] || 'Continue'}
              </a>

              <button class="practice-abandon-btn" id="practice-abandon">
                ${ui['practice.abandon'] || 'Abandon'}
              </button>
            </div>
          </div>
        `;

        document
          .getElementById('practice-abandon')
          .addEventListener('click', function () {
            localStorage.removeItem(practiceSessionKey);
            renderPracticePanel();
          });

        return;
      }

      const mixed = needsMixIn(activePracticeSize);

      const startLabel = mixed
        ? (ui['practice.start_mixed'] || 'Start (includes known)')
        : (ui['practice.start'] || 'Start');

      const sizeButtons = PRACTICE_SIZES
        .map(function (size) {
          return `
            <button
              class="practice-size-btn${size === activePracticeSize ? ' active' : ''}"
              data-size="${size}"
            >
              ${size}
            </button>
          `;
        })
        .join('');

      const listenStepper = `
        <div class="practice-listens-stepper">
          <button class="practice-listens-btn" id="listens-dec" aria-label="Decrease"${activeListens <= LISTENS_MIN ? ' disabled' : ''}>&#8722;</button>
          <span class="practice-listens-val" id="listens-val">${activeListens}</span>
          <button class="practice-listens-btn" id="listens-inc" aria-label="Increase"${activeListens >= LISTENS_MAX ? ' disabled' : ''}>+</button>
        </div>
      `;

      practiceEl.innerHTML = `
        <div class="practice-panel-card">
          <div class="practice-card-header">
            <span class="practice-label">${ui['practice.label'] || 'Practice'}</span>
            ${streakChipHtml()}
            ${badgesHtml}
          </div>
          <div class="practice-picker">
            <div class="practice-picker-rows">
              <div class="practice-picker-row">
                <span class="practice-size-hint">${ui['practice.size_unit'] || '# of verbs'}</span>
                <div class="practice-size-group">
                  ${sizeButtons}
                </div>
              </div>
              <div class="practice-picker-row">
                <span class="practice-size-hint">${ui['practice.listens_unit'] || '# audios / verb'}</span>
                ${listenStepper}
              </div>
            </div>
            <div class="practice-picker-start">
              <button class="btn-pill-navy" id="practice-start">
                ${startLabel}
              </button>
            </div>
          </div>
        </div>
      `;

      practiceEl
        .querySelectorAll('.practice-size-btn[data-size]')
        .forEach(function (button) {
          button.addEventListener('click', function () {
            activePracticeSize = parseInt(button.dataset.size, 10);
            localStorage.setItem(practiceSizeKey, String(activePracticeSize));
            _saveSessionSizeToServer(activePracticeSize);
            renderPracticePanel();
          });
        });

      function _updateListensStepper() {
        const valEl = document.getElementById('listens-val');
        const decBtn = document.getElementById('listens-dec');
        const incBtn = document.getElementById('listens-inc');
        if (valEl) valEl.textContent = activeListens;
        if (decBtn) decBtn.disabled = activeListens <= LISTENS_MIN;
        if (incBtn) incBtn.disabled = activeListens >= LISTENS_MAX;
      }

      const decBtn = document.getElementById('listens-dec');
      const incBtn = document.getElementById('listens-inc');
      if (decBtn) {
        decBtn.addEventListener('click', function () {
          if (activeListens > LISTENS_MIN) {
            activeListens--;
            localStorage.setItem(practiceMinPlaysKey, String(activeListens));
            _saveListensToServer(activeListens);
            _updateListensStepper();
          }
        });
      }
      if (incBtn) {
        incBtn.addEventListener('click', function () {
          if (activeListens < LISTENS_MAX) {
            activeListens++;
            localStorage.setItem(practiceMinPlaysKey, String(activeListens));
            _saveListensToServer(activeListens);
            _updateListensStepper();
          }
        });
      }

      document
        .getElementById('practice-start')
        .addEventListener('click', startPractice);
    }

    function startPractice() {
      const pool = buildPool(activePracticeSize);

      // Guard: nothing to practice (all verbs missing or pool empty).
      if (pool.length === 0) {
        return;
      }

      const shuffled = [...pool].sort(function () {
        return Math.random() - 0.5;
      });

      const picked = shuffled.slice(0, activePracticeSize);

      const ids = picked.map(v => v.id);
      const lemmas = {};

      picked.forEach(function (verb) {
        lemmas[verb.id] = verb.lemma;
      });

      storage.writeJson(practiceSessionKey, {
        ids,
        lemmas,
        size: activePracticeSize,
      });

      const verbsUrl = `/verbs?language=${encodeURIComponent(lang)}${_uiSuffix}`;

      window.location.href =
        `/learn?language=${encodeURIComponent(lang)}` +
        `&verb_id=${encodeURIComponent(ids[0])}` +
        `&return_to=${encodeURIComponent(verbsUrl)}` +
        _uiSuffix;
    }

    function maybeShowWrapUp() {
      const pendingWrapup = localStorage.getItem(practiceWrapupKey);

      if (!pendingWrapup) {
        return;
      }

      localStorage.removeItem(practiceWrapupKey);

      try {
        showWrapUp(JSON.parse(pendingWrapup));
      } catch (_) {}
    }

    function showWrapUp(wrapupData) {
      const knownSet = known();
      const lemmas = wrapupData.lemmas || {};

      const overlay = document.createElement('div');
      overlay.className = 'practice-wrapup-overlay';

      const card = document.createElement('div');
      card.className = 'practice-wrapup-card';

      const heading = document.createElement('h3');
      heading.textContent = ui['practice.wrap_up'] || 'Practice complete';

      card.appendChild(heading);

      const prompt = document.createElement('p');
      prompt.textContent = ui['practice.learned_prompt'] || 'Which verbs did you learn?';

      card.appendChild(prompt);

      if (wrapupData.streakLen > 0) {
        const streakLine = document.createElement('p');
        streakLine.className = 'practice-wrapup-streak';
        streakLine.textContent = (ui['practice.streak'] || 'Day streak') + ': \u{1F525} ' + wrapupData.streakLen;
        card.appendChild(streakLine);
      }

      const list = document.createElement('div');
      list.className = 'practice-wrapup-list';

      wrapupData.ids.forEach(function (id) {
        const label = document.createElement('label');
        label.className = 'practice-wrapup-item';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.dataset.id = id;
        checkbox.checked = knownSet.has(id);

        const span = document.createElement('span');
        span.textContent = lemmas[id] || id;

        label.appendChild(checkbox);
        label.appendChild(span);

        if (knownSet.has(id)) {
          const star = document.createElement('span');
          star.className = 'practice-wrapup-star';
          star.textContent = '★';
          label.appendChild(star);
        }

        list.appendChild(label);
      });

      card.appendChild(list);

      const actions = document.createElement('div');
      actions.className = 'practice-wrapup-actions';

      const doneButton = document.createElement('button');
      doneButton.className = 'btn-pill-navy';
      doneButton.textContent = ui['practice.done'] || 'Done';

      actions.appendChild(doneButton);

      card.appendChild(actions);

      overlay.appendChild(card);
      document.body.appendChild(overlay);

      doneButton.addEventListener('click', async function () {
        const checked = overlay.querySelectorAll("input[type='checkbox']:checked");

        if (checked.length > 0) {
          const newKnown = known();

          wrapupData.ids.forEach(function (id) {
            newKnown.delete(id);
          });

          checked.forEach(function (checkbox) {
            newKnown.add(checkbox.dataset.id);
          });

          storage.writeSet(`known:${lang}`, newKnown);

          for (const id of wrapupData.ids) {
            await saveKnownVerbToServer(id, newKnown.has(id));
          }
        }

        overlay.remove();
        render();
        updateProgress();
        renderPracticePanel();
      });
    }

    function _saveListensToServer(listens) {
      if (!window.VerbBoardAuth) return;
      window.VerbBoardAuth.getIdToken().then(function (token) {
        if (!token) return;
        fetch('/api/preferences', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
          body: JSON.stringify({ practice_min_plays: listens }),
        });
      });
    }

    function _saveSessionSizeToServer(size) {
      if (!window.VerbBoardAuth) return;
      window.VerbBoardAuth.getIdToken().then(function (token) {
        if (!token) return;
        fetch('/api/preferences', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
          body: JSON.stringify({ practice_session_size: size }),
        });
      });
    }

    function setSize(size) {
      if (!PRACTICE_SIZES.includes(size)) return;
      activePracticeSize = size;
      localStorage.setItem(practiceSizeKey, String(size));
      renderPracticePanel();
    }

    return {
      renderPracticePanel,
      maybeShowWrapUp,
      syncPracticeBadgesFromServer,
      savePracticeBadgesToServer,
      setSize,
    };
  }

  window.VerbBoardPracticeLoop = {
    createPracticeLoop,
  };
})();
