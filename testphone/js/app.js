(() => {
  const myNumberInput  = document.getElementById('my-number');
  const destNumberInput = document.getElementById('dest-number');
  const messageInput   = document.getElementById('message-input');
  const sendBtn        = document.getElementById('send-btn');
  const statusArea     = document.getElementById('status-area');
  const convContainer  = document.getElementById('conversation');

  let myNumber = null;
  let statusTimer = null;

  conversation.init(convContainer);
  conversation.load([], 'Enter My Phone Number to get started.');
  configEditor.init();

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

  // ── My Phone Number ───────────────────────────────────────────────────────

  myNumberInput.addEventListener('blur', () => {
    const raw = myNumberInput.value.trim();

    if (!raw) {
      myNumber = null;
      myNumberInput.value = '';
      conversation.load([], 'Enter My Phone Number to get started.');
      clearStatus();
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
    clearStatus();

    const msgs = storage.loadConversation(normalized);
    conversation.load(msgs);
  });

  myNumberInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') myNumberInput.blur();
  });

  // ── Destination Phone Number ──────────────────────────────────────────────

  destNumberInput.addEventListener('blur', () => {
    const raw = destNumberInput.value.trim();
    if (!raw) return;
    const normalized = phoneNumber.normalize(raw);
    if (normalized) {
      destNumberInput.value = phoneNumber.formatForDisplay(normalized);
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

  // ── Poll for incoming messages ─────────────────────────────────────────────

  setInterval(async () => {
    if (!myNumber) return;
    const incoming = await routerClient.pollForMessages(myNumber);
    if (incoming.length === 0) return;
    for (const msg of incoming) {
      conversation.addIncoming(msg.from, msg.body, msg.timestamp);
    }
    storage.saveConversation(myNumber, conversation.getMessages());
  }, 1000);

  // ── Easter egg: Ctrl+Shift+C / Cmd+Shift+C ───────────────────────────────

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'C' || e.key === 'c')) {
      e.preventDefault();
      configEditor.open();
    }
  });
})();
