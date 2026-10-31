/* Roster engine: the one builder behind the Instructors and Students stations (console/instructors.js, console/students.js).
   Moved out of console.js without changing what it does. It reaches the big file only through window.ConsoleKit. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  var $ = function (id) { return document.getElementById(id); };
  var mk = K.mk, admin = K.admin, lock = K.lock, adminProblem = K.adminProblem, line = UI.line, when = window.ConsoleFormat.when, statusToggle = UI.statusToggle, historyBtn = K.historyBtn;
  var peopleList = K.peopleList, peopleMatches = K.peopleMatches, pFull = K.pFull, lProblems = K.lProblems, pProblems = K.pProblems, addrForm = K.addrForm, refreshPlaces = K.refreshPlaces;
  var D = window.ConsoleData, COLL_P = D.COLL_P, COLL_L = D.COLL_L, COLL_LK = D.COLL_LK;
  var fmtClock = { format: function (d) { return window.ConsoleFormat.clock(d); } };

  // ---- Instructors and Students stations. One builder, two configs. A roster entry points at a person: name and contact stay in
  // People and are read in. Adding is one window (pick an existing person or make a new one); nothing is matched for you.
  var RISSUE = { "capabilities:out_of_range": "Use up to 30 tags, each up to 60 characters, separated by commas.", "capabilities:invalid_value": "Each tag needs a few characters, separated by commas.",
                 "bio:out_of_range": "The bio can be up to 2000 characters.", "service_area:out_of_range": "Up to 300 characters.", "notes:out_of_range": "Up to 2000 characters.",
                 required: "Required.", duplicate: "Already on this roster.", invalid_format: "That value is not valid.", out_of_range: "Too long or too short.",
                 invalid_type: "That value is not valid.", invalid_value: "That value is not valid.", not_found: "That person was not found.",
                 immutable: "That cannot be changed.", choose_one: "Choose one.", not_allowed: "Not allowed.",
                 address_required: "An instructor needs an address first. Use Add address on their card, or enter it in the form." };
  var RLABEL = { individual_id: "Person", status: "Status", bio: "Bio", capabilities: "What they can teach or do", service_area: "Where they will travel",
                 availability: "Weekly hours", availability_notes: "Availability notes", notes: "Notes", person: "Person", region_ids: "Regions they work in",
                 "person.given_name": "Given name", "person.family_name": "Family name", "person.email": "Email", "person.phone": "Phone" };
  var RDAYS = [["monday", "Mon"], ["tuesday", "Tue"], ["wednesday", "Wed"], ["thursday", "Thu"], ["friday", "Fri"], ["saturday", "Sat"], ["sunday", "Sun"]];
  var RPERSON = [["given_name", "Given name"], ["family_name", "Family name"], ["email", "Email"], ["phone", "Phone (text messages)"]];

  function rosterProblems(res, map) {
    var ps = (res.body && res.body.error && res.body.error.problems) || [], out = [], mine = {}, existing = "";
    ps.forEach(function (p) {
      var text = (/email$/.test(p.field) && p.issue === "invalid_format") ? "That email address does not look right."
               : (/phone$/.test(p.field) && p.issue === "invalid_format") ? "That phone number does not look right. Use digits, for example 303-555-0142."
               : (RISSUE[p.field + ":" + p.issue] || RISSUE[p.issue] || "That value is not valid.");
      if (p.existing_id) existing = p.existing_id;
      if (map && map[p.field]) mine[p.field] = text; else out.push((RLABEL[p.field] || p.field) + ": " + text);
    });
    if (!ps.length) out.push(adminProblem(res.status));
    return { fields: mine, other: out, existing: existing };
  }
  function rName(rec) { var p = rec.person; return p && !p.unavailable ? (p.display_name || p.given_name || "(no name)") : "(not available)"; }
  function rContact(rec) {
    var p = rec.person; if (!p || p.unavailable) return "";
    var bits = [p.email, p.phone].filter(Boolean);
    if (bits.length && bits.every(function (b) { return b === "(hidden)"; })) return "Contact is private";
    return bits.join(" · ");
  }
  function rField(f, idp, cur) {
    var wrap = mk("div"), l = mk("label", "f", f.label), el;
    if (f.t === "area") { el = mk("textarea"); el.maxLength = 2000; el.value = cur == null ? "" : cur; }
    else if (f.t === "tags") { el = mk("textarea"); el.rows = 3; el.maxLength = 1800; el.value = (cur || []).join(", "); el.style.minHeight = "72px"; }
    else { el = mk("input"); el.type = "text"; el.maxLength = 300; el.value = (cur == null ? "" : cur); }
    el.id = idp + f.k; l.htmlFor = el.id; wrap.appendChild(l); wrap.appendChild(el);
    if (f.hint) wrap.appendChild(mk("div", "hint", f.hint));
    var er = mk("div", "ferr"); wrap.appendChild(er);
    return { wrap: wrap, el: el, err: er, t: f.t };
  }
  function rRead(x) {
    var v = x.el.value.trim();
    if (x.t === "tags") return v ? v.split(/[,;\n]+/).map(function (s) { return s.trim(); }).filter(Boolean) : [];
    return v;
  }
  // The week at a glance (P-99): seven day boxes, the opening and closing time in each; a day with no hours shows a dash. Replaces the one line of text.
  function rHoursGrid(av) {
    var by = {}; (av || []).forEach(function (h) { by[h.day_of_week] = h; });
    var wrap = mk("div", "hwrap"); wrap.appendChild(mk("b", "", "Weekly hours"));
    var gr = mk("div", "hgrid"); gr.setAttribute("role", "list");
    RDAYS.forEach(function (d) {
      var h = by[d[0]], c = mk("div", "hday" + (h ? " on" : "")); c.setAttribute("role", "listitem");
      c.setAttribute("aria-label", d[1] + (h ? " " + h.opens_at + " to " + h.closes_at : " not available"));
      c.appendChild(mk("b", "", d[1]));
      if (h) { c.appendChild(mk("span", "", h.opens_at)); c.appendChild(mk("span", "", h.closes_at)); } else c.appendChild(mk("span", "", "–"));
      gr.appendChild(c);
    });
    wrap.appendChild(gr); return wrap;
  }

  function currTitle(S, id) { var l = S.curr || []; for (var i = 0; i < l.length; i++) if (l[i].id === id) return l[i].title; return "(removed curriculum)"; }
  // Write-only address for an instructor, for operators who may not open People. It never lists or shows existing places or addresses.
  // saveResidence saves a Lives-here link (reusing the place if the address is already saved, silently) and then ends older live Lives-here links,
  // so the person is never left without an address. Resolves {ok, text}.
  function saveResidence(individualId, addr) {
    return admin("list", { filters: { subject_id: individualId }, limit: 50 }, COLL_LK).then(function (old) {
      if (old.status === 401) { lock("That key did not work."); return { ok: false, text: "" }; }
      var olds = (old.status === 200 && old.body.ok ? old.body.data.records || [] : []).filter(function (l) { return l.relationship === "resides_at" && l.status === "active"; });
      return admin("find_by_address", { address: addr.addresses[0] }, COLL_L).then(function (f) {
        if (f.status === 401) { lock("That key did not work."); return { ok: false, text: "" }; }
        var found = (f.status === 200 && f.body.ok) ? (f.body.data.records || []) : [];
        var place = found.length ? Promise.resolve({ status: 200, body: { ok: true, data: found[0] } }) : admin("create", { data: addr }, COLL_L);
        return place.then(function (c) {
          if (c.status === 401) { lock("That key did not work."); return { ok: false, text: "" }; }
          if (!(c.status === 200 && c.body.ok)) return { ok: false, text: "Could not save the address: " + lProblems(c) };
          return admin("create", { data: { subject_type: "individual", subject_id: individualId, relationship: "resides_at", location_id: c.body.data.id, is_primary: true } }, COLL_LK).then(function (k) {
            if (k.status === 401) { lock("That key did not work."); return { ok: false, text: "" }; }
            if (!(k.status === 200 && k.body.ok)) return { ok: false, text: "Could not save the address: " + lProblems(k) };
            return Promise.all(olds.filter(function (l) { return l.location_id !== c.body.data.id; }).map(function (l) {
              return admin("end", { id: l.id }, COLL_LK);   // no stale-check: saving the new main link may just have touched this one
            })).then(function () { refreshPlaces(); return { ok: true, text: "" }; });
          });
        });
      });
    });
  }
  function instructorAddressBox(rec, done) {
    var form = mk("form", "eform"); form.noValidate = true; form.autocomplete = "off";
    form.appendChild(mk("div", "hint", "Where " + rName(rec) + " lives. Saved privately: after you save, only the state is shown here. A new address replaces the old one."));
    var block = addrForm({}); form.appendChild(block);
    var btns = mk("div", "btns"), save = mk("button", "btn-primary", "Save address"), cancel = mk("button", "btn-secondary", "Cancel"); save.type = "submit"; cancel.type = "button";
    btns.appendChild(save); btns.appendChild(cancel); form.appendChild(btns);
    var fm = mk("div", "msg"); fm.setAttribute("role", "alert"); form.appendChild(fm);
    cancel.addEventListener("click", function () { form.remove(); });
    form.addEventListener("submit", function (e) {
      e.preventDefault(); fm.textContent = "";
      var rd = block.read();
      if (!rd.ok) return;
      if (!rd.data.addresses) { fm.textContent = "A person's address needs a street or a PO box."; return; }
      save.disabled = true;
      saveResidence(rec.individual_id, rd.data).then(function (r) {
        save.disabled = false;
        if (!r.ok) { if (r.text) fm.textContent = r.text; return; }
        form.remove(); if (done) done();
      });
    });
    return form;
  }

  function buildRoster(cfg) {
    var P = cfg.pre, S = { cfg: cfg, all: [], loaded: false, seq: 0, newId: "", openId: "", choice: null };
    var g = function (s) { return $(P + s); };
    var root = $(cfg.id + "View");
    root.innerHTML =
      '<div class="bar phead"><div class="ptext"><h2 class="ptitle" id="' + P + 'Title">' + cfg.Many + '</h2><div class="count" id="' + P + 'Count"></div><div class="meta" id="' + P + 'Checked"></div></div>' +
      '<div class="actions"><button type="button" class="btn-link manualBtn" data-m="' + cfg.id + '">Manual</button><button id="' + P + 'Refresh" class="btn-link" type="button">Refresh</button>' +
      '<button id="' + P + 'AddBtn" type="button" class="btn-primary">Add ' + cfg.one + '</button></div></div>' +
      '<form class="panel" id="' + P + 'AddForm" hidden autocomplete="off" novalidate><h2>Add ' + (cfg.one === "instructor" ? "an" : "a") + ' ' + cfg.one + '</h2>' +
      '<div class="hint">Type a name. Pick them from the list, or choose "Someone new". Nothing is matched for you.</div>' +
      '<div class="fsec">Who</div>' +
      '<label class="f" for="' + P + 'Q">Name<span class="req" aria-hidden="true"> *</span></label><input type="text" id="' + P + 'Q" maxlength="100" autocomplete="off">' +
      '<div id="' + P + 'Opts" class="ropts"></div><div class="note" id="' + P + 'Chosen"></div><div class="ferr" id="' + P + 'EPick"></div>' +
      '<div id="' + P + 'New" class="eform" hidden><div class="hint">Their name, email and phone are saved with them.</div></div>' +
      '<div id="' + P + 'AddFields"></div>' +
      '<div class="btns"><button type="submit" id="' + P + 'SaveBtn" class="btn-primary">Add to ' + cfg.Many.toLowerCase() + '</button><button type="button" class="btn-secondary" id="' + P + 'CancelBtn">Cancel</button></div>' +
      '<div class="msg" id="' + P + 'FMsg" role="alert"></div></form>' +
      '<input type="search" id="' + P + 'Search" class="psearch" placeholder="Find by name" aria-label="Find by name" autocomplete="off">' +
      '<div id="' + P + 'Chips"></div>' +
      '<div class="notice" id="' + P + 'Notice" role="status"></div><div class="msg" id="' + P + 'Msg" role="alert"></div>' +
      '<button type="button" class="btn-secondary" id="' + P + 'Retry" hidden>Try again</button><ul id="' + P + 'List"></ul><div id="' + P + 'More"></div>' +
      '<div class="empty" id="' + P + 'Empty" hidden>No ' + cfg.Many.toLowerCase() + ' yet. Add one to begin.</div>' +
      '<div class="empty" id="' + P + 'NoMatch" hidden><b>Nobody matches that.</b><br>Try fewer letters, or <button type="button" class="btn-link" id="' + P + 'Clear">clear the filters and the search</button>.</div>';

    // new-person boxes and roster fields of the add window
    var newEls = {}, addEls = {};
    RPERSON.forEach(function (pf) {
      var l = pf[0] === "given_name" ? UI.requiredLabel(pf[1]) : mk("label", "f", pf[1] + " (optional)"), el = mk("input"); el.type = "text"; el.maxLength = 200; el.autocomplete = "off";
      el.id = P + "N_" + pf[0]; l.htmlFor = el.id; var er = mk("div", "ferr");
      g("New").appendChild(l); g("New").appendChild(el); g("New").appendChild(er); newEls["person." + pf[0]] = { el: el, err: er, k: pf[0] };
    });
    cfg.fields.forEach(function (f) { var x = rField(f, P + "A_", null); g("AddFields").appendChild(x.wrap); addEls[f.k] = x; });
    var addrBlock = null;
    if (cfg.curricula) {   // an instructor needs an address (slice B); saved privately, only the state is shown afterwards
      var ah = mk("div", "eform"); ah.appendChild(mk("div", "f", "Where they live"));
      ah.appendChild(mk("div", "hint", "Required for someone new. Saved privately: only the state is shown afterwards. Leave it blank only if this person already has an address on file."));
      addrBlock = addrForm({ optional: true }); ah.appendChild(addrBlock); g("AddFields").parentNode.insertBefore(ah, g("AddFields"));
    }

    function load() {
      var my = ++S.seq; g("Msg").textContent = ""; g("Retry").hidden = true;
      if (!S.loaded) K.skelOn(g("List"));
      return admin("list", { order: "name", expand: true, limit: 200 }, cfg.coll).then(function (res) {
        if (my !== S.seq) return;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status !== 200 || !res.body.ok) { K.skelOff(g("List")); g("Msg").textContent = "Could not load the " + cfg.Many.toLowerCase() + ". " + adminProblem(res.status); g("Retry").hidden = false; return; }
        S.all = res.body.data.records || []; S.loaded = true;
        var done = function () { fillChips(); render(); g("Checked").textContent = "Last checked " + fmtClock.format(new Date()); };
        if (cfg.placement) {   // Students: who holds a seat in a class right now (P-99). One read of the sign-ups list (the newest 200); null when it could not be read.
          return admin("list", { limit: 200 }, "attendances").then(function (ar) {
            if (my !== S.seq) return;
            if (ar.status !== 200 || !ar.body || !ar.body.ok) { S.placed = null; return; }
            var recs = ar.body.data.records || [], by = {};
            recs.forEach(function (a) { if (a.role === "student" && window.ConsoleWords.att.ATT_OPEN[a.status] && a.status !== "waitlisted") by[a.individual_id] = true; });
            S.placed = { by: by, capped: recs.length >= 200 };
          }, function () { S.placed = null; }).then(function () { if (my === S.seq) done(); });
        }
        if (!cfg.curricula) { done(); return; }
        return Promise.all([admin("list", { limit: 200 }, "curriculums"), admin("list", { limit: 200 }, "discovery_areas")]).then(function (all) {
          var cr = all[0], ar = all[1];
          S.curr = (cr.status === 200 && cr.body.ok) ? (cr.body.data.records || []) : [];
          S.regions = ((ar.status === 200 && ar.body && ar.body.ok) ? (ar.body.data.records || []) : []).filter(function (a) { return a.kind === "region"; });
          done();
        });
      });
    }
    S.load = load;
    function onRoster(personId) { for (var i = 0; i < S.all.length; i++) if (S.all[i].individual_id === personId) return S.all[i]; return null; }
    // ---- Filters (shared chip bar): Status (Active by default); Instructors add "Needs an address" and "No curriculum yet". Sorted by name, 50 at a time.
    var cf = null, show = 50, STEP = 50;
    function chips() {
      if (cf) return cf;
      var fl = [{ id: "status", label: "Status", kind: "multi", options: [{ value: "active", label: "Active" }, { value: "inactive", label: "Inactive" }] }];
      if (cfg.curricula) fl.push({ id: "needs", label: "Needs an address", kind: "toggle", noun: "instructors" }, { id: "nocurr", label: "No curriculum yet", kind: "toggle", noun: "instructors" });
      if (cfg.placement) fl.push({ id: "waiting", label: "Waiting for a class", kind: "toggle", noun: "students" }, { id: "inclass", label: "In a class", kind: "toggle", noun: "students" });
      cf = UI.chipFilters({ mount: g("Chips"), label: cfg.Many + " filters", filters: fl, onChange: function () { show = STEP; g("Notice").textContent = ""; render(); } });
      cf.setSelection({ status: ["active"] });
      return cf;
    }
    S.setStatus = function (vals) { chips().setSelection({ status: vals }); };
    function fillChips() {
      var cs = { active: 0, inactive: 0 };
      S.all.forEach(function (r) { if (cs[r.status] !== undefined) cs[r.status]++; });
      var c = chips(); c.setCounts({ status: cs });
      if (cfg.placement) { c.setBadge("waiting", S.placed ? S.all.filter(sWaiting).length : ""); c.setBadge("inclass", S.placed ? S.all.filter(sIn).length : ""); }
      if (cfg.curricula) { c.setBadge("needs", S.all.filter(function (r) { return r.status === "active" && !r.residence_state; }).length); c.setBadge("nocurr", S.all.filter(function (r) { return r.status === "active" && !(r.curriculum_ids || []).length; }).length); }
    }
    function sIn(r) { return !!S.placed && !!S.placed.by[r.individual_id]; }
    function sWaiting(r) { return !!S.placed && r.status === "active" && !S.placed.by[r.individual_id]; }   // an active student with no seat in a class (never placed, on the waiting list only, or the class is over)
    function render() {
      var q = g("Search").value.trim().toLowerCase(), sel = chips().getSelection(), st = sel.status || [], list = g("List");
      var shown = S.all.filter(function (r) {
        if (st.indexOf(r.status) < 0) return false;
        if (cfg.curricula && (sel.needs || []).length && r.residence_state) return false;
        if (cfg.curricula && (sel.nocurr || []).length && (r.curriculum_ids || []).length) return false;
        if (cfg.placement && (sel.waiting || []).length && !sWaiting(r)) return false;
        if (cfg.placement && (sel.inclass || []).length && !sIn(r)) return false;
        return !q || [rName(r), rContact(r)].join(" ").toLowerCase().indexOf(q) >= 0;
      }).sort(function (a, b) { var x = rName(a).toLowerCase(), y = rName(b).toLowerCase(); return x < y ? -1 : x > y ? 1 : 0; });
      var vis = shown.slice(0, show), had = list.children.length;
      K.skelOff(list); list.textContent = "";
      vis.forEach(function (r) { list.appendChild(row(r)); });
      S.newId = ""; S.openId = "";
      UI.moreBar(g("More"), vis.length, shown.length, STEP, function () { show += STEP; render(); var f = g("List").children[had]; if (f && f.querySelector("button.head")) f.querySelector("button.head").focus(); }, cfg.Many.toLowerCase());
      var noun = cfg.Many.toLowerCase();
      g("Count").textContent = shown.length + (shown.length === 1 ? " " + cfg.one : " " + noun) + (cfg.placement ? (!S.placed ? ". Could not check who is in a class just now, so those two switches show nothing." : S.placed.capped ? ". The class switches count only the newest 200 sign-ups." : "") : "");
      chips().setCount(shown.length !== S.all.length && S.all.length ? shown.length + " of " + S.all.length + " " + noun : "");
      g("Empty").hidden = S.all.length > 0;
      g("NoMatch").hidden = !(S.all.length > 0 && shown.length === 0);
    }

    function row(rec) {
      var li = mk("li", rec.id === S.newId ? "isnew" : "");
      var head = mk("button", "head"); head.type = "button"; head.setAttribute("aria-expanded", "false");
      var top = mk("div", "top");
      top.appendChild(mk("span", "vname", rName(rec)));
      var tgl = (rec.status === "active" || rec.status === "inactive") ? statusToggle(rec, li, { coll: cfg.coll, on: "active", off: "inactive", label: cfg.one, problem: function (res) { return rosterProblems(res).other.join(" "); } }) : null;
      if (!tgl) top.appendChild(mk("span", "type", rec.status || ""));
      head.appendChild(top);
      if (rContact(rec)) head.appendChild(mk("div", "sub", rContact(rec)));
      var more = [];
      if (rec.capabilities && rec.capabilities.length) more.push(rec.capabilities.join(", "));
      if (rec.service_area) more.push(rec.service_area);
      if (more.length) head.appendChild(mk("div", "sub", more.join(" · ")));
      var teach = cfg.curricula ? (rec.curriculum_ids || []).map(function (id) { return currTitle(S, id); }) : [];
      if (teach.length) head.appendChild(mk("div", "sub", "Can teach: " + teach.join(", ")));
      var detail = mk("div", "detail");
      detail.appendChild(actions(rec));
      cfg.fields.forEach(function (f) {
        if (rec[f.k] === undefined) return;
        detail.appendChild(line(f.label, f.t === "tags" ? rec[f.k].join(", ") : String(rec[f.k])));
      });
      if (cfg.curricula) {
        var lv = line("Lives in", rec.residence_state || "No address on file"); lv.id = "live_" + rec.id; detail.appendChild(lv);
        var ab = mk("button", "btn-secondary", rec.residence_state ? "Replace address" : "Add address"); ab.type = "button"; ab.id = "addaddr_" + rec.id;
        var ah = mk("div"); detail.appendChild(ab); detail.appendChild(ah);
        ab.addEventListener("click", function () { if (ah.firstChild) ah.textContent = ""; else ah.appendChild(instructorAddressBox(rec, function () { g("Notice").textContent = "Saved the address for " + rName(rec) + "."; S.openId = rec.id; load(); })); });
      }
      if (cfg.hours && rec.availability && rec.availability.length) detail.appendChild(rHoursGrid(rec.availability));
      if (cfg.hours && rec.availability_notes) detail.appendChild(line("Availability notes", rec.availability_notes));
      detail.appendChild(line("Added", when(rec.created_at)));
      head.addEventListener("click", function () { var open = li.classList.toggle("open"); head.setAttribute("aria-expanded", open ? "true" : "false"); });
      li.appendChild(head); if (tgl) { li.appendChild(tgl.btn); li.appendChild(tgl.msg); } li.appendChild(detail);
      if (rec.id === S.openId) { li.classList.add("open"); head.setAttribute("aria-expanded", "true"); setTimeout(function () { try { li.scrollIntoView({ block: "center" }); } catch (e) {} }, 0); }
      if (rec.id === S.newId) setTimeout(function () { li.classList.remove("isnew"); }, 6000);
      return li;
    }

    function actions(rec) {
      var wrap = mk("div"), r = mk("div", "actions-row");
      var ed = mk("button", "btn-primary", "Edit"), del = mk("button", "btn-danger pdel", "Remove from " + cfg.Many.toLowerCase());
      ed.type = "button"; del.type = "button"; r.appendChild(ed); var hr = historyBtn(rec.individual_id || rec.id, rName(rec)); if (hr) { hr.className = "btn-link"; r.appendChild(hr); } r.appendChild(del);
      var host = mk("div"), box = mk("div", "confirm"); box.hidden = true;
      box.appendChild(mk("div", "", "Remove " + rName(rec) + " from the " + cfg.Many.toLowerCase() + "? Their history is kept. You can add them again later."));
      var b = mk("div", "btns"), yes = mk("button", "btn-danger", "Remove"), no = mk("button", "btn-secondary", "Cancel"), err = mk("div", "msg");
      yes.type = "button"; no.type = "button"; err.setAttribute("role", "alert"); b.appendChild(yes); b.appendChild(no); box.appendChild(b); box.appendChild(err);
      ed.addEventListener("click", function () { box.hidden = true; if (host.firstChild) host.textContent = ""; else host.appendChild(editForm(rec, host)); });
      del.addEventListener("click", function () { host.textContent = ""; box.hidden = !box.hidden; err.textContent = ""; });
      no.addEventListener("click", function () { box.hidden = true; });
      yes.addEventListener("click", function () {
        yes.disabled = true; err.textContent = "";
        admin("soft_delete", { id: rec.id }, cfg.coll).then(function (res) {
          yes.disabled = false;
          if (res.status === 401) { lock("That key did not work."); return; }
          if (res.status === 200 && res.body && res.body.ok) { g("Notice").textContent = "Removed " + rName(rec) + " from the " + cfg.Many.toLowerCase() + "."; load(); }
          else if (res.status === 404) { g("Notice").textContent = "That entry was already gone."; load(); }
          else err.textContent = rosterProblems(res).other.join(" ");
        });
      });
      wrap.appendChild(r); wrap.appendChild(host); wrap.appendChild(box);
      return wrap;
    }

    function editForm(rec, host) {
      var form = mk("form", "eform"); form.noValidate = true; form.autocomplete = "off";
      var els = {}, pEls = {}, hEls = {}, havePerson = rec.person && !rec.person.unavailable;
      if (havePerson) {
        form.appendChild(mk("div", "fsec", "Name and contact"));
        form.appendChild(mk("div", "hint", "Name and contact are saved with them and shared across LAUNCH."));
        RPERSON.forEach(function (pf) {
          var x = rField({ k: pf[0], label: pf[1], t: "text" }, "rp_" + rec.id + "_", rec.person[pf[0]]); form.appendChild(x.wrap); pEls["person." + pf[0]] = x; x.k = pf[0];
        });
      }
      form.appendChild(mk("div", "fsec", cfg.curricula ? "About them" : "Notes"));
      cfg.fields.forEach(function (f) { var x = rField(f, "re_" + rec.id + "_", rec[f.k]); form.appendChild(x.wrap); els[f.k] = x; });
      var cEls = {};
      if (cfg.curricula) {
        form.appendChild(mk("div", "fsec", "What they can teach")); form.appendChild(mk("div", "f", "Curricula they can teach")); form.appendChild(mk("div", "hint", "A guide for choosing an instructor. Nothing is refused if you pick someone who is not ticked."));
        var chosen = rec.curriculum_ids || [], box2 = mk("div"); form.appendChild(box2);
        (S.curr || []).filter(function (c) { return c.status === "active" || chosen.indexOf(c.id) >= 0; }).forEach(function (c) {
          var lab = mk("label", "f"), cb = mk("input"); cb.type = "checkbox"; cb.checked = chosen.indexOf(c.id) >= 0; cb.value = c.id;
          lab.style.display = "flex"; lab.style.gap = "8px"; lab.style.alignItems = "center"; lab.appendChild(cb); lab.appendChild(document.createTextNode(c.title)); box2.appendChild(lab); cEls[c.id] = cb;
        });
        chosen.forEach(function (id) { if (!cEls[id]) { var lab = mk("label", "f"), cb = mk("input"); cb.type = "checkbox"; cb.checked = true; cb.value = id; lab.style.display = "flex"; lab.style.gap = "8px"; lab.style.alignItems = "center"; lab.appendChild(cb); lab.appendChild(document.createTextNode("(removed curriculum)")); box2.appendChild(lab); cEls[id] = cb; } });
        if (!Object.keys(cEls).length) box2.appendChild(mk("div", "hint", "No curricula yet. Add some in the Curriculum station."));
      }
      var gEls = {};
      if (cfg.curricula) {
        form.appendChild(mk("div", "fsec", "Where")); form.appendChild(mk("div", "f", "Regions they work in")); form.appendChild(mk("div", "hint", "Place them in regions of their own, wherever they live. People who look after a region see them there. You can only pick regions you manage."));
        var inRegs = rec.region_ids || [], box3 = mk("div", "rgbox"); form.appendChild(box3);
        (S.regions || []).forEach(function (a) {
          var lab = mk("label", "f"), cb = mk("input"); cb.type = "checkbox"; cb.checked = inRegs.indexOf(a.id) >= 0; cb.value = a.id;
          lab.style.display = "flex"; lab.style.gap = "8px"; lab.style.alignItems = "center"; lab.appendChild(cb); lab.appendChild(document.createTextNode((a.name || "(region)") + (a.state_code ? ", " + a.state_code : ""))); box3.appendChild(lab); gEls[a.id] = cb;
        });
        inRegs.forEach(function (id) { if (!gEls[id]) { var lab = mk("label", "f"), cb = mk("input"); cb.type = "checkbox"; cb.checked = true; cb.value = id; lab.style.display = "flex"; lab.style.gap = "8px"; lab.style.alignItems = "center"; lab.appendChild(cb); lab.appendChild(document.createTextNode("(a region not shown to you)")); box3.appendChild(lab); gEls[id] = cb; } });
        if (!Object.keys(gEls).length) box3.appendChild(mk("div", "hint", "No regions yet. Add some in the Access or Discovery station."));
      }
      if (cfg.hours) {
        form.appendChild(mk("div", "fsec", "Availability")); form.appendChild(mk("div", "f", "Weekly hours")); form.appendChild(mk("div", "hint", "When they can teach. Leave a day empty if they cannot."));
        var by = {}; (rec.availability || []).forEach(function (h) { by[h.day_of_week] = h; });
        RDAYS.forEach(function (d) {
          var rw = mk("div", "hrow"), a = mk("input"), z = mk("input"); a.type = "time"; z.type = "time";
          a.value = by[d[0]] ? by[d[0]].opens_at : ""; z.value = by[d[0]] ? by[d[0]].closes_at : "";
          a.setAttribute("aria-label", d[1] + " from"); z.setAttribute("aria-label", d[1] + " until");
          rw.appendChild(mk("span", "", d[1])); rw.appendChild(a); rw.appendChild(z); form.appendChild(rw); hEls[d[0]] = { a: a, z: z, label: d[1] };
        });
        var he = mk("div", "ferr"); form.appendChild(he); hEls._err = he;
        var an = rField({ k: "availability_notes", label: "Availability notes", t: "area", hint: "Anything the weekly hours cannot say." }, "re_" + rec.id + "_", rec.availability_notes);
        form.appendChild(an.wrap); els.availability_notes = an;
      }
      form.appendChild(mk("div", "fsec", "Record")); var sl = mk("label", "f", "Status"), ss = mk("select"); ss.id = "rst_" + rec.id; sl.htmlFor = ss.id;
      [["active", "Active"], ["inactive", "Inactive (kept, not offered)"]].forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; ss.appendChild(op); });
      ss.value = rec.status || "active"; form.appendChild(sl); form.appendChild(ss);
      var se = mk("div", "ferr"); form.appendChild(se); els.status = { el: ss, err: se, t: "select" };
      var btns = mk("div", "btns"), save = mk("button", "btn-primary", "Save changes"), cancel = mk("button", "btn-secondary", "Cancel");
      save.type = "submit"; cancel.type = "button"; btns.appendChild(save); btns.appendChild(cancel); form.appendChild(btns);
      var msg = mk("div", "msg"); msg.setAttribute("role", "alert"); form.appendChild(msg);
      cancel.addEventListener("click", function () { host.textContent = ""; });
      form.addEventListener("submit", function (e) {
        e.preventDefault(); msg.textContent = "";
        [els, pEls].forEach(function (m) { Object.keys(m).forEach(function (k) { m[k].err.textContent = ""; }); });
        if (cfg.hours) hEls._err.textContent = "";
        var changes = {}, person = {}, bad = false;
        cfg.fields.concat(cfg.hours ? [{ k: "availability_notes", t: "area" }] : []).forEach(function (f) {
          var x = els[f.k], v = rRead(x), cur = rec[f.k];
          if (f.t === "tags") { if (!v.length) { if (cur !== undefined) changes[f.k] = null; } else if (JSON.stringify(v) !== JSON.stringify(cur || [])) changes[f.k] = v; }
          else if (v === "") { if (cur !== undefined) changes[f.k] = null; }
          else if (v !== cur) changes[f.k] = v;
        });
        if (ss.value !== (rec.status || "active")) changes.status = ss.value;
        if (cfg.curricula) {
          var picked = Object.keys(cEls).filter(function (id) { return cEls[id].checked; }).sort(), was = (rec.curriculum_ids || []).slice().sort();
          if (JSON.stringify(picked) !== JSON.stringify(was)) changes.curriculum_ids = picked.length ? picked : null;
        }
        if (cfg.curricula) {
          var pickedR = Object.keys(gEls).filter(function (id) { return gEls[id].checked; }).sort(), wasR = (rec.region_ids || []).slice().sort();
          if (JSON.stringify(pickedR) !== JSON.stringify(wasR)) changes.region_ids = pickedR.length ? pickedR : null;
        }
        if (havePerson) Object.keys(pEls).forEach(function (k) {
          var v = pEls[k].el.value.trim(), cur = rec.person[pEls[k].k];
          if (v === "") { if (cur !== undefined) person[pEls[k].k] = null; } else if (v !== cur) person[pEls[k].k] = v;
        });
        if (cfg.hours) {
          var list = [];
          RDAYS.forEach(function (d) {
            var h = hEls[d[0]], a = h.a.value, z = h.z.value;
            if (!a && !z) return;
            if (!a || !z) { hEls._err.textContent = "Give both a start and an end time for " + h.label + ", or clear both."; bad = true; return; }
            if (a >= z) { hEls._err.textContent = h.label + ": the start has to be before the end."; bad = true; return; }
            list.push({ day_of_week: d[0], opens_at: a, closes_at: z });
          });
          if (!bad && JSON.stringify(list) !== JSON.stringify((rec.availability || []).slice().sort(function (p, q) {
            return RDAYS.map(function (d) { return d[0]; }).indexOf(p.day_of_week) - RDAYS.map(function (d) { return d[0]; }).indexOf(q.day_of_week); }).map(function (h) {
            return { day_of_week: h.day_of_week, opens_at: h.opens_at, closes_at: h.closes_at }; }))) changes.availability = list.length ? list : null;
        }
        if (bad) return;
        if (!Object.keys(changes).length && !Object.keys(person).length) { host.textContent = ""; g("Notice").textContent = "Nothing changed."; return; }
        var args = { id: rec.id, expected_updated_at: rec.updated_at };
        if (Object.keys(changes).length) args.changes = changes;
        if (Object.keys(person).length) args.person = person;
        save.disabled = true;
        admin("update_with_person", args, cfg.coll).then(function (res) {
          save.disabled = false;
          if (res.status === 401) { lock("That key did not work."); return; }
          if (res.status === 200 && res.body && res.body.ok) { S.newId = rec.id; g("Notice").textContent = "Saved changes to " + rName(rec) + "."; if (Object.keys(person).length) { K.peopleStale(); } load(); return; }
          if (res.status === 409) { msg.textContent = "Someone changed this entry while you were editing. Close this, tap Refresh, and try again. Nothing was overwritten."; return; }
          if (res.status === 404) { msg.textContent = "That entry is gone. Tap Refresh."; return; }
          var map = {}; Object.keys(els).forEach(function (k) { map[k] = els[k]; }); Object.keys(pEls).forEach(function (k) { map[k] = pEls[k]; });
          var pr = rosterProblems(res, map);
          Object.keys(pr.fields).forEach(function (k) { map[k].err.textContent = pr.fields[k]; });
          if (pr.other.length) msg.textContent = "Could not save: " + pr.other.join(" ");
        });
      });
      return form;
    }

    // ---- the one add window
    function clearAdd() {
      g("AddForm").reset(); S.choice = null; g("Opts").textContent = ""; g("Chosen").textContent = ""; g("EPick").textContent = ""; g("FMsg").textContent = ""; g("New").hidden = true;
      Object.keys(newEls).forEach(function (k) { newEls[k].err.textContent = ""; });
      Object.keys(addEls).forEach(function (k) { addEls[k].err.textContent = ""; });
      if (addrBlock) { var ci = addrBlock.querySelector("input[id$='_country']"); if (ci) ci.value = "US"; }   // reset() blanks the default country
    }
    function choose(c) {
      S.choice = c; g("EPick").textContent = ""; g("Opts").textContent = "";
      g("New").hidden = !c.isNew;
      g("Chosen").textContent = c.isNew ? "Adding someone new." : "Adding " + c.name + (c.contact ? " (" + c.contact + ")" : "") + "." + (c.noFamily ? " They have no family name on file. A super admin can add it so they are not added twice." : "");
      if (c.isNew) {
        var parts = c.typed.split(/\s+/).filter(Boolean);
        newEls["person.given_name"].el.value = parts.length > 1 ? parts.slice(0, -1).join(" ") : (parts[0] || "");
        newEls["person.family_name"].el.value = parts.length > 1 ? parts[parts.length - 1] : "";
        newEls["person.given_name"].el.focus();
      }
    }
    function showOpts() {
      var q = g("Q").value.trim().toLowerCase(), box = g("Opts"); box.textContent = ""; S.choice = null; g("Chosen").textContent = ""; g("New").hidden = true;
      if (!q) return;
      peopleList().then(function (people) {
        if (g("Q").value.trim().toLowerCase() !== q) return;
        box.textContent = "";
        var m = peopleMatches(people, g("Q").value.trim()), shown = m.exact.length ? m.exact : m.near;
        if (!m.exact.length && m.near.length) box.appendChild(mk("div", "hint", "No one matches every word you typed. Closest matches, so you do not add the same person twice:"));
        shown.slice(0, 8).forEach(function (p) {
          var on = onRoster(p.id), rw = mk("div", "pickrow"), contact = [p.email, p.phone].filter(Boolean).join(" · ");
          var b = mk("button", "btn-secondary", pFull(p) + (contact ? " — " + contact : "") + (on ? " (already on the roster)" : "")); b.type = "button";
          if (on) {
            b.textContent = pFull(p) + (contact ? " — " + contact : "") + " (already " + (cfg.one === "instructor" ? "an " : "a ") + cfg.one + ")";
            b.addEventListener("click", function () { openCard(on.id); });
          } else b.addEventListener("click", function () { g("Q").value = pFull(p); choose({ id: p.id, name: pFull(p), contact: contact, noFamily: !p.family_name }); });
          rw.appendChild(b); box.appendChild(rw);
        });
        var nb = mk("button", "btn-secondary", "Someone new: " + g("Q").value.trim()); nb.type = "button";
        nb.addEventListener("click", function () { choose({ isNew: true, typed: g("Q").value.trim() }); });
        var nr = mk("div", "pickrow"); nr.appendChild(nb); box.appendChild(nr);
      });
    }
    function openCard(id) {
      g("AddForm").hidden = true; g("AddBtn").hidden = false; S.setStatus(["active", "inactive"]); g("Search").value = ""; show = 1000; S.openId = id; render();
    }
    g("AddBtn").addEventListener("click", function () { clearAdd(); g("Notice").textContent = ""; K.forgetPeople(); g("AddForm").hidden = false; g("AddBtn").hidden = true; g("Q").focus(); });
    g("CancelBtn").addEventListener("click", function () { g("AddForm").hidden = true; g("AddBtn").hidden = false; });
    g("Q").addEventListener("input", showOpts);
    g("AddForm").addEventListener("submit", function (e) {
      e.preventDefault(); g("FMsg").textContent = ""; g("EPick").textContent = "";
      Object.keys(newEls).forEach(function (k) { newEls[k].err.textContent = ""; });
      if (!S.choice) { g("EPick").textContent = 'Pick someone from the list, or choose "Someone new".'; return; }
      var data = {}, person = null;
      cfg.fields.forEach(function (f) { var v = rRead(addEls[f.k]); if (f.t === "tags" ? v.length : v) data[f.k] = v; });
      if (S.choice.isNew) {
        person = {};
        RPERSON.forEach(function (pf) { var v = newEls["person." + pf[0]].el.value.trim(); if (v) person[pf[0]] = v; });
        if (!person.given_name) { newEls["person.given_name"].err.textContent = "Required."; return; }
      } else data.individual_id = S.choice.id;
      var args = { data: data }; if (person) args.person = person;
      if (addrBlock) { prepareInstructor(args, person, S.choice); return; }
      sendAdd(args);
    });
    // Instructors: a new person is made first (People), then the address, then the roster entry, so the server rule is met without ever showing an address.
    function prepareInstructor(args, person, choice) {
      var rd = addrBlock.read(); if (!rd.ok) return;
      var addr = rd.data.addresses ? rd.data : null;
      if (choice.isNew && !addr) { g("FMsg").textContent = "An instructor needs an address. Enter where they live."; return; }
      g("SaveBtn").disabled = true;
      function afterPerson(pid) {
        function next() { sendAdd({ data: Object.assign({}, args.data, { individual_id: pid }) }); }
        if (!addr) { next(); return; }
        saveResidence(pid, addr).then(function (r) { if (!r.ok) { g("SaveBtn").disabled = false; if (r.text) g("FMsg").textContent = r.text; return; } next(); });
      }
      if (!choice.isNew) { afterPerson(choice.id); return; }
      admin("create", { data: person }, COLL_P).then(function (res) {
        if (res.status === 401) { lock("That key did not work."); return; }
        if (!(res.status === 200 && res.body && res.body.ok)) { g("SaveBtn").disabled = false; g("FMsg").textContent = "Could not save the person: " + pProblems(res).other.join(" "); return; }
        K.peopleStale();
        S.choice = { id: res.body.data.id, name: person.given_name, contact: "" };   // a retry now uses the person just made, not a second copy
        afterPerson(res.body.data.id);
      });
    }
    function sendAdd(args) {
      g("SaveBtn").disabled = true;
      admin("create_with_person", args, cfg.coll).then(function (res) {
        g("SaveBtn").disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          S.newId = res.body.data.id; g("Notice").textContent = "Added " + rName(res.body.data) + " to the " + cfg.Many.toLowerCase() + ".";
          g("AddForm").hidden = true; g("AddBtn").hidden = false; S.setStatus(["active"]);
          if (res.body.data.created_person) { K.peopleStale(); }
          load(); return;
        }
        var map = {}; Object.keys(newEls).forEach(function (k) { map[k] = newEls[k]; }); Object.keys(addEls).forEach(function (k) { map[k] = addEls[k]; });
        var pr = rosterProblems(res, map);
        Object.keys(pr.fields).forEach(function (k) { map[k].err.textContent = pr.fields[k]; });
        if (pr.existing) {
          g("FMsg").textContent = "That person is already " + (cfg.one === "instructor" ? "an " : "a ") + cfg.one + ". ";
          var ob = mk("button", "btn-secondary", "Open their card"); ob.type = "button"; ob.addEventListener("click", function () { openCard(pr.existing); load(); });
          g("FMsg").appendChild(ob);
        } else if (pr.other.length) g("FMsg").textContent = "Could not save: " + pr.other.join(" ");
      });
    }
    g("Refresh").addEventListener("click", function () { g("Notice").textContent = ""; load(); });
    g("Retry").addEventListener("click", load);
    g("Search").addEventListener("input", function () { show = STEP; render(); });
    g("Clear").addEventListener("click", function () { g("Search").value = ""; show = STEP; chips().clearAll(); S.setStatus(["active"]); render(); g("Search").focus(); });
    S.reset = function () {
      S.loaded = false; S.all = []; S.newId = ""; S.openId = "";
      g("List").textContent = ""; g("Count").textContent = ""; g("Checked").textContent = ""; g("Msg").textContent = ""; g("Notice").textContent = "";
      g("Empty").hidden = true; g("NoMatch").hidden = true; g("Search").value = ""; show = STEP; g("More").textContent = ""; if (cf) cf.setSelection({ status: ["active"] }); g("AddForm").hidden = true; g("AddBtn").hidden = false;
    };
    return S;
  }

  window.ConsoleRoster = { build: buildRoster };
})();
