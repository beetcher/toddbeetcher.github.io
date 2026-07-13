(() => {
  const myNumberInput    = document.getElementById('my-number');
  const destNumberInput  = document.getElementById('dest-number');
  const messageInput     = document.getElementById('message-input');
  const sendBtn          = document.getElementById('send-btn');
  const statusArea       = document.getElementById('status-area');
  const convContainer    = document.getElementById('conversation');
  const contactHeader    = document.getElementById('phone-contact-header');
  const downloadBtn      = document.getElementById('download-btn');
  const resetBtn         = document.getElementById('reset-btn');
  const panelToggleBtn   = document.getElementById('panel-toggle-btn');
  const controlsCol      = document.getElementById('controls-col');
  const myDropdown       = document.getElementById('my-number-dropdown');
  const destDropdown     = document.getElementById('dest-number-dropdown');

  const PANEL_STATE_KEY = 'testphone_panel_collapsed';

  let myNumber = null;
  let statusTimer = null;
  const lastNumbers = { my: null, dest: null };
  const seenMessageSids = new Set();

  conversation.init(convContainer);
  conversation.load([], 'Enter My Phone Number to get started.');
  routerEndpoints.init();
  configEditor.init();
  help.init();

  document.getElementById('settings-gear-btn').addEventListener('click', () => configEditor.open());
  document.getElementById('help-btn').addEventListener('click', () => help.open());

  // ── Status display ────────────────────────────────────────────────────────

  function showStatus(msg, type) {
    clearTimeout(statusTimer);
    statusArea.textContent = msg;
    statusArea.className = `status-area status-${type || 'info'}`;
    if (type === 'success') {
      statusTimer = setTimeout(clearStatus, 3000);
    }
  }

  function clearStatus() {
    statusArea.textContent = '';
    statusArea.className = 'status-area';
  }

  // ── Task 2: Contact header (app name on phone screen) ─────────────────────

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  async function updateContactHeader(normalizedDest) {
    if (!normalizedDest) {
      contactHeader.innerHTML = '';
      contactHeader.classList.remove('has-contact');
      return;
    }
    const config = await routerClient.getConfig();
    const entry = config.find(e => e.phoneNumber === normalizedDest);
    const name = entry && entry.name ? entry.name : null;
    const formatted = phoneNumber.formatForDisplay(normalizedDest);
    contactHeader.classList.add('has-contact');
    if (name) {
      contactHeader.innerHTML =
        `<div class="phone-contact-name">${escapeHtml(name)}</div>` +
        `<div class="phone-contact-sub">${escapeHtml(formatted)}</div>`;
    } else {
      contactHeader.innerHTML =
        `<div class="phone-contact-name">${escapeHtml(formatted)}</div>`;
    }
  }

  // ── Task 5: Combo box history ─────────────────────────────────────────────

  function renderDropdown(dropdownEl, history, onSelect) {
    dropdownEl.innerHTML = '';
    for (const normalized of history) {
      const item = document.createElement('div');
      item.className = 'number-dropdown-item';
      item.textContent = phoneNumber.formatForDisplay(normalized);
      item.addEventListener('mousedown', (e) => {
        e.preventDefault(); // keep focus on input
        onSelect(normalized);
      });
      dropdownEl.appendChild(item);
    }
  }

  function setupComboBox(input, dropdownEl, fieldKey) {
    input.addEventListener('focus', () => {
      const history = storage.loadNumberHistory(fieldKey);
      if (history.length === 0) return;
      renderDropdown(dropdownEl, history, (normalized) => {
        input.value = phoneNumber.formatForDisplay(normalized);
        dropdownEl.hidden = true;
        input.blur();
      });
      dropdownEl.hidden = false;
    });

    input.addEventListener('blur', () => {
      setTimeout(() => { dropdownEl.hidden = true; }, 100);
    });

    input.addEventListener('input', () => {
      dropdownEl.hidden = true;
    });
  }

  setupComboBox(myNumberInput, myDropdown, 'my');
  setupComboBox(destNumberInput, destDropdown, 'dest');

  // ── My Phone Number ───────────────────────────────────────────────────────

  myNumberInput.addEventListener('blur', () => {
    const raw = myNumberInput.value.trim();

    if (!raw) {
      myNumber = null;
      myNumberInput.value = '';
      seenMessageSids.clear();
      conversation.load([], 'Enter My Phone Number to get started.');
      clearStatus();
      lastNumbers.my = null;
      storage.saveLastNumbers(lastNumbers);
      return;
    }

    const normalized = phoneNumber.normalize(raw);
    if (!normalized) {
      showStatus('Invalid phone number — try (555) 000-0000 or +15550000000', 'error');
      return;
    }

    if (normalized === myNumber) return;

    myNumber = normalized;
    myNumberInput.value = phoneNumber.formatForDisplay(normalized);
    seenMessageSids.clear();
    clearStatus();
    lastNumbers.my = normalized;
    storage.saveLastNumbers(lastNumbers);
    storage.addToNumberHistory('my', normalized);

    const msgs = storage.loadConversation(normalized);
    conversation.load(msgs, 'No messages yet.');
  });

  myNumberInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') myNumberInput.blur();
  });

  // ── Destination Phone Number ──────────────────────────────────────────────

  destNumberInput.addEventListener('blur', () => {
    const raw = destNumberInput.value.trim();
    if (!raw) {
      lastNumbers.dest = null;
      storage.saveLastNumbers(lastNumbers);
      updateContactHeader(null);
      return;
    }
    const normalized = phoneNumber.normalize(raw);
    if (normalized) {
      destNumberInput.value = phoneNumber.formatForDisplay(normalized);
      lastNumbers.dest = normalized;
      storage.saveLastNumbers(lastNumbers);
      storage.addToNumberHistory('dest', normalized);
      updateContactHeader(normalized);
    }
  });

  destNumberInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') destNumberInput.blur();
  });

  // ── Compose ───────────────────────────────────────────────────────────────

  messageInput.addEventListener('input', () => {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 80) + 'px';
  });

  messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      doSend();
    }
  });

  sendBtn.addEventListener('click', doSend);

  async function doSend() {
    if (!myNumber) {
      showStatus('Enter My Phone Number first.', 'error');
      return;
    }

    const destRaw = destNumberInput.value.trim();
    if (!destRaw) {
      showStatus('Enter a Destination Phone Number.', 'error');
      return;
    }

    const dest = phoneNumber.normalize(destRaw);
    if (!dest) {
      showStatus('Invalid destination phone number.', 'error');
      return;
    }

    const body = messageInput.value.trim();
    if (!body) {
      showStatus('Type a message first.', 'error');
      return;
    }

    sendBtn.disabled = true;
    const result = await routerClient.sendInbound({ from: myNumber, to: dest, body });
    sendBtn.disabled = false;

    if (!result.success) {
      showStatus(result.error.message, 'error');
      return;
    }

    conversation.addOutgoing(body, Date.now());
    storage.saveConversation(myNumber, conversation.getMessages());
    messageInput.value = '';
    messageInput.style.height = 'auto';
    showStatus('Sent', 'success');
  }

  // ── Task 3: Download conversation ─────────────────────────────────────────

  downloadBtn.addEventListener('click', doDownload);

  async function doDownload() {
    if (!myNumber) {
      showStatus('Enter My Phone Number first.', 'error');
      return;
    }

    const msgs = storage.loadConversation(myNumber);

    // Opportunistically fetch routing table for name resolution; never block on it.
    let routingTable = [];
    try {
      const config = await routerClient.getConfig();
      routingTable = Array.isArray(config) ? config : [];
    } catch {
      // Router unavailable — fall through, use raw numbers
    }

    function resolveAppName(number) {
      const entry = routingTable.find(e => e.phoneNumber === number);
      return (entry && entry.name) ? entry.name : null;
    }

    const destRaw = destNumberInput.value.trim();
    const dest = destRaw ? phoneNumber.normalize(destRaw) : null;

    const exportData = {
      exportedAt: new Date().toISOString(),
      myPhoneNumber: myNumber,
      destinationPhoneNumber: dest,
      messages: msgs.map(msg => {
        const counterpart = msg.direction === 'outgoing'
          ? dest
          : (msg.from || null);
        const appName = counterpart ? resolveAppName(counterpart) : null;
        return {
          direction: msg.direction,
          sender: msg.direction === 'incoming' ? (msg.from || myNumber) : myNumber,
          recipient: msg.direction === 'outgoing' ? dest : myNumber,
          body: msg.body,
          timestamp: msg.timestamp ? new Date(msg.timestamp).toISOString() : null,
          resolvedApplicationName: appName || counterpart || null,
        };
      }),
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const dateStr = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    a.download = `testphone-${myNumber.replace(/\+/g, '')}-${dateStr}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showStatus('Downloaded', 'success');
  }

  // ── Task 4: Reset conversation (archive + start fresh) ───────────────────

  resetBtn.addEventListener('click', doReset);

  function doReset() {
    if (!myNumber) {
      showStatus('Enter My Phone Number first.', 'error');
      return;
    }

    if (!confirm('Archive current conversation and start fresh? The history is preserved but will no longer be visible.')) {
      return;
    }

    const msgs = storage.loadConversation(myNumber);
    storage.archiveConversation(myNumber, msgs);
    storage.saveConversation(myNumber, []);
    seenMessageSids.clear();
    conversation.load([], 'No messages yet.');
    showStatus('Conversation archived and reset.', 'success');
  }

  // ── Poll for incoming messages ─────────────────────────────────────────────

  setInterval(async () => {
    if (!myNumber) return;
    const incoming = await routerClient.pollForMessages(myNumber);
    if (incoming.length === 0) return;
    let added = false;
    for (const msg of incoming) {
      if (msg.messageSid && seenMessageSids.has(msg.messageSid)) continue;
      if (msg.messageSid) seenMessageSids.add(msg.messageSid);
      conversation.addIncoming(msg.from, msg.body, msg.timestamp);
      added = true;
    }
    if (added) storage.saveConversation(myNumber, conversation.getMessages());
  }, 1000);

  // ── Easter egg: Ctrl+Shift+C / Cmd+Shift+C ───────────────────────────────

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'C' || e.key === 'c')) {
      e.preventDefault();
      configEditor.open();
    }
  });

  // ── Task 6: Collapsible panel ─────────────────────────────────────────────

  function setPanelCollapsed(collapsed) {
    if (collapsed) {
      controlsCol.classList.add('panel-collapsed');
      panelToggleBtn.textContent = '‹'; // ‹
      panelToggleBtn.setAttribute('aria-label', 'Expand developer controls');
    } else {
      controlsCol.classList.remove('panel-collapsed');
      panelToggleBtn.textContent = '›'; // ›
      panelToggleBtn.setAttribute('aria-label', 'Collapse developer controls');
    }
    try {
      localStorage.setItem(PANEL_STATE_KEY, collapsed ? 'true' : 'false');
    } catch {
      // ignore
    }
  }

  panelToggleBtn.addEventListener('click', () => {
    const nowCollapsed = !controlsCol.classList.contains('panel-collapsed');
    setPanelCollapsed(nowCollapsed);
  });

  // ── Pre-fill from last session ────────────────────────────────────────────

  const saved = storage.loadLastNumbers();
  if (saved.my) {
    myNumber = saved.my;
    lastNumbers.my = saved.my;
    myNumberInput.value = phoneNumber.formatForDisplay(saved.my);
    const msgs = storage.loadConversation(saved.my);
    conversation.load(msgs, 'No messages yet.');
  }
  if (saved.dest) {
    lastNumbers.dest = saved.dest;
    destNumberInput.value = phoneNumber.formatForDisplay(saved.dest);
    updateContactHeader(saved.dest);
  }

  // Restore panel collapsed state
  try {
    const panelSaved = localStorage.getItem(PANEL_STATE_KEY);
    if (panelSaved === 'true') setPanelCollapsed(true);
  } catch {
    // ignore
  }
})();
