const configEditor = (() => {
  let modalEl, tableBodyEl, addRowBtn, saveBtnEl, cancelBtnEl, closeBtnEl;
  let pendingRows = [];
  let dirty = false;

  function init() {
    modalEl     = document.getElementById('config-modal');
    tableBodyEl = document.getElementById('config-table-body');
    addRowBtn   = document.getElementById('add-row-btn');
    saveBtnEl   = document.getElementById('config-save-btn');
    cancelBtnEl = document.getElementById('config-cancel-btn');
    closeBtnEl  = document.getElementById('modal-close');

    addRowBtn.addEventListener('click', _addRow);
    saveBtnEl.addEventListener('click', _save);
    cancelBtnEl.addEventListener('click', () => _attemptClose());
    closeBtnEl.addEventListener('click', () => _attemptClose());

    modalEl.addEventListener('click', (e) => {
      if (e.target === modalEl) _attemptClose();
    });

    modalEl.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        _attemptClose();
      }
    });
  }

  async function open() {
    const config = await routerClient.getConfig();
    pendingRows = config.map(r => ({ ...r }));
    dirty = false;
    _render();
    modalEl.classList.add('open');
    const firstInput = tableBodyEl.querySelector('input');
    if (firstInput) firstInput.focus();
    else addRowBtn.focus();
  }

  function _close() {
    modalEl.classList.remove('open');
  }

  function _attemptClose() {
    if (dirty) {
      if (confirm('Discard unsaved changes?')) _close();
    } else {
      _close();
    }
  }

  function _addRow() {
    pendingRows.push({ phoneNumber: '', webhookUrl: '' });
    dirty = true;
    _render();
    const phoneInputs = tableBodyEl.querySelectorAll('input[data-field="phoneNumber"]');
    const last = phoneInputs[phoneInputs.length - 1];
    if (last) last.focus();
  }

  function _deleteRow(index) {
    pendingRows.splice(index, 1);
    dirty = true;
    _render();
  }

  function _render(errors) {
    tableBodyEl.innerHTML = '';

    if (pendingRows.length === 0) {
      const tr = document.createElement('tr');
      tr.className = 'config-empty-row';
      const td = document.createElement('td');
      td.colSpan = 3;
      td.textContent = 'No entries. Add a routing entry below.';
      tr.appendChild(td);
      tableBodyEl.appendChild(tr);
      return;
    }

    pendingRows.forEach((row, i) => {
      const rowErrors = errors ? errors.filter(e => e.row === i) : [];
      const phoneError = rowErrors.find(e => e.field === 'phoneNumber');
      const urlError   = rowErrors.find(e => e.field === 'webhookUrl');

      const tr = document.createElement('tr');

      // Phone number cell
      const tdPhone = document.createElement('td');
      const phoneInput = document.createElement('input');
      phoneInput.type = 'tel';
      phoneInput.className = 'config-input' + (phoneError ? ' has-error' : '');
      phoneInput.value = row.phoneNumber;
      phoneInput.placeholder = '+1 (555) 000-0000';
      phoneInput.dataset.field = 'phoneNumber';
      phoneInput.dataset.row = i;
      phoneInput.autocomplete = 'off';
      phoneInput.spellcheck = false;
      phoneInput.addEventListener('input', () => {
        pendingRows[i].phoneNumber = phoneInput.value;
        dirty = true;
      });
      phoneInput.addEventListener('keydown', (e) => _onCellKeydown(e, i, 'phoneNumber'));
      tdPhone.appendChild(phoneInput);
      if (phoneError) {
        const span = document.createElement('span');
        span.className = 'field-error';
        span.textContent = phoneError.message;
        tdPhone.appendChild(span);
      }

      // Webhook URL cell
      const tdUrl = document.createElement('td');
      const urlInput = document.createElement('input');
      urlInput.type = 'text';
      urlInput.className = 'config-input' + (urlError ? ' has-error' : '');
      urlInput.value = row.webhookUrl;
      urlInput.placeholder = 'https://your-app.example.com/sms';
      urlInput.dataset.field = 'webhookUrl';
      urlInput.dataset.row = i;
      urlInput.autocomplete = 'off';
      urlInput.spellcheck = false;
      urlInput.addEventListener('input', () => {
        pendingRows[i].webhookUrl = urlInput.value;
        dirty = true;
      });
      urlInput.addEventListener('keydown', (e) => _onCellKeydown(e, i, 'webhookUrl'));
      tdUrl.appendChild(urlInput);
      if (urlError) {
        const span = document.createElement('span');
        span.className = 'field-error';
        span.textContent = urlError.message;
        tdUrl.appendChild(span);
      }

      // Delete button cell
      const tdDel = document.createElement('td');
      const delBtn = document.createElement('button');
      delBtn.className = 'delete-row-btn';
      delBtn.title = 'Delete row';
      delBtn.innerHTML = '&times;';
      delBtn.addEventListener('click', () => _deleteRow(i));
      tdDel.appendChild(delBtn);

      tr.appendChild(tdPhone);
      tr.appendChild(tdUrl);
      tr.appendChild(tdDel);
      tableBodyEl.appendChild(tr);
    });
  }

  function _onCellKeydown(e, rowIndex, field) {
    if (e.key !== 'Enter') return;
    e.preventDefault();

    if (field === 'phoneNumber') {
      const urlInputs = tableBodyEl.querySelectorAll('input[data-field="webhookUrl"]');
      if (urlInputs[rowIndex]) urlInputs[rowIndex].focus();
    } else {
      const nextPhoneInputs = tableBodyEl.querySelectorAll('input[data-field="phoneNumber"]');
      if (nextPhoneInputs[rowIndex + 1]) {
        nextPhoneInputs[rowIndex + 1].focus();
      } else {
        _addRow();
      }
    }
  }

  async function _save() {
    const result = await routerClient.saveConfig(pendingRows);
    if (!result.success) {
      _render(result.errors);
      return;
    }
    dirty = false;
    _close();
  }

  return { init, open };
})();
