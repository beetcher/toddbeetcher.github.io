const storage = (() => {
  const CONV_PREFIX = 'testphone_conv_';
  const LAST_NUMBERS_KEY = 'testphone_last_numbers';
  const NUMBER_HISTORY_KEY = 'testphone_number_history';
  const NUMBER_HISTORY_MAX = 10;

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

  // Task 4: Archive conversation under a timestamped key (never deletes).
  function archiveConversation(normalizedNumber, messages) {
    try {
      const key = `testphone_archive_${normalizedNumber}_${Date.now()}`;
      localStorage.setItem(key, JSON.stringify(messages));
    } catch (e) {
      console.warn('testphone: failed to archive conversation:', e);
    }
  }

  // Task 5: Number history per field ('my' | 'dest').
  function loadNumberHistory(field) {
    try {
      const raw = localStorage.getItem(NUMBER_HISTORY_KEY);
      const all = raw ? JSON.parse(raw) : {};
      return Array.isArray(all[field]) ? all[field] : [];
    } catch {
      return [];
    }
  }

  function addToNumberHistory(field, normalized) {
    try {
      const raw = localStorage.getItem(NUMBER_HISTORY_KEY);
      const all = raw ? JSON.parse(raw) : {};
      const list = Array.isArray(all[field]) ? all[field] : [];
      const filtered = list.filter(n => n !== normalized);
      all[field] = [normalized, ...filtered].slice(0, NUMBER_HISTORY_MAX);
      localStorage.setItem(NUMBER_HISTORY_KEY, JSON.stringify(all));
    } catch (e) {
      console.warn('testphone: failed to save number history:', e);
    }
  }

  return {
    loadConversation,
    saveConversation,
    loadLastNumbers,
    saveLastNumbers,
    archiveConversation,
    loadNumberHistory,
    addToNumberHistory,
  };
})();
