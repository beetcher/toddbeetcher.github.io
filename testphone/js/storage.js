const storage = (() => {
  const CONV_PREFIX = 'testphone_conv_';
  const LAST_NUMBERS_KEY = 'testphone_last_numbers';

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

  function loadLastNumbers() {
    try {
      const raw = localStorage.getItem(LAST_NUMBERS_KEY);
      return raw ? JSON.parse(raw) : { my: null, dest: null };
    } catch {
      return { my: null, dest: null };
    }
  }

  function saveLastNumbers(obj) {
    try {
      localStorage.setItem(LAST_NUMBERS_KEY, JSON.stringify(obj));
    } catch (e) {
      console.warn('testphone: failed to persist last numbers:', e);
    }
  }

  return { loadConversation, saveConversation, loadLastNumbers, saveLastNumbers };
})();
