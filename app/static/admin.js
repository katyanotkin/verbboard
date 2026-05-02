'use strict';

const initialPanel = ['feedback', 'signals', 'candidates', 'live_verbs'].includes(location.hash.slice(1))
  ? location.hash.slice(1)
  : 'feedback';

showPanel(initialPanel);
