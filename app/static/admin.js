'use strict';

const initialPanel = ['signals', 'candidates', 'live_verbs'].includes(location.hash.slice(1))
  ? location.hash.slice(1)
  : 'signals';

showPanel(initialPanel);
