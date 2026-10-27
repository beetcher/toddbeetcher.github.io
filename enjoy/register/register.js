// enjoy/register/register.js: one script for the three request pages (private, group, class).
// The page sets <main class="reg" data-type="private|group|class">. This script builds the form,
// keeps a draft on this device, checks the answers, and sends one JSON request to our endpoint.
// It never writes to Firestore directly. The rules live on the server (enjoy_router).
(function () {
  'use strict';

  var CONTACT_EMAIL = 'toddbeetcher17@gmail.com';
  // The endpoint address. Local testing uses the address the page was opened from (?endpoint=...).
  // Production: set PROD_ENDPOINT once the function is deployed. Until then the page says so plainly.
  var PROD_ENDPOINT = 'https://enjoy-registration-request-o4aryqt6sq-uc.a.run.app';

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
  var LEAN = TYPE === 'private';   // the small ask: name and email up top, the rest is "add details now"
  // Soft email check (the server does the strict one): one @, no spaces, a domain of letters, digits, dots and hyphens with a dot in it.
  // A + before the @ is fine (name+tag@gmail.com); a + after it is not, so that case gets its own hint.
  var EMAIL_OK = /^[^\s@]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$/;
  function emailOk(v) { return EMAIL_OK.test(v); }
  // Says exactly what is wrong with an address ('' when it is fine). Never returns '' when emailOk() is false.
  function emailProblem(v) {
    v = (v || '').trim();
    if (!v) return '';
    if (/\s/.test(v)) return "An email can't contain spaces.";
    var parts = v.split('@');
    if (parts.length < 2) return 'Your email needs an @, like name@gmail.com.';
    if (parts.length > 2) return 'An email can only have one @.';
    var local = parts[0], dom = parts[1], plus = dom.indexOf('+');
    if (!local) return 'Please put your name before the @, like name@gmail.com.';
    if (!dom) return 'Please add the rest after the @, like gmail.com.';
    if (plus >= 0) {
      var tag = dom.slice(plus + 1), base = dom.slice(0, plus);
      if (base && base.indexOf('.') < 0) base += '.com';
      if (local.indexOf('+') < 0 && tag && /^[A-Za-z0-9._-]+$/.test(tag) && /^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$/.test(base)) {
        return 'The +' + tag + ' part has to come before the @. Did you mean ' + local + '+' + tag + '@' + base + '?';
      }
      return 'A + has to come before the @ (name+tag@gmail.com), not after it.';
    }
    if (dom.indexOf('.') < 0) return 'After the @ we need a full address ending like .com, for example name@gmail.com.';
    if (!emailOk(v)) return 'The part after the @ should end like .com, for example name@gmail.com.';
    return '';
  }
  // Domain slips: the typed domain is compared with the big mail providers and, when it is one slip away (a letter swapped, missing,
  // extra or wrong), we ask "Did you mean ...?". Domains in MAIL_OK are real and never questioned. This is a soft question only.
  var MAIL_SUGGEST = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com', 'aol.com', 'comcast.net', 'live.com', 'msn.com', 'me.com', 'protonmail.com', 'sbcglobal.net', 'att.net', 'verizon.net'];
  var MAIL_OK = ['mail.com', 'email.com', 'inbox.com', 'gmx.com', 'gmx.net', 'hey.com', 'zoho.com', 'ymail.com', 'rocketmail.com', 'mac.com', 'pm.me', 'proton.me', 'fastmail.com', 'cox.net', 'charter.net', 'bellsouth.net',
    'earthlink.net', 'frontier.com', 'aim.com', 'hotmail.co.uk', 'yahoo.co.uk', 'live.co.uk', 'outlook.co.uk', 'googlemail.com'];
  function slips(a, b) {   // letters that differ, counting a swapped pair as one slip (optimal string alignment distance)
    var d = [], x, y;
    for (x = 0; x <= a.length; x++) { d[x] = [x]; }
    for (y = 1; y <= b.length; y++) d[0][y] = y;
    for (x = 1; x <= a.length; x++) for (y = 1; y <= b.length; y++) {
      d[x][y] = Math.min(d[x - 1][y] + 1, d[x][y - 1] + 1, d[x - 1][y - 1] + (a[x - 1] === b[y - 1] ? 0 : 1));
      if (x > 1 && y > 1 && a[x - 1] === b[y - 2] && a[x - 2] === b[y - 1]) d[x][y] = Math.min(d[x][y], d[x - 2][y - 2] + 1);
    }
    return d[a.length][b.length];
  }
  function emailTypo(v) {
    var m = /^([^\s@]+)@([^\s@]+)$/.exec((v || '').trim());
    if (!m) return '';
    var dom = m[2].toLowerCase();
    if (MAIL_SUGGEST.indexOf(dom) >= 0 || MAIL_OK.indexOf(dom) >= 0) return '';
    var best = '', bestN = 99;
    MAIL_SUGGEST.forEach(function (k) {
      var n = slips(dom, k);
      if ((n <= 1 || (n === 2 && k.length >= 11)) && n < bestN) { best = k; bestN = n; }
    });
    return best ? m[1] + '@' + best : '';
  }
  var resumeToken = (function () { if (!LEAN) return ''; var t = new URLSearchParams(location.search).get('r'); return t && /^[A-Za-z0-9_-]{43}$/.test(t) ? t : ''; })();   // the receipt-email link
  var form = document.getElementById('rf');
  if (!form) return;

  // Local testing: a page opened from localhost or 127.0.0.1 talks to the Firebase emulator by itself.
  // ?endpoint=<url> overrides that (local addresses only, and it sticks for the tab).
  var LOCAL_EMULATOR = 'http://127.0.0.1:5101/demo-icdt/us-central1/enjoy_registration_request';
  function isLocalPage() { return location.hostname === 'localhost' || location.hostname === '127.0.0.1'; }
  function endpoint() {
    var q = new URLSearchParams(location.search).get('endpoint');
    try {
      if (q && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?\//.test(q)) sessionStorage.setItem('icdt_endpoint', q);
      if (isLocalPage()) { var saved = sessionStorage.getItem('icdt_endpoint'); if (saved) return saved; }
    } catch (e) { /* storage blocked: fall through */ }
    if (q && isLocalPage() && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?\//.test(q)) return q;
    if (isLocalPage()) return LOCAL_EMULATOR;
    return PROD_ENDPOINT;
  }
  // The venue list (private and group pages): active public venues as "Name, Town", read from our server.
  var VENUES_URL = 'https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_public_venues';
  function venuesUrl() {
    var e = endpoint();
    return isLocalPage() ? e.replace('enjoy_registration_request', 'enjoy_public_venues') : VENUES_URL;
  }
  // The curriculum list (private page): active curriculums by title, read from our server.
  var CURRICULUMS_URL = 'https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_public_curriculums';
  function curriculumsUrl() {
    var e = endpoint();
    return isLocalPage() ? e.replace('enjoy_registration_request', 'enjoy_public_curriculums') : CURRICULUMS_URL;
  }
  // The region list (private page): State and Region drop-downs of switched-on places, read from our server.
  var REGIONS_URL = 'https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_public_regions';
  function regionsUrl() {
    var e = endpoint();
    return isLocalPage() ? e.replace('enjoy_registration_request', 'enjoy_public_regions') : REGIONS_URL;
  }

  // The place lookup (private page, P-93): a typed ZIP fills in State and Region (or State and City); a region or a city offers its ZIPs.
  // Any failure is silent: the form works exactly as before without it.
  var ZIPLOOK_URL = 'https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_public_zip';
  function zipLookUrl() {
    var e = endpoint();
    return isLocalPage() ? e.replace('enjoy_registration_request', 'enjoy_public_zip') : ZIPLOOK_URL;
  }
  var ALL_STATES = [['AL', 'Alabama'], ['AK', 'Alaska'], ['AZ', 'Arizona'], ['AR', 'Arkansas'], ['CA', 'California'], ['CO', 'Colorado'], ['CT', 'Connecticut'],
    ['DE', 'Delaware'], ['DC', 'District of Columbia'], ['FL', 'Florida'], ['GA', 'Georgia'], ['HI', 'Hawaii'], ['ID', 'Idaho'], ['IL', 'Illinois'], ['IN', 'Indiana'],
    ['IA', 'Iowa'], ['KS', 'Kansas'], ['KY', 'Kentucky'], ['LA', 'Louisiana'], ['ME', 'Maine'], ['MD', 'Maryland'], ['MA', 'Massachusetts'], ['MI', 'Michigan'],
    ['MN', 'Minnesota'], ['MS', 'Mississippi'], ['MO', 'Missouri'], ['MT', 'Montana'], ['NE', 'Nebraska'], ['NV', 'Nevada'], ['NH', 'New Hampshire'],
    ['NJ', 'New Jersey'], ['NM', 'New Mexico'], ['NY', 'New York'], ['NC', 'North Carolina'], ['ND', 'North Dakota'], ['OH', 'Ohio'], ['OK', 'Oklahoma'],
    ['OR', 'Oregon'], ['PA', 'Pennsylvania'], ['RI', 'Rhode Island'], ['SC', 'South Carolina'], ['SD', 'South Dakota'], ['TN', 'Tennessee'], ['TX', 'Texas'],
    ['UT', 'Utah'], ['VT', 'Vermont'], ['VA', 'Virginia'], ['WA', 'Washington'], ['WV', 'West Virginia'], ['WI', 'Wisconsin'], ['WY', 'Wyoming']];
  var doorOk = false, regionsShown = false, servedOnly = true, zipSeq = 0, citySeq = 0, lastLook = null, cityList = [], zipDatalist = null, regionZipCache = {}, stateCityCache = {};
  function lookup(query, done) {   // one GET to the place lookup; done(data) on success, nothing at all on any failure
    if (!window.fetch) return;
    var ctl = ('AbortController' in window) ? new AbortController() : null;
    var to = setTimeout(function () { if (ctl) ctl.abort(); }, 8000);
    fetch(zipLookUrl() + '?' + query, { method: 'GET', signal: ctl ? ctl.signal : undefined })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { clearTimeout(to); if (j && j.ok && j.data) { doorOk = true; revealServedBox(); done(j.data); } })
      .catch(function () { clearTimeout(to); });
  }
  function revealServedBox() {   // the tick box shows only once the lookup has answered, so a lookup that is down leaves the form as it always was
    if (doorOk && regionsShown && FIELDS.only_served) FIELDS.only_served.wrap.hidden = false;
  }
  function setZipList(items) {   // the ZIP box offers these as you type or from its arrow; typing any other ZIP still works
    if (!zipDatalist) return;
    while (zipDatalist.firstChild) zipDatalist.removeChild(zipDatalist.firstChild);
    items.forEach(function (it) { zipDatalist.appendChild(h('option', { value: it.zip, label: it.zip + (it.town ? ' ' + it.town : '') })); });
  }
  function loadRegionZips(rid) {   // the ZIPs of one served region
    if (!rid) { setZipList([]); return; }
    if (regionZipCache[rid]) { setZipList(regionZipCache[rid]); return; }
    lookup('region=' + encodeURIComponent(rid), function (d) {
      regionZipCache[rid] = Array.isArray(d.zips) ? d.zips : [];
      if (servedOnly && val('region_id') === rid) setZipList(regionZipCache[rid]);
    });
  }
  function zipLook(z) {   // a complete ZIP was typed: fill in the rest for the person (a stale answer is ignored)
    var mine = ++zipSeq;
    lookup('zip=' + encodeURIComponent(z), function (d) {
      if (mine !== zipSeq || val('postal_code') !== z || !d.found) return;
      lastLook = d; applyLook(d);
    });
  }
  function applyLook(d) {
    if (!FIELDS.state_code || FIELDS.state_code.wrap.hidden) return;   // the boxes never loaded: nothing to fill
    if (servedOnly) {
      // a served ZIP picks its State and Region; a ZIP nobody serves leaves them alone (the page line says we will find a trainer)
      if (d.covered && d.region) { FIELDS.state_code.el.value = d.region.state_code; fillRegions(d.region.state_code, d.region.id); rememberRegion(d.region.id); loadRegionZips(d.region.id); }
    } else {
      FIELDS.state_code.el.value = d.state_code; fillCities(d.state_code, d.town);
    }
  }
  function fillAllStates(wanted) {
    var ss = FIELDS.state_code.el;
    while (ss.firstChild) ss.removeChild(ss.firstChild);
    ALL_STATES.forEach(function (c) { ss.appendChild(h('option', { value: c[0], text: c[1] })); });
    ss.value = wanted;
  }
  function fillCities(sc, wantedTown) {   // the City box: the state's biggest cities, plus the town of a typed ZIP
    var sel = FIELDS.city.el, mine = ++citySeq;
    function paint(list) {
      if (mine !== citySeq) return;
      cityList = list;
      while (sel.firstChild) sel.removeChild(sel.firstChild);
      sel.appendChild(h('option', { value: '', text: 'City' }));
      list.forEach(function (c) { sel.appendChild(h('option', { value: c.name, text: c.name })); });
      if (wantedTown && !list.some(function (c) { return c.name === wantedTown; })) sel.appendChild(h('option', { value: wantedTown, text: wantedTown }));
      sel.value = wantedTown || '';
      if (wantedTown) { if (!ZIP_RE.test(val('postal_code'))) onCityPick(); } else onCityPick();
    }
    paint([]);   // the town of a typed ZIP shows at once; the full list follows
    if (stateCityCache[sc]) { paint(stateCityCache[sc]); return; }
    lookup('state=' + encodeURIComponent(sc), function (d) { stateCityCache[sc] = Array.isArray(d.cities) ? d.cities : []; paint(stateCityCache[sc]); });
  }
  function onCityPick() {   // a picked city offers its own ZIPs
    var name = val('city'), c = cityList.filter(function (x) { return x.name === name; })[0];
    setZipList(c ? c.zips.map(function (z) { return { zip: z, town: name }; }) : []);
  }
  function showServedPick() {   // served areas only: the served States, the remembered (else default) Region, and its ZIPs
    var names = {}, codes = [];
    regionList.forEach(function (r) { if (!names[r.state_code]) { names[r.state_code] = r.state_name || r.state_code; codes.push(r.state_code); } });
    var ss = FIELDS.state_code.el;
    while (ss.firstChild) ss.removeChild(ss.firstChild);
    codes.sort(function (a, b) { return names[a].localeCompare(names[b]); }).forEach(function (c) { ss.appendChild(h('option', { value: c, text: names[c] })); });
    var mine = rememberedRegion(), pick = regionList.filter(function (r) { return r.id === mine; })[0]
      || regionList.filter(function (r) { return r.state_code === 'CO' && r.name.toLowerCase() === 'boulder'; })[0] || regionList[0];
    ss.value = pick.state_code; fillRegions(pick.state_code, pick.id); loadRegionZips(pick.id);
  }
  function setServedOnly(on) {   // the "Only areas we serve now" box
    servedOnly = on;
    FIELDS.region_id.wrap.hidden = !on; FIELDS.city.wrap.hidden = on;
    var z = val('postal_code');
    if (on) showServedPick(); else { var sc = val('state_code') || 'CO'; fillAllStates(sc); fillCities(sc, ''); }
    loadVenues(ZIP_RE.test(z) ? z : '');
    if (ZIP_RE.test(z)) zipLook(z);
  }
  var REGION_KEY = 'icdt_region', regionList = [];
  function rememberedRegion() { try { return window.localStorage.getItem(REGION_KEY) || ''; } catch (e) { return ''; } }
  function rememberRegion(id) { try { if (id) window.localStorage.setItem(REGION_KEY, id); } catch (e) { /* storage blocked: no memory, still works */ } }
  function regionId() { return FIELDS.region_id && !FIELDS.region_id.wrap.hidden ? val('region_id') : ''; }
  function fillRegions(stateCode, wanted) {   // the Region box for one state; picks `wanted` if it is there, else the first
    var sel = FIELDS.region_id.el;
    while (sel.firstChild) sel.removeChild(sel.firstChild);
    regionList.filter(function (r) { return r.state_code === stateCode; }).forEach(function (r) { sel.appendChild(h('option', { value: r.id, text: r.name })); });
    if (wanted && regionList.some(function (r) { return r.id === wanted && r.state_code === stateCode; })) sel.value = wanted;
  }
  function loadRegions() {
    if (!LEAN || !FIELDS.region_id || !window.fetch) return;
    var ctl = ('AbortController' in window) ? new AbortController() : null;
    var to = setTimeout(function () { if (ctl) ctl.abort(); }, 8000);
    fetch(regionsUrl(), { method: 'GET', signal: ctl ? ctl.signal : undefined })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        clearTimeout(to);
        if (!(j && j.ok && j.data && Array.isArray(j.data.regions))) return;   // failed: the boxes stay hidden and the form works as before
        regionList = j.data.regions.filter(function (r) { return r && typeof r.id === 'string' && typeof r.name === 'string' && typeof r.state_code === 'string'; });
        if (!regionList.length) return;
        showServedPick();
        FIELDS.state_code.wrap.hidden = false; regionsShown = true; revealServedBox(); FIELDS.region_id.wrap.hidden = !servedOnly; FIELDS.city.wrap.hidden = servedOnly;
        if (ZIP_RE.test(val('postal_code'))) zipLook(val('postal_code'));   // a ZIP this device remembers picks its own State and Region
        loadVenues(ZIP_RE.test(val('postal_code')) ? val('postal_code') : '');
      })
      .catch(function () { clearTimeout(to); });
  }
  function onRegionPick(stateChanged) {
    if (stateChanged) fillRegions(val('state_code'), '');
    rememberRegion(val('region_id'));
    loadRegionZips(val('region_id'));
    shownZip = null;
    loadVenues(ZIP_RE.test(val('postal_code')) ? val('postal_code') : '');
  }
  var pendingCurriculum = '';   // a curriculum saved in the draft, applied once the list has loaded
  function loadCurriculums() {
    if (!LEAN || !FIELDS.curriculum_id || !window.fetch) return;
    var ctl = ('AbortController' in window) ? new AbortController() : null;
    var to = setTimeout(function () { if (ctl) ctl.abort(); }, 8000);
    fetch(curriculumsUrl(), { method: 'GET', signal: ctl ? ctl.signal : undefined })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        clearTimeout(to);
        if (!(j && j.ok && j.data && Array.isArray(j.data.curriculums))) return;   // failed: the box stays hidden
        var sel = FIELDS.curriculum_id.el, cur = sel.value || pendingCurriculum;
        j.data.curriculums.forEach(function (c) {
          if (c && typeof c.id === 'string' && typeof c.title === 'string') sel.appendChild(h('option', { value: c.id, text: c.title }));
        });
        if (sel.options.length < 2) return;
        if (cur) sel.value = cur;
        FIELDS.curriculum_id.wrap.hidden = false;
      })
      .catch(function () { clearTimeout(to); });
  }
  var pendingWhere = '';   // a venue choice saved in the draft, applied once the list has loaded
  var ZIP_KEY = 'icdt_zip', ZIP_RE = /^[0-9]{5}$/;   // any US ZIP code (five digits)
  function rememberedZip() { try { var z = window.localStorage.getItem(ZIP_KEY); return z && ZIP_RE.test(z) ? z : ''; } catch (e) { return ''; } }
  function rememberZip(z) { try { if (z) window.localStorage.setItem(ZIP_KEY, z); else window.localStorage.removeItem(ZIP_KEY); } catch (e) { /* storage blocked: no memory, still works */ } }
  var venueLabels = [], moreSel = null, moreWrap = null, shownZip = null, venueSeq = 0, zipTimer = null;
  function venueText(v) {
    var t = v.town ? v.name + ', ' + v.town : v.name;
    if (typeof v.miles === 'number') t += v.miles < 1 ? ' (under 1 mile)' : ' (' + Math.round(v.miles) + (Math.round(v.miles) === 1 ? ' mile)' : ' miles)');
    return t;
  }
  function clearVenueChoices() {
    var f = FIELDS.location_type; if (!f) return;
    venueLabels.forEach(function (n) { if (n.parentNode) n.parentNode.removeChild(n); });
    venueLabels = []; f.els = f.els.slice(0, 2);
    if (moreWrap && moreWrap.parentNode) moreWrap.parentNode.removeChild(moreWrap);
    moreSel = null; moreWrap = null;
  }
  function syncMore() {   // the dropdown shows a pick that is one of its own, and rests otherwise
    if (!moreSel) return;
    var on = FIELDS.location_type.els.filter(function (e) { return e.checked; })[0];
    var has = on && Array.prototype.some.call(moreSel.options, function (o) { return o.value === on.value; });
    moreSel.value = has ? on.value : '';
  }
  // list: venues from the server. ranked: they came nearest first (the person gave a ZIP code).
  // Up to 5 show as choices; with a ZIP the rest sit in a "More places" dropdown, without one they all sit in a dropdown.
  function renderVenues(list, ranked) {
    var f = FIELDS.location_type; if (!f) return;
    var cur = val('location_type') || pendingWhere;
    clearVenueChoices();
    list = list.filter(function (v) { return v && typeof v.id === 'string' && typeof v.name === 'string'; });
    if (!list.length) return;
    var shown = (list.length <= 5) ? list : (ranked ? list.slice(0, 5) : []);
    var rest = list.slice(shown.length);
    function add(v, hidden) {
      var i = h('input', { type: 'radio', name: 'location_type', value: 'venue:' + v.id });
      f.els.push(i);
      var lab = h('label', { class: 'rf__choice' }, [i, h('span', { text: venueText(v) })]);
      if (hidden) lab.hidden = true;
      f.box.appendChild(lab); venueLabels.push(lab);
      return i;
    }
    shown.forEach(function (v) { add(v, false); });
    if (rest.length) {
      moreSel = h('select', { id: nextId('more_venues'), 'aria-label': ranked ? 'More places, nearest first' : 'Choose a place from the list' });
      moreSel.appendChild(h('option', { value: '', text: ranked ? 'More places…' : 'Choose a place from the list…' }));
      rest.forEach(function (v) { var i = add(v, true); moreSel.appendChild(h('option', { value: i.value, text: venueText(v) })); });
      function pick() { if (moreSel.value) setVal('location_type', moreSel.value); }
      moreSel.addEventListener('input', function (e) { e.stopPropagation(); pick(); onChange(); });   // before the form-wide listener could rest the dropdown
      moreSel.addEventListener('change', pick);
      moreWrap = h('div', { class: 'rf__field', style: 'margin-top:10px' }, [moreSel]);
      f.box.parentNode.insertBefore(moreWrap, f.box.nextSibling);
    }
    if (cur && f.els.some(function (e) { return e.value === cur; })) setVal('location_type', cur);
    syncMore(); updateNeeds();
  }
  var trainerNote = null, trainerZip = '';
  var TRAINER_MSG = "We're securing the best trainer for your area. Go ahead and send your request.";
  function showTrainerNote(zip) {   // a ZIP no active region holds: say so at once; the request is still taken
    if (!trainerNote) return;
    trainerZip = zip; trainerNote.textContent = TRAINER_MSG; trainerNote.setAttribute('data-show', '1');
  }
  function hideTrainerNote() {
    if (!trainerNote) return;
    trainerZip = ''; trainerNote.textContent = ''; trainerNote.removeAttribute('data-show');
  }
  function loadVenues(zip) {
    if (!CFG.showWhere || !window.fetch) return;
    var mine = ++venueSeq;
    var ctl = ('AbortController' in window) ? new AbortController() : null;
    var to = setTimeout(function () { if (ctl) ctl.abort(); }, 8000);
    var q = [], rid = regionId();
    if (zip) q.push('zip=' + encodeURIComponent(zip));
    if (rid) q.push('region=' + encodeURIComponent(rid));
    fetch(venuesUrl() + (q.length ? '?' + q.join('&') : ''), { method: 'GET', signal: ctl ? ctl.signal : undefined })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        clearTimeout(to);
        if (mine !== venueSeq || !(j && j.ok && j.data && Array.isArray(j.data.venues))) return;   // failed or out of date: leave things as they are
        shownZip = zip || '';
        if (LEAN && zip && j.data.covered === false && val('postal_code') === zip) showTrainerNote(zip); else if (trainerZip !== val('postal_code')) hideTrainerNote();
        renderVenues(j.data.venues, !!zip && j.data.venues.some(function (v) { return typeof v.miles === 'number'; }));
      })
      .catch(function () { clearTimeout(to); });
  }
  function onZipInput() {   // remember a good ZIP on this device; refresh the list when it changes
    var z = val('postal_code'), target;
    if (trainerZip && z !== trainerZip) hideTrainerNote();   // the message belongs to the ZIP it was said for
    if (z === '') target = ''; else if (ZIP_RE.test(z)) target = z; else return;   // half-typed: wait
    rememberZip(target);
    if (target) zipLook(target); else zipSeq++;
    if (target === shownZip) return;
    clearTimeout(zipTimer); zipTimer = setTimeout(function () { loadVenues(target); }, 350);
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
    FIELDS[name] = { kind: 'radio', els: inputs, box: box, name: name, wrap: fs, required: !!o.required, label: label };
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
  var AGE_LABEL = { adult: 'adult', teen: 'teen', child: 'child' };
  function personName(r) {
    var n = (r.first.value.trim() + ' ' + r.last.value.trim()).trim();
    return n || 'New person';
  }
  function refreshSummary(r) {
    var age = r.age.value ? ' (' + AGE_LABEL[r.age.value] + ')' : '';
    r.sumText.textContent = personName(r) + age;
  }
  function expandPerson(r) {
    r.collapsed = false;
    r.node.classList.remove('rf__person--collapsed');
    r.editBtn.setAttribute('aria-expanded', 'true');
  }
  function collapsePerson(r) {
    if (!r.first.value.trim() && !r.last.value.trim()) {
      r.err.textContent = 'Please add a first or last name, or remove this person.';
      r.err.setAttribute('data-show', '1');
      return false;
    }
    if (r.email.value.trim() && !emailOk(r.email.value.trim())) {
      r.err.textContent = emailProblem(r.email.value.trim());
      r.err.setAttribute('data-show', '1');
      return false;
    }
    r.err.textContent = ''; r.err.removeAttribute('data-show');
    refreshSummary(r);
    r.collapsed = true;
    r.node.classList.add('rf__person--collapsed');
    r.editBtn.setAttribute('aria-expanded', 'false');
    return true;
  }
  function addPerson(v, startCollapsed) {
    v = v || {};
    var row = { first: null, last: null, email: null, age: null, node: null, collapsed: false };
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

    // One-line summary (shown when the person is collapsed) and the full form (shown while editing).
    var sumText = h('span', { class: 'rf__person-name' });
    var editBtn = h('button', { type: 'button', class: 'rf__linkbtn', text: 'Edit', 'aria-expanded': 'true' });
    var removeSum = h('button', { type: 'button', class: 'rf__linkbtn', text: 'Remove' });
    var sum = h('div', { class: 'rf__person-sum' }, [sumText, h('span', { class: 'rf__person-actions' }, [editBtn, removeSum])]);
    var removeBody = h('button', { type: 'button', class: 'rf__linkbtn', text: 'Remove' });
    var doneBtn = h('button', { type: 'button', class: 'btn rf__done', text: 'Done' });
    var body = h('div', { class: 'rf__person-body' }, [
      h('div', { class: 'rf__person-head' }, [h('span', { class: 'rf__person-title' }), removeBody]),
      h('div', { class: 'rf__row rf__row--2' }, [mk('First name', 'text', 'first', 100, 'off'), mk('Last name', 'text', 'last', 100, 'off')]),
      h('div', { class: 'rf__row rf__row--2' }, [
        mk('Email (optional)', 'email', 'email', 200),
        h('div', { class: 'rf__field' }, [h('label', { class: 'rf__label', for: ageId, text: 'Age group (optional)' }), age]),
      ]),
      h('div', { class: 'rf__error', role: 'alert' }),
      doneBtn,
    ]);
    var node = h('div', { class: 'rf__person' }, [sum, body]);
    row.node = node; row.sumText = sumText; row.editBtn = editBtn;
    row.err = body.querySelector('.rf__error');
    var remove = function () {
      peopleRows.splice(peopleRows.indexOf(row), 1);
      node.remove();
      renumber(); saveDraft(); syncMinors();
    };
    removeSum.addEventListener('click', remove);
    removeBody.addEventListener('click', remove);
    editBtn.addEventListener('click', function () { expandPerson(row); row.first.focus(); });
    doneBtn.addEventListener('click', function () { if (collapsePerson(row)) saveDraft(); });
    [row.first, row.last, row.email, row.age].forEach(function (e) { e.addEventListener('input', onChange); e.addEventListener('change', onChange); });
    peopleRows.push(row);
    peopleBox.appendChild(node);
    renumber();
    refreshSummary(row);
    if (startCollapsed && (row.first.value.trim() || row.last.value.trim())) collapsePerson(row);
    return row;
  }
  function renumber() {
    peopleRows.forEach(function (r, i) { r.node.querySelector('.rf__person-title').textContent = 'Person ' + (i + 1); });
  }

  // ---------- build the form ----------
  var summary = h('div', { class: 'rf__summary', id: 'rf-summary', role: 'alert', tabindex: '-1' });
  var status = h('p', { class: 'rf__status', id: 'rf-status', role: 'status', 'aria-live': 'polite' });
  var submit = h('button', { type: 'submit', class: 'btn btn--block rf__submit', id: 'rf-submit', text: TYPE === 'class' ? 'Send my workshop request' : 'Send my request' });

  var moreBox = null;       // the closed "a little more" section
  var needBox = null;       // the checklist at the top
  var NEEDS = [];           // [{label, field, done()}]
  function build() {
    // ===== What we need (everything here is required) =====
    var need = [
      h('div', { class: 'rf__row rf__row--2' }, [
        textField('first_name', 'First name', { required: true, max: 100, autocomplete: 'given-name' }),
        textField('last_name', 'Last name', { required: true, max: 100, autocomplete: 'family-name' }),
      ]),
      textField('email', 'Email', { type: 'email', required: true, max: 200, autocomplete: 'email', hint: 'We will write to you here.' }),
    ];
    var detailAsk = [
      radioField('is_requester_attending', 'Will you be taking part?', [['yes', 'Yes, I will be there'], ['no', 'No, I am arranging this for someone else']], { required: !LEAN }),
      textField('attendee_count', 'How many people in total?', { type: 'number', required: !LEAN, inputmode: 'numeric', hint: 'Count everyone who would like a seat, including you if you are coming.' }),
      radioField('has_minors_present', 'Will anyone under 18 be there?', [['no', 'No'], ['yes', 'Yes']], { required: !LEAN, hint: 'We ask so we can plan for it.' }),
    ];
    FIELDS.attendee_count.el.setAttribute('min', String(CFG.minCount));
    FIELDS.attendee_count.el.setAttribute('max', '50');
    if (LEAN) {
      need.push(selectField('curriculum_id', 'What would you like to learn?', [], { blank: 'Not sure yet / any', hint: 'Pick a topic, or leave it and we will help you choose.' }));
      FIELDS.curriculum_id.wrap.hidden = true;   // shown once the list arrives; if it never does, the form works without it
    } else {
      need = need.concat(detailAsk); detailAsk = [];
    }
    var whereAsk = [];
    if (CFG.showWhere) {
      var zipField = textField('postal_code', LEAN ? 'ZIP code' : 'ZIP code (optional)', { max: 5, inputmode: 'numeric', autocomplete: 'postal-code', hint: LEAN ? 'Helps us find a place near you, and shows us where people want classes. Not required, but it helps a lot.' : 'Enter the ZIP code where you would like it, and we will show the closest places first.' });
      FIELDS.postal_code.noDraft = true;   // remembered on its own, below
      trainerNote = h('div', { class: 'rf__note', role: 'status', 'aria-live': 'polite' });   // shown when no active region holds the ZIP (P-83)
      zipField.appendChild(trainerNote);
      if (LEAN) {
        zipDatalist = h('datalist', { id: nextId('zip_list') });   // the ZIPs of the chosen region or city, offered as you type
        FIELDS.postal_code.el.setAttribute('list', zipDatalist.id);
        zipField.appendChild(zipDatalist);
        need.push(zipField);   // the ZIP comes first: typing it fills in the State and Region (or City) for the person
        var servedBox = checkField('only_served', 'Only show areas we serve now', { noDraft: true });
        FIELDS.only_served.el.checked = true;
        servedBox.appendChild(h('span', { class: 'rf__hint', text: 'Untick it to use any ZIP in the US. We will fill in the city and state.' }));
        need.push(servedBox);
        need.push(h('div', { class: 'rf__row rf__row--2' }, [
          selectField('state_code', 'State', [], { blank: 'State' }),
          selectField('region_id', 'Region', [], { blank: 'Region' }),
          selectField('city', 'City', [], { blank: 'City' }),
        ]));
        ['state_code', 'region_id', 'city', 'only_served'].forEach(function (n) { FIELDS[n].noDraft = true; FIELDS[n].wrap.hidden = true; });   // shown once the list arrives; remembered on its own
        FIELDS.only_served.el.addEventListener('change', function () { setServedOnly(FIELDS.only_served.el.checked); });
        FIELDS.state_code.el.addEventListener('change', function () { if (servedOnly) onRegionPick(true); else { fillCities(val('state_code'), ''); loadVenues(ZIP_RE.test(val('postal_code')) ? val('postal_code') : ''); } });
        FIELDS.region_id.el.addEventListener('change', function () { onRegionPick(false); });
        FIELDS.city.el.addEventListener('change', onCityPick);
      } else whereAsk.push(zipField);
      whereAsk.push(radioField('location_type', 'Where would you like it?', [['home', 'At a home'], ['off_site', 'A public place (a library, cafe, hall or office)']], { required: !LEAN }));
      if (!LEAN) { need = need.concat(whereAsk); whereAsk = []; }
    }
    var parts = [section('What we need', need)];

    // ===== A little more (all optional, closed to begin with) =====
    var more = detailAsk.concat(whereAsk);
    more.push(textField('phone', 'Phone (optional)', { type: 'tel', max: 40, autocomplete: 'tel' }));
    more.push(radioField('preferred_contact_method', 'How would you like to hear from us? (optional)', [['email', 'Email'], ['phone', 'Phone']]));

    more.push(h('p', { class: 'rf__label', text: 'Anyone else coming? (optional) You can add their names now, or later.' }));
    more.push(peopleBox);
    var addBtn = h('button', { type: 'button', class: 'rf__linkbtn', text: '+ Add a person' });
    addBtn.addEventListener('click', function () {
      // tidy the people already added, so the list stays short
      peopleRows.forEach(function (r) { if (!r.collapsed) collapsePerson(r); });
      var r = addPerson(); r.first.focus(); saveDraft();
    });
    more.push(addBtn);

    if (CFG.showWhere) {
      more.push(textField('preferred_location', 'Town or area (optional)', { max: 200, hint: 'For example, Boulder, or Louisville.' }));
      more.push(radioField('venue_arrangement', 'Who finds the space? (optional)', [['we_have_space', 'We have a place'], ['need_suggestion', 'Please suggest a place']]));
    } else {
      more.push(textField('preferred_location', 'Where would you like it? (optional)', { max: 200, hint: 'A town or area. A venue idea is welcome too.' }));
    }
    more.push(textField('requested_date', 'A date that could work (optional)', { type: 'date', min: todayLocal() }));
    more.push(textField('alternate_requested_date', 'Another date (optional)', { type: 'date', min: todayLocal() }));
    more.push(selectField('requested_time_of_day', 'Best time of day (optional)', [['morning', 'Morning'], ['afternoon', 'Afternoon'], ['evening', 'Evening']]));
    more.push(textField('preferred_times', 'Anything else about timing (optional)', { max: 500, hint: 'For example, weekday mornings, or not on Fridays.' }));

    if (CFG.group) {
      more.push(selectField('group_type', 'What kind of group is it? (optional)', [['family', 'Family'], ['friends', 'Friends'], ['colleagues', 'Colleagues'], ['club_or_nonprofit', 'Club or nonprofit'], ['other', 'Other']]));
      more.push(textField('organization_name', 'Organization name (optional)', { max: 200 }));
      more.push(checkField('needs_invoice', 'We would need an invoice (optional)'));
    }

    var aiOpts = []; for (var i = 1; i <= 10; i++) aiOpts.push([String(i), i === 1 ? '1: Never tried it' : (i === 10 ? '10: Use it every day' : String(i))]);
    more.push(selectField('proficiency', 'How comfortable are you with AI today? (optional)', aiOpts));
    more.push(areaField('what_they_want', 'What would you love to do with it? (optional)', { max: 2000, placeholder: 'Plan a trip, write a great note, fix something...' }));
    more.push(textField('how_heard', 'How did you hear about this? (optional)', { max: 200 }));

    moreBox = h('details', { class: 'rf__more' }, [
      h('summary', {}, [h('span', { class: 'rf__more-title', text: LEAN ? 'Add details now, if you like' : 'A little more, if you like' }), h('span', { class: 'rf__more-sub', text: LEAN ? 'All optional. How many, where, dates, and a few questions about you. You can finish these later.' : 'All optional. Dates, names of others, and a few questions about you.' })]),
      h('div', { class: 'rf__more-body' }, more),
    ]);
    parts.push(moreBox);

    var hp = h('div', { class: 'rf__hp', 'aria-hidden': 'true' }, [h('label', {}, ['Leave this blank ', h('input', { type: 'text', name: 'website', tabindex: '-1', autocomplete: 'off' })])]);
    FIELDS.website = { kind: 'text', el: hp.querySelector('input'), wrap: hp, required: false, label: 'website', noDraft: true };

    parts.push(section('One last thing', [
      checkField('consent_to_contact', 'It is okay for you to contact me about this request.', { required: true, noDraft: true }),
    ]));

    // ===== The checklist at the top =====
    NEEDS = [
      { label: 'Your name', field: 'first_name', done: function () { return !!(val('first_name') && val('last_name')); } },
      { label: 'Your email', field: 'email', done: function () { return emailOk(val('email')); } }
    ];
    if (!LEAN) {
      NEEDS.push({ label: 'Taking part?', field: 'is_requester_attending', done: function () { return !!val('is_requester_attending'); } });
      NEEDS.push({ label: 'How many people', field: 'attendee_count', done: function () { var c = parseInt(val('attendee_count'), 10); return c >= CFG.minCount && c <= 50; } });
      NEEDS.push({ label: 'Anyone under 18?', field: 'has_minors_present', done: function () { return !!val('has_minors_present'); } });
      if (CFG.showWhere) NEEDS.push({ label: 'Where', field: 'location_type', done: function () { return !!val('location_type'); } });
    }
    NEEDS.push({ label: 'OK to contact you', field: 'consent_to_contact', done: function () { return !!val('consent_to_contact'); } });

    needBox = h('div', { class: 'rf__need', id: 'rf-need' });
    var needHead = h('p', { class: 'rf__need-head' }, [h('strong', { class: 'rf__need-count' }), h('span', { class: 'rf__need-sub', text: ' needed to send this. Everything else is optional.' })]);
    var needList = h('ul', { class: 'rf__need-list' });
    NEEDS.forEach(function (n) {
      var a = h('button', { type: 'button', class: 'rf__need-item', text: n.label });
      a.addEventListener('click', function () { jumpTo(n.field); });
      n.node = h('li', {}, [a]);
      needList.appendChild(n.node);
    });
    needBox.appendChild(needHead); needBox.appendChild(needList);
    needBox._count = needHead.querySelector('.rf__need-count');
    needHead.addEventListener('click', function () { needBox.setAttribute('data-open', needBox.getAttribute('data-open') === '1' ? '0' : '1'); });
    var sentinel = h('div', { class: 'rf__need-sentinel', 'aria-hidden': 'true' });
    var stickQueued = false;
    function checkStuck() {
      stickQueued = false;
      var stuck = sentinel.getBoundingClientRect().top < 0;
      if (needBox.getAttribute('data-stuck') === (stuck ? '1' : '0')) return;
      needBox.setAttribute('data-stuck', stuck ? '1' : '0');
      if (!stuck) needBox.setAttribute('data-open', '0');
    }
    function queueStuck() { if (!stickQueued) { stickQueued = true; (window.requestAnimationFrame || setTimeout)(checkStuck); } }
    window.addEventListener('scroll', queueStuck, { passive: true });
    window.addEventListener('resize', queueStuck);

    form.appendChild(sentinel);
    form.appendChild(needBox);
    queueStuck();
    parts.forEach(function (p) { form.appendChild(p); });
    form.appendChild(hp);
    form.appendChild(summary);
    form.appendChild(submit);
    form.appendChild(status);
  }
  function jumpTo(name) {
    var f = FIELDS[name]; if (!f) return;
    f.wrap.scrollIntoView({ block: 'center', behavior: 'smooth' });
    var t = f.kind === 'radio' ? f.els[0] : f.el;
    if (t) setTimeout(function () { try { t.focus({ preventScroll: true }); } catch (e) {} }, 250);
  }
  function updateNeeds() {
    if (!needBox) return;
    var left = 0;
    NEEDS.forEach(function (n) {
      var ok = n.done();
      if (!ok) left += 1;
      n.node.setAttribute('data-done', ok ? '1' : '0');
      var b = n.node.firstChild;
      b.textContent = (ok ? '✓ ' : '') + n.label;
      b.setAttribute('aria-label', n.label + (ok ? ', done' : ', still needed'));
    });
    needBox.setAttribute('data-all', left === 0 ? '1' : '0');
    needBox._count.textContent = left === 0 ? 'Everything we need is here.' : (left === NEEDS.length ? NEEDS.length + ' things' : left + (left === 1 ? ' thing' : ' things') + ' still');
    needBox.querySelector('.rf__need-sub').textContent = left === 0 ? ' You can send it now, or add more below.' : ' needed to send this. Everything else is optional.';
  }
  function openMoreIfFilled() {
    if (!moreBox) return;
    var filled = peopleRows.length > 0;
    Object.keys(FIELDS).forEach(function (n) {
      var f = FIELDS[n];
      if (f.noDraft || NEEDS.some(function (x) { return x.field === n; }) || n === 'last_name' || n === 'location_type' || n === 'curriculum_id') return;
      var v = val(n); if (v && v !== '') filled = true;
    });
    if (filled) moreBox.open = true;
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
    if (resumeToken) return;   // finishing an existing request through its email link: nothing is saved on this device
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
      if (n === 'location_type' && String(v).indexOf('venue:') === 0) pendingWhere = v;
      if (n === 'curriculum_id') { pendingCurriculum = v; return; }
      setVal(n, v); any = true;
    });
    (d.people || []).forEach(function (p) { addPerson(p, true); any = true; });
    idemKey = d.key || null;
    return any;
  }
  function clearDraft() {
    var s = storage(); if (s) { try { s.removeItem(DRAFT_KEY); } catch (e) {} }
    idemKey = null;
  }
  function onChange() { syncMinors(); syncMore(); saveDraft(); updateNeeds(); }

  // ---------- checking ----------
  var FRIENDLY = {
    first_name: 'your first name', last_name: 'your last name', email: 'a valid email address',
    is_requester_attending: 'whether you will be taking part', attendee_count: 'how many people in total',
    has_minors_present: 'whether anyone under 18 will be there', location_type: 'where you would like it', postal_code: 'a five-digit ZIP code',
    curriculum_id: 'what you would like to learn', consent_to_contact: 'your OK for us to contact you', participants: 'the people you are arranging this for',
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
    else if (!emailOk(em)) bad.push(['email', emailProblem(em)]);
    if (!LEAN) {
      need('is_requester_attending', 'Please choose one.');
      need('has_minors_present', 'Please choose one.');
      if (CFG.showWhere) need('location_type', 'Please choose where you would like it.');
    }
    if (CFG.showWhere && val('postal_code') && !ZIP_RE.test(val('postal_code'))) bad.push(['postal_code', 'Please use a five-digit ZIP code, like 80027, or leave it blank.']);
    var cnt = parseInt(val('attendee_count'), 10);
    var attending = val('is_requester_attending') === 'yes';
    var cntGiven = !isNaN(cnt) || !LEAN;
    if (cntGiven && !(cnt >= CFG.minCount && cnt <= 50)) bad.push(['attendee_count', TYPE === 'group' ? 'Please enter a number from 2 to 50.' : 'Please enter a number from 1 to 50.']);
    var ppl = people();
    var named = ppl.filter(function (p) { return p.first || p.last || p.email; });
    named.forEach(function (p, i) {
      if (!p.first && !p.last) bad.push(['__person' + i, 'Please add a first or last name for each person, or remove the row.']);
      if (p.email && !emailOk(p.email)) bad.push(['__person' + i, emailProblem(p.email)]);
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
    if (moreBox) bad.forEach(function (b) { var f = FIELDS[b[0]]; if (b[0].indexOf('__person') === 0 || (f && moreBox.contains(f.wrap))) moreBox.open = true; });
    bad.forEach(function (b) {
      if (b[0].indexOf('__person') === 0) {
        var i = parseInt(b[0].slice(8), 10);
        var named = peopleRows.filter(function (r) { return r.first.value.trim() || r.last.value.trim() || r.email.value.trim(); });
        var r = named[i]; if (r) { expandPerson(r); r.err.textContent = b[1]; r.err.setAttribute('data-show', '1'); }
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
    // Only what was answered is sent. An unanswered question is never sent as "no" or "zero".
    if (val('is_requester_attending')) r.is_requester_attending = val('is_requester_attending') === 'yes';
    if (val('has_minors_present')) r.has_minors_present = val('has_minors_present') === 'yes';
    if (val('attendee_count')) r.attendee_count = parseInt(val('attendee_count'), 10);
    if (FIELDS.curriculum_id && val('curriculum_id')) r.curriculum_id = val('curriculum_id');
    if (!resumeToken && regionId()) r.region_id = regionId();
    r.presented_cost_cents = CFG.cents; r.presented_cost_basis = CFG.basis;
    if (CFG.duration) r.duration_minutes_requested = CFG.duration;
    var strs = ['phone', 'preferred_location', 'requested_date', 'alternate_requested_date', 'requested_time_of_day', 'preferred_times',
      'what_they_want', 'how_heard', 'preferred_contact_method', 'venue_arrangement', 'location_type', 'group_type', 'organization_name'];
    strs.forEach(function (n) { if (FIELDS[n] && val(n)) r[n] = val(n); });
    if (CFG.showWhere && ZIP_RE.test(val('postal_code'))) r.postal_code = val('postal_code');
    if (String(r.location_type || '').indexOf('venue:') === 0) {   // a venue from the list: a public place, plus which one
      r.preferred_venue_id = r.location_type.slice(6);
      r.location_type = 'off_site';
    }
    if (FIELDS.proficiency && val('proficiency')) r.proficiency = parseInt(val('proficiency'), 10);
    if (FIELDS.needs_invoice && val('needs_invoice')) r.needs_invoice = true;
    if (TYPE === 'class') r.no_class_fits = true; // no classes are scheduled yet: this is a request to build one
    var named = people().filter(function (p) { return p.first || p.last || p.email; });
    if (named.length) r.participants = named.map(function (p) {
      var o = {};
      if (p.first) o.first_name = p.first;
      if (p.last) o.last_name = p.last;
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
    d.querySelector('.reg__conf').textContent = (data && data.confirmation_number) || resumeConf || '';
    if (resumeAnswers) { d.querySelector('h2').textContent = 'Thank you. Your details are saved.'; }
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
    var url = endpoint(), payload = body;
    if (resumeAnswers) { url = completionUrl(); payload = { t: resumeToken, changes: diffChanges(body) }; if (body.website) payload.website = body.website; }
    submit.disabled = true; say(resumeAnswers ? 'Saving your details...' : 'Sending your request...', '');
    var ctl = ('AbortController' in window) ? new AbortController() : null;
    var to = setTimeout(function () { if (ctl) ctl.abort(); }, 25000);
    fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: ctl ? ctl.signal : undefined })
      .then(function (res) { return res.json().catch(function () { return null; }).then(function (j) { return { status: res.status, body: j }; }); })
      .then(function (r) {
        clearTimeout(to);
        if (r.body && r.body.ok) { done(r.body.data); return; }
        var err = r.body && r.body.error || {};
        if (err.code === 'already_scheduled') { failure('This request has already been scheduled, so it cannot be changed here. Please reply to the email we sent you.'); return; }
        if (r.status === 429 || err.code === 'rate_limited') { failure('That was a lot of tries in a short time. Please wait a few minutes and try again.'); return; }
        if (err.code === 'validation_failed' && err.field_errors && err.field_errors.length) {
          var shown = 0;
          err.field_errors.forEach(function (fe) {
            if (FIELDS[fe.field]) { if (moreBox && moreBox.contains(FIELDS[fe.field].wrap)) moreBox.open = true; flag(fe.field, 'Please check ' + (FRIENDLY[fe.field] || 'this answer') + '.'); shown += 1; }
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

  // ---------- the completion link (?r=<token>), private page only ----------
  // The receipt email links back to the SAME request. We read its answers, fill the form, and save changes to that request; a second request is never made.
  var COMPLETION_URL = 'https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_request_completion';
  function completionUrl() { var e = endpoint(); return isLocalPage() ? e.replace('enjoy_registration_request', 'enjoy_request_completion') : COMPLETION_URL; }
  var LOCKED_KEYS = ['registration_type', 'idempotency_key', 'first_name', 'last_name', 'email', 'consent_to_contact', 'presented_cost_cents', 'presented_cost_basis',
    'scheduled_class_id', 'no_class_fits', 'website'];
  var MANAGED_KEYS = ['phone', 'preferred_location', 'requested_date', 'alternate_requested_date', 'requested_time_of_day', 'preferred_times', 'what_they_want',
    'how_heard', 'preferred_contact_method', 'venue_arrangement', 'location_type', 'preferred_venue_id', 'postal_code', 'curriculum_id', 'is_requester_attending',
    'has_minors_present', 'attendee_count', 'proficiency', 'needs_invoice', 'participants'];   // the questions this page can show; anything else is never cleared
  function canon(v) { return JSON.stringify(v, function (k, x) { if (x && typeof x === 'object' && !Array.isArray(x)) { var o = {}; Object.keys(x).sort().forEach(function (key) { o[key] = x[key]; }); return o; } return x; }); }
  function diffChanges(r) {
    var a = resumeAnswers, ch = {};
    // keep what this page could not show (the lists did not load): never turn it into a change
    if (a.curriculum_id && !r.curriculum_id && !(FIELDS.curriculum_id && FIELDS.curriculum_id.el.options.length > 1)) r.curriculum_id = a.curriculum_id;
    if (a.preferred_venue_id && !r.preferred_venue_id && !val('location_type')) { r.preferred_venue_id = a.preferred_venue_id; r.location_type = a.location_type || 'off_site'; }
    Object.keys(r).forEach(function (k) { if (LOCKED_KEYS.indexOf(k) < 0 && canon(r[k]) !== canon(a[k])) ch[k] = r[k]; });
    MANAGED_KEYS.forEach(function (k) { if (k in a && !(k in r)) ch[k] = null; });
    return ch;
  }
  function fillFromAnswers(a) {
    ['first_name', 'last_name', 'email'].forEach(function (n) { setVal(n, a[n]); FIELDS[n].el.readOnly = true; });
    FIELDS.email.wrap.appendChild(h('span', { class: 'rf__hint', text: 'To change your name or email, just reply to the email we sent you.' }));
    setVal('consent_to_contact', true);
    FIELDS.consent_to_contact.wrap.parentNode.hidden = true;   // already agreed when the request was sent
    if (needBox) needBox.hidden = true;
    ['is_requester_attending', 'has_minors_present'].forEach(function (n) { if (typeof a[n] === 'boolean') setVal(n, a[n] ? 'yes' : 'no'); });
    ['attendee_count', 'proficiency'].forEach(function (n) { if (a[n] != null) setVal(n, String(a[n])); });
    ['phone', 'preferred_location', 'requested_date', 'alternate_requested_date', 'requested_time_of_day', 'preferred_times', 'what_they_want', 'how_heard',
      'preferred_contact_method', 'venue_arrangement', 'postal_code'].forEach(function (n) { if (a[n] != null && FIELDS[n]) setVal(n, String(a[n])); });
    if (a.needs_invoice === true && FIELDS.needs_invoice) setVal('needs_invoice', true);
    if (a.curriculum_id) pendingCurriculum = a.curriculum_id;
    if (a.preferred_venue_id) pendingWhere = 'venue:' + a.preferred_venue_id; else if (a.location_type) setVal('location_type', a.location_type);
    (a.participants || []).forEach(function (p) { addPerson({ first: p.first_name, last: p.last_name, email: p.email, age: p.age_band }, true); });
    if (FIELDS.postal_code) FIELDS.postal_code.el.addEventListener('input', onZipInput);   // a changed ZIP re-ranks the places
    if (moreBox) moreBox.open = true;
    submit.textContent = 'Save my details';
  }
  function startResume() {
    var title = document.querySelector('.reg__title'); if (title) title.textContent = 'Finish your request';
    var lede = document.querySelector('.reg__lede'); if (lede) lede.textContent = 'Thank you for sending your request. Add whatever you like below. What you already told us is filled in.';
    form.style.display = 'none';
    var note = h('p', { class: 'reg__note', role: 'status', text: 'Opening your request...' });
    form.parentNode.insertBefore(note, form);
    fetch(completionUrl() + '?t=' + encodeURIComponent(resumeToken), { method: 'GET' })
      .then(function (res) { return res.json().catch(function () { return null; }).then(function (j) { return { status: res.status, body: j }; }); })
      .then(function (r) {
        if (r.status === 404) {   // not a link we know: carry on as an ordinary new request
          note.textContent = 'That link did not open a request, so you can send a new one here.';
          if (title) title.textContent = 'Schedule a one on one';
          resumeToken = ''; form.style.display = ''; startNormal(); return;
        }
        if (!(r.body && r.body.ok && r.body.data)) { note.textContent = 'We could not open your request just now. Please reload this page to try again.'; return; }
        var d = r.body.data; resumeConf = d.confirmation_number || '';
        if (!d.editable) { note.textContent = 'Your request ' + resumeConf + ' has already been scheduled, so it cannot be changed here. Please reply to the email we sent you.'; return; }
        resumeAnswers = d.answers || {};
        note.textContent = 'Your request ' + resumeConf + '. Add details below, then tap Save my details.';
        fillFromAnswers(resumeAnswers);
        form.style.display = '';
        loadVenues(ZIP_RE.test(resumeAnswers.postal_code || '') ? resumeAnswers.postal_code : '');
        loadCurriculums(); updateNeeds();
      })
      .catch(function () { note.textContent = 'We could not reach the server. Please reload this page to try again.'; });
  }

  // ---------- check as you go: email and ZIP are checked the moment the cursor leaves the field ----------
  function unflag(name) {
    var f = FIELDS[name]; if (!f) return;
    var err = f.wrap.querySelector('.rf__error');
    if (err) { err.textContent = ''; err.removeAttribute('data-show'); }
    if (f.el) f.el.removeAttribute('aria-invalid');
  }
  function errShown(f) { var e = f.wrap.querySelector('.rf__error'); return !!e && e.getAttribute('data-show') === '1'; }
  function hideNote(f) { var n = f.wrap.querySelector('.rf__note'); if (n) { n.textContent = ''; n.removeAttribute('data-show'); } }
  function showTypoNote(f, fixed, typed) {
    var n = f.wrap.querySelector('.rf__note');
    if (!n) { n = h('div', { class: 'rf__note', role: 'status' }); f.wrap.appendChild(n); }
    n.textContent = 'Did you mean ' + fixed + '? ';
    var yes = h('button', { type: 'button', class: 'rf__use', text: 'Yes, use that' });
    yes.addEventListener('click', function () { f.el.value = fixed; hideNote(f); f.el.dispatchEvent(new Event('input', { bubbles: true })); f.el.focus(); });
    var no = h('button', { type: 'button', class: 'rf__use', text: 'No, keep mine' });
    no.addEventListener('click', function () { f.keepEmail = typed; hideNote(f); });
    n.appendChild(yes); n.appendChild(no); n.setAttribute('data-show', '1');
  }
  function emailField() { var f = FIELDS.email; return f && f.el && !f.el.readOnly ? f : null; }
  function checkEmailField(leaving) {
    var f = emailField(); if (!f) return;
    var v = f.el.value.trim(), msg = emailProblem(v);
    hideNote(f);
    if (msg) { flag('email', msg); return; }
    unflag('email');
    if (leaving && v && f.keepEmail !== v) { var fix = emailTypo(v); if (fix) showTypoNote(f, fix, v); }
  }
  function checkZipField() {
    var z = FIELDS.postal_code; if (!z) return;
    var v = z.el.value.trim();
    if (v && !ZIP_RE.test(v)) flag('postal_code', 'Please use a five-digit ZIP code, like 80027, or leave it blank.'); else unflag('postal_code');
  }
  function checkRowEmail(r) {
    var msg = emailProblem(r.email.value);
    if (msg) { r.err.textContent = msg; r.err.setAttribute('data-show', '1'); r.err.setAttribute('data-kind', 'email'); r.email.setAttribute('aria-invalid', 'true'); }
    else if (r.err.getAttribute('data-kind') === 'email') { r.err.textContent = ''; r.err.removeAttribute('data-show'); r.err.removeAttribute('data-kind'); r.email.removeAttribute('aria-invalid'); }
  }
  form.addEventListener('focusout', function (e) {
    var f = emailField();
    if (f && e.target === f.el) { checkEmailField(true); return; }
    var z = FIELDS.postal_code;
    if (z && e.target === z.el) { checkZipField(); return; }
    peopleRows.forEach(function (r) { if (e.target === r.email) checkRowEmail(r); });
  });
  form.addEventListener('input', function (e) {   // once a message is showing, it follows what they type and clears the moment the entry is right
    var f = emailField();
    if (f && e.target === f.el) { if (errShown(f)) checkEmailField(false); else hideNote(f); return; }
    var z = FIELDS.postal_code;
    if (z && e.target === z.el) { if (errShown(z)) checkZipField(); return; }
    peopleRows.forEach(function (r) { if (e.target === r.email && r.err.getAttribute('data-show') === '1' && r.err.getAttribute('data-kind') === 'email') checkRowEmail(r); });
  });

  // ---------- start ----------
  var resumeAnswers = null, resumeConf = '';
  build();
  form.addEventListener('input', onChange);
  form.addEventListener('change', onChange);
  if (resumeToken) startResume(); else startNormal();
  function startNormal() {
  var restored = loadDraft();
  if (FIELDS.postal_code) {
    FIELDS.postal_code.el.value = rememberedZip();   // what this device remembers from last time
    FIELDS.postal_code.el.addEventListener('input', onZipInput);
  }
  loadVenues(FIELDS.postal_code ? rememberedZip() : '');
  loadRegions();
  loadCurriculums();
  openMoreIfFilled();
  updateNeeds();
  if (restored && draftNote) {
    draftNote.setAttribute('data-show', '1');
    var startOver = draftNote.querySelector('button');
    if (startOver) startOver.addEventListener('click', function () {
      clearDraft(); form.reset(); peopleRows.splice(0).forEach(function (r) { r.node.remove(); });
      if (FIELDS.postal_code) FIELDS.postal_code.el.value = rememberedZip();
      draftNote.removeAttribute('data-show'); clearFlags(); if (moreBox) moreBox.open = false; syncMore(); updateNeeds();
    });
  }
  if (CFG.minCount > 1 && !val('attendee_count')) setVal('attendee_count', '');
  }
})();
