const conversation = (() => {
  let messages = [];
  let containerEl = null;
  let emptyText = 'No messages yet.';

  function init(el) {
    containerEl = el;
    _render();
  }

  function load(msgs, customEmptyText) {
    messages = Array.isArray(msgs) ? msgs : [];
    if (customEmptyText !== undefined) emptyText = customEmptyText;
    _render();
  }

  function addOutgoing(body, timestamp) {
    messages.push({ direction: 'outgoing', body, timestamp: timestamp || Date.now() });
    _render();
  }

  function addIncoming(from, body, timestamp) {
    messages.push({ direction: 'incoming', from, body, timestamp: timestamp || Date.now() });
    _render(true);
  }

  function getMessages() {
    return messages.slice();
  }

  function _formatTime(ts) {
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function _render(flashLast) {
    if (!containerEl) return;
    containerEl.innerHTML = '';

    if (messages.length === 0) {
      const el = document.createElement('div');
      el.className = 'conversation-empty';
      el.textContent = emptyText;
      containerEl.appendChild(el);
      return;
    }

    for (const msg of messages) {
      const el = document.createElement('div');
      el.className = `message ${msg.direction}`;

      const body = document.createElement('div');
      body.className = 'message-body';
      body.textContent = msg.body;

      const meta = document.createElement('div');
      meta.className = 'message-meta';
      if (msg.direction === 'incoming' && msg.from) {
        meta.textContent = `${phoneNumber.formatForDisplay(msg.from)} · ${_formatTime(msg.timestamp)}`;
      } else {
        meta.textContent = _formatTime(msg.timestamp);
      }

      el.appendChild(body);
      el.appendChild(meta);
      containerEl.appendChild(el);
    }

    containerEl.scrollTop = containerEl.scrollHeight;

    if (flashLast) {
      const last = containerEl.lastElementChild;
      if (last && last.classList.contains('incoming')) {
        last.classList.add('flash');
        last.addEventListener('animationend', () => last.classList.remove('flash'), { once: true });
      }
    }
  }

  return { init, load, addOutgoing, addIncoming, getMessages };
})();
