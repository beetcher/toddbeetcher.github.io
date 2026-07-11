const routerEndpoints = (() => {
  const STORAGE_LIST   = 'testphone_router_endpoints';
  const STORAGE_ACTIVE = 'testphone_active_router_endpoint';
  const AUTO_ID = 'auto-detect';

  let overlayEl, listEl, labelInput, urlInput, addBtn, addErrorEl;

  function _loadList() {
    try { return JSON.parse(localStorage.getItem(STORAGE_LIST) || '[]'); } catch { return []; }
  }
  function _saveList(list) { localStorage.setItem(STORAGE_LIST, JSON.stringify(list)); }
  function _getActive() { return localStorage.getItem(STORAGE_ACTIVE) || AUTO_ID; }
  function _setActive(id) { localStorage.setItem(STORAGE_ACTIVE, id); }

  function init() {
    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
      <div id="endpoints-popup" class="endpoints-popup-overlay" role="dialog" aria-label="Router Endpoints">
        <div class="endpoints-popup-box">
          <div class="endpoints-popup-header">
            <span class="endpoints-popup-title">Router Endpoints</span>
            <button id="endpoints-popup-close" class="modal-close-btn" aria-label="Close">&times;</button>
          </div>
          <div id="endpoints-list" class="endpoints-list"></div>
          <div class="endpoints-add-area">
            <div class="endpoints-add-row">
              <input type="text" id="endpoint-label-input" class="endpoint-input endpoint-input-label" placeholder="Label" autocomplete="off" spellcheck="false">
              <input type="url" id="endpoint-url-input" class="endpoint-input endpoint-input-url" placeholder="https://..." autocomplete="off" spellcheck="false">
              <button id="endpoint-add-btn" class="endpoint-add-btn">Add</button>
            </div>
            <span id="endpoint-add-error" class="endpoint-add-error"></span>
          </div>
        </div>
      </div>
    `.trim();
    document.body.appendChild(wrapper.firstElementChild);

    overlayEl  = document.getElementById('endpoints-popup');
    listEl     = document.getElementById('endpoints-list');
    labelInput = document.getElementById('endpoint-label-input');
    urlInput   = document.getElementById('endpoint-url-input');
    addBtn     = document.getElementById('endpoint-add-btn');
    addErrorEl = document.getElementById('endpoint-add-error');

    document.getElementById('endpoints-popup-close').addEventListener('click', close);
    overlayEl.addEventListener('click', (e) => { if (e.target === overlayEl) close(); });
    overlayEl.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { e.preventDefault(); close(); }
    });
    addBtn.addEventListener('click', _addEntry);
    urlInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') _addEntry(); });
  }

  function open() {
    _render();
    overlayEl.classList.add('open');
    labelInput.focus();
  }

  function close() {
    overlayEl.classList.remove('open');
  }

  function _render() {
    const list   = _loadList();
    const active = _getActive();
    listEl.innerHTML = '';

    _appendEntry({ id: AUTO_ID, label: 'Auto-detect (default)', url: null }, active);
    for (const entry of list) {
      _appendEntry(entry, active);
    }

    labelInput.value       = '';
    urlInput.value         = '';
    addErrorEl.textContent = '';
  }

  function _appendEntry(entry, active) {
    const isActive  = entry.id === active;
    const isBuiltin = entry.id === AUTO_ID;

    const row = document.createElement('div');
    row.className = 'endpoint-entry' + (isActive ? ' active' : '');
    row.dataset.id = entry.id;

    const radio = document.createElement('div');
    radio.className = 'endpoint-radio';
    const dot = document.createElement('div');
    dot.className = 'endpoint-radio-dot';
    radio.appendChild(dot);

    const info = document.createElement('div');
    info.className = 'endpoint-info';

    const labelEl = document.createElement('div');
    labelEl.className = 'endpoint-label';
    labelEl.textContent = entry.label;
    info.appendChild(labelEl);

    if (!isBuiltin && entry.url) {
      const urlEl = document.createElement('div');
      urlEl.className = 'endpoint-url';
      urlEl.textContent = entry.url;
      info.appendChild(urlEl);
    }

    row.appendChild(radio);
    row.appendChild(info);

    if (!isBuiltin) {
      const delBtn = document.createElement('button');
      delBtn.className = 'endpoint-delete-btn';
      delBtn.title = 'Remove';
      delBtn.innerHTML = '&times;';
      delBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        _deleteEntry(entry.id);
      });
      row.appendChild(delBtn);
    }

    row.addEventListener('click', () => _selectEntry(entry.id));
    listEl.appendChild(row);
  }

  function _selectEntry(id) {
    _setActive(id);
    _render();
  }

  function _deleteEntry(id) {
    const list = _loadList().filter(e => e.id !== id);
    _saveList(list);
    if (_getActive() === id) _setActive(AUTO_ID);
    _render();
  }

  function _addEntry() {
    const label = labelInput.value.trim();
    const url   = urlInput.value.trim();

    if (!label) {
      addErrorEl.textContent = 'Label is required.';
      labelInput.focus();
      return;
    }

    let parsed;
    try { parsed = new URL(url); } catch { parsed = null; }
    if (!parsed || (parsed.protocol !== 'http:' && parsed.protocol !== 'https:')) {
      addErrorEl.textContent = 'URL must start with http:// or https://';
      urlInput.focus();
      return;
    }

    const id   = 'ep_' + Date.now();
    const list = _loadList();
    list.push({ id, label, url });
    _saveList(list);
    addErrorEl.textContent = '';
    _render();
  }

  return { init, open, close };
})();
