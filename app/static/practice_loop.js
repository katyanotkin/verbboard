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

    const practiceSessionKey = `practice_session:${lang}`;
    const practiceSizeKey = `practice_size:${lang}`;
    const practiceBadgesKey = `practice_badges:${lang}`;
    const practiceWrapupKey = `practice_wrapup:${lang}`;

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

    async function savePracticeBadgesToServer(badges) {
      if (!window.VerbBoardAuth || !window.VerbBoardAuth.getIdToken) {
        return;
      }

      const token = await window.VerbBoardAuth.getIdToken();

      if (!token) {
        return;
      }

      await fetch('/api/progress/practice', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          language: lang,
          badges,
        }),
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
      // locally-earned badges on the next sync.
      const localBadges = storage.readJson(practiceBadgesKey, []);
      const badgesToStore = payload.badges.length >= localBadges.length
        ? payload.badges
        : localBadges;
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

      let badgesHtml = '';
      if (badges.length > 0) {
        let inner;
        if (badges.length < BADGE_COMPACT_THRESHOLD) {
          // Below threshold: one medal per completed session.
          inner = badges
            .map(function (n) { return `<span class="practice-badge"><span class="practice-badge-ribbon"></span>${n}</span>`; })
            .join('');
        } else {
          // At or above threshold: one group per size showing count.
          const counts = {};
          badges.forEach(function (n) { counts[n] = (counts[n] || 0) + 1; });
          inner = Object.keys(counts)
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
        }
        badgesHtml = `<div class="practice-badges">${inner}</div>`;
      }

      if (session && Array.isArray(session.ids) && session.ids.length > 0) {
        const seenSet = seen();

        const visitedCount = session.ids.filter(function (id) {
          return seenSet.has(id);
        }).length;

        const continueId = session.ids.find(function (id) {
          return !seenSet.has(id);
        }) || session.ids[session.ids.length - 1];

        const verbsUrl = `/verbs?language=${encodeURIComponent(lang)}`;

        const continueUrl =
          `/learn?language=${encodeURIComponent(lang)}` +
          `&verb_id=${encodeURIComponent(continueId)}` +
          `&return_to=${encodeURIComponent(verbsUrl)}`;

        practiceEl.innerHTML = `
          <div class="practice-panel-card">
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

            ${badgesHtml}
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

      practiceEl.innerHTML = `
        <div class="practice-panel-card">
          <div class="practice-picker">
            <span class="practice-label">
              ${ui['practice.label'] || 'Practice'}
            </span>

            <div class="practice-size-group">
              ${sizeButtons}
            </div>

            <span class="practice-size-hint">${ui['practice.size_unit'] || '# of verbs'}</span>

            <button class="btn-pill-navy" id="practice-start">
              ${startLabel}
            </button>
          </div>

          ${badgesHtml}
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

      const verbsUrl = `/verbs?language=${encodeURIComponent(lang)}`;

      window.location.href =
        `/learn?language=${encodeURIComponent(lang)}` +
        `&verb_id=${encodeURIComponent(ids[0])}` +
        `&return_to=${encodeURIComponent(verbsUrl)}`;
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
