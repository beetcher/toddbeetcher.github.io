const storage = (() => {
  const CONV_PREFIX = 'testphone_conv_';

  function loadConversation(normalizedNumber) {
    try {
      const raw = localStorage.getItem(CONV_PREFIX + normalizedNumber);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }

  function saveConversation(normalizedNumber, messages) {
    try {
      localStorage.setItem(CONV_PREFIX + normalizedNumber, JSON.stringify(messages));
    } catch (e) {
      console.warn('testphone: failed to persist conversation:', e);
    }
  }

  return { loadConversation, saveConversation };
})();
