// enjoy/register/register.js: one script for the three request pages (private, group, class).
// The page sets <main class="reg" data-type="private|group|class">. This script builds the form,
// keeps a draft on this device, checks the answers, and sends one JSON request to our endpoint.
// It never writes to Firestore directly. The rules live on the server (enjoy_router).
(function () {
  'use strict';

  var CONTACT_EMAIL = 'toddbeetcher17@gmail.com';
  // The endpoint address. Local testing uses the address the page was opened from (?endpoint=...).
  // Production: set PROD_ENDPOINT once the function is deployed. Until then the page says so plainly.
  var PROD_ENDPOINT = 'REPLACE_WITH_DEPLOYED_FUNCTION_URL';

  var TYPES = {
    private: { cents: 50000, basis: 'per_session', duration: 120, minCount: 1, showWhere: true, group: false },
    group:   { cents: 50000, basis: 'per_session', duration: 120, minCount: 2, showWhere: true, group: true },
    'class': { cents: 5000,  basis: 'per_person',  duration: null, minCount: 1, showWhere: false, group: false },
  };

  var root = document.querySelector('main.reg');
  if (!root) return;
  var TYPE = root.getAttribute('data-type');
  var CFG = TYPES[TYPE];
  if (!CFG) return;
  var form = document.getElementById('rf');
  if (!form) return;

  function endpoint() {
    var q = new URLSearchParams(location.search).get('endpoint');
    if (q && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?\//.test(q)) return q; // local testing only
    return PROD_ENDPOINT;
  }
  function configured() { return endpoint().indexOf('REPLACE') !== 0; }

  // ---------- tiny helpers ----------
  function h(tag, attrs, kids) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') n.textContent = attrs[k];
      else if (k === 'class') n.className = attrs[k];
      else n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }
  var uid = 0;
  function nextId(p) { uid += 1; return p + '-' + uid; }
  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    var b = new Uint8Array(16); crypto.getRandomValues(b);
    b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
    var s = Array.prototype.map.call(b, function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
    return s.slice(0, 8) + '-' + s.slice(8, 12) + '-' + s.slice(12, 16) + '-' + s.slice(16, 20) + '-' + s.slice(20);
  }
  function todayLocal() {
    var d = new Date();
    return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
  }

  // ---------- field builders ----------
  // Every field is registered in FIELDS so it can be read, restored, checked and flagged.
  var FIELDS = {};

  function errorBox(id) { return h('div', { class: 'rf__error', id: id + '-err', role: 'alert' }); }

  function textField(name, label, o) {
    o = o || {};
    var id = nextId(name);
    var input = h('input', { type: o.type || 'text', id: id, name: name, maxlength: o.max || 200 });
    if (o.autocomplete) input.setAttribute('autocomplete', o.autocomplete);
    if (o.inputmode) input.setAttribute('inputmode', o.inputmode);
    if (o.min) input.setAttribute('min', o.min);
    if (o.placeholder) input.setAttribute('placeholder', o.placeholder);
    var lab = h('label', { class: 'rf__label', for: id }, [label, o.hint ? h('span', { class: 'rf__hint', text: o.hint }) : null]);
    var wrap = h('div', { class: 'rf__field' }, [lab, input, errorBox(id)]);
    FIELDS[name] = { kind: 'text', el: input, wrap: wrap, required: !!o.required, label: o.requiredLabel || label };
    return wrap;
  }
  function areaField(name, label, o) {
    o = o || {};
    var id = nextId(name);
    var input = h('textarea', { id: id, name: name, maxlength: o.max || 2000, rows: 4 });
    if (o.placeholder) input.setAttribute('placeholder', o.placeholder);
    var wrap = h('div', { class: 'rf__field' }, [h('label', { class: 'rf__label', for: id }, [label, o.hint ? h('span', { class: 'rf__hint', text: o.hint }) : null]), input, errorBox(id)]);
    FIELDS[name] = { kind: 'text', el: input, wrap: wrap, required: false, label: label };
    return wrap;
  }
  function selectField(name, label, options, o) {
    o = o || {};
    var id = nextId(name);
    var sel = h('select', { id: id, name: name });
    sel.appendChild(h('option', { value: '', text: o.blank || 'Choose one' }));
    options.forEach(function (op) { sel.appendChild(h('option', { value: op[0], text: op[1] })); });
    var wrap = h('div', { class: 'rf__field' }, [h('label', { class: 'rf__label', for: id }, [label, o.hint ? h('span', { class: 'rf__hint', text: o.hint }) : null]), sel, errorBox(id)]);
    FIELDS[name] = { kind: 'text', el: sel, wrap: wrap, required: !!o.required, label: label };
    return wrap;
  }
  function radioField(name, label, options, o) {
    o = o || {};
    var fs = h('fieldset', { class: 'rf__field', style: 'border:0;padding:0;min-width:0' });
    fs.appendChild(h('legend', { class: 'rf__label' }, [label, o.hint ? h('span', { class: 'rf__hint', text: o.hint }) : null]));
    var box = h('div', { class: 'rf__choices' });
    var inputs = [];
    options.forEach(function (op) {
      var i = h('input', { type: 'radio', name: name, value: op[0] });
      inputs.push(i);
      box.appendChild(h('label', { class: 'rf__choice' }, [i, h('span', { text: op[1] })]));
    });
    fs.appendChild(box);
    fs.appendChild(errorBox(name));
    FIELDS[name] = { kind: 'radio', els: inputs, wrap: fs, required: !!o.required, label: label };
    return fs;
  }
  function checkField(name, label, o) {
    o = o || {};
    var i = h('input', { type: 'checkbox', name: name, id: nextId(name) });
    var wrap = h('div', { class: 'rf__field' }, [h('label', { class: 'rf__choice' }, [i, h('span', { text: label })]), errorBox(name)]);
    FIELDS[name] = { kind: 'check', el: i, wrap: wrap, required: !!o.required, label: label, noDraft: !!o.noDraft };
    return wrap;
  }
  function section(title, kids) {
    var fs = h('fieldset', { class: 'rf__section' }, [h('legend', { text: title })]);
    kids.forEach(function (k) { if (k) fs.appendChild(k); });
    return fs;
  }

  // ---------- participants (other people coming) ----------
  var peopleBox = h('div', { class: 'rf__people' });
  var peopleRows = [];
  function addPerson(v) {
    v = v || {};
    var n = peopleRows.length + 1;
    var row = { first: null, last: null, email: null, age: null, node: null };
    var mk = function (lab, type, key, max, ac) {
      var id = nextId('p' + key);
      var inp = h('input', { type: type, id: id, maxlength: max, autocomplete: ac || 'off' });
      inp.value = v[key] || '';
      row[key] = inp;
      return h('div', { class: 'rf__field' }, [h('label', { class: 'rf__label', for: id, text: lab }), inp]);
    };
    var ageId = nextId('page');
    var age = h('select', { id: ageId });
    [['', 'Prefer not to say'], ['adult', 'Adult'], ['teen', 'Teen'], ['child', 'Child']].forEach(function (o) { age.appendChild(h('option', { value: o[0], text: o[1] })); });
    age.value = v.age || '';
    row.age = age;
    var remove = h('button', { type: 'button', class: 'rf__linkbtn', text: 'Remove' });
    var head = h('div', { class: 'rf__person-head' }, [h('span', { text: 'Person ' + n }), remove]);
    var node = h('div', { class: 'rf__person' }, [
      head,
      h('div', { class: 'rf__row rf__row--2' }, [mk('First name', 'text', 'first', 100, 'off'), mk('Last name', 'text', 'last', 100, 'off')]),
      mk('Email (optional)', 'email', 'email', 200),
      h('div', { class: 'rf__field' }, [h('label', { class: 'rf__label', for: ageId, text: 'Age group (optional)' }), age]),
      h('div', { class: 'rf__error', role: 'alert' }),
    ]);
    row.node = node;
    row.err = node.lastChild;
    remove.addEventListener('click', function () {
      peopleRows.splice(peopleRows.indexOf(row), 1);
      node.remove();
      renumber(); saveDraft(); syncMinors();
    });
    [row.first, row.last, row.email, row.age].forEach(function (e) { e.addEventListener('input', onChange); e.addEventListener('change', onChange); });
    peopleRows.push(row);
    peopleBox.appendChild(node);
    renumber();
  }
  function renumber() {
    peopleRows.forEach(function (r, i) { r.node.querySelector('.rf__person-head span').textContent = 'Person ' + (i + 1); });
  }

  // ---------- build the form ----------
  var summary = h('div', { class: 'rf__summary', id: 'rf-summary', role: 'alert', tabindex: '-1' });
  var status = h('p', { class: 'rf__status', id: 'rf-status', role: 'status', 'aria-live': 'polite' });
  var submit = h('button', { type: 'submit', class: 'btn btn--block rf__submit', id: 'rf-submit', text: TYPE === 'class' ? 'Send my workshop request' : 'Send my request' });

  function build() {
    var parts = [];

    parts.push(section('About you', [
      h('div', { class: 'rf__row rf__row--2' }, [
        textField('first_name', 'First name', { required: true, max: 100, autocomplete: 'given-name' }),
        textField('last_name', 'Last name', { required: true, max: 100, autocomplete: 'family-name' }),
      ]),
      textField('email', 'Email', { type: 'email', required: true, max: 200, autocomplete: 'email', hint: 'We will write to you here.' }),
      textField('phone', 'Phone (optional)', { type: 'tel', max: 40, autocomplete: 'tel' }),
      radioField('preferred_contact_method', 'How would you like to hear from us?', [['email', 'Email'], ['phone', 'Phone']]),
    ]));

    var who = [
      radioField('is_requester_attending', 'Will you be taking part?', [['yes', 'Yes, I will be there'], ['no', 'No, I am arranging this for someone else']], { required: true }),
      textField('attendee_count', 'How many people in total?', { type: 'number', required: true, inputmode: 'numeric', hint: 'Count everyone who would like a seat, including you if you are coming.' }),
    ];
    FIELDS.attendee_count.el.setAttribute('min', String(CFG.minCount));
    FIELDS.attendee_count.el.setAttribute('max', '50');
    who.push(h('p', { class: 'rf__label', text: 'Anyone else coming? You can add their names now, or later.' }));
    who.push(peopleBox);
    var addBtn = h('button', { type: 'button', class: 'rf__linkbtn', text: '+ Add a person' });
    addBtn.addEventListener('click', function () { addPerson(); saveDraft(); });
    who.push(addBtn);
    who.push(radioField('has_minors_present', 'Will anyone under 18 be there?', [['no', 'No'], ['yes', 'Yes']], { required: true, hint: 'We ask so we can plan for it.' }));
    parts.push(section(TYPE === 'class' ? 'Who would come' : 'Who is coming', who));

    var when = [];
    if (CFG.showWhere) {
      when.push(radioField('location_type', 'Where would you like it?', [['home', 'At a home'], ['off_site', 'Somewhere else (a library, cafe, hall, office)']], { required: true }));
      when.push(textField('preferred_location', 'Town or area', { max: 200, hint: 'For example, Boulder, or Louisville.' }));
      when.push(radioField('venue_arrangement', 'Who finds the space?', [['we_have_space', 'We have a place'], ['need_suggestion', 'Please suggest a place']]));
    } else {
      when.push(textField('preferred_location', 'Where would you like it?', { max: 200, hint: 'A town or area. A venue idea is welcome too.' }));
    }
    when.push(textField('requested_date', 'A date that could work (optional)', { type: 'date', min: todayLocal() }));
    when.push(textField('alternate_requested_date', 'Another date (optional)', { type: 'date', min: todayLocal() }));
    when.push(selectField('requested_time_of_day', 'Best time of day (optional)', [['morning', 'Morning'], ['afternoon', 'Afternoon'], ['evening', 'Evening']]));
    when.push(textField('preferred_times', 'Anything else about timing (optional)', { max: 500, hint: 'For example, weekday mornings, or not on Fridays.' }));
    parts.push(section(TYPE === 'class' ? 'Where and when' : 'When and where', when));

    if (CFG.group) {
      parts.push(section('About your group', [
        selectField('group_type', 'What kind of group is it? (optional)', [['family', 'Family'], ['friends', 'Friends'], ['colleagues', 'Colleagues'], ['club_or_nonprofit', 'Club or nonprofit'], ['other', 'Other']]),
        textField('organization_name', 'Organization name (optional)', { max: 200 }),
        checkField('needs_invoice', 'We would need an invoice'),
      ]));
    }

    var aiOpts = []; for (var i = 1; i <= 10; i++) aiOpts.push([String(i), i === 1 ? '1: Never tried it' : (i === 10 ? '10: Use it every day' : String(i))]);
    parts.push(section('A little about you and AI', [
      selectField('proficiency', 'How comfortable are you with AI today? (optional)', aiOpts),
      areaField('what_they_want', 'What would you love to do with it? (optional)', { max: 2000, placeholder: 'Plan a trip, write a great note, fix something...' }),
      textField('how_heard', 'How did you hear about this? (optional)', { max: 200 }),
    ]));

    var hp = h('div', { class: 'rf__hp', 'aria-hidden': 'true' }, [h('label', {}, ['Leave this blank ', h('input', { type: 'text', name: 'website', tabindex: '-1', autocomplete: 'off' })])]);
    FIELDS.website = { kind: 'text', el: hp.querySelector('input'), wrap: hp, required: false, label: 'website', noDraft: true };

    parts.push(section('Permission', [
      checkField('consent_to_contact', 'It is okay for you to contact me about this request.', { required: true, noDraft: true }),
    ]));

    parts.forEach(function (p) { form.appendChild(p); });
    form.appendChild(hp);
    form.appendChild(summary);
    form.appendChild(submit);
    form.appendChild(status);
  }

  // ---------- reading values ----------
  function val(name) {
    var f = FIELDS[name]; if (!f) return '';
    if (f.kind === 'radio') { var on = f.els.filter(function (e) { return e.checked; })[0]; return on ? on.value : ''; }
    if (f.kind === 'check') return f.el.checked;
    return String(f.el.value || '').trim();
  }
  function setVal(name, v) {
    var f = FIELDS[name]; if (!f) return;
    if (f.kind === 'radio') f.els.forEach(function (e) { e.checked = (e.value === v); });
    else if (f.kind === 'check') f.el.checked = !!v;
    else f.el.value = v == null ? '' : v;
  }
  function people() {
    return peopleRows.map(function (r) {
      return { first: r.first.value.trim(), last: r.last.value.trim(), email: r.email.value.trim(), age: r.age.value };
    });
  }
  function anyMinorListed() { return people().some(function (p) { return p.age === 'teen' || p.age === 'child'; }); }
  function syncMinors() {
    if (anyMinorListed()) setVal('has_minors_present', 'yes');
  }

  // ---------- draft saved on this device ----------
  var DRAFT_KEY = 'icdt_reg_draft_' + TYPE;
  var draftNote = document.getElementById('rf-draft');
  var idemKey = null;
  var timer = null;
  function storage() { try { return window.localStorage; } catch (e) { return null; } }
  function collect() {
    var d = { v: 1, fields: {}, people: people(), key: idemKey };
    Object.keys(FIELDS).forEach(function (n) { var f = FIELDS[n]; if (!f.noDraft) d.fields[n] = val(n); });
    return d;
  }
  function saveDraft(now) {
    var s = storage(); if (!s) return;
    clearTimeout(timer);
    var write = function () { try { s.setItem(DRAFT_KEY, JSON.stringify(collect())); } catch (e) {} };
    if (now) write(); else timer = setTimeout(write, 300);
  }
  function loadDraft() {
    var s = storage(); if (!s) return false;
    var raw; try { raw = s.getItem(DRAFT_KEY); } catch (e) { return false; }
    if (!raw) return false;
    var d; try { d = JSON.parse(raw); } catch (e) { return false; }
    if (!d || d.v !== 1) return false;
    var any = false;
    Object.keys(d.fields || {}).forEach(function (n) {
      var v = d.fields[n]; if (v === '' || v === false || v == null) return;
      setVal(n, v); any = true;
    });
    (d.people || []).forEach(function (p) { addPerson(p); any = true; });
    idemKey = d.key || null;
    return any;
  }
  function clearDraft() {
    var s = storage(); if (s) { try { s.removeItem(DRAFT_KEY); } catch (e) {} }
    idemKey = null;
  }
  function onChange() { syncMinors(); saveDraft(); }

  // ---------- checking ----------
  var FRIENDLY = {
    first_name: 'your first name', last_name: 'your last name', email: 'a valid email address',
    is_requester_attending: 'whether you will be taking part', attendee_count: 'how many people in total',
    has_minors_present: 'whether anyone under 18 will be there', location_type: 'where you would like it',
    consent_to_contact: 'your OK for us to contact you', participants: 'the people you are arranging this for',
    requested_date: 'a date that is today or later', alternate_requested_date: 'a date that is today or later',
  };
  function flag(name, msg) {
    var f = FIELDS[name]; if (!f) return;
    var err = f.wrap.querySelector('.rf__error');
    if (err) { err.textContent = msg; err.setAttribute('data-show', '1'); }
    if (f.kind === 'radio') f.els.forEach(function (e) { e.setAttribute('aria-invalid', 'true'); });
    else if (f.el) f.el.setAttribute('aria-invalid', 'true');
  }
  function clearFlags() {
    Object.keys(FIELDS).forEach(function (n) {
      var f = FIELDS[n], err = f.wrap.querySelector('.rf__error');
      if (err) { err.textContent = ''; err.removeAttribute('data-show'); }
      if (f.kind === 'radio') f.els.forEach(function (e) { e.removeAttribute('aria-invalid'); });
      else if (f.el) f.el.removeAttribute('aria-invalid');
    });
    peopleRows.forEach(function (r) { r.err.textContent = ''; r.err.removeAttribute('data-show'); });
    summary.removeAttribute('data-show'); summary.textContent = '';
  }
  function check() {
    var bad = []; // [fieldName, message]
    function need(n, msg) { if (!val(n)) bad.push([n, msg]); }
    need('first_name', 'Please add your first name.');
    need('last_name', 'Please add your last name.');
    var em = val('email');
    if (!em) bad.push(['email', 'Please add your email address.']);
    else if (!/^\S+@\S+\.\S+$/.test(em)) bad.push(['email', 'That email address does not look right.']);
    need('is_requester_attending', 'Please choose one.');
    need('has_minors_present', 'Please choose one.');
    if (CFG.showWhere) need('location_type', 'Please choose where you would like it.');
    var cnt = parseInt(val('attendee_count'), 10);
    var attending = val('is_requester_attending') === 'yes';
    if (!(cnt >= CFG.minCount && cnt <= 50)) bad.push(['attendee_count', TYPE === 'group' ? 'Please enter a number from 2 to 50.' : 'Please enter a number from 1 to 50.']);
    var ppl = people();
    var named = ppl.filter(function (p) { return p.first || p.last || p.email; });
    named.forEach(function (p, i) {
      if (!p.first || !p.last) bad.push(['__person' + i, 'Please add a first and last name for each person, or remove the row.']);
      if (p.email && !/^\S+@\S+\.\S+$/.test(p.email)) bad.push(['__person' + i, 'That email address does not look right.']);
    });
    if (val('is_requester_attending') === 'no' && named.length < 1) bad.push(['is_requester_attending', 'Please add at least one person who will be taking part, below.']);
    if (cnt >= 1 && named.length + (attending ? 1 : 0) > cnt) bad.push(['attendee_count', 'You have listed more people than the total. Please raise the total.']);
    if (named.some(function (p) { return p.age === 'teen' || p.age === 'child'; }) && val('has_minors_present') !== 'yes') bad.push(['has_minors_present', 'You listed someone under 18, so please choose Yes.']);
    ['requested_date', 'alternate_requested_date'].forEach(function (n) {
      var v = val(n); if (v && v < todayLocal()) bad.push([n, 'Please choose today or a later date.']);
    });
    if (!val('consent_to_contact')) bad.push(['consent_to_contact', 'Please tick the box so we can reply to you.']);
    return bad;
  }
  function showProblems(bad) {
    clearFlags();
    bad.forEach(function (b) {
      if (b[0].indexOf('__person') === 0) {
        var i = parseInt(b[0].slice(8), 10);
        var named = peopleRows.filter(function (r) { return r.first.value.trim() || r.last.value.trim() || r.email.value.trim(); });
        var r = named[i]; if (r) { r.err.textContent = b[1]; r.err.setAttribute('data-show', '1'); }
      } else flag(b[0], b[1]);
    });
    summary.textContent = 'Please look at ' + bad.length + (bad.length === 1 ? ' thing' : ' things') + ' above. They are marked in red.';
    summary.setAttribute('data-show', '1');
    var first = form.querySelector('[aria-invalid="true"], .rf__error[data-show="1"]');
    if (first) { var t = first.closest('.rf__field, .rf__person') || first; t.scrollIntoView({ block: 'center', behavior: 'smooth' }); }
  }

  // ---------- building the request ----------
  function buildRequest() {
    var r = { registration_type: TYPE, idempotency_key: idemKey };
    r.first_name = val('first_name'); r.last_name = val('last_name'); r.email = val('email');
    r.consent_to_contact = true;
    r.is_requester_attending = val('is_requester_attending') === 'yes';
    r.has_minors_present = val('has_minors_present') === 'yes';
    r.attendee_count = parseInt(val('attendee_count'), 10);
    r.presented_cost_cents = CFG.cents; r.presented_cost_basis = CFG.basis;
    if (CFG.duration) r.duration_minutes_requested = CFG.duration;
    var strs = ['phone', 'preferred_location', 'requested_date', 'alternate_requested_date', 'requested_time_of_day', 'preferred_times',
      'what_they_want', 'how_heard', 'preferred_contact_method', 'venue_arrangement', 'location_type', 'group_type', 'organization_name'];
    strs.forEach(function (n) { if (FIELDS[n] && val(n)) r[n] = val(n); });
    if (FIELDS.proficiency && val('proficiency')) r.proficiency = parseInt(val('proficiency'), 10);
    if (FIELDS.needs_invoice && val('needs_invoice')) r.needs_invoice = true;
    if (TYPE === 'class') r.no_class_fits = true; // no classes are scheduled yet: this is a request to build one
    var named = people().filter(function (p) { return p.first || p.last || p.email; });
    if (named.length) r.participants = named.map(function (p) {
      var o = { first_name: p.first, last_name: p.last };
      if (p.email) o.email = p.email;
      if (p.age) o.age_band = p.age;
      return o;
    });
    var trap = val('website'); if (trap) r.website = trap;
    return r;
  }

  // ---------- sending ----------
  function say(msg, kind) { status.textContent = msg; status.setAttribute('data-kind', kind || ''); }
  function mailtoLink() {
    var a = h('a', { text: 'Email us instead' });
    a.href = 'mailto:' + CONTACT_EMAIL + '?subject=' + encodeURIComponent('Request: ' + TYPE) + '&body=' + encodeURIComponent('Hello, I tried to send a request on the site and it did not go through.\n\nName: ' + val('first_name') + ' ' + val('last_name') + '\nEmail: ' + val('email') + '\nPeople: ' + val('attendee_count') + '\nWhat I was hoping for: ');
    return a;
  }
  function failure(msg) {
    status.textContent = ''; status.setAttribute('data-kind', 'error');
    status.appendChild(document.createTextNode(msg + ' '));
    status.appendChild(mailtoLink());
    status.appendChild(document.createTextNode('.'));
  }
  function done(data) {
    clearDraft();
    form.style.display = 'none';
    var d = document.getElementById('rf-done');
    d.querySelector('.reg__conf').textContent = data.confirmation_number || '';
    d.setAttribute('data-show', '1');
    d.scrollIntoView({ behavior: 'smooth', block: 'start' });
    var hd = d.querySelector('h2'); hd.setAttribute('tabindex', '-1'); hd.focus({ preventScroll: true });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearFlags(); say('', '');
    var bad = check();
    if (bad.length) { showProblems(bad); return; }
    if (!configured()) { failure('Requests are not connected yet, so nothing was sent.'); return; }
    if (!idemKey) idemKey = uuid();
    saveDraft(true); // keep the key, so a retry after a failure cannot create a second request
    var body = buildRequest();
    submit.disabled = true; say('Sending your request...', '');
    var ctl = ('AbortController' in window) ? new AbortController() : null;
    var to = setTimeout(function () { if (ctl) ctl.abort(); }, 25000);
    fetch(endpoint(), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctl ? ctl.signal : undefined })
      .then(function (res) { return res.json().catch(function () { return null; }).then(function (j) { return { status: res.status, body: j }; }); })
      .then(function (r) {
        clearTimeout(to);
        if (r.body && r.body.ok) { done(r.body.data); return; }
        var err = r.body && r.body.error || {};
        if (r.status === 429 || err.code === 'rate_limited') { failure('That was a lot of tries in a short time. Please wait a few minutes and try again.'); return; }
        if (err.code === 'validation_failed' && err.field_errors && err.field_errors.length) {
          var shown = 0;
          err.field_errors.forEach(function (fe) {
            if (FIELDS[fe.field]) { flag(fe.field, 'Please check ' + (FRIENDLY[fe.field] || 'this answer') + '.'); shown += 1; }
          });
          summary.textContent = shown ? 'Something needs another look. It is marked in red above.' : 'We could not accept that request. Please check your answers.';
          summary.setAttribute('data-show', '1'); summary.focus();
          say('', ''); return;
        }
        failure('We could not send that just now.');
      })
      .catch(function () { clearTimeout(to); failure('We could not reach the server.'); })
      .then(function () { submit.disabled = false; });
  });

  // ---------- start ----------
  build();
  form.addEventListener('input', onChange);
  form.addEventListener('change', onChange);
  var restored = loadDraft();
  if (restored && draftNote) {
    draftNote.setAttribute('data-show', '1');
    var startOver = draftNote.querySelector('button');
    if (startOver) startOver.addEventListener('click', function () {
      clearDraft(); form.reset(); peopleRows.splice(0).forEach(function (r) { r.node.remove(); });
      draftNote.removeAttribute('data-show'); clearFlags();
    });
  }
  if (CFG.minCount > 1 && !val('attendee_count')) setVal('attendee_count', '');
})();
