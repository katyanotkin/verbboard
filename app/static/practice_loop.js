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

    const PRACTICE_SIZES = [3, 6, 9];
    const PRACTICE_POOL = 20;

    let activePracticeSize = parseInt(
      localStorage.getItem(practiceSizeKey) || '6',
      10
    );

    if (!PRACTICE_SIZES.includes(activePracticeSize)) {
      activePracticeSize = 6;
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

    async function saveKnownVerbToServer(verbId, known) {
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
	      known: known,
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

      storage.writeJson(practiceBadgesKey, payload.badges);

      renderPracticePanel();
    }

    function buildPool(size) {
      const knownSet = known();

      const nonKnown = verbs
        .filter(v => !knownSet.has(v.id))
        .slice(0, PRACTICE_POOL);

      if (nonKnown.length >= size) {
        return nonKnown;
      }

      const knownVerbs = verbs.filter(v => knownSet.has(v.id));

      return [...nonKnown, ...knownVerbs];
    }

    function needsMixIn(size) {
      const knownSet = known();

      return verbs
        .filter(v => !knownSet.has(v.id))
        .slice(0, PRACTICE_POOL)
        .length < size;
    }

    function renderPracticePanel() {
      if (!practiceEl) {
        return;
      }

      const session = readPracticeSession();
      const badges = readPracticeBadges();

      const badgesHtml = badges.length
        ? `
          <div class="practice-badges">
            ${badges.map(n => `<span class="practice-badge">${n}</span>`).join('')}
          </div>
        `
        : '';

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
              class="vb-ftbtn${size === activePracticeSize ? ' active' : ''}"
              data-size="${size}"
            >
              ${size}
            </button>
          `;
        })
        .join('');

      practiceEl.innerHTML = `
        <div class="practice-picker">
          <span class="practice-label">
            ${ui['practice.label'] || 'Practice'}
          </span>

          <div class="vb-filter-toggle">
            ${sizeButtons}
          </div>

          <button class="btn-pill-navy" id="practice-start">
            ${startLabel}
          </button>
        </div>

        ${badgesHtml}
      `;

      practiceEl
        .querySelectorAll('.vb-ftbtn[data-size]')
        .forEach(function (button) {
          button.addEventListener('click', function () {
            activePracticeSize = parseInt(button.dataset.size, 10);

            localStorage.setItem(
              practiceSizeKey,
              String(activePracticeSize)
            );

            renderPracticePanel();
          });
        });

      document
        .getElementById('practice-start')
        .addEventListener('click', startPractice);
    }

    function startPractice() {
      const pool = buildPool(activePracticeSize);

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

      const saveButton = document.createElement('button');
      saveButton.className = 'btn-pill-navy';
      saveButton.textContent = ui['practice.save'] || 'Save';

      const skipButton = document.createElement('button');
      skipButton.className = 'practice-abandon-btn';
      skipButton.textContent = ui['practice.skip'] || 'Skip';

      actions.appendChild(saveButton);
      actions.appendChild(skipButton);

      card.appendChild(actions);

      overlay.appendChild(card);
      document.body.appendChild(overlay);

      saveButton.addEventListener('click', async function () {
        const newKnown = known();

        wrapupData.ids.forEach(function (id) {
          newKnown.delete(id);
        });

        overlay
          .querySelectorAll("input[type='checkbox']:checked")
          .forEach(function (checkbox) {
            newKnown.add(checkbox.dataset.id);
          });


	storage.writeSet(`known:${lang}`, newKnown);

	for (const id of wrapupData.ids) {
	  await saveKnownVerbToServer(
	    id,
	    newKnown.has(id)
	  );
	}

	const updatedBadges = [...new Set([
	  ...readPracticeBadges(),
	  wrapupData.ids.length,
	])].sort(function (left, right) {
	  return left - right;
	});

	storage.writeJson(practiceBadgesKey, updatedBadges);

	await savePracticeBadgesToServer(updatedBadges);

        overlay.remove();

        render();
        updateProgress();
        renderPracticePanel();
      });

      skipButton.addEventListener('click', function () {
        overlay.remove();
      });
    }

    return {
      renderPracticePanel,
      maybeShowWrapUp,
      syncPracticeBadgesFromServer,
      savePracticeBadgesToServer,
    };
  }

  window.VerbBoardPracticeLoop = {
    createPracticeLoop,
  };
})();
