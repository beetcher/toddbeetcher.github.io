/* Classes station for the Console: the class list with tick-box filters, Add class, the Edit form built from the published class schema (Basics,
   When and where, Capacity and price, the curriculum and series pickers, the Instructors box), the time-zone helpers, and the placing machinery
   (Put in a class on a request card, the add-a-person form used by the Attendance dialog, the class builder). Moved out of console.js (the Classes
   extraction, C-2): the code is the same; everything it used to borrow from the big file now comes through ConsoleKit (K), the form engine
   (ConsoleForms) or ui.js (UI). The page markup (#classesView, #cEditPanel, #cAddForm) stays in index.html and the manual text in the stations
   list in console.js (DT-7). Loaded by index.html after venues.js.
   window.ClassesStation = { show, stop, reset, dirty, forget, putInClass, assignForm, classWhen, choices, byId }. The last five are what the kit
   forwards to for Requests and Attendance (they ask through the kit, never this file). */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var $ = function (id) { return document.getElementById(id); };
  var CF = window.ConsoleForms;
  var mk = K.mk, admin = K.admin, lock = K.lock, adminProblem = K.adminProblem, line = K.line, str = K.str, historyBtn = K.historyBtn, attName = K.attName, attFail = K.attFail;
  var askDiscard = K.askDiscard, openAttendance = K.openAttendance, refreshPlaced = K.refreshPlaced, attLine = K.attLine, openWorkflows = K.openWorkflows;
  var pFull = K.pFull, peopleList = K.peopleList, peopleMatches = K.peopleMatches;
  var fmtClock = { format: function (d) { return K.clock(d); } };
  var LABELS = CF.labels, humanize = CF.humanize, readValue = CF.readValue, buildField = CF.buildField;
  var ISSUE = CF.issue, wholeNum = CF.wholeNum, slugify = CF.slugify, skelOn = UI.skelOn, skelOff = UI.skelOff;
  var AC = K.attConsts(), ATT = AC.ATT, ATT_STATUSES = AC.ATT_STATUSES, ATT_WORD = AC.ATT_WORD, ROLE_WORD = AC.ROLE_WORD, REASON_WORD = AC.REASON_WORD;
  // ======================================================================================================
  // ---- Classes view: list, add, edit, delete. Same pattern as venues; the server does all the checking.
  // The form is built from the published scheduled_class schema. The venue and room are pick lists made from
  // the venues collection; the start time is typed in the venue's time zone and saved as UTC.
  // ======================================================================================================
  var CLS_SCHEMA_URL = "/schemas/scheduled_class.schema.json";
  var CTYPES = { workshop: "Workshop", group: "Group", "private": "One on one" };
  var CPRIMARY = ["Basics", "When and where", "Capacity and price"];
  var CLAYOUT = [
    ["Basics", ["title", "class_type", "curriculum_id", "series_id", "session_number", "status", "is_public", "description", "cancelled_reason"]],
    ["When and where", ["venue_id", "venue_room_label", "starts_at", "time_zone", "duration_minutes", "is_venue_confirmed", "venue_notes"]],
    ["Capacity and price", ["capacity_minimum", "capacity_target", "capacity_max", "is_waitlist_enabled", "waitlist_max", "price_cents", "price_basis"]],
    ["Program and organizer", ["program_slug", "accessibility_notes", "organizer_name", "organizer_email", "organizer_phone"]]
  ];
  var CLABELS = { title: "Title", class_type: "Kind of class", is_public: "Show in the public list", program_slug: "Program", session_number: "Session number in the series",
                  venue_id: "Venue", venue_room_label: "Room", starts_at: "Starts", duration_minutes: "Length (minutes)",
                  is_venue_confirmed: "Venue confirmed with them", venue_notes: "Notes about the venue for this class",
                  capacity_minimum: "Fewest people (needed to run)", capacity_target: "Target number", capacity_max: "Most people",
                  is_waitlist_enabled: "Keep a waiting list", waitlist_max: "Waiting list limit", price_cents: "Price", price_basis: "Price is",
                  cancelled_reason: "Why it was cancelled", organizer_name: "Organizer name", organizer_email: "Organizer email", organizer_phone: "Organizer phone" };
  Object.keys(CLABELS).forEach(function (k) { if (!LABELS[k]) LABELS[k] = CLABELS[k]; });
  var CISSUE = {
    venue_id: { not_found: "That venue was not found.", inactive: "That venue is not active. Make the venue active first, or keep this class as an idea.", required: "Choose a venue." },
    venue_room_label: { not_found: "That venue has no room with that name." },
    curriculum_id: { not_found: "That curriculum was not found." },
    series_id: { required: "Choose a series for the session number, or clear the session number." },
    session_number: { duplicate: "Another class in this series already has that number.", out_of_range: "A whole number from 1 to 50." },
    capacity_minimum: { out_of_range: "The fewest people is above the target." },
    capacity_max: { out_of_range: "Check the numbers: fewest ≤ target ≤ most, and the most cannot be above the room's size." },
    cancelled_reason: { not_allowed: "Only for a cancelled class." }
  };

  var cCtx = { prefix: "c_", schema: null, fields: {} };
  var cSchemaP = null, cRec = null, cLoaded = false, cNewId = "", cSlugTouched = false, cVenueFetch = null, cAreas = [];

  function getClassSchema() {
    if (!cSchemaP) {
      cSchemaP = fetch(CLS_SCHEMA_URL, { cache: "no-cache" })
        .then(function (r) { if (!r.ok) throw new Error("x"); return r.json(); })
        .catch(function () { cSchemaP = null; return null; });
    }
    return cSchemaP;
  }
  // ---- time zone helpers: the time is typed in the class's time zone and saved as UTC
  function zoneParts(ms, tz) {
    var f = new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
                                                hour: "2-digit", minute: "2-digit", second: "2-digit" });
    var o = {}; f.formatToParts(new Date(ms)).forEach(function (p) { o[p.type] = p.value; });
    return o;
  }
  function zoneOffsetMin(ms, tz) {
    var o = zoneParts(ms, tz), h = Number(o.hour) === 24 ? 0 : Number(o.hour);
    return (Date.UTC(Number(o.year), Number(o.month) - 1, Number(o.day), h, Number(o.minute), Number(o.second)) - Math.floor(ms / 1000) * 1000) / 60000;
  }
  function zonedToUtc(date, time, tz) {
    var m = /^(\d{4})-(\d\d)-(\d\d)$/.exec(date || ""), t = /^(\d\d):(\d\d)$/.exec(time || "");
    if (!m || !t || !tz) return null;
    try {
      var naive = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(t[1]), Number(t[2]));
      var off = zoneOffsetMin(naive, tz), guess = naive - off * 60000, off2 = zoneOffsetMin(guess, tz);
      if (off2 !== off) guess = naive - off2 * 60000;
      return new Date(guess).toISOString().replace(/\.\d{3}Z$/, "Z");
    } catch (e) { return null; }
  }
  function utcToZoned(iso, tz) {
    var d = new Date(iso); if (isNaN(d) || !tz) return null;
    try {
      var o = zoneParts(d.getTime(), tz), h = Number(o.hour) === 24 ? "00" : o.hour;
      return { date: o.year + "-" + o.month + "-" + o.day, time: h + ":" + o.minute };
    } catch (e) { return null; }
  }
  function classWhen(rec) {
    if (!rec.starts_at) return "No date yet";
    try {
      var d = new Date(rec.starts_at);
      return new Intl.DateTimeFormat("en-US", { timeZone: rec.time_zone, weekday: "short", month: "short", day: "numeric",
                                                 hour: "numeric", minute: "2-digit", timeZoneName: "short" }).format(d);
    } catch (e) { return String(rec.starts_at); }
  }
  function money(cents) { return "$" + (cents / 100).toFixed(cents % 100 === 0 ? 0 : 2); }

  // ---- list
  function classRow(rec, isNew) {
    var li = document.createElement("li");
    if (isNew) li.className = "isnew";
    var head = document.createElement("button");
    head.className = "head"; head.type = "button";
    var top = mk("div", "top");
    top.appendChild(mk("span", "vname", rec.title || "(no title)"));
    top.appendChild(mk("span", "type" + (rec.status === "enrolling" || rec.status === "scheduled" ? " on" : ""), rec.status || ""));
    head.appendChild(top);
    head.appendChild(mk("div", "who", classWhen(rec)));
    var v = rec.venue_id ? ConsoleNames.venueById(rec.venue_id) : null;
    var where = rec.venue_id ? ((v ? v.name : "(venue not found)") + (rec.venue_room_label ? " · " + rec.venue_room_label : "")) : "No venue yet";
    head.appendChild(mk("div", "sub", where));
    var chips = mk("div", "chips");
    chips.appendChild(mk("span", "", (CTYPES[rec.class_type] || rec.class_type) + (rec.is_public ? ", public" : ", not public")));
    if (rec.session_number) chips.appendChild(mk("span", "", "Session " + rec.session_number));
    chips.appendChild(mk("span", "", "People: " + rec.capacity_minimum + " to " + rec.capacity_target + " (up to " + rec.capacity_max + ")"));
    var links = mk("div", "lchips");   // outside the card's head button: a button cannot sit inside a button
    var at = mk("button", "chiplink", "Attendance"); at.type = "button";
    at.addEventListener("click", function () { openAttendance(rec); });
    links.appendChild(at);
    var jl = mk("button", "chiplink", "Journal"); jl.type = "button";
    jl.addEventListener("click", function () { ConsoleDialogs.openJournal({ scheduled_class_id: rec.id }, "Journal: " + (rec.title || "class")); });
    links.appendChild(jl);
    if (rec.price_cents != null) chips.appendChild(mk("span", "", money(rec.price_cents) + (rec.price_basis === "per_person" ? " per person" : " per session")));
    head.appendChild(chips);

    head.addEventListener("click", function () { openHub(rec, "Overview"); });
    li.appendChild(head); li.appendChild(links); li.appendChild(classActions(rec));
    if (isNew) setTimeout(function () { li.classList.remove("isnew"); }, 6000);
    return li;
  }

  function classActions(rec) {
    var wrap = document.createElement("div"); wrap.className = "tilebtns";
    var row = mk("div", "actions-row");
    var ed = mk("button", "", "Edit"); ed.type = "button";
    var cn = mk("button", "", "Cancel class"); cn.type = "button";
    var del = mk("button", "danger", "Delete"); del.type = "button";
    row.appendChild(ed);
    var hc = historyBtn(rec.id, rec.title || rec.short_name); if (hc) row.appendChild(hc);
    if (rec.status !== "cancelled" && rec.status !== "completed") row.appendChild(cn);
    row.appendChild(del);
    var box = mk("div", "confirm"); box.hidden = true;
    var what = mk("div", ""), why = mk("input"); why.type = "text"; why.maxLength = 200; why.setAttribute("aria-label", "Why is it cancelled?"); why.placeholder = "Why? (optional)";
    var btns = mk("div", "btns");
    var yes = mk("button", "danger", ""); yes.type = "button";
    var no = mk("button", "quiet", "Never mind"); no.type = "button";
    var err = mk("div", "msg"); err.setAttribute("role", "alert");
    btns.appendChild(yes); btns.appendChild(no);
    box.appendChild(what); box.appendChild(why); box.appendChild(btns); box.appendChild(err);
    var mode = "";
    function show(m) {
      if (!box.hidden && mode === m) { box.hidden = true; return; }
      mode = m; box.hidden = false; err.textContent = ""; why.hidden = m !== "cancel";
      what.textContent = m === "cancel"
        ? "Cancel this class? It stays in the list marked cancelled. Everyone in it, students and instructors, is cancelled and their requests go back to waiting to be placed. Each of them is also emailed that it is cancelled, with a calendar file that removes it. Use this when a real class does not happen."
        : "Delete this class? Use this for a class built by mistake or a duplicate. It disappears from the lists, everyone in it is cancelled, and their requests go back to waiting to be placed. Each of them is also emailed that it is cancelled. The record is kept.";
      yes.textContent = m === "cancel" ? "Cancel class" : "Delete class";
    }
    function problem(res) {
      var e = res.body && res.body.error;
      var code = e && (e.code || (e.problems && e.problems[0] && (e.problems[0].field + " " + e.problems[0].issue)));
      return adminProblem(res.status) + (code ? " (" + res.status + ": " + code + ")" : " (" + res.status + ")");
    }
    ed.addEventListener("click", function () { openHub(rec, "Edit"); });
    cn.addEventListener("click", function () { show("cancel"); });
    del.addEventListener("click", function () { show("delete"); });
    no.addEventListener("click", function () { box.hidden = true; });
    yes.addEventListener("click", function () {
      yes.disabled = true; err.textContent = "";
      var p = mode === "cancel"
        ? admin("update", { id: rec.id, changes: Object.assign({ status: "cancelled" }, why.value.trim() ? { cancelled_reason: why.value.trim() } : {}), expected_updated_at: rec.updated_at }, "scheduled_classes")
        : admin("soft_delete", { id: rec.id }, "scheduled_classes");
      p.then(function (res) {
        yes.disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          $("cNotice").textContent = (mode === "cancel" ? "Cancelled " : "Deleted ") + (rec.title || "class") + ". Everyone in it was cancelled and emailed. Messages shows any email that could not be sent.";
          refreshPlaced(); closeHub(); loadClasses();
        }
        else if (res.status === 404) { $("cNotice").textContent = "That class was already gone."; closeHub(); loadClasses(); }
        else if (res.status === 409 && mode === "cancel") err.textContent = "This class changed since the list loaded. Refresh and try again.";
        else if (res.status === 409) err.textContent = "This class still holds old seat decisions from before attendance existed, so it cannot be deleted. Cancel it instead.";
        else err.textContent = problem(res);
      });
    });
    wrap.appendChild(row); wrap.appendChild(box);
    return wrap;
  }

  // ---- filters: tick boxes. Everything ticked shows everything; unticking narrows. The page holds the whole list and filters it here.
  var CSTAT = ["identified", "scheduled", "enrolling", "completed", "cancelled"], CKIND = ["workshop", "group", "private"];
  var CF_STORE = "console_class_filters";
  var cAll = [], cSeq = 0;
  function cChecks() { return document.querySelectorAll("#cFilters input[type=checkbox]"); }
  function cSelected() {
    var o = { status: {}, class_type: {} };
    Array.prototype.forEach.call(cChecks(), function (c) { if (c.checked) o[c.getAttribute("data-f")][c.value] = 1; });
    return o;
  }
  function cSaveFilters() {
    try {
      var off = [];
      Array.prototype.forEach.call(cChecks(), function (c) { if (!c.checked) off.push(c.getAttribute("data-f") + ":" + c.value); });
      if (off.length) sessionStorage.setItem(CF_STORE, JSON.stringify(off)); else sessionStorage.removeItem(CF_STORE);
    } catch (e) {}
  }
  function cRestoreFilters() {
    try {
      var off = JSON.parse(sessionStorage.getItem(CF_STORE) || "[]");
      Array.prototype.forEach.call(cChecks(), function (c) { c.checked = off.indexOf(c.getAttribute("data-f") + ":" + c.value) < 0; });
    } catch (e) {}
    cFilterSummary();
  }
  function cShowEverything() {
    Array.prototype.forEach.call(cChecks(), function (c) { c.checked = true; });
    cSaveFilters(); cFilterSummary(); renderClasses();
  }
  function cFilterSummary() {
    var all = true;
    Array.prototype.forEach.call(cChecks(), function (c) { if (!c.checked) all = false; });
    $("cFilterSummary").textContent = all ? "Filters: all classes shown" : "Filters: some classes are hidden";
    $("cFilterSummary").className = all ? "" : "some";
  }
  function cPass(sel, field, v) { var known = (field === "status" ? CSTAT : CKIND).indexOf(v) >= 0; return known ? !!sel[field][v] : true; }
  function cTick(rec) {
    Array.prototype.forEach.call(cChecks(), function (c) {
      var f = c.getAttribute("data-f");
      if (rec[f] === c.value) c.checked = true;
    });
    cSaveFilters(); cFilterSummary();
  }

  function renderClasses() {
    var sel = cSelected();
    function shownList() { return cAll.filter(function (r) { return cPass(sel, "status", r.status) && cPass(sel, "class_type", r.class_type); }); }
    var shown = shownList();
    if (cNewId) {   // a class you just added or saved is never hidden by the filters
      var nr = cAll.filter(function (r) { return r.id === cNewId; })[0];
      if (nr && shown.indexOf(nr) < 0) { cTick(nr); sel = cSelected(); shown = shownList(); }
    }
    shown.sort(function (a, b) {
      if (a.starts_at && b.starts_at) return a.starts_at < b.starts_at ? -1 : a.starts_at > b.starts_at ? 1 : 0;
      if (a.starts_at) return -1;
      if (b.starts_at) return 1;
      return (a.title || "").toLowerCase() < (b.title || "").toLowerCase() ? -1 : 1;
    });
    var ul = $("cList"); ul.textContent = "";
    var focus = null;
    shown.forEach(function (r) { var li = classRow(r, r.id === cNewId); ul.appendChild(li); if (r.id === cNewId) focus = li; });
    var n = shown.length, t = cAll.length;
    $("cCount").textContent = (n === t ? t + (t === 1 ? " class" : " classes") : "Showing " + n + " of " + t + " classes") + (t >= 200 ? " (the first 200)" : "");
    $("cEmpty").hidden = t > 0;
    $("cNoMatch").hidden = !(t > 0 && n === 0);
    cFilterSummary();
    if (focus) { try { focus.scrollIntoView({ block: "center" }); } catch (e) {} }
    cNewId = "";
  }

  function loadClasses() {
    var my = ++cSeq;   // only the newest load may change the page, so a slow older answer can never overwrite a newer one
    $("cMsg").textContent = ""; $("cRetry").hidden = true;
    if (!cLoaded) skelOn($("cList"));
    return Promise.all([ConsoleNames.loadVenueChoices(), admin("list", { limit: 200 }, "scheduled_classes")]).then(function (both) {
      if (my !== cSeq) return;
      var res = both[1];
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body.ok) {
        skelOff($("cList")); $("cMsg").textContent = "Could not load the classes. " + adminProblem(res.status); $("cRetry").hidden = false; return;
      }
      cAll = res.body.data.records || [];
      UI.limitNote($("cList"), cAll.length, 200);
      cLoaded = true;
      renderClasses();
      $("cChecked").textContent = "Last checked " + fmtClock.format(new Date());
    });
  }

  // ---- add
  function cClearErrs() { ["eCTitle", "eCSlug", "eCType", "eCPublic", "eCMin", "eCTarget", "eCMax", "cFMsg"].forEach(function (id) { $(id).textContent = ""; }); }
  function openClassForm() {
    $("cAddForm").reset(); cSlugTouched = false; cClearErrs(); $("cNotice").textContent = "";
    $("cMin").value = "6"; $("cTarget").value = "10"; $("cMax").value = "15";
    $("cAddForm").hidden = false; $("cAddBtn").hidden = true; $("cTitle").focus();
  }
  function closeClassForm() { $("cAddForm").hidden = true; $("cAddBtn").hidden = false; }
  var CADD_ERR = { title: "eCTitle", slug: "eCSlug", class_type: "eCType", is_public: "eCPublic", capacity_minimum: "eCMin", capacity_target: "eCTarget", capacity_max: "eCMax" };

  // ---- edit
  function classNeeds(schema, status) {
    var need = [];
    (schema.allOf || []).forEach(function (b) {
      var c = b["if"] && b["if"].properties && b["if"].properties.status;
      if (c && c["enum"] && c["enum"].indexOf(status) >= 0 && b.then) (b.then.required || []).forEach(function (f) { if (need.indexOf(f) < 0) need.push(f); });
    });
    return need;
  }
  function cField(name) { return cCtx.fields[name]; }
  function cValue(name) {
    var f = cField(name); if (!f) return cRec && cRec[name] !== undefined ? cRec[name] : null;
    if (f.kind === "when") return f.date.value && f.time.value ? "set" : null;
    return readValue(f);
  }
  function cTz() { var f = cField("time_zone"); return f ? readValue(f) : null; }
  function cStartsUtc() {
    var f = cField("starts_at"); if (!f.date.value && !f.time.value) return { value: null };
    if (!f.date.value || !f.time.value) return { bad: "Give both a date and a time." };
    var tz = cTz(); if (!tz) return { bad: "Choose the time zone first." };
    var u = zonedToUtc(f.date.value, f.time.value, tz);
    return u ? { value: u } : { bad: "That date or time is not valid." };
  }

  // ---- what a class teaches, and which series it is in (piece 3)
  function curriculumLabel(c) { return (c.title || "(no title)") + " (" + c.session_count + (c.session_count === 1 ? " session" : " sessions") + " of " + c.minutes_per_session + " min)"; }
  function newUuid() {
    try { if (window.crypto && crypto.randomUUID) return crypto.randomUUID(); } catch (e) {}
    return "xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx".replace(/x/g, function () { return Math.floor(Math.random() * 16).toString(16); });
  }
  function buildCurriculumField(rec) {
    var wrap = mk("div"), id = "ef_c_curriculum_id";
    var l = mk("label", "f", "Curriculum (what is taught)"); l.htmlFor = id;
    var sel = mk("select"); sel.id = id;
    var o0 = mk("option", "", "Not chosen yet"); o0.value = ""; sel.appendChild(o0);
    ConsoleNames.curricula().forEach(function (c) { var o = mk("option", "", curriculumLabel(c)); o.value = c.id; sel.appendChild(o); });
    if (rec.curriculum_id && !ConsoleNames.curricula().some(function (c) { return c.id === rec.curriculum_id; })) { var ox = mk("option", "", "(inactive or removed curriculum)"); ox.value = rec.curriculum_id; sel.appendChild(ox); }
    sel.value = rec.curriculum_id || "";
    wrap.appendChild(l); wrap.appendChild(sel);
    var er = mk("div", "ferr"); er.id = "ee_c_curriculum_id"; wrap.appendChild(er);
    cCtx.fields.curriculum_id = { el: sel, other: null, kind: "text", def: cCtx.schema.properties.curriculum_id, sec: null, summary: null };
    return wrap;
  }
  function buildSeriesField(rec) {
    var wrap = mk("div"), id = "ef_c_series_id";
    var l = mk("label", "f", "Series (a curriculum taught over several sessions)"); l.htmlFor = id;
    var sel = mk("select"); sel.id = id;
    function opt(v, t) { var o = mk("option", "", t); o.value = v; sel.appendChild(o); }
    opt("", "Not part of a series");
    var fresh = newUuid(); opt(fresh, "A new series (this class is its first session)");
    var groups = {};
    cAll.forEach(function (c) { if (c.series_id) (groups[c.series_id] = groups[c.series_id] || []).push(c); });
    Object.keys(groups).forEach(function (sid) {
      var list = groups[sid].slice().sort(function (a, b) { return (a.session_number || 99) - (b.session_number || 99); });
      opt(sid, "Series of " + (list[0].title || "class") + " (" + list.length + (list.length === 1 ? " class" : " classes") + ")");
    });
    if (rec.series_id && !groups[rec.series_id]) opt(rec.series_id, "This class's series");
    sel.value = rec.series_id || "";
    wrap.appendChild(l); wrap.appendChild(sel);
    wrap.appendChild(mk("div", "hint", "Each session is its own class. Give each one its session number below."));
    var er = mk("div", "ferr"); er.id = "ee_c_series_id"; wrap.appendChild(er);
    cCtx.fields.series_id = { el: sel, other: null, kind: "text", def: cCtx.schema.properties.series_id, sec: null, summary: null };
    sel.addEventListener("change", function () {
      var sn = cCtx.fields.session_number;
      if (sel.value === fresh && sn && !sn.el.value) sn.el.value = "1";
    });
    return wrap;
  }

  function buildVenueField(rec) {
    var wrap = mk("div"), id = "ef_c_venue_id";
    var l = mk("label", "f", "Venue"); l.htmlFor = id;
    var sel = mk("select"); sel.id = id;
    var o0 = mk("option", "", "Not chosen yet"); o0.value = ""; sel.appendChild(o0);
    // A venue belongs to a region (its ZIP is on the region's list). A class that already has a venue can only move to another venue
    // in that same region; to go outside it, cancel the class and put the request in a new one. No venue yet, or a venue in no served region: all venues.
    var cur = rec.venue_id ? ConsoleNames.venueById(rec.venue_id) : null, inRegion = cur ? regionZipsOfZip(cAreas, venueZip(cur)) : null;
    ConsoleNames.venues().forEach(function (v) {
      if (inRegion && !inRegion[venueZip(v)] && v.id !== rec.venue_id) return;
      var o = mk("option", "", (v.name || "(no name)") + (v.status === "active" ? "" : " (inactive)")); o.value = v.id; sel.appendChild(o);
    });
    if (rec.venue_id && !ConsoleNames.venueById(rec.venue_id)) { var ox = mk("option", "", "(venue not found)"); ox.value = rec.venue_id; sel.appendChild(ox); }
    sel.value = rec.venue_id || "";
    wrap.appendChild(l); wrap.appendChild(sel);
    if (inRegion) wrap.appendChild(mk("div", "hint", "Only venues in this class's region are listed. To use a venue in another region, cancel this class and put the request in a new one."));
    var er = mk("div", "ferr"); er.id = "ee_c_venue_id"; wrap.appendChild(er);
    cCtx.fields.venue_id = { el: sel, other: null, kind: "text", def: cCtx.schema.properties.venue_id, sec: null, summary: null };
    return wrap;
  }
  function buildRoomPick(rec) {
    var wrap = mk("div"), id = "ef_c_venue_room_label";
    var l = mk("label", "f", "Room"); l.htmlFor = id;
    var sel = mk("select"); sel.id = id;
    wrap.appendChild(l); wrap.appendChild(sel);
    var er = mk("div", "ferr"); er.id = "ee_c_venue_room_label"; wrap.appendChild(er);
    cCtx.fields.venue_room_label = { el: sel, other: null, kind: "text", def: cCtx.schema.properties.venue_room_label, sec: null, summary: null };
    fillRooms(rec.venue_room_label || "");
    return wrap;
  }
  function fillRooms(keep) {
    var sel = cField("venue_room_label").el, vid = cField("venue_id").el.value, v = vid ? ConsoleNames.venueById(vid) : null;
    sel.textContent = "";
    var o0 = mk("option", "", vid ? "Not chosen yet" : "Choose a venue first"); o0.value = ""; sel.appendChild(o0);
    var found = false;
    ((v && v.rooms) || []).forEach(function (r) {
      var o = mk("option", "", r.label + (r.max_occupancy != null ? " (up to " + r.max_occupancy + ")" : "")); o.value = r.label; sel.appendChild(o);
      if (r.label === keep) found = true;
    });
    if (keep && !found) { var ox = mk("option", "", keep + " (not in this venue)"); ox.value = keep; sel.appendChild(ox); }
    sel.value = keep || "";
    sel.disabled = !vid;
  }
  function buildStartsField(rec) {
    var wrap = mk("div");
    var l = mk("label", "f", "Starts (in the time zone below)"); l.htmlFor = "ef_c_starts_date"; wrap.appendChild(l);
    var two = mk("div", "two");
    var d = mk("input"); d.type = "date"; d.id = "ef_c_starts_date";
    var t = mk("input"); t.type = "time"; t.id = "ef_c_starts_time"; t.setAttribute("aria-label", "Start time");
    two.appendChild(d); two.appendChild(t); wrap.appendChild(two);
    var er = mk("div", "ferr"); er.id = "ee_c_starts_at"; wrap.appendChild(er);
    var z = rec.starts_at ? utcToZoned(rec.starts_at, rec.time_zone) : null;
    if (z) { d.value = z.date; t.value = z.time; }
    cCtx.fields.starts_at = { el: d, other: null, kind: "when", date: d, time: t, def: cCtx.schema.properties.starts_at, sec: null, summary: null,
                              initial: { date: d.value, time: t.value, tz: rec.time_zone || "" } };
    return wrap;
  }

  function cBuildSections(rec) {
    var host = $("cEditSections"); host.textContent = "";
    cCtx.fields = {};
    var props = cCtx.schema.properties, used = {};
    function section(title, open, parent) {
      var d = document.createElement("details"); d.className = "sec"; if (open) d.open = true;
      var sm = document.createElement("summary"); sm.textContent = title; d.appendChild(sm);
      var body = document.createElement("div"); body.className = "body"; d.appendChild(body);
      (parent || host).appendChild(d);
      return { d: d, sm: sm, body: body };
    }
    function put(sec, n) {
      used[n] = 1; var node;
      if (n === "venue_id") node = buildVenueField(rec);
      else if (n === "curriculum_id") node = buildCurriculumField(rec);
      else if (n === "series_id") node = buildSeriesField(rec);
      else if (n === "venue_room_label") node = buildRoomPick(rec);
      else if (n === "starts_at") node = buildStartsField(rec);
      else { var df = props[n]; if (!df || df.readOnly || df.type === "array") return; node = buildField(n, df, rec, cCtx); }
      node.id = "cw_" + n;
      sec.body.appendChild(node);
      var f = cCtx.fields[n]; if (f) { f.sec = sec.d; f.summary = sec.sm; f.wrap = node; }
    }
    CLAYOUT.forEach(function (l) {
      if (CPRIMARY.indexOf(l[0]) < 0) return;
      var s2 = section(l[0], true);
      l[1].forEach(function (n) { put(s2, n); });
      if (l[0] === "Capacity and price") {
        var btn = mk("button", "linkbtn", "What’s needed to schedule or open enrolment?"); btn.type = "button"; btn.id = "cReadyBtn";
        var box = mk("div", "ready"); box.id = "cReadyBox"; box.hidden = true;
        btn.addEventListener("click", function () { box.hidden = !box.hidden; if (!box.hidden) renderClassReady(); });
        s2.body.appendChild(btn); s2.body.appendChild(box);
      }
    });
    var more = mk("details", "more");
    more.appendChild(mk("summary", "", "More (program, organizer, accessibility)"));
    var mbody = mk("div", "mbody"); more.appendChild(mbody); host.appendChild(more);
    CLAYOUT.forEach(function (l) {
      if (CPRIMARY.indexOf(l[0]) >= 0) return;
      var s3 = section(l[0], false, mbody);
      l[1].forEach(function (n) { put(s3, n); });
    });

    // behaviour: venue changes the room list and (if blank) the time zone; status shows the cancelled reason
    cField("venue_id").el.addEventListener("change", function () {
      fillRooms("");
      var v = ConsoleNames.venueById(this.value), tzf = cField("time_zone"), vtz = v && v.place && v.place.time_zone;
      if (vtz && tzf && !readValue(tzf)) {
        var has = Array.prototype.some.call(tzf.el.options, function (o) { return o.value === vtz; });
        if (has) tzf.el.value = vtz;
      }
    });
    function syncReason() {
      var show = cField("status").el.value === "cancelled", w = cField("cancelled_reason").wrap;
      w.hidden = !show;
    }
    cField("status").el.addEventListener("change", syncReason); syncReason();
  }

  // Instructors of a class, on the Edit class screen. Instructors are placements (Attendance records), not class fields, so these buttons
  // save at once (the Save changes button below saves only the class details) and email the people in the class: a new lead tells everyone
  // the lead changed, and the instructor who is placed or removed is told too. The new lead is promoted first and the old lead demoted
  // second, so the class sees ONE lead change, not two.
  function classInstructors(rec) {
    var box = mk("div", "insbox"), list = mk("div"), say = mk("div", "msg"), st = { lead: null, others: [], all: [] };
    say.setAttribute("role", "status"); say.id = "cInsMsg"; box.id = "cInstructors";
    function nameOf(r) { return attName(r); }
    function fail(res) {
      var ps = (res.body && res.body.error && res.body.error.problems) || [];
      if (ps.some(function (p) { return p.issue === "address_required"; })) return "That instructor has no address on file. Open the Instructors station, open them and tap Add address, then try again.";
      return attFail(res);
    }
    function nextOrder() { var m = 0; st.all.forEach(function (r) { if ((r.order || 0) > m) m = r.order; }); return Math.min(m + 1, 50); }
    function load() {
      list.textContent = "Loading instructors…";
      return admin("list", { filters: { scheduled_class_id: rec.id }, limit: 200, expand: true }, ATT).then(function (res) {
        list.textContent = "";
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status !== 200 || !res.body || !res.body.ok) { list.appendChild(mk("div", "hint", "Could not load the instructors. " + adminProblem(res.status))); return; }
        var ins = (res.body.data.records || []).filter(function (r) {
          return (r.role === "primary_instructor" || r.role === "instructor") && r.status !== "declined" && r.status !== "withdrawn" && r.status !== "cancelled";
        });
        ins.sort(function (a, b) { return (a.order || 999) - (b.order || 999) || String(a.created_at).localeCompare(String(b.created_at)); });
        st.all = ins;
        st.lead = ins.filter(function (r) { return r.role === "primary_instructor" && (r.status === "assigned" || r.status === "confirmed"); })[0] || null;
        st.others = ins.filter(function (r) { return r !== st.lead; });
        list.appendChild(mk("div", "note", st.lead ? "Lead instructor: " + nameOf(st.lead) : "No lead instructor yet."));
        st.others.forEach(function (r) {
          var row = mk("div", "arow"), top = mk("div", "atop"), rm = mk("button", "quiet", "Remove"), armed = false;
          rm.type = "button";
          top.appendChild(mk("span", "aname", nameOf(r) + (r.role === "primary_instructor" ? " (lead role, not seated)" : " · also teaching")));
          top.appendChild(rm); row.appendChild(top); list.appendChild(row);
          rm.addEventListener("click", function () {
            if (!armed) { armed = true; rm.textContent = "Really remove? They are emailed."; rm.className = "danger"; return; }
            rm.disabled = true;
            admin("soft_delete", { id: r.id }, ATT).then(function (res2) {
              if (res2.status === 200 && res2.body && res2.body.ok) { say.textContent = nameOf(r) + " was removed from this class and emailed that they are no longer assigned. Messages shows the result."; load(); return; }
              rm.disabled = false; armed = false; rm.textContent = "Remove"; rm.className = "quiet"; say.textContent = fail(res2);
            });
          });
        });
      });
    }
    function chooser(label, buttonText, go) {
      var wrap = mk("div", "addbox"), finder = instructorFinder(""), b = mk("button", "", buttonText);
      b.type = "button"; wrap.appendChild(mk("div", "rhead", label)); wrap.appendChild(finder.el); wrap.appendChild(b);
      b.addEventListener("click", function () {
        var id = finder.id(); if (!id) { say.textContent = "Search for an instructor and tap their name first."; return; }
        say.textContent = ""; b.disabled = true;
        go(id).then(function (said) { b.disabled = false; if (said) { finder.reset(); say.textContent = said; } return load(); });
      });
      return wrap;
    }
    function personOf(id) { return st.all.filter(function (r) { return r.individual_id === id; })[0] || null; }
    function makeLead(id) {
      var cur = st.lead, mine = personOf(id), order = cur ? (cur.order || 1) : 1;
      if (cur && cur.individual_id === id) return Promise.resolve("That person is already the lead.");
      var first = mine
        ? admin("update", { id: mine.id, changes: { role: "primary_instructor", order: order }, expected_updated_at: mine.updated_at }, ATT)
        : admin("assign", { data: { scheduled_class_id: rec.id, role: "primary_instructor", individual_id: id, order: order } }, ATT);
      return first.then(function (res) {
        if (!(res.status === 200 && res.body && res.body.ok)) { say.textContent = fail(res); return null; }
        var done = function () {
          return "The lead instructor is now " + (mine ? nameOf(mine) : "the person you chose") + ". Everyone in the class was emailed the change" + (mine ? "." : ", and the new lead was emailed that they are assigned to teach.") + (cur ? " " + nameOf(cur) + " stays on as an instructor." : "") + " Messages shows the results.";
        };
        if (!cur) return done();
        return admin("update", { id: cur.id, changes: { role: "instructor", order: Math.min(nextOrder(), 50) }, expected_updated_at: cur.updated_at }, ATT).then(function (res2) {
          if (res2.status === 200 && res2.body && res2.body.ok) return done();
          say.textContent = "The new lead was saved, but the old lead could not be moved to instructor: " + fail(res2); return null;
        });
      });
    }
    function addOne(id) {
      if (personOf(id)) return Promise.resolve("That person is already an instructor of this class.");
      return admin("assign", { data: { scheduled_class_id: rec.id, role: "instructor", individual_id: id, order: nextOrder() } }, ATT).then(function (res) {
        if (res.status === 200 && res.body && res.body.ok) return "Added. They were emailed that they are assigned to teach.";
        say.textContent = fail(res); return null;
      });
    }
    box.appendChild(mk("div", "hint", "These buttons save at once and email the people in the class. The class details on the Edit tab are saved with Save changes."));
    box.appendChild(list);
    box.appendChild(chooser("Change the lead instructor", "Make lead", makeLead));
    box.appendChild(chooser("Add another instructor", "Add instructor", addOne));
    box.appendChild(say);
    load();
    return box;
  }

  function renderClassReady() {
    var box = $("cReadyBox"); if (!box) return;
    box.textContent = "";
    var sch = cCtx.schema;
    function group(title, status) {
      box.appendChild(mk("div", "sum", title));
      var miss = 0;
      classNeeds(sch, status).forEach(function (f) {
        var ok;
        if (f === "starts_at") ok = !!cField("starts_at").date.value && !!cField("starts_at").time.value;
        else { var v = cValue(f); ok = v !== null && v !== undefined; }
        if (!ok) miss++;
        box.appendChild(mk("div", ok ? "ok" : "todo", (ok ? "✓ " : "○ ") + humanize(f)));
      });
      var vid = cField("venue_id").el.value, v = vid ? ConsoleNames.venueById(vid) : null;
      var vok = !!v && v.status === "active"; if (!vok) miss++;
      box.appendChild(mk("div", vok ? "ok" : "todo", (vok ? "✓ " : "○ ") + "An active venue"));
      return miss;
    }
    group("To schedule it:", "scheduled");
    group("To open enrolment:", "enrolling");
  }

  function cClearEditErrs() {
    $("cEditMsg").textContent = ""; $("cEditReload").hidden = true;
    Object.keys(cCtx.fields).forEach(function (n) {
      var e = $("ee_c_" + n); if (e) e.textContent = "";
      if (cCtx.fields[n].summary) cCtx.fields[n].summary.className = "";
    });
    document.querySelectorAll("#cEditSections details.more > summary").forEach(function (sm) { sm.className = ""; });
  }
  function cOpenSec(f) {
    if (!f.sec) return;
    f.sec.open = true;
    var m = f.sec.closest("details.more");
    if (m) { m.open = true; m.firstChild.className = "haserr"; }
  }

  // Collect what changed. Returns {changes, bad:{field:message}}
  function collectClassChanges() {
    var changes = {}, bad = {};
    Object.keys(cCtx.fields).forEach(function (n) {
      var f = cCtx.fields[n];
      if (n === "starts_at") {
        var ini = f.initial, tz = cTz() || "";
        if (f.date.value === ini.date && f.time.value === ini.time && tz === ini.tz) return;   // untouched: leave it as stored
        var r = cStartsUtc();
        if (r.bad) { bad.starts_at = r.bad; return; }
        var orig = cRec.starts_at === undefined ? null : cRec.starts_at;
        if (r.value !== orig) changes.starts_at = r.value;
        return;
      }
      var v = readValue(f);
      if (v === undefined) { bad[n] = "Enter a number."; return; }
      if (n === "cancelled_reason" && cField("status").el.value !== "cancelled") v = null;
      var o = cRec[n] === undefined ? null : cRec[n];
      if (v !== o) changes[n] = v;
    });
    return { changes: changes, bad: bad };
  }
  function classDirty() {
    if (!cRec) return false;
    var c = collectClassChanges();
    return Object.keys(c.bad).length > 0 || Object.keys(c.changes).length > 0;
  }
  function dropClassEdit() { cRec = null; cCtx.fields = {}; $("cEditPanel").hidden = true; }
  function closeClassEdit() { dropClassEdit(); closeHub(); }
  function openClassEdit(rec) {
    $("cMsg").textContent = "";
    var areasP = admin("list", { limit: 200 }, "discovery_areas").then(function (r) { return r.status === 200 && r.body && r.body.ok ? (r.body.data.records || []) : []; }, function () { return []; });
    Promise.all([getClassSchema(), ConsoleNames.loadVenueChoices(), ConsoleNames.loadCurriculumChoices(), areasP]).then(function (both) {
      var schema = both[0]; cAreas = both[3];
      if (!schema) { $("cMsg").textContent = "Could not load the class form. Try again."; return; }
      cCtx.schema = schema; cRec = rec;
      $("cEditTitle").textContent = "Edit " + (rec.title || "class");
      $("cEditSub").textContent = "Slug: " + rec.slug + " (cannot be changed)";
      cBuildSections(rec);
      cClearEditErrs();
      $("cEditPanel").classList.remove("showhelp"); $("cHelpBtn").textContent = "Show field help";
      $("cEditPanel").hidden = false;
    });
  }
  // ---- the class page: tabs Overview, People, Attendance, Edit. The list is unchanged; tapping a class opens this.
  var HUB_TABS = ["Overview", "People", "Attendance", "Edit"], hub = { rec: null, tab: "" };
  function hubPane(t) { return $("cTab" + t); }
  function closeHub() {
    hub.rec = null; hub.tab = "";
    ["Overview", "People", "Attendance"].forEach(function (t) { hubPane(t).textContent = ""; });
    $("cHub").hidden = true; $("cMain").hidden = false;
  }
  function openHub(rec, tab) {
    $("cMsg").textContent = "";
    hub.rec = rec; hub.tab = "";
    $("cHubTitle").textContent = rec.title || "(no title)";
    $("cHubSub").textContent = classWhen(rec);
    $("cMain").hidden = true; $("cHub").hidden = false;
    showTab(tab || "Overview");
    window.scrollTo(0, 0);
  }
  function showTab(t) {
    if (t === hub.tab) return;
    if (hub.tab === "Edit") { askDiscard(classDirty(), function () { dropClassEdit(); activateTab(t); }); return; }
    activateTab(t);
  }
  // The Overview in plain words (DT-30): when, where, how many people, price, status. The full field list stays one tap away under "All fields".
  var STATUS_WORD = { identified: "An idea (no date yet)", scheduled: "Scheduled", enrolling: "Open for sign-ups", completed: "Finished", cancelled: "Cancelled" };
  function overviewRows(rec) {
    var rows = [];
    function add(label, value) { if (value !== undefined && value !== null && value !== "") rows.push([label, String(value)]); }
    add("Status", STATUS_WORD[rec.status] || rec.status);
    if (rec.status === "cancelled") add("Why it was cancelled", rec.cancelled_reason);
    add("Kind", (CTYPES[rec.class_type] || rec.class_type) + (rec.is_public ? ", shown in the public list" : ", not in the public list"));
    add("When", classWhen(rec) + (rec.starts_at && rec.duration_minutes ? " (" + rec.duration_minutes + " minutes)" : ""));
    var v = rec.venue_id ? ConsoleNames.venueById(rec.venue_id) : null;
    add("Where", rec.venue_id
      ? (v ? v.name : "(venue not found)") + (rec.venue_room_label ? ", " + rec.venue_room_label : "") + (rec.is_venue_confirmed ? "" : " (not confirmed with the venue yet)")
      : "No venue yet");
    if (rec.capacity_minimum != null && rec.capacity_target != null && rec.capacity_max != null) {
      add("People", "at least " + rec.capacity_minimum + " to run, aiming for " + rec.capacity_target + ", up to " + rec.capacity_max);
    }
    if (rec.registered_count != null) {
      add("Signed up", rec.registered_count + (rec.waitlist_count ? ", plus " + rec.waitlist_count + " on the waiting list" : "") + (rec.attended_count ? "; " + rec.attended_count + " came" : ""));
    }
    if (rec.price_cents != null) add("Price", rec.price_cents === 0 ? "Free" : money(rec.price_cents) + (rec.price_basis === "per_person" ? " per person" : " per session"));
    if (rec.session_number) add("Series", "Session " + rec.session_number);
    add("Venue notes", rec.venue_notes);
    add("Accessibility", rec.accessibility_notes);
    if (rec.organizer_name) add("Organizer", [rec.organizer_name, rec.organizer_email, rec.organizer_phone].filter(Boolean).join(", "));
    add("About", rec.description);
    return rows;
  }
  function drawOverview(rec, host) {
    host.textContent = "";
    var detail = mk("div", "detail");
    overviewRows(rec).forEach(function (r) { detail.appendChild(line(r[0], r[1])); });
    var all = mk("details", "allfields"); all.appendChild(mk("summary", "", "All fields"));
    var raw = mk("div", "rawfields"), done = {};
    ["title", "slug", "status", "class_type", "starts_at", "time_zone", "venue_id", "venue_room_label", "id"].forEach(function (f) {
      if (rec[f] !== undefined) { raw.appendChild(line(f, str(rec[f]))); done[f] = 1; }
    });
    Object.keys(rec).sort().forEach(function (f) { if (!done[f]) raw.appendChild(line(f, str(rec[f]))); });
    all.appendChild(raw);
    var jl = mk("button", "chiplink", "Journal"); jl.type = "button";
    jl.addEventListener("click", function () { ConsoleDialogs.openJournal({ scheduled_class_id: rec.id }, "Journal: " + (rec.title || "class")); });
    host.appendChild(classActions(rec)); host.appendChild(jl); host.appendChild(detail); host.appendChild(all);
  }
  function drawPeople(rec, host) {
    host.textContent = "";
    host.appendChild(classInstructors(rec));
    var say = mk("div", "msg"); say.setAttribute("role", "status");
    var det = mk("details", "addbox"); det.id = "cPeopleAdd";
    det.appendChild(mk("summary", "", "Add a student or instructor"));
    det.appendChild(assignForm({ cls: rec, onCancel: function () { det.open = false; }, onAdded: function (d, said) { say.textContent = said; det.open = false; } }));
    host.appendChild(det); host.appendChild(say);
    host.appendChild(mk("div", "hint", "Students and each person’s attendance are on the Attendance tab."));
  }
  function activateTab(t) {
    hub.tab = t;
    HUB_TABS.forEach(function (n) {
      var on = n === t, b = $("cTabBtn" + n);
      b.setAttribute("aria-selected", on ? "true" : "false"); b.tabIndex = on ? 0 : -1; hubPane(n).hidden = !on;
    });
    var rec = hub.rec, p = hubPane(t);
    if (t === "Overview") drawOverview(rec, p);
    else if (t === "People") drawPeople(rec, p);
    else if (t === "Attendance") openAttendance(rec, p);
    else openClassEdit(rec);
  }
  $("cTabs").addEventListener("click", function (e) { var b = e.target.closest("[data-t]"); if (b) showTab(b.getAttribute("data-t")); });
  $("cTabs").addEventListener("keydown", function (e) {
    var i = HUB_TABS.indexOf(hub.tab), n = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : -1;
    if (n < 0) return;
    e.preventDefault(); n = (n + HUB_TABS.length) % HUB_TABS.length;
    $("cTabBtn" + HUB_TABS[n]).focus(); showTab(HUB_TABS[n]);
  });
  $("cHubBack").addEventListener("click", function () { askDiscard(classDirty(), closeClassEdit); });

  function cIssueText(p, f) {
    var m = CISSUE[p.field] && CISSUE[p.field][p.issue];
    if (m) return m;
    if (p.issue === "required") return "Required.";
    if (p.issue === "invalid_format") return f && f.def && f.def.format === "email" ? "That email address does not look right." : "That value is not valid.";
    if (p.issue === "out_of_range") return "That number is outside the allowed range.";
    return ISSUE[p.issue] || "That value is not valid.";
  }

  $("cEditForm").addEventListener("submit", function (e) {
    e.preventDefault();
    if (!cRec) return;
    cClearEditErrs();
    var c = collectClassChanges(), badKeys = Object.keys(c.bad);
    if (badKeys.length) {
      badKeys.forEach(function (n) { $("ee_c_" + n).textContent = c.bad[n]; cOpenSec(cCtx.fields[n]); });
      $("cEditMsg").textContent = "Not saved. Fix the marked fields.";
      return;
    }
    if (!Object.keys(c.changes).length) { $("cEditMsg").textContent = "Nothing changed."; return; }
    $("cEditSave").disabled = true;
    admin("update", { id: cRec.id, changes: c.changes, expected_updated_at: cRec.updated_at }, "scheduled_classes").then(function (res) {
      $("cEditSave").disabled = false;
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status === 200 && res.body && res.body.ok) {
        cNewId = cRec.id;
        var told = ["starts_at", "time_zone", "duration_minutes", "venue_id", "venue_room_label", "venue_notes"].some(function (k) { return k in c.changes; });
        $("cNotice").textContent = "Saved " + (c.changes.title || cRec.title) + "." + (told ? " Everyone placed in it is being emailed what changed. Messages shows the result." : "");
        closeClassEdit(); loadClasses();
        return;
      }
      var err = res.body && res.body.error;
      if (res.status === 409) { $("cEditMsg").textContent = "This class changed since you opened it. Nothing was saved."; $("cEditReload").hidden = false; return; }
      if (res.status === 404) { $("cEditMsg").textContent = "This class no longer exists."; $("cEditReload").hidden = false; return; }
      if (res.status === 400 && err && err.problems && err.problems.length) {
        var other = [], first = null, n = 0;
        err.problems.forEach(function (p) {
          var f = cCtx.fields[p.field];
          if (f) {
            $("ee_c_" + p.field).textContent = cIssueText(p, f);
            cOpenSec(f); if (f.summary) f.summary.className = "haserr"; n++;
            if (!first) first = f.el;
          } else other.push(humanize(p.field) + (p.issue === "required" ? " (required)" : ""));
        });
        $("cEditMsg").textContent = "Not saved. " + (n ? n + " field" + (n === 1 ? "" : "s") + " need attention, marked below." : "")
          + (other.length ? " Also needed: " + other.join(", ") + "." : "");
        if (first) first.scrollIntoView({ block: "center" });
        return;
      }
      $("cEditMsg").textContent = adminProblem(res.status);
    });
  });
  function liveClassReady() { var b = $("cReadyBox"); if (b && !b.hidden) renderClassReady(); }
  $("cEditSections").addEventListener("input", liveClassReady);
  $("cEditSections").addEventListener("change", liveClassReady);
  $("cHelpBtn").addEventListener("click", function () {
    var on = $("cEditPanel").classList.toggle("showhelp");
    $("cHelpBtn").textContent = on ? "Hide field help" : "Show field help";
  });
  $("cEditCancel").addEventListener("click", function () {
    askDiscard(classDirty(), closeClassEdit);
  });
  $("cEditReload").addEventListener("click", function () { closeClassEdit(); loadClasses(); });

  function resetClasses() {
    cLoaded = false; cNewId = ""; cAll = []; cSeq++;
    $("cList").textContent = ""; $("cCount").textContent = ""; $("cChecked").textContent = "";
    $("cMsg").textContent = ""; $("cNotice").textContent = ""; $("cEmpty").hidden = true; $("cNoMatch").hidden = true; $("cRetry").hidden = true;
    Array.prototype.forEach.call(cChecks(), function (c) { c.checked = true; });
    try { sessionStorage.removeItem(CF_STORE); } catch (e) {}
    cFilterSummary(); closeClassForm(); closeClassEdit();
  }
  $("cTitle").addEventListener("input", function () { if (!cSlugTouched) $("cSlug").value = slugify($("cTitle").value); });
  $("cSlug").addEventListener("input", function () { cSlugTouched = true; });
  $("cAddBtn").addEventListener("click", openClassForm);
  $("cCancelBtn").addEventListener("click", closeClassForm);
  $("cRefresh").addEventListener("click", function () { $("cNotice").textContent = ""; loadClasses(); });
  $("cFilters").addEventListener("change", function () { cSaveFilters(); cFilterSummary(); renderClasses(); });
  $("cShowAll").addEventListener("click", cShowEverything);
  $("cNoMatchAll").addEventListener("click", cShowEverything);
  $("cRetry").addEventListener("click", function () { loadClasses(); });
  cRestoreFilters();
  $("cAddForm").addEventListener("submit", function (e) {
    e.preventDefault(); cClearErrs();
    var ty = $("cType").value, pub = $("cPublic").value, bad = false;
    if (!ty) { $("eCType").textContent = "Choose one."; bad = true; }
    if (!pub) { $("eCPublic").textContent = "Choose one."; bad = true; }
    var nums = { capacity_minimum: $("cMin").value, capacity_target: $("cTarget").value, capacity_max: $("cMax").value };
    Object.keys(nums).forEach(function (k) {
      var n = wholeNum(nums[k]);
      if (n === null || isNaN(n)) { $(CADD_ERR[k]).textContent = "Enter a whole number."; bad = true; } else nums[k] = n;
    });
    if (bad) return;
    var data = { title: $("cTitle").value, slug: $("cSlug").value, class_type: ty, program_slug: "launch", status: "identified", is_public: pub === "yes" };
    Object.keys(nums).forEach(function (k) { data[k] = nums[k]; });
    $("cSaveBtn").disabled = true;
    admin("create", { data: data }, "scheduled_classes").then(function (res) {
      $("cSaveBtn").disabled = false;
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status === 200 && res.body && res.body.ok) {
        cNewId = res.body.data.id;
        $("cNotice").textContent = "Added " + res.body.data.title + " (an idea, no date yet).";
        closeClassForm(); loadClasses();
        return;
      }
      var probs = res.status === 400 && res.body && res.body.error && res.body.error.problems;
      if (probs && probs.length) {
        var other = [];
        probs.forEach(function (p) {
          var target = CADD_ERR[p.field];
          var text = (p.field === "slug" && p.issue === "invalid_format") ? "Use lowercase letters, numbers and underscores only."
                   : (CISSUE[p.field] && CISSUE[p.field][p.issue]) || (ISSUE[p.issue] || "That value is not valid.");
          if (target) $(target).textContent = text; else other.push(p.field + " (" + p.issue + ")");
        });
        if (other.length) $("cFMsg").textContent = "Could not save: " + other.join(", ");
        return;
      }
      $("cFMsg").textContent = adminProblem(res.status);
    });
  });


  var aClasses = [], aClassById = {};

  function loadClassChoices() {
    return admin("list", { limit: 200 }, "scheduled_classes").then(function (res) {
      if (res.status === 200 && res.body.ok) { aClasses = res.body.data.records || []; aClassById = {}; aClasses.forEach(function (c) { aClassById[c.id] = c; }); }
    });
  }

  // A small person finder: type part of a name, pick one.
  function personFinder() {
    var wrap = mk("div"), cur = mk("div", "note", "Nobody chosen."), search = mk("input"), results = mk("div");
    var chosen = { id: "", name: "" };
    search.type = "text"; search.placeholder = "Search by name"; search.autocomplete = "off"; search.setAttribute("aria-label", "Search by name");
    search.addEventListener("input", function () {
      var q = search.value.trim().toLowerCase(); results.textContent = "";
      if (!q) return;
      peopleList().then(function (list) {
        results.textContent = "";
        var m = peopleMatches(list, q), shown = m.exact.length ? m.exact : m.near;
        if (!m.exact.length && m.near.length) results.appendChild(mk("div", "hint", "No one matches every word. Closest matches:"));
        shown.slice(0, 8).forEach(function (p) {
          var b = mk("button", "quiet", pFull(p)); b.type = "button";
          b.addEventListener("click", function () { chosen.id = p.id; chosen.name = pFull(p); cur.textContent = "Chosen: " + chosen.name; results.textContent = ""; search.value = chosen.name; });
          results.appendChild(b);
        });
        if (!results.firstChild) results.appendChild(mk("div", "hint", "No one by that name. Choose “Someone new” to add them."));
      });
    });
    wrap.appendChild(cur); wrap.appendChild(search); wrap.appendChild(results);
    return { el: wrap, id: function () { return chosen.id; }, reset: function () { chosen.id = ""; chosen.name = ""; cur.textContent = "Nobody chosen."; search.value = ""; results.textContent = ""; } };
  }

  // The lead-instructor picker: only people on the instructor roster with an active entry. When the request has a Colorado ZIP only
  // instructors who live in that ZIP's state show (the server derives residence_state from the person's address; only the state comes
  // here). Without a ZIP all active instructors show, and one with no address on file says so. Nothing here creates anyone.
  function stateOfZip(zip) { return /^8[01][0-9]{3}$/.test(zip || "") ? "CO" : ""; }   // Colorado only for now; another state adds its rule here
  function instructorFinder(state) {
    var wrap = mk("div"), cur = mk("div", "note", "Nobody chosen."), search = mk("input"), results = mk("div");
    var chosen = { id: "", name: "" }, roster = null;
    search.type = "text"; search.placeholder = "Search instructors by name"; search.autocomplete = "off"; search.setAttribute("aria-label", "Search instructors by name");
    function nameOf(r) { var p = r.person || {}; return p.display_name || [p.given_name, p.family_name].filter(Boolean).join(" ") || "(no name)"; }
    function draw() {
      results.textContent = "";
      if (roster === null) { results.appendChild(mk("div", "hint", "Loading instructors…")); return; }
      var q = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
      var eligible = roster.filter(function (r) { return !(r.person && r.person.unavailable) && (!state || r.residence_state === state); });
      var shown = eligible.filter(function (r) { var n = nameOf(r).toLowerCase(); return q.every(function (w) { return n.indexOf(w) >= 0; }); });
      shown.slice(0, 12).forEach(function (r) {
        var b = mk("button", "quiet", nameOf(r) + (!state && !r.residence_state ? " (no address on file)" : "")); b.type = "button";
        b.addEventListener("click", function () { chosen.id = r.individual_id; chosen.name = nameOf(r); cur.textContent = "Chosen: " + chosen.name; search.value = chosen.name; results.textContent = ""; });
        results.appendChild(b);
      });
      if (!shown.length) results.appendChild(mk("div", "hint", eligible.length ? "No instructor matches that name." :
        (state ? "No active instructor lives in " + state + ". Open an instructor in the Instructors station and tap Add address."
               : "No active instructors yet. Add them in the Instructors station.")));
    }
    search.addEventListener("input", draw);
    admin("list", { filters: { status: "active" }, limit: 200, expand: true }, "instructor_rosters").then(function (r) {
      roster = (r.status === 200 && r.body.ok) ? (r.body.data.records || []) : [];
      draw();
    });
    wrap.appendChild(cur); wrap.appendChild(search); wrap.appendChild(results); draw();
    return { el: wrap, id: function () { return chosen.id; }, reset: function () { chosen.id = ""; chosen.name = ""; cur.textContent = "Nobody chosen."; search.value = ""; draw(); } };
  }

  function classFail(res) {
    var ps = (res.body && res.body.error && res.body.error.problems) || [];
    if (!ps.length) return adminProblem(res.status);
    return ps.map(function (p) { return "Could not build the class: " + (LABELS[p.field] || p.field) + ": " + cIssueText(p, null); }).join(" ");
  }

  // The ZIPs of the region a request belongs to, as a lookup; null when it has none (then nothing is filtered).
  function venueZip(v) { var a = (v.place && v.place.address) || {}; return String(a.postal_code || v.postal_code || "").slice(0, 5); }
  function regionZipsOfZip(areas, zip) {   // the ZIP lookup of the live region holding this ZIP, or null
    var hit = null;
    areas.forEach(function (a) { if (!hit && a.kind === "region" && a.is_active && !a.deleted_at && (a.zip_codes || []).some(function (z) { return String(z).slice(0, 5) === zip; })) hit = a; });
    if (!hit) return null;
    var m = {}; (hit.zip_codes || []).forEach(function (z) { m[String(z).slice(0, 5)] = 1; }); return m;
  }
  function regionZipsFor(areas, req) {
    var live = areas.filter(function (a) { return a.kind === "region" && a.is_active && !a.deleted_at; }), hit = null;
    live.forEach(function (a) { if (!hit && req.region_id && a.id === req.region_id) hit = a; });
    live.forEach(function (a) { if (!hit && (a.zip_codes || []).some(function (z) { return String(z).slice(0, 5) === req.postal_code; })) hit = a; });
    if (!hit) return null;
    var m = {}; (hit.zip_codes || []).forEach(function (z) { m[String(z).slice(0, 5)] = 1; }); return m;
  }
  // The "build a class" part of Put in a class: curriculum, venue and room, date and time, and a lead instructor.
  function buildClassBox(uid, req) {
    var el = mk("div", "addbox"), titleTouched = false;
    function opt(sel, v, t) { var o = mk("option", "", t); o.value = v; sel.appendChild(o); }
    function lab(text, node, key, hint) {
      var l = mk("label", "f", text); node.id = uid + "n_" + key; l.htmlFor = node.id; el.appendChild(l); el.appendChild(node);
      if (hint) el.appendChild(mk("div", "hint", hint));
    }
    el.appendChild(mk("div", "rhead", "Build the class"));
    var TOD = { morning: "Morning", afternoon: "Afternoon", evening: "Evening" };
    if (req) {   // what the requester said about timing: shown so the operator sees it; only the first choice date is filled in
      var asks = [];
      if (req.requested_date) asks.push("First choice date: " + req.requested_date);
      if (req.alternate_requested_date) asks.push("Second choice date: " + req.alternate_requested_date);
      if (TOD[req.requested_time_of_day]) asks.push("Best time of day: " + TOD[req.requested_time_of_day]);
      if (req.preferred_times) asks.push("Other timing notes: " + req.preferred_times);
      if (asks.length) {
        var wish = mk("div", "wishbox"); wish.setAttribute("data-wishes", "1");
        wish.appendChild(mk("div", "wishhead", "They asked for"));
        asks.forEach(function (t) { wish.appendChild(mk("div", "wishline", t)); });
        el.appendChild(wish);
      }
    }
    var cur = mk("select"); opt(cur, "", "No curriculum chosen");
    ConsoleNames.curricula().forEach(function (c) { opt(cur, c.id, curriculumLabel(c)); });
    lab("Curriculum", cur, "cur");
    if (req && req.curriculum_id) {   // the requester picked a topic on the form: offer it, the operator may keep it or change it
      var askedC = ConsoleNames.curriculumAsked(req.curriculum_id);
      if (askedC) { cur.value = req.curriculum_id; el.appendChild(mk("div", "hint", "Chosen by the requester on the form: " + askedC + ". It is filled in; change it if it does not suit.")); }
      else el.appendChild(mk("div", "hint", "The requester picked a curriculum that is no longer active. Choose another, or none."));
    }
    var who = req ? [req.first_name, req.last_name].filter(Boolean).join(" ") : "";
    var title = mk("input"); title.type = "text"; title.maxLength = 200; lab("Title of the class", title, "title");
    title.addEventListener("input", function () { titleTouched = true; });
    function curById() { var r = null; ConsoleNames.curricula().forEach(function (c) { if (c.id === cur.value) r = c; }); return r; }
    function fillTitle() { if (!titleTouched) title.value = ((curById() || {}).title || "Private session") + (who ? " for " + who : ""); }
    cur.addEventListener("change", fillTitle); fillTitle();
    var kind = mk("select"); opt(kind, "private", "One on one"); opt(kind, "group", "Group"); opt(kind, "workshop", "Workshop"); lab("Kind of class", kind, "kind");
    var ven = mk("select"); opt(ven, "", "Not chosen yet");
    ConsoleNames.venues().forEach(function (v) { if (v.status === "active") opt(ven, v.id, v.name || "(no name)"); });
    lab("Venue", ven, "ven");
    if (req && req.preferred_venue_id) {   // the requester picked a venue on the form: offer it, the operator may keep it or change it
      var asked = ConsoleNames.venueAsked(req.preferred_venue_id), askedV = ConsoleNames.venueById(req.preferred_venue_id);
      if (askedV && askedV.status === "active") {
        ven.value = askedV.id;
        el.appendChild(mk("div", "hint", "Chosen by the requester on the form: " + asked + ". It is filled in; change it if it does not suit."));
      } else {
        el.appendChild(mk("div", "hint", "The requester asked for a venue that is no longer active" + (asked ? " (" + asked + ")" : "") + ". Choose another."));
      }
    }
    var zipHint = mk("div", "hint"); el.appendChild(zipHint);   // says when the list is nearest-first or a nearest place was filled in
    var room = mk("select"); lab("Room", room, "room");
    var date = mk("input"); date.type = "date"; lab("Date", date, "date");
    if (req && req.requested_date) date.value = req.requested_date;
    var time = mk("input"); time.type = "time"; lab("Start time", time, "time");
    if (req && TOD[req.requested_time_of_day]) {   // display only: shows which part of the day they asked for, never fills the start time
      var pills = mk("div", "todpills"); pills.setAttribute("data-tod", req.requested_time_of_day);
      Object.keys(TOD).forEach(function (k) {
        var pl = mk("span", "todpill" + (k === req.requested_time_of_day ? " on" : ""), TOD[k]); pl.setAttribute("data-k", k);
        if (k === req.requested_time_of_day) pl.setAttribute("aria-label", TOD[k] + ", asked for by the requester");
        pills.appendChild(pl);
      });
      el.appendChild(pills);
      el.appendChild(mk("div", "hint", "They asked for: " + TOD[req.requested_time_of_day] + ". Pick the actual start time yourself."));
    }
    var tzNote = mk("div", "hint"); el.appendChild(tzNote);
    function tz() { var v = ConsoleNames.venueById(ven.value); return (v && v.place && v.place.time_zone) || ""; }
    function syncVenue() {
      room.textContent = ""; opt(room, "", "No room chosen");
      var v = ConsoleNames.venueById(ven.value); ((v && v.rooms) || []).forEach(function (r) { opt(room, r.label, r.label); });
      tzNote.textContent = tz() ? "The time is in " + tz().replace(/_/g, " ") + " (the venue's time zone)." : ven.value ? "This venue has no time zone yet. Add it to the venue's place before giving the class a time." : "Choose a venue to use its time zone.";
    }
    var venTouched = false;
    ven.addEventListener("change", function () { venTouched = true; syncVenue(); }); syncVenue();
    // The request has a ZIP: ask the server for the venues nearest first, show the distances, and (unless the requester
    // picked a venue, or chose a home) fill in the nearest public place. The operator may change it. Without a ZIP nothing changes.
    if (req && /^[0-9]{5}$/.test(req.postal_code || "")) {
      // Only venues in the request's region are offered (a venue is in a region when its ZIP is on the region's list). The region is
      // the one the requester picked, else the live region holding their ZIP. No region found (not served yet): the list is not limited.
      var areasP = admin("list", { limit: 200 }, "discovery_areas").then(function (r) { return r.status === 200 && r.body && r.body.ok ? (r.body.data.records || []) : []; }, function () { return []; });
      Promise.all([admin("list", { filters: { status: "active" }, limit: 200, expand: true, near_zip: req.postal_code }, "venues"), areasP]).then(function (pair) {
        var res = pair[0], areas = pair[1];
        if (res.status !== 200 || !res.body.ok) return;
        var regionZips = regionZipsFor(areas, req);
        var recs = (res.body.data.records || []).filter(function (v) { return !regionZips || regionZips[venueZip(v)] || v.id === ven.value; }), keep = ven.value, pickedByRequester = !!(req.preferred_venue_id && keep === req.preferred_venue_id);
        if (!regionZips && !recs.some(function (v) { return typeof v.miles === "number"; })) return;   // no ranking and no region: leave the plain list
        while (ven.options.length > 1) ven.remove(1);
        recs.forEach(function (v) {
          if (v.status !== "active") return;
          var m = typeof v.miles === "number" ? (v.miles < 1 ? " (under 1 mile)" : " (" + Math.round(v.miles) + (Math.round(v.miles) === 1 ? " mile)" : " miles)")) : "";
          opt(ven, v.id, (v.name || "(no name)") + m);
        });
        ven.value = keep;
        if (!ven.value) ven.value = "";
        if (pickedByRequester) { zipHint.textContent = "Places are listed nearest first to ZIP " + req.postal_code + "."; return; }
        var near = null;
        recs.forEach(function (v) { if (!near && v.status === "active" && v.is_public_venue === true && typeof v.miles === "number") near = v; });
        if (!venTouched && !ven.value && near && req.location_type !== "home") {
          ven.value = near.id; syncVenue();
          zipHint.textContent = "Nearest public place to ZIP " + req.postal_code + " is filled in. Change it if it does not suit.";
        } else zipHint.textContent = "Places are listed nearest first to ZIP " + req.postal_code + ".";
      });
    }
    el.appendChild(mk("div", "hint", "With a venue, a date and a time it is saved as scheduled. Without them it is saved as an idea you can finish later in Classes."));
    var finder = instructorFinder(req ? stateOfZip(req.postal_code) : ""); el.appendChild(mk("div", "f", "Lead instructor (optional)")); el.appendChild(finder.el);
    var CAP = { "private": [1, 2, 4], group: [2, 8, 15], workshop: [6, 10, 15] };
    function collect() {
      var t = title.value.trim();
      if (!t) return { error: "Give the new class a title." };
      var data = { title: t, slug: (slugify(t) || "class").slice(0, 80) + "_" + Math.random().toString(36).slice(2, 6), class_type: kind.value, program_slug: "launch", status: "identified", is_public: false,
                   capacity_minimum: CAP[kind.value][0], capacity_target: CAP[kind.value][1], capacity_max: CAP[kind.value][2] };
      var c = curById();
      if (c) {
        data.curriculum_id = c.id;
        if (c.session_count > 1) { data.series_id = newUuid(); data.session_number = 1; }
      }
      if (date.value || time.value) {
        if (!date.value || !time.value) return { error: "Give both a date and a time, or neither." };
        if (!ven.value) return { error: "Choose a venue for a class with a date." }; if (!tz()) return { error: "This venue has no time zone, so the class time cannot be set. Add the time zone to the venue's place first (Places)." };
        var u = zonedToUtc(date.value, time.value, tz());
        if (!u) return { error: "That date or time is not valid." };
        data.starts_at = u; data.time_zone = tz();
      }
      if (ven.value) { data.venue_id = ven.value; if (room.value) data.venue_room_label = room.value; }
      if (data.venue_id && data.starts_at) {
        data.status = "scheduled"; data.is_venue_confirmed = false;
        data.duration_minutes = Math.max(15, Math.min(600, c ? c.minutes_per_session : 60));
      }
      return { data: data, instructor: finder.id(), series: !!data.series_id && c.session_count > 1 ? c.session_count : 0 };
    }
    return { el: el, collect: collect };
  }

  // The one way to put a person in a class. opts: cls (fixed class) or classes (list to choose from), req (a request record, optional),
  // role (starting role), canBuild (offer "a new class"), onAdded(data, said).
  function assignForm(opts) {
    var uid = "af" + K.afNext() + "_", req = opts.req || null, BUILD = "__new__";
    // A request that names other people (participants) puts them ALL in the class, together; the requester too unless they are not attending.
    var folks = req && Array.isArray(req.participants) ? req.participants : [], attending = !req || req.is_requester_attending !== false;
    function folkName(x) { return [x.first_name, x.last_name].filter(Boolean).join(" ").trim() || "Guest"; }
    var form = mk("form", "eform"); form.noValidate = true; form.autocomplete = "off";
    function field(text, el, key, hint) {
      var l = mk("label", "f", text); el.id = uid + key; l.htmlFor = el.id; form.appendChild(l); form.appendChild(el);
      if (hint) form.appendChild(mk("div", "hint", hint));
    }
    function opt(sel, v, t) { var o = mk("option", "", t); o.value = v; sel.appendChild(o); }
    var clsSel = null, bx = null;
    if (!opts.cls) {
      clsSel = mk("select"); opt(clsSel, "", "Choose a class");
      if (opts.canBuild) { opt(clsSel, BUILD, "+ A new class (build it now)"); var nb = clsSel.lastChild; nb.style.color = "var(--ok)"; nb.style.fontWeight = "700"; }
      (opts.classes || []).slice().sort(function (a, b) { return (a.starts_at || "9") < (b.starts_at || "9") ? -1 : 1; }).forEach(function (c) { opt(clsSel, c.id, (c.title || "(no title)") + " · " + classWhen(c) + " (" + c.status + ")"); });
      field("Class", clsSel, "cls");
      if (opts.canBuild) {
        bx = buildClassBox(uid, req); bx.el.hidden = true; form.appendChild(bx.el);
        clsSel.addEventListener("change", function () { bx.el.hidden = clsSel.value !== BUILD; clsSel.classList.toggle("buildnew", clsSel.value === BUILD); });
      }
    }
    var role = mk("select"); ["student", "primary_instructor", "instructor"].forEach(function (r) { opt(role, r, ROLE_WORD[r]); });
    role.value = opts.role || "student";
    var who = mk("select");
    if (req) role.value = "student";            // from a request the person can only be a student; the lead instructor is chosen with the class
    else field("Role in this class", role, "role");
    if (req && req.individual_id) opt(who, "request", "The requester");
    opt(who, "existing", req ? "Someone we already know" : "Someone we already know"); opt(who, "new", "Someone new");
    who.value = (req && req.individual_id) ? "request" : (req ? "new" : "existing");
    if (!req) field("Who", who, "who");
    var sumBox = null;
    if (req) { sumBox = mk("div", "note"); sumBox.setAttribute("role", "status"); form.appendChild(sumBox); }
    var finder = personFinder(); var exBox = mk("div"); if (!req) { exBox.appendChild(finder.el); form.appendChild(exBox); }
    var nb = mk("div"), nw = {};
    [["given_name", "Given name", req && req.first_name], ["family_name", "Family name", req && req.last_name], ["email", "Email", req && req.email], ["phone", "Phone", req && req.phone]].forEach(function (f) {
      var l = mk("label", "f", f[1]), el = mk("input"); el.type = "text"; el.maxLength = 200; el.id = uid + f[0]; l.htmlFor = el.id; el.value = f[2] || "";
      nb.appendChild(l); nb.appendChild(el); nw[f[0]] = el;
    });
    nb.appendChild(mk("div", "hint", req ? "These details are saved with the student." : "A new one is added to the student list (or the instructor list) as part of this step."));
    if (req) {
      var dt = mk("details", "addbox"); dt.appendChild(mk("summary", "", "Change the name or contact details")); dt.appendChild(nb); form.appendChild(dt);
      var upd = function () {
        var nm = [nw.given_name.value, nw.family_name.value].map(function (x) { return x.trim(); }).filter(Boolean).join(" ") || "This person", em = nw.email.value.trim();
        if (folks.length) {
          var all = (attending ? [nm] : []).concat(folks.map(folkName));
          sumBox.textContent = "Everyone on this request will be placed in this class as students: " + all.join(", ") + " (" + all.length + "). Each person with an email is sent the confirmation; anyone without one is placed and not told.";
          return;
        }
        sumBox.textContent = req.individual_id ? nm + " will be placed in this class as a student." : nm + (em ? " (" + em + ")" : "") + " will be added to the student roster and placed in this class as a student.";
      };
      Object.keys(nw).forEach(function (k) { nw[k].addEventListener("input", upd); }); upd();
    } else form.appendChild(nb);
    var status = mk("select"); opt(status, "", "Automatic (assigned, or the waiting list if the class is full)");
    ATT_STATUSES.forEach(function (s) { opt(status, s, ATT_WORD[s]); }); field("Status", status, "status");
    var ord = mk("input"); ord.type = "number"; ord.min = "1"; ord.max = "50"; ord.step = "1";
    var ordL = mk("label", "f", "Place among the instructors (optional)"); ord.id = uid + "order"; ordL.htmlFor = ord.id; form.appendChild(ordL); form.appendChild(ord);
    function sync() {
      exBox.hidden = who.value !== "existing"; nb.hidden = req ? false : who.value !== "new";
      var ins = role.value !== "student"; ord.hidden = !ins; ordL.hidden = !ins;
    }
    who.addEventListener("change", sync); role.addEventListener("change", sync); sync();
    var btns = mk("div", "btns"), add = mk("button", "btn-primary", "Add to class"); add.type = "submit"; btns.appendChild(add);
    if (opts.onCancel) {
      var back = mk("button", "quiet", "Cancel"); back.type = "button";
      back.addEventListener("click", function () { opts.onCancel(); });
      btns.appendChild(back);
    }
    form.appendChild(btns);
    var msg = mk("div", "msg"); msg.setAttribute("role", "alert"); form.appendChild(msg);
    var dupBox = mk("div", "confirm"); dupBox.hidden = true; form.appendChild(dupBox);
    var checked = false, forcedId = "";
    function resubmit() { setTimeout(function () { if (form.requestSubmit) form.requestSubmit(); else form.dispatchEvent(new Event("submit", { cancelable: true })); }, 0); }   // after the first submit has finished, or the browser ignores it
    form.addEventListener("submit", function (e) {
      e.preventDefault(); msg.textContent = ""; dupBox.hidden = true;
      var building = !opts.cls && clsSel.value === BUILD, cid = opts.cls ? opts.cls.id : clsSel.value, made = null;
      if (!cid) { msg.textContent = "Choose a class."; return; }
      var data = { scheduled_class_id: cid, role: role.value }, person = null;
      var many = folks.length > 0 && role.value === "student";
      if (many && !attending) { /* only the other people on the request are placed */ }
      else if (forcedId) data.individual_id = forcedId;
      else if (who.value === "request") data.individual_id = req.individual_id;
      else if (who.value === "existing") { if (!finder.id()) { msg.textContent = "Choose someone, or choose “Someone new”."; return; } data.individual_id = finder.id(); }
      else {
        person = {};
        Object.keys(nw).forEach(function (k) { var v = nw[k].value.trim(); if (v) person[k] = v; });
        if (!person.given_name) { msg.textContent = "A new student or instructor needs at least a given name."; if (req) dt.open = true; return; }
        if (!checked) {   // before adding someone new, look for the same email or name on file and let the operator decide
          add.disabled = true;
          peopleList().then(function (list) {
            add.disabled = false;
            var em = (person.email || "").toLowerCase(), full = [person.given_name, person.family_name].filter(Boolean).join(" ").toLowerCase();
            var hit = list.filter(function (x) { return x.status !== "erased" && ((em && (x.email || "").toLowerCase() === em) || (person.family_name && pFull(x).toLowerCase() === full)); })[0];
            if (!hit) { checked = true; resubmit(); return; }
            dupBox.textContent = ""; dupBox.hidden = false;
            dupBox.appendChild(mk("div", "", "We already have " + pFull(hit) + (hit.email ? " (" + hit.email + ")" : "") + " on file. Use that one so they are not added twice?"));
            var bs = mk("div", "btns"), yes = mk("button", "btn-primary", "Use " + pFull(hit)), no = mk("button", "btn-secondary", "No, add as someone new"); yes.type = "button"; no.type = "button";
            yes.addEventListener("click", function () { forcedId = hit.id; checked = true; resubmit(); });
            no.addEventListener("click", function () { checked = true; resubmit(); });
            bs.appendChild(yes); bs.appendChild(no); dupBox.appendChild(bs);
          });
          return;
        }
      }
      if (status.value) data.status = status.value;
      if (role.value !== "student" && ord.value.trim()) data.order = Number(ord.value);
      if (req) data.request_id = req.id;
      if (building) { made = bx.collect(); if (made.error) { msg.textContent = made.error; return; } }
      add.disabled = true;
      function place(classId, prefix) {
        data.scheduled_class_id = classId;
        var args = { data: data }; if (person) args.person = person;
        // A new class with a lead instructor: the instructor goes in FIRST, so the student's confirmation email can name them.
        function placeStudent(instructorSaid) {
          return admin("assign", args, ATT).then(function (res) {
            if (res.status === 401) { lock("That key did not work."); return; }
            if (res.status === 200 && res.body && res.body.ok) {
              var d = res.body.data;
              if (d.created_person) K.forgetPeople();
              var told = function (last) {
                var said = (prefix || "") + "Added " + attName(d) + " as " + ROLE_WORD[d.role].toLowerCase() + ": " + ATT_WORD[d.status].toLowerCase() + "."
                  + (d.created_roster_entry ? " Added to the " + (d.role === "student" ? "student" : "instructor") + " list." : "")
                  + (instructorSaid || "")
                  + (!last || last.status === "skipped" ? "" : last.status === "sent" ? " A confirmation email with the calendar file went to " + last.to + "."
                    : last.status === "not_sent" ? " No confirmation email went out (" + (REASON_WORD[last.reason] || String(last.reason).replace(/_/g, " ")) + ")."
                    : " The confirmation email did not go (see the log on their row); you can send it again there.");
                finish(d, said);
              };
              // The CMS wrote the message log; ask it what happened to the confirmation (students only).
              if (d.role !== "student") { told(null); return; }
              return admin("list", { filters: { attendance_id: d.id } }, "communication_logs").then(function (lr) {
                var recs = (lr.body && lr.body.data && lr.body.data.records) || [];
                told(recs.length ? recs[0] : null);
              });
            }
            add.disabled = false;
            msg.textContent = (prefix ? prefix : "") + attFail(res);
          });
        }
        if (made && made.instructor) {
          return admin("assign", { data: { scheduled_class_id: classId, role: "primary_instructor", individual_id: made.instructor }, via_request_id: req ? req.id : undefined }, ATT).then(function (r2) {
            (many ? placeMany : placeStudent)(r2.status === 200 && r2.body && r2.body.ok ? " Lead instructor: " + attName(r2.body.data) + "." : " The lead instructor could not be added (" + attFail(r2) + "); add them from the class Attendance.");
          });
        }
        function placeMany(instructorSaid) {
          var a = { data: { request_id: req.id, scheduled_class_id: classId } };
          if (data.status) a.data.status = data.status;
          if (attending) a.requester = data.individual_id ? { individual_id: data.individual_id } : { person: person };
          return admin("assign_request", a, ATT).then(function (res) {
            if (res.status === 401) { lock("That key did not work."); return; }
            if (res.status === 200 && res.body && res.body.ok) {
              var recs = res.body.data.records || [];
              if (res.body.data.created_people) K.forgetPeople();
              return Promise.all(recs.map(function (r) { return admin("list", { filters: { attendance_id: r.id } }, "communication_logs"); })).then(function (lrs) {
                var parts = recs.map(function (r, i) {
                  var l = ((lrs[i].body && lrs[i].body.data && lrs[i].body.data.records) || [])[0];
                  var how = !l || l.status === "skipped" ? "" : l.status === "sent" ? "emailed" : l.status === "not_sent" ? "not told (" + (REASON_WORD[l.reason] || String(l.reason).replace(/_/g, " ")) + ")" : "email did not go";
                  return attName(r) + " (" + ATT_WORD[r.status].toLowerCase() + (how ? ", " + how : "") + ")";
                });
                var d = recs[0]; d.everyone = recs.map(attName); d.created_roster_entry = true;
                finish(d, (prefix || "") + "Placed " + recs.length + " students: " + parts.join("; ") + "." + (instructorSaid || ""));
              });
            }
            add.disabled = false;
            var probs = (res.body && res.body.error && res.body.error.problems) || [];
            msg.textContent = (prefix || "") + (probs.some(function (p) { return p.issue === "already_in_class"; })
              ? "Someone from this request is already in that class, so nobody was added. Add the others from the class Attendance."
              : probs.length ? "Nobody was added. Check the details: " + probs.map(function (p) { return String(p.field).replace(/_/g, " ").replace(/\./g, " ") + " (" + String(p.issue).replace(/_/g, " ") + ")"; }).join(", ") + "."
              : attFail(res));
          });
        }
        return many ? placeMany("") : placeStudent("");
      }
      function finish(d, said) {
        add.disabled = false;
        finder.reset(); Object.keys(nw).forEach(function (k) { nw[k].value = ""; }); ord.value = ""; checked = false; forcedId = "";
        if (opts.onAdded) opts.onAdded(d, said);
      }
      if (!building) { place(cid); return; }
      admin("create", { data: made.data }, "scheduled_classes").then(function (res) {
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          aClasses = []; cLoaded = false;
          var nm = res.body.data.title;
          place(res.body.data.id, "Built the class " + nm + (made.series ? " (session 1 of " + made.series + "; add the other sessions in Classes)" : "") + ". ");
          return;
        }
        add.disabled = false; msg.textContent = classFail(res);
      });
    });
    return form;
  }

  // On a registration request: put the requester (or anyone) into a class.
  function putInClass(rec, host, said) {
    host.textContent = "Loading…";
    Promise.all([loadClassChoices(), ConsoleNames.loadVenueChoices(), ConsoleNames.loadCurriculumChoices(), admin("list", { filters: { request_id: rec.id }, limit: 50, expand: true }, ATT)]).then(function (all4) {
      var both = [null, all4[3]];
      host.textContent = "";
      var res = both[1];
      if (res.status === 401) { lock("That key did not work."); return; }
      if (said) { var n = mk("div", "note", said); n.setAttribute("role", "status"); host.appendChild(n); }
      var already = (res.status === 200 && res.body.ok) ? (res.body.data.records || []) : [];
      if (already.length) {
        host.appendChild(mk("div", "rhead", "Placed from this request"));
        already.forEach(function (r) { var row = attLine(r, true); row.insertBefore(mk("span", "", attName(r)), row.firstChild); host.appendChild(row); });
      }
      var live = aClasses.filter(function (c) { return c.status !== "cancelled" && c.status !== "completed"; });
      var hb = mk("button", "quiet infoBtn", "ⓘ"); hb.type = "button"; hb.setAttribute("aria-label", "Help: put this request in a class");
      hb.addEventListener("click", function () { openWorkflows(["place_existing", "build_class"]); });
      var hr = mk("div", "rhead"); hr.appendChild(mk("span", "", "Put in a class")); hr.appendChild(hb); host.appendChild(hr);
      if (rec.preferred_venue_id) host.appendChild(mk("div", "hint", "This person asked for: " + (ConsoleNames.venueAsked(rec.preferred_venue_id) || "a venue that can no longer be found") + ". Choose + A new class (build it now) to start from that venue."));
      host.appendChild(assignForm({ classes: live, req: rec, role: "student", canBuild: true, onCancel: function () { host.hidden = true; host.textContent = ""; }, onAdded: function (d, s) {
        host.hidden = true; host.textContent = "";
        var num = d.confirmation_number || rec.confirmation_number;
        var bn = $("reqDone");
        bn.textContent = "Request " + (num ? num + " " : "") + "is closed. " + (d.everyone ? d.everyone.join(", ") + " are in " : attName(d) + " is in ") + ((d["class"] && d["class"].title) || "the class") + ". You will find it in Classes."
          + (d.created_roster_entry ? " Added to the student list." : "");
        bn.hidden = false; $("reqShow").value = "open";
        refreshPlaced().then(function () { bn.scrollIntoView({ block: "nearest" }); });
      } }));
    });
  }

  window.ClassesStation = {
    show: function () { if (!cLoaded) loadClasses(); }, stop: function () { closeClassEdit(); }, forget: function () { cLoaded = false; },
    reset: function () { resetClasses(); aClasses = []; aClassById = {}; }, dirty: function () { return !!(cRec && classDirty()); },
    putInClass: function (rec, host, said) { putInClass(rec, host, said); }, assignForm: function (opts) { return assignForm(opts); },
    classWhen: function (c) { return classWhen(c); }, choices: function () { return loadClassChoices(); }, byId: function (id) { return aClassById ? aClassById[id] : undefined; }
  };
})();
