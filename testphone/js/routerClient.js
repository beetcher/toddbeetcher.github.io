const routerClient = (() => {

  async function getConfig() {
    try {
      const res = await fetch(`${ROUTER_BASE_URL}/config`);
      if (!res.ok) return [];
      return res.json();
    } catch {
      return [];
    }
  }

  async function saveConfig(routingTable) {
    let res, data;
    try {
      res = await fetch(`${ROUTER_BASE_URL}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(routingTable),
      });
      data = await res.json();
    } catch {
      return { success: false, errors: [{ row: 0, field: 'phoneNumber', category: 'NETWORK_ERROR', message: 'Could not reach Router. Is the emulator running?' }] };
    }
    if (!res.ok) return { success: false, errors: data.errors || [] };
    return data;
  }

  async function sendInbound({ from, to, body }) {
    const params = new URLSearchParams({ From: from, To: to, Body: body });
    let res, data;
    try {
      res = await fetch(`${ROUTER_BASE_URL}/incoming`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params.toString(),
      });
      data = await res.json();
    } catch (err) {
      return { success: false, error: { category: 'NETWORK_ERROR', message: 'Could not reach Router. Is the emulator running?' } };
    }

    if (!res.ok) {
      const message = data.error === 'ROUTING_NOT_FOUND'
        ? `No routing entry for ${to}. Open config (Ctrl+Shift+C) to add one.`
        : data.message || 'Unknown error';
      return { success: false, error: { category: data.error, message } };
    }

    return { success: true, messageSid: data.messageSid };
  }

  async function pollForMessages(myNumber) {
    let res, data;
    try {
      res = await fetch(`${ROUTER_BASE_URL}/poll?phoneNumber=${encodeURIComponent(myNumber)}`);
      data = await res.json();
    } catch {
      return [];
    }
    if (!res.ok || !Array.isArray(data.messages)) return [];
    return data.messages.map(m => ({
      from: m.from,
      to: m.to,
      body: m.body,
      messageSid: m.messageSid,
      timestamp: new Date(m.createdAt).getTime(),
    }));
  }

  return { getConfig, saveConfig, sendInbound, pollForMessages };
})();
