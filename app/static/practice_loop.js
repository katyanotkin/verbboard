'use strict';

(function () {
  // Verbs seen but never marked known, longest-waiting first, capped at ~1/3
  // of the session (same cap as SRS review; the two pools never overlap since
  // SRS only covers known verbs). Ordering is by when a verb last occupied a
  // repeat slot (missing = never = 0, sorts first), so every struggling verb
  // is guaranteed to resurface in turn instead of relying on the random
  // shuffle. Ties (e.g. all never-repeated) are broken randomly.
  // Pure function: exported below for the Node unit test.
  function pickRepeatCandidates(verbs, seenSet, knownSet, excludeIds, lastRepeatedMap, size) {
    const cap = Math.max(1, Math.floor(size / 3));
    const candidates = verbs.filter(function (v) {
      return seenSet.has(v.id) && !knownSet.has(v.id) && !excludeIds.has(v.id);
    });
    const shuffled = candidates.sort(function () { return Math.random() - 0.5; });
    shuffled.sort(function (a, b) {
      return (lastRepeatedMap[a.id] || 0) - (lastRepeatedMap[b.id] || 0);
    });
    return shuffled.slice(0, cap);
  }

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

    const nav = window.VerbBoardNav;
    if (!nav) {
      throw new Error('nav_urls.js must be loaded before practice_loop.js');
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    const helpHintLabel = ui['help.hint_label'] || 'More info';
    function helpHint(spot) {
      return `
        <span class="help-hint">
          <button type="button" class="help-hint-trigger" aria-expanded="false" aria-label="${escapeHtml(helpHintLabel)}">?</button>
          <span class="help-hint-panel" role="note" hidden>${escapeHtml(ui['help.' + spot] || '')}</span>
        </span>
      `;
    }
    const practiceTitleHtml = `
      <span class="practice-label">
        ${escapeHtml(ui['practice.label'] || 'Practice')}
        ${helpHint('practice')}
      </span>
    `;

    const practiceSessionKey = `practice_session:${lang}`;
    const practiceSizeKey = `practice_size:${lang}`;
    const practiceBadgesKey = `practice_badges:${lang}`;
    const practiceWrapupKey = `practice_wrapup:${lang}`;
    const practiceLastRepeatedKey = `practice_last_repeated:${lang}`;
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

      const body = { language: lang, badges };

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

      if (localBadges.length > payload.badges.length) {
        savePracticeBadgesToServer(badgesToStore);
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

    // Verbs due for spaced-repetition review right now, capped at ~1/3 of
    // the session so review never crowds out new material. Kept separate
    // from buildPool() (which stays the "new verb" pool, unchanged, since
    // needsMixIn() also depends on it) -- selection into the actual session
    // happens in startPractice() below.
    function allDueVerbIds() {
      if (!window.VerbBoardSRS) return new Set();
      const dueSet = new Set(window.VerbBoardSRS.getDueVerbIds(lang));

      // Verbs marked known before this feature shipped (or before their
      // first review under it) never got an srs entry at all -- treat them
      // as immediately due too, so that backlog gets swept into review
      // instead of sitting inert forever. Nothing is written here; a
      // missing/box-0 entry already lands on box 1 on first real review
      // regardless of recall (see leitner_next_box/nextBox), so this is
      // purely a due-ness read, not new persisted state.
      const srsMap = window.VerbBoardSRS.readSrs(lang);
      known().forEach(function (id) {
        if (!srsMap[id]) dueSet.add(id);
      });

      return dueSet;
    }

    function dueReviewCandidates(size) {
      const dueSet = allDueVerbIds();
      if (dueSet.size === 0) return [];
      const dueVerbs = verbs.filter(v => dueSet.has(v.id));
      const cap = Math.max(1, Math.floor(size / 3));
      const shuffled = [...dueVerbs].sort(function () { return Math.random() - 0.5; });
      return shuffled.slice(0, cap);
    }

    // readJson can hand back null/an array if the stored value is corrupt;
    // a bad map must degrade to "nothing repeated yet", not abort startPractice.
    function readLastRepeated() {
      const map = storage.readJson(practiceLastRepeatedKey, {});
      return map && typeof map === 'object' && !Array.isArray(map) ? map : {};
    }

    function repeatCandidates(size, excludeIds) {
      return pickRepeatCandidates(verbs, seen(), known(), excludeIds, readLastRepeated(), size);
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

        const continueUrl = nav.learnUrl(lang, continueId, { returnTo: nav.verbsUrl(lang) });

        practiceEl.innerHTML = `
          <div class="practice-panel-card">
            <div class="practice-card-header">
              ${practiceTitleHtml}
              ${badgesHtml}
            </div>
            <div class="practice-inprogress">
              <span class="practice-inprogress-label">
                ${escapeHtml(ui['practice.in_progress'] || 'In progress')}:
                ${visitedCount}/${session.ids.length}
              </span>

              <a href="${continueUrl}" class="btn-pill-navy">
                ${escapeHtml(ui['practice.continue'] || 'Continue')}
              </a>

              <button class="practice-abandon-btn" id="practice-abandon">
                ${escapeHtml(ui['practice.abandon'] || 'Discard practice')}
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
            ${practiceTitleHtml}
            ${badgesHtml}
          </div>
          <div class="practice-picker">
            <div class="practice-picker-rows">
              <div class="practice-picker-row">
                <span class="practice-size-hint">${escapeHtml(ui['practice.size_unit'] || '# of verbs')}</span>
                ${helpHint('session_size')}
                <div class="practice-size-group">
                  ${sizeButtons}
                </div>
              </div>
              <div class="practice-picker-row">
                <span class="practice-size-hint">${escapeHtml(ui['practice.listens_unit'] || '# audios / verb')}</span>
                ${helpHint('listens')}
                ${listenStepper}
              </div>
            </div>
            <div class="practice-picker-start">
              <button class="btn-pill-navy" id="practice-start">
                ${escapeHtml(startLabel)}
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

    // Fire-and-forget, auth-independent practice engagement beacon (issue
    // #48) -- must never block or fail the actual practice flow, same
    // try/catch + .catch(() => {}) idiom as auth.js's _trackSignInTapped().
    function _trackPracticeEvent(event) {
      try {
        fetch('/api/analytics/practice_event', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ event: event }),
          keepalive: true,
        }).catch(function () {});
      } catch (_) {}
    }

    function startPractice() {
      const reviewPicked = dueReviewCandidates(activePracticeSize);
      const reviewIds = new Set(reviewPicked.map(v => v.id));

      // Seen-but-not-known verbs get a guaranteed slice too (issue #19), so a
      // verb you're stuck on can't go sessions without coming back.
      const repeatPicked = repeatCandidates(activePracticeSize, reviewIds);
      const repeatIds = new Set(repeatPicked.map(v => v.id));

      const pool = buildPool(activePracticeSize).filter(v => !reviewIds.has(v.id) && !repeatIds.has(v.id));

      // Guard: nothing to practice (no new verbs, no repeats, no due reviews).
      if (pool.length === 0 && reviewPicked.length === 0 && repeatPicked.length === 0) {
        return;
      }

      _trackPracticeEvent('started');

      const shuffled = [...pool].sort(function () {
        return Math.random() - 0.5;
      });

      const remainingSlots = Math.max(0, activePracticeSize - reviewPicked.length - repeatPicked.length);
      const newPicked = shuffled.slice(0, remainingSlots);

      if (repeatPicked.length > 0) {
        const lastRepeated = readLastRepeated();
        const now = Date.now();
        repeatPicked.forEach(function (verb) { lastRepeated[verb.id] = now; });
        storage.writeJson(practiceLastRepeatedKey, lastRepeated);
      }

      const picked = [...reviewPicked, ...repeatPicked, ...newPicked].sort(function () {
        return Math.random() - 0.5;
      });

      const ids = picked.map(v => v.id);
      const lemmas = {};
      const modes = {};

      picked.forEach(function (verb) {
        lemmas[verb.id] = verb.lemma;
        // Absent/'new' means the ordinary practice bar (Next/Skip); 'review'
        // means the recall buttons -- see learn_practice.js. Kept as an
        // explicit per-id map (not inferred from srs.js at render time) so
        // a verb's mode is fixed for the whole session even if its due
        // state changes mid-session (e.g. reviewed on another tab).
        modes[verb.id] = reviewIds.has(verb.id) ? 'review' : 'new';
      });

      storage.writeJson(practiceSessionKey, {
        ids,
        lemmas,
        modes,
        size: activePracticeSize,
      });

      window.location.href = nav.learnUrl(lang, ids[0], { returnTo: nav.verbsUrl(lang) });
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

      // Login-nudge badge-earned CTA -- eligibility was already decided in
      // learn_practice.js's _finishPractice() (at the moment the badge was
      // actually earned, on the previous page) and travels here via
      // wrapupData.loginNudge, since this modal only mounts after the
      // redirect to /verbs. markShown() here (not there) is deliberate: it
      // marks the lifetime-cap slot used at the point the CTA is actually
      // rendered, not merely decided-eligible.
      //
      // isAnonymous() is re-checked live via whenAuthReady() (not just
      // trusted from the stale decision above) because practice_wrapup:
      // {lang} is a localStorage payload that can outlive the page that
      // wrote it -- a backgrounded/OS-killed mobile tab can die before the
      // redirect to /verbs completes, leaving the payload behind. If the
      // user then signs in and later opens /verbs in a fresh tab,
      // maybeShowWrapUp() would otherwise replay a decision made while
      // still anonymous and show this CTA to a now-signed-in user.
      // whenAuthReady() (not a bare isAnonymous() check) because this
      // script (practice_loop.js) is a non-deferred body script that can
      // run before window.VerbBoardAuth even exists yet -- see its comment
      // in login_nudge.js. The callback below is guaranteed to run after
      // `actions` has already been appended to `card` (that happens
      // synchronously, right after this block, before any promise
      // resolves), so insertBefore(nudgeEl, actions) is always valid.
      //
      // reserveThisPageLoad() is called synchronously here, before
      // whenAuthReady() -- not inside its async callback -- so the "one
      // nudge per page load" guarantee (shared with login_nudge_card.js's
      // /verbs threshold card) holds unconditionally, during initial parse,
      // regardless of script load order or which of the two surfaces'
      // whenAuthReady() callbacks happens to resolve first. It reserves the
      // slot whenever this badge-earned payload is in play at all, even if
      // the live isAnonymous() check below later decides not to render.
      if (wrapupData.loginNudge && window.VerbBoardLoginNudge) {
        window.VerbBoardLoginNudge.reserveThisPageLoad();
        window.VerbBoardLoginNudge.whenAuthReady(function () {
          if (!window.VerbBoardLoginNudge.isAnonymous()) return;
          const nudgeCopy =
            ui['login_nudge.badge'] ||
            "You just earned a badge! Sign in with Google so it's still here next time.";
          const nudgeEl = window.VerbBoardLoginNudge.buildCta(nudgeCopy);
          card.insertBefore(nudgeEl, actions);
          window.VerbBoardLoginNudge.markShown();
        });
      }

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
    pickRepeatCandidates,
  };
})();
