'use strict';

const initialPanel = ['feedback', 'signals', 'candidates'].includes(location.hash.slice(1))
  ? location.hash.slice(1)
  : 'feedback';

showPanel(initialPanel);
loadFeedback();
