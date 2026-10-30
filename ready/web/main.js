/* READY management surface — D002. No participant test player.
 * Accepted key stays in this tab's sessionStorage across reloads, never localStorage/cookies.
 * Render content with textContent, never interpret authored strings as HTML.
 */
(() => {
  'use strict';
  // A fresh iris on each load. The static blue eye remains if fetching is blocked.
  async function refreshEye() {
    const icon = document.querySelector('link[rel="icon"]');
    try {
      const response = await fetch(icon.href);
      if (!response.ok) return;
      const svg = new DOMParser().parseFromString(await response.text(), 'image/svg+xml');
      const random = crypto.getRandomValues(new Uint32Array(3));
      svg.getElementById('iris-color').setAttribute('stop-color', `hsl(${190 + random[0] % 41} 85% 58%)`);
      svg.getElementById('iris-fibers').setAttribute('transform', `rotate(${random[1] % 360} 32 32)`);
      svg.getElementById('pupil').setAttribute('r', String(9 + (random[2] % 31) / 10));
      icon.href = 'data:image/svg+xml,' + encodeURIComponent(new XMLSerializer().serializeToString(svg.documentElement));
    } catch { /* Keep the static eye when offline or in a restricted browser. */ }
  }
  refreshEye();
  const $ = id => document.getElementById(id);
  const preview = /\/ready\/web(?:\/|$)/.test(location.pathname);
  if (preview) {
    $('preview-notice').hidden = false;
    $('environment').textContent = 'Unconnected preview';
    $('connect-form').closest('section').hidden = true;
    $('api-key').disabled = true;
    $('library-list').textContent = 'Preview only. Inventory is available in the operational Firebase workshop.';
  }
  const state = {key: '', kind: 'questions', editing: null, questions: [], answers: [], working: [], test: null, importKey: crypto.randomUUID()};
  const sessionKeyName = 'ready.adminKey';
  function rememberedKey() {
    try { return sessionStorage.getItem(sessionKeyName) || ''; } catch { return ''; }
  }
  function rememberKey(key) {
    try { if (key) sessionStorage.setItem(sessionKeyName, key); else sessionStorage.removeItem(sessionKeyName); }
    catch { /* Storage-blocking browsers can still connect for the current page. */ }
  }
  const split = value => [...new Set(value.split(',').map(x => x.trim()).filter(Boolean))];
  const pretty = value => JSON.stringify(value, null, 2);
  const node = (tag, text, cls) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (cls) el.className = cls; return el; };
  function status(message, error = false) { $('status').textContent = message; $('status').className = error ? 'error' : ''; }
  async function task(work) {
    document.body.classList.add('busy');
    const buttons = [...document.querySelectorAll('button')].filter(button => !button.disabled);
    buttons.forEach(button => button.disabled = true);
    try { await work(); } catch (error) { status(error.message, true); }
    finally { buttons.forEach(button => { if (button.isConnected) button.disabled = false; }); document.body.classList.remove('busy'); duplicateControls(); }
  }
  async function api(path, {method = 'GET', data, key, version, format = 'json'} = {}) {
    if (preview) throw new Error('This is an unconnected preview. Use the operational Firebase workshop for this action.');
    if (!state.key) throw new Error('Connect with your super-admin API key first.');
    const headers = {Authorization: 'Bearer ' + state.key};
    if (data !== undefined) headers['Content-Type'] = 'application/json';
    if (key) headers['Idempotency-Key'] = key;
    if (version) headers['If-Match'] = '"' + version + '"';
    const response = await fetch('/v1/' + path, {method, headers, body: data === undefined ? undefined : JSON.stringify(data), cache: 'no-store'});
    if (response.status === 401) {
      rememberKey(''); state.key = ''; $('environment').textContent = 'Not connected';
    }
    if (response.ok && format === 'pdf') {
      if (!(response.headers.get('Content-Type') || '').includes('application/pdf')) throw new Error('The service did not return a PDF.');
      return response.blob();
    }
    let result;
    try { result = await response.json(); } catch { throw new Error('The service did not return JSON.'); }
    if (!response.ok || !result.ok) {
      const detail = result.error || {};
      const fields = (detail.fields || []).map(item => item.field + ': ' + item.code).join('; ');
      throw new Error((detail.message || 'Request failed') + (fields ? ' ' + fields : ''));
    }
    return result.data;
  }
  async function all(kind, options = {}) {
    const records = []; let cursor = 0;
    do {
      const query = new URLSearchParams({...options, limit: '100', cursor: String(cursor)});
      const page = await api(kind + '?' + query);
      records.push(...page.records); cursor = page.next_cursor;
      if (records.length > 1000) throw new Error('Inventory exceeds this release’s 1000-record bound.');
    } while (cursor !== undefined);
    return records;
  }
  function tab(name) {
    document.querySelectorAll('.panel').forEach(panel => panel.hidden = panel.id !== 'panel-' + name);
    document.querySelectorAll('[data-tab]').forEach(button => { const active = button.dataset.tab === name; button.classList.toggle('active', active); if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current'); });
  }
  document.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', () => tab(button.dataset.tab)));
  function option(select, value, text) { const el = node('option', text); el.value = value; select.append(el); }
  function badge(text, warning = false) { return node('span', text, 'pill' + (warning ? ' warning' : '')); }
  function label(row) { return row.question_text || row.answer_text || row.label || row.id; }
  function card(row, action, buttonLabel = 'Inspect / edit') {
    const el = node('article', undefined, 'record-card');
    el.append(node('h3', label(row)));
    const meta = node('div');
    meta.append(badge(row.is_archived ? 'archived' : row.status || 'preserved', row.is_archived), badge('revision ' + row.revision_number));
    (row.metadata?.tags || []).slice(0, 4).forEach(tag => meta.append(badge(tag)));
    el.append(meta, node('p', row.id));
    const actions = node('div', undefined, 'actions'); const edit = node('button', buttonLabel, 'secondary');
    edit.type = 'button'; edit.addEventListener('click', () => task(() => action(row))); actions.append(edit); el.append(actions); return el;
  }
  async function references() {
    [state.questions, state.answers] = await Promise.all([all('questions'), all('answers')]);
    $('question-reference').replaceChildren();
    state.questions.forEach(row => option($('question-reference'), row.id, label(row)));
  }
  function resetEditor(row = null) {
    state.editing = row;
    $('record-form').reset(); $('connections').replaceChildren();
    const isSet = state.kind === 'sets', isQuestion = state.kind === 'questions';
    $('editor-mode').textContent = row ? 'Inspect revision ' + row.revision_number : 'New ' + (isSet ? 'question–answer set' : isQuestion ? 'question' : 'answer');
    $('text-label').firstChild.textContent = isSet ? 'Set name' : isQuestion ? 'Question' : 'Answer';
    $('question-type-label').hidden = !isQuestion;
    $('question-reference-label').hidden = !isSet;
    $('connections-section').hidden = !isSet;
    $('archive-record').hidden = !row;
    $('archive-record').textContent = row?.is_archived ? 'Restore availability' : 'Archive';
    $('save-record').textContent = row ? 'Save a new preserved revision' : 'Create record';
    if (!row) return;
    $('record-text').value = label(row);
    $('record-state').value = row.status;
    $('question-type').value = row.question_type || 'single_choice';
    const metadata = row.metadata || {}, origin = row.origin || {};
    $('record-description').value = metadata.description || '';
    $('record-difficulty').value = metadata.difficulty || '';
    [['topics', 'topics'], ['audiences', 'audiences'], ['objectives', 'learning_objectives'], ['tags', 'tags']].forEach(([id, field]) => $('record-' + id).value = (metadata[field] || []).join(', '));
    $('record-author').value = origin.author || '';
    $('record-authorship').value = origin.authorship_kind || 'human';
    $('record-source').value = origin.source_reference || '';
    $('record-notes').value = origin.notes || '';
    if (isSet) {
      if (![...$('question-reference').options].some(item => item.value === row.question_id)) option($('question-reference'), row.question_id, 'Historical question · ' + row.question_id);
      $('question-reference').value = row.question_id;
      row.connections.forEach(addConnection);
    }
  }
  function addConnection(value = {}) {
    const row = node('div', undefined, 'connection-row');
    const pair = node('div', undefined, 'two');
    const answerLabel = node('label', 'Answer atom'), answer = node('select'); answer.className = 'connection-answer';
    state.answers.forEach(item => option(answer, item.id, label(item)));
    if (value.answer_id && !state.answers.some(item => item.id === value.answer_id)) option(answer, value.answer_id, 'Historical answer · ' + value.answer_id);
    if (value.answer_id) answer.value = value.answer_id;
    const roleLabel = node('label', 'Role here'), role = node('select'); role.className = 'connection-role';
    ['strong', 'ambiguous', 'incorrect'].forEach(item => option(role, item, item)); role.value = value.role || 'incorrect';
    answerLabel.append(answer); roleLabel.append(role); pair.append(answerLabel, roleLabel);
    const feedbackLabel = node('label', 'Teaching explanation'), feedback = node('textarea'); feedback.rows = 2; feedback.className = 'connection-feedback'; feedback.value = value.feedback || ''; feedbackLabel.append(feedback);
    const notesLabel = node('label', 'Connection notes'), notes = node('input'); notes.className = 'connection-notes'; notes.value = value.notes || ''; notesLabel.append(notes);
    // Preserve rich per-connection metadata when editing; future dimension UI can expand it.
    row._metadata = value.metadata;
    const remove = node('button', 'Remove connection', 'quiet'); remove.type = 'button'; remove.addEventListener('click', () => row.remove());
    row.append(pair, feedbackLabel, notesLabel, remove); $('connections').append(row);
  }
  async function loadLibrary() {
    const list = $('library-list');
    const rows = await all(state.kind, {include_archived: String($('show-archived').checked), include_history: String($('show-history').checked)});
    list.replaceChildren();
    if (!rows.length) list.append(node('p', 'No matching records. Add one or import builder validation data.', 'empty'));
    rows.forEach(row => {
      const el = card(row, async selected => { await references(); resetEditor(selected); });
      if (state.kind === 'sets' && !row.is_archived && row.status === 'published') {
        const add = node('button', 'Add to test', 'quiet'); add.type = 'button';
        add.addEventListener('click', () => task(async () => { const bundle = (await api('sets/' + row.id)).bundle; state.working.push({id: row.id, label: row.label, question_id: bundle.question_id}); renderWorking(); status('Set added to working assembly.'); }));
        el.querySelector('.actions').append(add);
      }
      list.append(el);
    });
  }
  async function connect(key) {
    state.key = key; $('api-key').value = '';
    const capabilities = await api('capabilities');
    rememberKey(state.key);
    $('environment').textContent = capabilities.persistence + ' · super admin';
    if (capabilities.persistence === 'MemoryStore') status('Connected to ephemeral local demo memory. Restarting clears this demo; production records belong in Firestore.');
    else status('Connected to READY · Firestore persistence.');
    await references(); await loadLibrary();
    const schemas = await api('schemas'); $('schema-select').replaceChildren(); option($('schema-select'), '', 'Select a contract'); schemas.schemas.forEach(row => option($('schema-select'), row.name, row.name));
  }
  $('connect-form').addEventListener('submit', event => { event.preventDefault(); const key = $('api-key').value; task(() => connect(key)); });
  $('disconnect').addEventListener('click', () => { rememberKey(''); state.key = ''; state.working = []; state.test = null; state.questions = []; state.answers = []; state.editing = null; $('environment').textContent = 'Disconnected'; location.reload(); });
  $('library-kind').addEventListener('change', () => task(async () => { state.kind = $('library-kind').value; await references(); resetEditor(); await loadLibrary(); }));
  $('new-record').addEventListener('click', () => task(async () => { await references(); resetEditor(); $('record-text').focus(); }));
  ['refresh-library', 'show-archived', 'show-history'].forEach(id => $(id).addEventListener(id === 'refresh-library' ? 'click' : 'change', () => task(loadLibrary)));
  $('add-connection').addEventListener('click', () => addConnection());
  $('record-form').addEventListener('submit', event => { event.preventDefault(); task(async () => {
    const metadata = {topics: split($('record-topics').value), audiences: split($('record-audiences').value), learning_objectives: split($('record-objectives').value), tags: split($('record-tags').value), attributes: state.editing?.metadata?.attributes || {}};
    if ($('record-difficulty').value) metadata.difficulty = $('record-difficulty').value;
    if ($('record-description').value.trim()) metadata.description = $('record-description').value.trim();
    const origin = {author: $('record-author').value.trim(), authorship_kind: $('record-authorship').value, source_reference: $('record-source').value.trim()};
    if ($('record-notes').value.trim()) origin.notes = $('record-notes').value.trim();
    const data = {metadata, origin, status: $('record-state').value};
    if (state.kind === 'questions') Object.assign(data, {question_text: $('record-text').value.trim(), question_type: $('question-type').value});
    else if (state.kind === 'answers') data.answer_text = $('record-text').value.trim();
    else {
      Object.assign(data, {label: $('record-text').value.trim(), question_id: $('question-reference').value});
      data.connections = [...$('connections').children].map(row => {
        const value = {answer_id: row.querySelector('.connection-answer').value, role: row.querySelector('.connection-role').value};
        if (row.querySelector('.connection-feedback').value.trim()) value.feedback = row.querySelector('.connection-feedback').value.trim();
        if (row.querySelector('.connection-notes').value.trim()) value.notes = row.querySelector('.connection-notes').value.trim();
        if (row._metadata) value.metadata = row._metadata;
        return value;
      });
    }
    const row = state.editing ? await api(state.kind + '/' + state.editing.id, {method: 'PATCH', version: state.editing.record_version, data}) : await api(state.kind, {method: 'POST', key: crypto.randomUUID(), data});
    await references(); resetEditor(row); await loadLibrary(); status('Saved revision ' + row.revision_number + '. Earlier content is preserved.');
  }); });
  $('archive-record').addEventListener('click', () => task(async () => {
    const row = state.editing; if (!row) return;
    const reason = prompt('Reason for changing availability (content is retained):'); if (!reason) return;
    const result = await api(state.kind + '/' + row.id + '/archive', {method: 'PUT', data: {is_archived: !row.is_archived, reason, expected_record_version: row.record_version}});
    resetEditor(result); await loadLibrary(); status('Availability updated; history retained.');
  }));
  function duplicateControls() { $('duplicate-pairs').disabled = !$('allow-duplicates').checked; $('arrange-pairs').disabled = !$('allow-duplicates').checked; }
  $('allow-duplicates').addEventListener('change', duplicateControls);
  function renderWorking() {
    $('working-count').textContent = state.working.length;
    $('working-list').replaceChildren();
    if (!state.working.length) $('working-list').append(node('p', 'No sets selected. Found items will stay here until you decide.', 'empty'));
    state.working.forEach((item, index) => { const el = node('div', undefined, 'record-card'); el.append(node('h3', (index + 1) + '. ' + item.label)); const remove = node('button', 'Remove occurrence', 'quiet'); remove.addEventListener('click', () => { state.working.splice(index, 1); renderWorking(); }); el.append(remove); $('working-list').append(el); });
  }
  $('selection-form').addEventListener('submit', event => { event.preventDefault(); task(async () => {
    const criteria = {};
    [['topics', 'topics'], ['audiences', 'audiences'], ['objectives', 'learning_objectives'], ['tags', 'tags']].forEach(([id, field]) => { const value = split($('selection-' + id).value); if (value.length) criteria[field] = value; });
    if ($('selection-difficulty').value) criteria.difficulty = [$('selection-difficulty').value];
    const result = await api('selections', {method: 'POST', data: {target: 'sets', mode: $('selection-mode').value, count: Number($('selection-count').value), criteria, exclude_ids: [...new Set(state.working.map(row => row.id))]}});
    result.items.forEach(row => state.working.push({id: row.id, label: row.label, question_id: row.question_id}));
    renderWorking(); $('shortfall').hidden = !result.shortfall_count;
    $('shortfall-summary').textContent = 'Requested ' + result.requested_count + '; found ' + result.found_count + '; short by ' + result.shortfall_count + '. Your working list now contains ' + state.working.length + ' occurrences.';
    status('Added ' + result.found_count + ' found sets. Nothing has been finalized.');
  }); });
  $('start-over').addEventListener('click', () => { state.working = []; renderWorking(); $('shortfall').hidden = true; status('Working selection cleared. Existing tests are unchanged.'); });
  $('clear-working').addEventListener('click', () => { if (confirm('Clear the unfinalized working assembly?')) { state.working = []; renderWorking(); } });
  $('add-more').addEventListener('click', () => { $('selection-topics').focus(); status('Adjust criteria or count, then find and add more. Current items are retained.'); });
  $('cancel-selection').addEventListener('click', () => { $('shortfall').hidden = true; status('Search canceled. Found items remain until you explicitly clear or use them.'); });
  $('arrange-pairs').addEventListener('click', () => {
    const wanted = Number($('duplicate-pairs').value), counts = new Map(); state.working.forEach(row => counts.set(row.question_id, (counts.get(row.question_id) || 0) + 1));
    let existing = [...counts.values()].filter(value => value === 2).length;
    if ([...counts.values()].some(value => value > 2) || existing > wanted) return status('Remove excess occurrences before arranging pairs. Nothing was discarded.', true);
    const singles = state.working.filter(row => counts.get(row.question_id) === 1);
    if (singles.length < wanted - existing) return status('Not enough distinct single questions to create those pairs. Add more sets.', true);
    for (const item of singles) { if (existing >= wanted) break; state.working.push({...item}); existing++; }
    renderWorking(); status('Arranged ' + wanted + ' duplicate pairs; each paired question occurs exactly twice.');
  });
  async function loadTests() {
    const rows = await all('tests', {include_archived: String($('tests-archived').checked)}); $('test-list').replaceChildren();
    rows.forEach(row => $('test-list').append(card(row, showTest, 'Inspect test')));
    if (!rows.length) $('test-list').append(node('p', 'No preserved tests yet.', 'empty'));
  }
  async function showTest(row) {
    const saved = await api('tests/' + row.id);
    state.test = saved;
    $('test-detail-title').textContent = saved.label;
    $('test-summary').textContent = saved.items.length + ' question occurrences · Author: ' + saved.origin.author + ' · ' + (saved.is_archived ? 'Archived' : 'Preserved') + ' · ID: ' + saved.id;
    $('test-items').replaceChildren();
    saved.items.forEach(item => {
      const question = node('li', undefined, 'record-card');
      question.append(node('h3', item.question_text));
      const answers = node('ul');
      item.answers.forEach(answer => {
        const entry = node('li');
        entry.append(node('span', answer.answer_text + ' '), badge(answer.role));
        if (answer.feedback) entry.append(node('p', answer.feedback, 'hint'));
        answers.append(entry);
      });
      question.append(answers); $('test-items').append(question);
    });
    $('test-json').textContent = pretty(saved);
    $('archive-test').textContent = saved.is_archived ? 'Restore availability' : 'Archive test';
    const detail = $('test-detail');
    detail.hidden = false;
    detail.focus({preventScroll: true});
    detail.scrollIntoView({block: 'start', behavior: 'instant'});
    status('Inspecting saved test: ' + saved.label + '.');
  }
  $('test-form').addEventListener('submit', event => { event.preventDefault(); task(async () => {
    if (!state.working.length) throw new Error('Add at least one set before creating a test.');
    const value = await api('tests', {method: 'POST', key: crypto.randomUUID(), data: {label: $('test-name').value.trim(), metadata: {topics: split($('test-topics').value), tags: split($('test-tags').value)}, origin: {author: $('test-author').value.trim(), authorship_kind: 'human', source_reference: $('test-source').value.trim()}, set_ids: state.working.map(row => row.id), allow_duplicates: $('allow-duplicates').checked, duplicate_pair_count: $('allow-duplicates').checked ? Number($('duplicate-pairs').value) : 0}});
    await showTest(value); await loadTests(); status('Test preserved as ' + value.id + '. Deliver the downloaded bundle through your caller application.');
  }); });
  $('refresh-tests').addEventListener('click', () => task(loadTests)); $('tests-archived').addEventListener('change', () => task(loadTests));
  function downloadBlob(blob, name) { const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
  function download(value, name) { downloadBlob(new Blob([pretty(value)], {type: 'application/json'}), name); }
  $('download-test').addEventListener('click', () => { if (state.test) download(state.test, 'ready-test-' + state.test.id + '.json'); });
  $('download-test-pdf').addEventListener('click', () => task(async () => {
    if (!state.test) throw new Error('Inspect a saved test before downloading its PDF.');
    const pdf = await api('tests/' + state.test.id + '/pdf', {format: 'pdf'});
    downloadBlob(pdf, 'ready-test-' + state.test.id + '.pdf');
    status('Test PDF downloaded. This review copy includes answer classifications and feedback.');
  }));
  $('archive-test').addEventListener('click', () => task(async () => { if (!state.test) return; const reason = prompt('Archive/restore reason:'); if (!reason) return; await api('tests/' + state.test.id + '/archive', {method: 'PUT', data: {is_archived: !state.test.is_archived, reason, expected_record_version: state.test.record_version}}); await showTest(state.test); await loadTests(); status('Test availability changed. Frozen content and results remain.'); }));
  async function loadResults() { const options = {include_history: String($('result-history').checked)}; if ($('result-person').value.trim()) options.person_id = $('result-person').value.trim(); const rows = await all('attempts', options); $('result-list').replaceChildren(); rows.forEach(row => { const display = {...row, label: 'Result · ' + row.test_id.slice(0, 8) + (row.person_id ? ' · ' + row.person_id : ' · anonymous')}; $('result-list').append(card(display, async selected => renderResult(await api('attempts/' + selected.id)), 'Inspect result')); }); if (!rows.length) $('result-list').append(node('p', 'No returned results found.', 'empty')); }
  function renderResult(value) {
    const root = $('result-detail'); root.replaceChildren(); root.append(node('p', 'Preserved result', 'eyebrow'), node('h3', value.attempt_id || value.id));
    const scores = node('div', undefined, 'score-grid'); [['Returned', value.returned_score], ['Calculated', value.calculated_score]].forEach(([title, score]) => { const box = node('div', undefined, 'score'); box.append(node('span', title), node('strong', score.points_earned + ' / ' + score.points_possible)); scores.append(box); }); root.append(scores);
    root.append(node('p', value.score_difference.is_different ? 'The calculated score differs from the returned score. Both are retained.' : 'Returned and calculated scores agree.', value.score_difference.is_different ? 'notice' : 'hint'));
    const table = node('table'), head = node('tr'); ['Question occurrence', 'Credit', 'Ambiguous choices'].forEach(text => head.append(node('th', text))); table.append(head);
    value.item_results.forEach(item => { const row = node('tr'); row.append(node('td', item.question_text), node('td', String(item.credit)), node('td', String(item.ambiguous_answer_ids.length))); table.append(row); }); root.append(table);
    const details = node('details'), summary = node('summary', 'Full report, explanations & history references'); details.append(summary, node('pre', pretty(value))); root.append(details);
  }
  $('result-form').addEventListener('submit', event => { event.preventDefault(); task(async () => { const data = JSON.parse($('result-input').value); if (!data.idempotency_key) { data.idempotency_key = crypto.randomUUID(); $('result-input').value = pretty(data); } const result = await api('attempts', {method: 'POST', data}); renderResult(result); await loadResults(); status('Returned evidence and calculated score recorded. Reusing this submission key retries the same report.'); }); });
  $('new-result-key').addEventListener('click', () => { try { const value = JSON.parse($('result-input').value || '{}'); value.idempotency_key = crypto.randomUUID(); $('result-input').value = pretty(value); status('New submission key assigned. Next submit is a genuine report, not a retry.'); } catch (error) { status(error.message, true); } });
  $('refresh-results').addEventListener('click', () => task(loadResults)); $('result-history').addEventListener('change', () => task(loadResults));
  async function loadFile(input, target) { if (input.files[0]) { const text = await input.files[0].text(); JSON.parse(text); $(target).value = text; } }
  $('result-file').addEventListener('change', () => task(() => loadFile($('result-file'), 'result-input')));
  $('import-file').addEventListener('change', () => task(async () => { await loadFile($('import-file'), 'import-input'); state.importKey = crypto.randomUUID(); }));
  $('load-seed').addEventListener('click', () => task(async () => { const response = await fetch(preview ? '../seed/ai_readiness.json' : './seed.json'); if (!response.ok) throw new Error('Could not load validation seed.'); $('import-input').value = pretty(await response.json()); state.importKey = crypto.randomUUID(); status('Validation seed loaded. Preview it before committing.'); }));
  async function doImport(commit) { const value = JSON.parse($('import-input').value); value.dry_run = !commit; if (commit) { value.idempotency_key = value.idempotency_key || state.importKey; $('import-input').value = pretty(value); } const result = await api('content/imports', {method: 'POST', data: value}); $('import-report').textContent = pretty(result); status(commit ? 'Import recorded. IDs and provenance are preserved.' : result.is_valid ? 'Preview passed; no records were stored.' : 'Preview found issues; no records were stored.', !result.is_valid); if (commit) { await references(); await loadLibrary(); } }
  $('import-form').addEventListener('submit', event => { event.preventDefault(); task(() => doImport(false)); });
  $('commit-import').addEventListener('click', () => task(() => doImport(true)));
  $('schema-select').addEventListener('change', () => task(async () => { if ($('schema-select').value) $('schema-json').textContent = pretty((await api('schemas/' + $('schema-select').value)).schema); }));
  const storedKey = preview ? '' : rememberedKey();
  if (storedKey) task(() => connect(storedKey));
})();
