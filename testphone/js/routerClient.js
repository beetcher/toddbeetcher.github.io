const routerClient = (() => {
  const ROUTING_KEY = 'testphone_routing_table';
  const INBOX_PREFIX = 'testphone_inbox_';

  // ── MOCK ECHO ─────────────────────────────────────────────────────────────
  // Simulates an auto-reply from the destination so the receive path can be
  // tested without a real application server. Delete this block (and the
  // _mockEcho call in sendInbound) when the real Router exists.
  function _mockEcho(toNumber, fromNumber) {
    setTimeout(() => {
      const inbox = _readInbox(toNumber);
      inbox.push({
        from: fromNumber,
        to: toNumber,
        body: '[Mock] Auto-reply: your message was received.',
        messageSid: 'SM_ECHO_' + Math.random().toString(36).slice(2, 18).toUpperCase(),
        timestamp: Date.now(),
      });
      _writeInbox(toNumber, inbox);
    }, 1500);
  }

  function _readInbox(number) {
    try {
      return JSON.parse(localStorage.getItem(INBOX_PREFIX + number) || '[]');
    } catch {
      return [];
    }
  }

  function _writeInbox(number, messages) {
    localStorage.setItem(INBOX_PREFIX + number, JSON.stringify(messages));
  }
  // ── end mock echo ──────────────────────────────────────────────────────────

  async function getConfig() {
    try {
      const raw = localStorage.getItem(ROUTING_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }

  async function saveConfig(routingTable) {
    const errors = [];
    const seenNumbers = new Set();

    routingTable.forEach((row, i) => {
      const normalized = phoneNumber.normalize(row.phoneNumber);
      if (!normalized) {
        errors.push({ row: i, field: 'phoneNumber', category: 'INVALID_PHONE', message: 'Invalid phone number format' });
      } else if (seenNumbers.has(normalized)) {
        errors.push({ row: i, field: 'phoneNumber', category: 'DUPLICATE_PHONE', message: 'Duplicate phone number' });
      } else {
        seenNumbers.add(normalized);
      }

      const url = (row.webhookUrl || '').trim();
      if (!url || !/^https?:\/\/.+/.test(url)) {
        errors.push({ row: i, field: 'webhookUrl', category: 'INVALID_URL', message: 'Must start with http:// or https://' });
      }
    });

    if (errors.length > 0) return { success: false, errors };

    const normalized = routingTable.map(row => ({
      phoneNumber: phoneNumber.normalize(row.phoneNumber),
      webhookUrl: row.webhookUrl.trim(),
    }));
    localStorage.setItem(ROUTING_KEY, JSON.stringify(normalized));
    return { success: true, errors: [] };
  }

  async function sendInbound({ from, to, body }) {
    const table = await getConfig();
    const entry = table.find(r => r.phoneNumber === to);

    if (!entry) {
      return {
        success: false,
        error: {
          category: 'ROUTING_NOT_FOUND',
          message: `No routing entry for ${to}. Open config (Ctrl+Shift+C) to add one.`,
        },
      };
    }

    const messageSid = 'SM' + Math.random().toString(36).slice(2, 34).toUpperCase();

    _mockEcho(from, to); // remove when real Router exists

    return { success: true, messageSid };
  }

  async function pollForMessages(myNumber) {
    const messages = _readInbox(myNumber);
    if (messages.length > 0) {
      localStorage.removeItem(INBOX_PREFIX + myNumber);
    }
    return messages;
  }

  return { getConfig, saveConfig, sendInbound, pollForMessages };
})();
