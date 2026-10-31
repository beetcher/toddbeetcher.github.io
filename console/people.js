/* People station (window.PeopleStation: show, reset, forget, and the doors the kit forwards): the individuals list, filter, search, Add, Edit, Merge and undo,
   Delete, change history, and the Addresses panel on a person's card; plus the date and problem words, the cached pick list and the name matching other
   pages borrow. Moved out of console.js without changing what it does (PP-5). It reaches the big file only through window.ConsoleKit; the address form and
   place words come from console/addresses.js. #peopleView is in index.html. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  var $ = function (id) { return document.getElementById(id); };
  var mk = K.mk, admin = K.admin, lock = K.lock, adminProblem = K.adminProblem, line = K.line, str = K.str, statusToggle = K.statusToggle, historyBtn = K.historyBtn;
  var skelOn = K.skelOn, skelOff = K.skelOff, personHistory = K.personHistory, refreshPlaces = K.refreshPlaces, when = K.when;
  var D = window.ConsoleData, COLL_P = D.COLL_P, COLL_L = D.COLL_L, COLL_LK = D.COLL_LK, REL = D.REL, PERSON_RELS = D.PERSON_RELS;
  var A = window.ConsoleAddresses, addrForm = A.addrForm, lProblems = A.lProblems, locAddr = A.locAddr, locSummary = A.locSummary, placeText = A.placeText;
  var fmtClock = { format: function (d) { return K.clock(d); } };

  // People that fit what was typed. Every word must appear somewhere in the name, email or phone (any order), so "Todd Beecher" finds a Todd Beecher.
  // If nobody fits every word, people who fit ANY word are offered as "close" matches, so a record with only a first name is not missed and then duplicated.
  function peopleMatches(list, q) {
    var words = q.toLowerCase().split(/\s+/).filter(Boolean), live = list.filter(function (p) { return p.status !== "erased"; });
    var text = function (p) { return [pName(p), p.given_name, p.name_to_use, p.family_name, p.email, p.phone].join(" ").toLowerCase(); };
    var all = live.filter(function (p) { var t = text(p); return words.every(function (w) { return t.indexOf(w) >= 0; }); });
    if (all.length || words.length < 2) return { exact: all, near: [] };
    var any = live.filter(function (p) { var t = text(p); return words.some(function (w) { return w.length >= 2 && t.indexOf(w) >= 0; }); });
    return { exact: [], near: any };
  }

  // ---- People station: the individuals, through the same admin door. Restricted details are not reachable from here (the server refuses them).
  var COLL_MERGE = "merge_events";
  var pAll = [], pLoaded = false, pSeq = 0, pNewId = "", pTown = {}, pRoles = {};
  var LIFE_WORDS = { deceased: "Deceased", unknown: "Not sure if living" }, PRIV_WORDS = { restricted: "Protected record", sensitive: "Sensitive record", private: "Private record" };
  // Page join (after first paint, best effort): each person's town from their address links, and their roles from the Instructors and Students lists.
  function joinPeople() {
    var my = pSeq;
    Promise.all([admin("list", { filters: { subject_type: "individual" }, limit: 200 }, COLL_LK), admin("list", { limit: 200 }, COLL_L), admin("list", { limit: 200 }, "instructor_rosters"), admin("list", { limit: 200 }, "student_rosters")]).then(function (rs) {
      if (my !== pSeq) return;
      var ok = function (r) { return r.status === 200 && r.body && r.body.ok ? (r.body.data.records || []) : null; };
      var links = ok(rs[0]), locs = ok(rs[1]), ins = ok(rs[2]), stu = ok(rs[3]), changed = false;
      if (links && locs) {
        var lm = {}; locs.forEach(function (l) { lm[l.id] = l; });
        links.filter(function (l) { return l.status !== "ended"; }).sort(function (a, b) { return (b.is_primary ? 1 : 0) - (a.is_primary ? 1 : 0); }).forEach(function (l) {
          var loc = lm[l.location_id], a = loc && loc.addresses && loc.addresses[0], t = a && a.locality;
          if (t && !pTown[l.subject_id]) { pTown[l.subject_id] = t; changed = true; }
        });
      }
      [[ins, "Instructor"], [stu, "Student"]].forEach(function (p) { (p[0] || []).forEach(function (r) { if (r.individual_id && r.status !== "inactive") { (pRoles[r.individual_id] = pRoles[r.individual_id] || []).push(p[1]); changed = true; } }); });
      if (changed) renderPeople();
    }).catch(function () {});
  }
  var PLABEL = { given_name: "Given name", middle_names: "Middle names", family_name: "Family name", name_to_use: "Name to use", pronouns: "Pronouns",
                 birth_date: "Birth date", birth_date_certainty: "Birth date certainty", preferred_language: "Preferred language", time_zone: "Time zone",
                 requires_interpreter: "Interpreter", email: "Email", phone: "Phone", backup_email: "Backup email", backup_phone: "Backup phone", prefers_email: "Preferred way to reach", status: "Status", notes: "Notes", survivor_id: "Person to keep", duplicate_id: "This person", reason: "Reason", id: "Person" };
  var PISSUE = { required: "Required.", invalid_format: "That value is not valid.", out_of_range: "Too long or too short.", invalid_value: "That value is not valid.",
                 invalid_type: "That value is not valid.", not_found: "That person was not found.", same_as_survivor: "Pick a different person.",
                 conflict_restricted_detail: "Both people hold protected details. That needs a person to sort out first.",
                 too_many_links: "Too many records point at this person to merge in one go.", snapshots_erased: "One of the people has been erased, so this cannot be undone.",
                 not_merged: "This merge was already undone.", already_erased: "Already erased.", in_use: "Protected details exist for this person.", immutable: "That cannot be changed.",
                 inconsistent: "That does not fit with the other answers." };
  var PADD_ERR = { given_name: "epaGiven", family_name: "epaFamily", name_to_use: "epaUse", birth_date: "epaBirth", email: "epaEmail", phone: "epaPhone" };
  var P_FIELDS = [
    { k: "given_name", label: "Given name", t: "text" }, { k: "middle_names", label: "Middle names", t: "text" },
    { k: "family_name", label: "Family name", t: "text" }, { k: "name_to_use", label: "Name to use", t: "text", hint: "What the person asks to be called. It shows instead of the given name." },
    { k: "pronouns", label: "Pronouns", t: "text", hint: "As the person says them, for example she/her." },
    { k: "birth_date", label: "Birth date", t: "text", hint: "Month first: 04-17-1961, 04-1961 or just 1961. A year alone is fine." },
    { k: "birth_date_certainty", label: "How sure is the birth date?", t: "select", opts: [["", "Not stated (treated as exact)"], ["exact", "Exact"], ["approximate", "Approximate"], ["estimated", "Estimated"]] },
    { k: "preferred_language", label: "Preferred language", t: "text", hint: "A language tag such as en or es-MX." },
    { k: "time_zone", label: "Time zone", t: "text", hint: "For example America/Denver." },
    { k: "requires_interpreter", label: "Needs an interpreter?", t: "bool" },
    { k: "email", label: "Email", t: "text", hint: "The email address they asked us to use. Couples may share one." },
    { k: "phone", label: "Phone (text messages)", t: "text", hint: "We send text messages only and never call." },
    { k: "backup_email", label: "Backup email", t: "text", hint: "Used when the first one is missing or fails." },
    { k: "backup_phone", label: "Backup phone", t: "text", hint: "Used when the first one is missing or fails." },
    { k: "prefers_email", label: "How do they want to hear from us?", t: "prefer", opts: [["", "Not said (the one they gave, or email if both)"], ["email", "Email"], ["text", "Text message"]] },
    { k: "status", label: "Status", t: "select", opts: [["active", "Active"], ["inactive", "Inactive (kept, not offered in pickers)"]] },
    { k: "notes", label: "Notes", t: "area", hint: "Visible to operators only." }
  ];
  // Dates: people type and read them the American way, month first (04-17-1961, 04-1961 or just 1961). The record stores YYYY, YYYY-MM or YYYY-MM-DD.
  var MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var DATE_HELP = "Use 1961, 04-1961 or 04-17-1961 (month first).";
  function pDateIn(s) {   // text typed by a person -> {iso} or {bad:true}; blank -> {iso:""}
    var t = String(s || "").trim().replace(/[\/.\s]+/g, "-"), m;
    if (t === "") return { iso: "" };
    if (/^\d{4}$/.test(t)) return { iso: t };
    if ((m = /^(\d{4})-(\d{2})(?:-(\d{2}))?$/.exec(t))) return pDateParts(m[1], m[2], m[3]);   // already stored style
    if ((m = /^(\d{1,2})-(\d{4})$/.exec(t))) return pDateParts(m[2], m[1]);
    if ((m = /^(\d{1,2})-(\d{1,2})-(\d{4})$/.exec(t))) return pDateParts(m[3], m[1], m[2]);
    return { bad: true };
  }
  function pDateParts(y, mo, d) {
    var M = parseInt(mo, 10), D = d === undefined ? 0 : parseInt(d, 10), Y = parseInt(y, 10);
    if (M < 1 || M > 12 || Y < 1) return { bad: true };
    if (D) { var dt = new Date(Date.UTC(Y, M - 1, D)); if (dt.getUTCFullYear() !== Y || dt.getUTCMonth() !== M - 1 || dt.getUTCDate() !== D) return { bad: true }; }
    var z = function (n) { return (n < 10 ? "0" : "") + n; };
    return { iso: y + "-" + z(M) + (D ? "-" + z(D) : "") };
  }
  function pDateOut(iso) {   // stored value -> "Apr 17, 1961", "Apr 1961" or "1961"
    var m = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$/.exec(String(iso || ""));
    if (!m) return String(iso || "");
    return (m[2] ? MON[parseInt(m[2], 10) - 1] + " " : "") + (m[3] ? parseInt(m[3], 10) + ", " : "") + m[1];
  }
  function pDateField(iso) {   // stored value -> what the box shows: 04-17-1961, 04-1961 or 1961
    var m = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$/.exec(String(iso || ""));
    if (!m) return String(iso || "");
    return m[3] ? m[2] + "-" + m[3] + "-" + m[1] : m[2] ? m[2] + "-" + m[1] : m[1];
  }
  function pName(rec) { return rec.display_name || rec.given_name || "(no name)"; }
  // The whole name for pickers: the display name, plus the family name when the display name leaves it out.
  function pFull(rec) {
    var d = pName(rec), fam = rec.family_name;
    if (fam && d.toLowerCase().indexOf(fam.toLowerCase()) < 0) return (rec.name_to_use || rec.given_name || d) + " " + fam;
    return d;
  }
  function pById(id) { for (var i = 0; i < pAll.length; i++) if (pAll[i].id === id) return pAll[i]; return null; }
  function pProblems(res, map) {
    var ps = (res.body && res.body.error && res.body.error.problems) || [], out = [], mine = {};
    ps.forEach(function (p) {
      var text = (p.field === "birth_date" && p.issue === "invalid_format") ? DATE_HELP + " It has to be a real date."
               : (/email$/.test(p.field) && p.issue === "invalid_format") ? "That email address does not look right."
               : (/phone$/.test(p.field) && p.issue === "invalid_format") ? "That phone number does not look right. Use digits, for example 303-555-0142."
               : (PISSUE[p.issue] || "That value is not valid.");
      if (map && map[p.field]) mine[p.field] = text; else out.push((PLABEL[p.field] || p.field) + ": " + text);
    });
    if (!ps.length) out.push(adminProblem(res.status));
    return { fields: mine, other: out };
  }

  function loadPeople() {
    var my = ++pSeq;
    $("pMsg").textContent = ""; $("pRetry").hidden = true;
    if (!pLoaded) skelOn($("pList"));
    return admin("list", { filters: {}, limit: 200 }, COLL_P).then(function (res) {
      if (my !== pSeq) return;
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body.ok) { skelOff($("pList")); $("pMsg").textContent = "Could not load the people. " + adminProblem(res.status); $("pRetry").hidden = false; return; }
      pAll = res.body.data.records || []; pLoaded = true;
      UI.limitNote($("pList"), pAll.length, 200);
      fillPChips();
      renderPeople(); joinPeople();
      $("pChecked").textContent = "Last checked " + fmtClock.format(new Date());
      if ($("pHist").open) loadMerges();
    });
  }
  // ---- Filters (shared chip bar): Status (Active by default). Everything is filtered in the page, 50 rows at a time.
  var pCf = null, pShow = 50, PSTEP = 50;
  function pChips() {
    if (pCf) return pCf;
    pCf = UI.chipFilters({
      mount: $("pChips"), label: "People filters",
      filters: [{ id: "status", label: "Status", kind: "multi", options: [{ value: "active", label: "Active" }, { value: "inactive", label: "Inactive" }] }],
      onChange: function () { pShow = PSTEP; $("pNotice").textContent = ""; renderPeople(); }
    });
    pCf.setSelection({ status: ["active"] });
    return pCf;
  }
  function fillPChips() {
    var cs = { active: 0, inactive: 0 };
    pAll.forEach(function (r) { if (cs[r.status] !== undefined) cs[r.status]++; });
    pChips().setCounts({ status: cs });
  }
  function renderPeople() {
    var q = $("pSearch").value.trim().toLowerCase(), list = $("pList"), st = pChips().getSelection().status || [];
    var shown = pAll.filter(function (r) { return st.indexOf(r.status) >= 0 && (!q || [r.display_name, r.given_name, r.family_name, r.name_to_use].join(" ").toLowerCase().indexOf(q) >= 0); })
      .sort(function (a, b) { var x = pFull(a).toLowerCase(), y = pFull(b).toLowerCase(); return x < y ? -1 : x > y ? 1 : 0; });
    var vis = shown.slice(0, pShow), had = list.children.length;
    list.textContent = "";
    vis.forEach(function (r) { list.appendChild(personRow(r, r.id === pNewId)); });
    pNewId = "";
    UI.moreBar($("pMore"), vis.length, shown.length, PSTEP, function () {
      pShow += PSTEP; renderPeople();
      var f = $("pList").children[had]; if (f && f.querySelector("button.head")) f.querySelector("button.head").focus();
    }, "people");
    $("pCount").textContent = shown.length + (shown.length === 1 ? " person" : " people");
    pChips().setCount(shown.length !== pAll.length && pAll.length ? shown.length + " of " + pAll.length + " people" : "");
    $("pEmpty").hidden = pAll.length > 0;
    $("pNoMatch").hidden = !(pAll.length > 0 && shown.length === 0);
  }

  function personRow(rec, isNew) {
    var li = mk("li", isNew ? "isnew" : "");
    var head = mk("button", "head"); head.type = "button"; head.setAttribute("aria-expanded", "false");
    var top = mk("div", "top");
    top.appendChild(mk("span", "vname", pName(rec)));
    var tgl = (rec.status === "active" || rec.status === "inactive") ? statusToggle(rec, li, { coll: COLL_P, on: "active", off: "inactive", label: "Person", problem: function (res) { return pProblems(res).other.join(" "); } }) : null;
    if (!tgl) top.appendChild(mk("span", "type", rec.status || ""));
    head.appendChild(top);
    var bits = [];
    if (rec.birth_date) bits.push("Born " + pDateOut(rec.birth_date));
    if (rec.is_minor) bits.push("Under 18");
    if (pTown[rec.id]) bits.push(pTown[rec.id]);
    if (rec.life_status && rec.life_status !== "alive") bits.push(LIFE_WORDS[rec.life_status] || rec.life_status.replace(/_/g, " "));
    if (rec.record_privacy && rec.record_privacy !== "normal") bits.push(PRIV_WORDS[rec.record_privacy] || rec.record_privacy);
    (pRoles[rec.id] || []).forEach(function (r) { bits.push(r); });
    if (bits.length) head.appendChild(mk("div", "sub", bits.join(" · ")));
    var detail = mk("div", "detail");
    detail.appendChild(personActions(rec));
    function group(title) { var g = mk("div", "dgroup"); g.appendChild(mk("h3", "dgh", title)); detail.appendChild(g); return g; }
    function add(g, label, v) { if (v !== undefined && v !== null && v !== "") g.appendChild(line(label, String(v))); }
    var CERT = { exact: "exact", approximate: "approximate", estimated: "estimated" };
    var gn = group("About them");
    add(gn, "Full name", pFull(rec)); if (rec.name_to_use) add(gn, "Called", rec.name_to_use);
    add(gn, "Pronouns", rec.pronouns);
    if (rec.birth_date) add(gn, "Born", pDateOut(rec.birth_date) + (rec.birth_date_certainty && rec.birth_date_certainty !== "exact" ? " (" + (CERT[rec.birth_date_certainty] || rec.birth_date_certainty) + ")" : ""));
    if (rec.is_minor) add(gn, "Age", "Under 18");
    if (rec.life_status && rec.life_status !== "alive") add(gn, "Living", LIFE_WORDS[rec.life_status] || rec.life_status.replace(/_/g, " "));
    if (rec.record_privacy && rec.record_privacy !== "normal") add(gn, "Record", PRIV_WORDS[rec.record_privacy] || rec.record_privacy);
    var gc = group("How to reach them");
    add(gc, "Email", rec.email); add(gc, "Phone (text only)", rec.phone); add(gc, "Backup email", rec.backup_email); add(gc, "Backup phone", rec.backup_phone);
    if (rec.prefers_email === true || rec.prefers_email === "email") add(gc, "Prefers", "Email"); else if (rec.prefers_email === false || rec.prefers_email === "text") add(gc, "Prefers", "Text message");
    if (gc.children.length === 1) gc.appendChild(mk("div", "hint", "No way to reach them on file yet."));
    var gd = group("Details");
    add(gd, "Language", rec.preferred_language); add(gd, "Time zone", rec.time_zone ? (UI.zoneName(rec.time_zone) || rec.time_zone) : "");
    if (rec.requires_interpreter) add(gd, "Interpreter", "Needed");
    add(gd, "Town", pTown[rec.id]); add(gd, "Roles", (pRoles[rec.id] || []).join(", "));
    add(gd, "Status", rec.status === "active" ? "Active" : rec.status === "inactive" ? "Inactive" : rec.status);
    add(gd, "Notes", rec.notes);
    head.addEventListener("click", function () { var open = li.classList.toggle("open"); head.setAttribute("aria-expanded", open ? "true" : "false"); });
    li.appendChild(head); if (tgl) { li.appendChild(tgl.btn); li.appendChild(tgl.msg); } li.appendChild(detail);
    if (isNew) setTimeout(function () { li.classList.remove("isnew"); }, 6000);
    return li;
  }

  function personActions(rec) {
    var wrap = mk("div"), row = mk("div", "actions-row");
    var ed = mk("button", "btn-primary", "Edit"); ed.type = "button";
    var ad = mk("button", "btn-secondary", "Addresses"); ad.type = "button";
    var mg = mk("button", "btn-secondary", "Merge into another person"); mg.type = "button";
    var del = mk("button", "btn-danger pdel", "Delete"); del.type = "button";
    // Cues: Edit orange, two outlined, one History link, Delete red last.
    row.appendChild(ed); row.appendChild(ad); row.appendChild(mg); var hp = historyBtn(rec.id, pName(rec)); if (hp) { hp.className = "btn-link"; row.appendChild(hp); }
    var hi = mk("button", "btn-link", "Class history"); hi.type = "button"; row.appendChild(hi);
    var histHost = mk("div");
    hi.addEventListener("click", function () { if (histHost.firstChild) histHost.textContent = ""; else personHistory(rec, histHost); });
    row.appendChild(del);
    var editHost = mk("div"), mergeHost = mk("div"), addrHost = mk("div");
    var box = mk("div", "confirm"); box.hidden = true;
    box.appendChild(mk("div", "", "Delete " + pName(rec) + "? They are hidden from the lists but the record is kept."));
    var btns = mk("div", "btns"), yes = mk("button", "btn-danger", "Delete person"), no = mk("button", "btn-secondary", "Cancel");
    yes.type = "button"; no.type = "button";
    var err = mk("div", "msg"); err.setAttribute("role", "alert");
    btns.appendChild(yes); btns.appendChild(no); box.appendChild(btns); box.appendChild(err);
    ed.addEventListener("click", function () { mergeHost.textContent = ""; addrHost.textContent = ""; box.hidden = true; if (editHost.firstChild) editHost.textContent = ""; else editHost.appendChild(personEditForm(rec, editHost)); });
    mg.addEventListener("click", function () { editHost.textContent = ""; addrHost.textContent = ""; box.hidden = true; if (mergeHost.firstChild) mergeHost.textContent = ""; else mergeHost.appendChild(mergeForm(rec, mergeHost)); });
    del.addEventListener("click", function () { editHost.textContent = ""; mergeHost.textContent = ""; addrHost.textContent = ""; box.hidden = !box.hidden; err.textContent = ""; });
    ad.addEventListener("click", function () { editHost.textContent = ""; mergeHost.textContent = ""; box.hidden = true; if (addrHost.firstChild) addrHost.textContent = ""; else addrHost.appendChild(personAddresses(rec, addrHost)); });
    no.addEventListener("click", function () { box.hidden = true; });
    yes.addEventListener("click", function () {
      yes.disabled = true; err.textContent = "";
      admin("soft_delete", { id: rec.id }, COLL_P).then(function (res) {
        yes.disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) { $("pNotice").textContent = "Deleted " + pName(rec) + "."; loadPeople(); }
        else if (res.status === 404) { $("pNotice").textContent = "That person was already gone."; loadPeople(); }
        else if (res.status === 409) err.textContent = "This person has protected details on file. Those have to be dealt with first.";
        else err.textContent = pProblems(res).other.join(" ");
      });
    });
    wrap.appendChild(row); wrap.appendChild(histHost); wrap.appendChild(editHost); wrap.appendChild(mergeHost); wrap.appendChild(addrHost); wrap.appendChild(box);
    return wrap;
  }

  function personEditForm(rec, host) {
    var form = mk("form", "eform"); form.noValidate = true; form.autocomplete = "off";
    var els = {};
    P_FIELDS.forEach(function (f) {
      var id = "pe_" + rec.id + "_" + f.k, cur = rec[f.k];
      var SEC = { given_name: "Name", birth_date: "Birth date", preferred_language: "Language and needs", email: "How to reach them", status: "Record" };
      if (SEC[f.k]) form.appendChild(mk("div", "fsec", SEC[f.k]));
      var l = f.k === "given_name" ? UI.requiredLabel(f.label, id) : mk("label", "f", f.label); l.htmlFor = id; form.appendChild(l);
      var el;
      if (f.t === "select" || f.t === "bool" || f.t === "prefer") {
        el = mk("select");
        var opts = f.t === "bool" ? [["", "Not stated"], ["yes", "Yes"], ["no", "No"]] : f.opts;
        opts.forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; el.appendChild(op); });
        el.value = f.t === "prefer" ? (cur === true ? "email" : cur === false ? "text" : "") : f.t === "bool" ? (cur === true ? "yes" : cur === false ? "no" : "") : (cur === undefined ? (f.k === "status" ? "active" : "") : cur);
      } else if (f.t === "area") { el = mk("textarea"); el.maxLength = 2000; el.value = cur === undefined ? "" : cur; }
      else { el = mk("input"); el.type = "text"; el.maxLength = 200; el.value = cur === undefined ? "" : (f.k === "birth_date" ? pDateField(cur) : cur); }
      el.id = id; form.appendChild(el);
      if (f.hint) form.appendChild(mk("div", "hint", f.hint));
      var er = mk("div", "ferr"); form.appendChild(er);
      els[f.k] = { el: el, err: er, t: f.t };
    });
    var btns = mk("div", "btns"), save = mk("button", "btn-primary", "Save changes"), cancel = mk("button", "btn-secondary", "Cancel");
    save.type = "submit"; cancel.type = "button"; btns.appendChild(save); btns.appendChild(cancel); form.appendChild(btns);
    var msg = mk("div", "msg"); msg.setAttribute("role", "alert"); form.appendChild(msg);
    cancel.addEventListener("click", function () { host.textContent = ""; });
    form.addEventListener("submit", function (e) {
      e.preventDefault(); msg.textContent = "";
      Object.keys(els).forEach(function (k) { els[k].err.textContent = ""; });
      var changes = {}, badDate = false;
      P_FIELDS.forEach(function (f) {
        var x = els[f.k], v = x.el.value.trim(), cur = rec[f.k];
        if (f.k === "birth_date" && v !== "") { var pd = pDateIn(v); if (pd.bad) { x.err.textContent = DATE_HELP + " It has to be a real date."; badDate = true; return; } v = pd.iso; }
        var val = f.t === "prefer" ? (v === "email" ? true : v === "text" ? false : null) : f.t === "bool" ? (v === "yes" ? true : v === "no" ? false : null) : (v === "" ? null : v);
        if (f.k === "status" && val === null) val = "active";
        if (val === null) { if (cur !== undefined) changes[f.k] = null; }
        else if (val !== cur) changes[f.k] = val;
      });
      if (badDate) return;
      if (!Object.keys(changes).length) { host.textContent = ""; $("pNotice").textContent = "Nothing changed."; return; }
      save.disabled = true;
      admin("update", { id: rec.id, changes: changes, expected_updated_at: rec.updated_at }, COLL_P).then(function (res) {
        save.disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) { pNewId = rec.id; $("pNotice").textContent = "Saved changes to " + pName(rec) + "."; loadPeople(); return; }
        if (res.status === 409) { msg.textContent = "Someone changed this person while you were editing. Close this, tap Refresh, and try again. Nothing was overwritten."; return; }
        if (res.status === 404) { msg.textContent = "That person is gone or merged. Tap Refresh."; return; }
        var pr = pProblems(res, els);
        Object.keys(pr.fields).forEach(function (k) { els[k].err.textContent = pr.fields[k]; });
        if (pr.other.length) msg.textContent = "Could not save: " + pr.other.join(" ");
      });
    });
    return form;
  }

  function mergeForm(rec, host) {
    var box = mk("div", "mergebox");
    box.appendChild(mk("div", "", pName(rec) + " is the same person as someone already listed. Pick who to keep. Anything missing on that person is filled in from this record, links to this person move over, and this record is marked merged. It can be undone in Merge history."));
    var l1 = mk("label", "f", "Person to keep"); var sel = mk("select"); sel.id = "pm_" + rec.id; l1.htmlFor = sel.id;
    var o0 = mk("option", "", "Choose one"); o0.value = ""; sel.appendChild(o0);
    pAll.filter(function (p) { return p.id !== rec.id && p.status === "active"; }).forEach(function (p) {
      var o = mk("option", "", pName(p) + (p.birth_date || pTown[p.id] ? " (" + [p.birth_date ? "born " + pDateOut(p.birth_date) : "", pTown[p.id] || ""].filter(Boolean).join(", ") + ")" : "")); o.value = p.id; sel.appendChild(o);
    });
    var e1 = mk("div", "ferr");
    var l2 = mk("label", "f", "Reason"); var why = mk("input"); why.type = "text"; why.maxLength = 500; why.id = "pr_" + rec.id; l2.htmlFor = why.id; why.placeholder = "For example: same phone and birth date, confirmed by phone";
    var e2 = mk("div", "ferr");
    var btns = mk("div", "btns"), go = mk("button", "btn-primary", "Merge"), no = mk("button", "btn-secondary", "Cancel"); go.type = "button"; no.type = "button";
    btns.appendChild(go); btns.appendChild(no);
    var msg = mk("div", "msg"); msg.setAttribute("role", "alert");
    [l1, sel, e1, l2, why, e2, btns, msg].forEach(function (n) { box.appendChild(n); });
    no.addEventListener("click", function () { host.textContent = ""; });
    go.addEventListener("click", function () {
      e1.textContent = ""; e2.textContent = ""; msg.textContent = "";
      var bad = false;
      if (!sel.value) { e1.textContent = "Choose one."; bad = true; }
      if (!why.value.trim()) { e2.textContent = "Say why they are the same person."; bad = true; }
      if (bad) return;
      go.disabled = true;
      admin("merge", { survivor_id: sel.value, duplicate_id: rec.id, reason: why.value.trim() }, COLL_P).then(function (res) {
        go.disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          var d = res.body.data, keep = pById(sel.value);
          $("pNotice").textContent = "Merged " + pName(rec) + " into " + (keep ? pName(keep) : "the other person") + ": " + d.changed_fields.length + " values filled in, " + d.moved_links + " records moved. Undo it in Merge history.";
          if ($("pHist").open) loadMerges();
          loadPeople(); return;
        }
        if (res.status === 409) { msg.textContent = "Someone changed one of them while you were working. Tap Refresh and try again."; return; }
        msg.textContent = "Could not merge: " + pProblems(res).other.join(" ");
      });
    });
    return box;
  }

  function loadMerges() {
    $("pHMsg").textContent = "";
    return admin("list", { limit: 50 }, COLL_MERGE).then(function (res) {
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body.ok) { $("pHMsg").textContent = "Could not load the merge history. " + adminProblem(res.status); return; }
      var evs = res.body.data.records || [], ul = $("pHList");
      ul.textContent = "";
      evs.forEach(function (ev) {
        var li = mk("li"), body = mk("div", "detail"); body.style.display = "block";
        var a = pById(ev.duplicate_id) || ev.duplicate_before, b = pById(ev.survivor_id) || ev.survivor_before;
        body.appendChild(mk("div", "", when(ev.created_at) + ": " + (a && (a.display_name || a.given_name) ? pName(a) : "a person") + " merged into " + (b && (b.display_name || b.given_name) ? pName(b) : "another person") + " (" + ev.status + ")"));
        body.appendChild(line("reason", ev.reason || ""));
        if (ev.status === "unmerged" && ev.unmerge_skipped && ev.unmerge_skipped.length) body.appendChild(line("left as they were after the undo", String(ev.unmerge_skipped.length) + " values changed since the merge"));
        if (ev.status === "merged") {
          var row = mk("div", "actions-row"), undo = mk("button", "quiet", "Undo this merge"); undo.type = "button"; row.appendChild(undo);
          var err = mk("div", "msg"); err.setAttribute("role", "alert");
          undo.addEventListener("click", function () {
            undo.disabled = true; err.textContent = "";
            admin("unmerge", { id: ev.id }, COLL_P).then(function (r2) {
              undo.disabled = false;
              if (r2.status === 401) { lock("That key did not work."); return; }
              if (r2.status === 200 && r2.body && r2.body.ok) {
                var sk = (r2.body.data.skipped || []).length;
                $("pNotice").textContent = "Undone: " + r2.body.data.restored_links + " records pointed back." + (sk ? " " + sk + " values were left alone because they changed after the merge." : "");
                loadPeople(); return;
              }
              err.textContent = "Could not undo: " + pProblems(r2).other.join(" ");
            });
          });
          body.appendChild(row); body.appendChild(err);
        }
        li.appendChild(body); ul.appendChild(li);
      });
      $("pHEmpty").hidden = evs.length > 0;
    });
  }

  function resetPeople() {
    pLoaded = false; pAll = []; pNewId = ""; pTown = {}; pRoles = {};
    $("pList").textContent = ""; $("pCount").textContent = ""; $("pChecked").textContent = ""; $("pMsg").textContent = ""; $("pNotice").textContent = "";
    $("pEmpty").hidden = true; $("pNoMatch").hidden = true; $("pSearch").value = ""; pShow = PSTEP; $("pMore").textContent = ""; if (pCf) pCf.setSelection({ status: ["active"] });
    $("pAddForm").hidden = true; $("pAddBtn").hidden = false; $("pHist").open = false; $("pHList").textContent = "";
  }
  function pClearErrs() { Object.keys(PADD_ERR).forEach(function (k) { $(PADD_ERR[k]).textContent = ""; }); $("pFMsg").textContent = ""; }
  $("pAddBtn").addEventListener("click", function () { $("pAddForm").reset(); pClearErrs(); $("pNotice").textContent = ""; $("pAddForm").hidden = false; $("pAddBtn").hidden = true; $("paGiven").focus(); });
  $("pCancelBtn").addEventListener("click", function () { $("pAddForm").hidden = true; $("pAddBtn").hidden = false; });
  $("pAddForm").addEventListener("submit", function (e) {
    e.preventDefault(); pClearErrs();
    var data = {}, map = { given_name: "paGiven", family_name: "paFamily", name_to_use: "paUse", birth_date: "paBirth", email: "paEmail", phone: "paPhone" };
    Object.keys(map).forEach(function (k) { var v = $(map[k]).value.trim(); if (v) data[k] = v; });
    if (!data.given_name) { $("epaGiven").textContent = "Required."; return; }
    if (data.birth_date) { var pd = pDateIn(data.birth_date); if (pd.bad) { $("epaBirth").textContent = DATE_HELP + " It has to be a real date."; return; } data.birth_date = pd.iso; }
    $("pSaveBtn").disabled = true;
    admin("create", { data: data }, COLL_P).then(function (res) {
      $("pSaveBtn").disabled = false;
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status === 200 && res.body && res.body.ok) {
        pNewId = res.body.data.id; $("pNotice").textContent = "Added " + pName(res.body.data) + ".";
        $("pAddForm").hidden = true; $("pAddBtn").hidden = false;
        pChips().setSelection({ status: ["active"] });
        loadPeople(); return;
      }
      var pr = pProblems(res, PADD_ERR);
      Object.keys(pr.fields).forEach(function (k) { $(PADD_ERR[k]).textContent = pr.fields[k]; });
      if (pr.other.length) $("pFMsg").textContent = "Could not save: " + pr.other.join(" ");
    });
  });
  $("pRefresh").addEventListener("click", function () { $("pNotice").textContent = ""; loadPeople(); });
  $("pRetry").addEventListener("click", loadPeople);
  $("pClear").addEventListener("click", function () { $("pSearch").value = ""; pShow = PSTEP; pChips().setSelection({ status: ["active"] }); renderPeople(); $("pSearch").focus(); });
  $("pSearch").addEventListener("input", function () { pShow = PSTEP; renderPeople(); });
  $("pHist").addEventListener("toggle", function () { if ($("pHist").open) loadMerges(); });
  $("pHistLink").addEventListener("click", function () {   // the link in the page head opens the Merge history box at the bottom and brings it into view
    $("pHist").open = true; $("pHist").scrollIntoView({ block: "start" }); $("pHist").querySelector("summary").focus();
  });

  // A person pointer on the venue form. The venue stores only the person's id; the name is read from their record.
  var peopleForPick = null;
  function peopleList() {
    if (peopleForPick) return Promise.resolve(peopleForPick);
    return admin("list", { order: "display_name", limit: 200 }, "individuals").then(function (r) {
      if (r.status === 401) { lock("That key did not work."); return []; }
      peopleForPick = (r.status === 200 && r.body.ok) ? (r.body.data.records || []) : [];
      return peopleForPick;
    });
  }

  // ---- Addresses on a person's card
  function personAddresses(rec, host) {
    var wrap = mk("div", "eform"), listHost = mk("div"), formHost = mk("div"), btnRow = mk("div", "actions-row");
    var msg = mk("div", "msg"); msg.setAttribute("role", "alert");
    wrap.appendChild(mk("div", "", "Addresses for " + pName(rec) + ". A place is saved once; the person is linked to it with dates. When someone moves, end the old address and add the new one."));
    var addBtn = mk("button", "", "Add an address"); addBtn.type = "button"; btnRow.appendChild(addBtn);
    var closeBtn = mk("button", "quiet", "Close"); closeBtn.type = "button"; btnRow.appendChild(closeBtn);
    wrap.appendChild(listHost); wrap.appendChild(btnRow); wrap.appendChild(formHost); wrap.appendChild(msg);
    closeBtn.addEventListener("click", function () { host.textContent = ""; });
    addBtn.addEventListener("click", function () { msg.textContent = ""; if (formHost.firstChild) formHost.textContent = ""; else formHost.appendChild(addressForm()); });

    function refresh() {
      listHost.textContent = ""; listHost.appendChild(mk("div", "hint", "Loading addresses..."));
      admin("list", { filters: { subject_id: rec.id }, limit: 50 }, COLL_LK).then(function (res) {
        if (res.status === 401) { lock("That key did not work."); return; }
        listHost.textContent = "";
        if (res.status !== 200 || !res.body.ok) { listHost.appendChild(mk("div", "msg", "Could not load addresses. " + adminProblem(res.status))); return; }
        var links = res.body.data.records || [];
        if (!links.length) { listHost.appendChild(mk("div", "hint", "No addresses yet.")); return; }
        Promise.all(links.map(function (l) { return admin("get", { id: l.location_id }, COLL_L); })).then(function (locs) {
          links.forEach(function (l, i) { listHost.appendChild(linkRow(l, locs[i].status === 200 && locs[i].body.ok ? locs[i].body.data : null)); });
        });
      });
    }
    function linkRow(l, loc) {
      var row = mk("div", "mergebox"), ended = l.status === "ended";
      var h = mk("div", "", (REL[l.relationship] || l.relationship) + (l.is_primary ? " (main)" : "") + (ended ? " (ended)" : "")); h.style.fontWeight = "700"; row.appendChild(h);
      row.appendChild(mk("div", "", loc ? locSummary(loc) : "(place not available)"));
      var span = (l.valid_from ? "From " + pDateOut(l.valid_from) : "") + (l.valid_to ? (l.valid_from ? " " : "") + "until " + pDateOut(l.valid_to) : "");
      if (span) row.appendChild(mk("div", "hint", span));
      var acts = mk("div", "actions-row"), box = mk("div"), err = mk("div", "msg"); err.setAttribute("role", "alert");
      if (!ended) {
        var en = mk("button", "quiet", "End"); en.type = "button"; acts.appendChild(en);
        en.addEventListener("click", function () { box.textContent = ""; err.textContent = ""; box.appendChild(endBox(l, err)); });
        if (!l.is_primary) {
          var mm = mk("button", "quiet", "Make main"); mm.type = "button"; acts.appendChild(mm);
          mm.addEventListener("click", function () {
            mm.disabled = true; err.textContent = "";
            admin("update", { id: l.id, changes: { is_primary: true }, expected_updated_at: l.updated_at }, COLL_LK).then(function (r) {
              mm.disabled = false; if (r.status === 401) { lock("That key did not work."); return; }
              if (r.status === 200 && r.body.ok) { refresh(); return; }
              err.textContent = r.status === 409 ? "This changed while you were looking. Close and reopen." : lProblems(r);
            });
          });
        }
      }
      var rm = mk("button", "danger", "Remove"); rm.type = "button"; acts.appendChild(rm);
      rm.addEventListener("click", function () {
        box.textContent = ""; err.textContent = "";
        var c = mk("div", "confirm"); c.appendChild(mk("div", "", "Remove this address? Use this for a mistake. To record a move, use End instead."));
        var b = mk("div", "btns"), y = mk("button", "danger", "Remove"), n = mk("button", "quiet", "Cancel"); y.type = "button"; n.type = "button";
        b.appendChild(y); b.appendChild(n); c.appendChild(b); box.appendChild(c);
        n.addEventListener("click", function () { box.textContent = ""; });
        y.addEventListener("click", function () {
          y.disabled = true;
          admin("soft_delete", { id: l.id }, COLL_LK).then(function (r) {
            y.disabled = false; if (r.status === 401) { lock("That key did not work."); return; }
            if (r.status === 200 || r.status === 404) { refreshPlaces(); refresh(); return; }
            err.textContent = lProblems(r);
          });
        });
      });
      row.appendChild(acts); row.appendChild(box); row.appendChild(err);
      return row;
    }
    function endBox(l, err) {
      var b = mk("div", "confirm"), lab = mk("label", "f", "Last day at this address (blank means today)"), inp = mk("input");
      inp.type = "text"; inp.maxLength = 10; inp.id = "ed_" + l.id; lab.htmlFor = inp.id; inp.placeholder = "MM-DD-YYYY";
      var btns = mk("div", "btns"), go = mk("button", "", "End this address"), no = mk("button", "quiet", "Cancel"); go.type = "button"; no.type = "button";
      btns.appendChild(go); btns.appendChild(no);
      [lab, inp, mk("div", "hint", DATE_HELP), btns].forEach(function (n) { b.appendChild(n); });
      no.addEventListener("click", function () { b.remove(); });
      go.addEventListener("click", function () {
        err.textContent = ""; var args = { id: l.id, expected_updated_at: l.updated_at };
        if (inp.value.trim()) { var pd = pDateIn(inp.value); if (pd.bad) { err.textContent = DATE_HELP + " It has to be a real date."; return; } args.valid_to = pd.iso; }
        go.disabled = true;
        admin("end", args, COLL_LK).then(function (r) {
          go.disabled = false; if (r.status === 401) { lock("That key did not work."); return; }
          if (r.status === 200 && r.body.ok) { refreshPlaces(); refresh(); return; }
          err.textContent = r.status === 409 ? "That address already ended, or it changed while you were looking. Close and reopen." : lProblems(r);
        });
      });
      return b;
    }
    function addressForm() {
      var form = mk("form", "eform"); form.noValidate = true; form.autocomplete = "off";
      var rl = mk("label", "f", "What is this address?"), rs = mk("select"); rs.id = "ar_" + rec.id; rl.htmlFor = rs.id;
      PERSON_RELS.forEach(function (k) { var o = mk("option", "", REL[k]); o.value = k; rs.appendChild(o); });
      form.appendChild(rl); form.appendChild(rs);
      var block = addrForm({ name: true }); form.appendChild(block);
      var sl = mk("label", "f", "Since (optional)"), si = mk("input"); si.type = "text"; si.maxLength = 10; si.id = "as_" + rec.id; sl.htmlFor = si.id; si.placeholder = "MM-DD-YYYY, MM-YYYY or YYYY";
      var se = mk("div", "ferr"); form.appendChild(sl); form.appendChild(si); form.appendChild(mk("div", "hint", DATE_HELP)); form.appendChild(se);
      var pl = mk("label", "f"), pc = mk("input"); pc.type = "checkbox"; pc.id = "ap_" + rec.id; pl.htmlFor = pc.id; pl.appendChild(pc); pl.appendChild(document.createTextNode(" This is the main one"));
      pl.style.display = "flex"; pl.style.gap = "8px"; pl.style.alignItems = "center"; form.appendChild(pl);
      var chooser = mk("div", "confirm"); chooser.hidden = true; form.appendChild(chooser);
      var btns = mk("div", "btns"), save = mk("button", "", "Save address"), cancel = mk("button", "quiet", "Cancel"); save.type = "submit"; cancel.type = "button";
      btns.appendChild(save); btns.appendChild(cancel); form.appendChild(btns);
      var fm = mk("div", "msg"); fm.setAttribute("role", "alert"); form.appendChild(fm);
      var step = "start", locData = null, linkBase = null;
      cancel.addEventListener("click", function () { formHost.textContent = ""; });
      function link(locationId) {
        var data = {}; Object.keys(linkBase).forEach(function (k) { data[k] = linkBase[k]; }); data.location_id = locationId;
        return admin("create", { data: data }, COLL_LK).then(function (r) {
          save.disabled = false;
          if (r.status === 401) { lock("That key did not work."); return; }
          if (r.status === 200 && r.body.ok) { formHost.textContent = ""; msg.textContent = ""; refreshPlaces(); refresh(); return; }
          fm.textContent = "The place was saved but the link was not: " + lProblems(r);
        });
      }
      form.addEventListener("submit", function (e) {
        e.preventDefault(); fm.textContent = ""; se.textContent = "";
        if (step === "choose") {
          var pick = form.querySelector("input[name=usep]:checked"); save.disabled = true;
          if (pick && pick.value) return link(pick.value);
          return admin("create", { data: locData }, COLL_L).then(function (r) {
            if (r.status === 401) { lock("That key did not work."); return; }
            if (r.status === 200 && r.body.ok) return link(r.body.data.id);
            save.disabled = false; fm.textContent = "Could not save the place: " + lProblems(r);
          });
        }
        var rd = block.read(), ok = rd.ok, since = "";
        if (ok && !(rd.data.addresses)) { ok = false; fm.textContent = "A person's address needs a street or a PO box."; }
        if (si.value.trim()) { var pd = pDateIn(si.value); if (pd.bad) { se.textContent = DATE_HELP + " It has to be a real date."; ok = false; } else since = pd.iso; }
        if (!ok) return;
        locData = rd.data; linkBase = { subject_type: "individual", subject_id: rec.id, relationship: rs.value };
        if (since) linkBase.valid_from = since;
        if (pc.checked) linkBase.is_primary = true;
        save.disabled = true;
        admin("find_by_address", { address: locData.addresses[0] }, COLL_L).then(function (r) {
          if (r.status === 401) { lock("That key did not work."); return; }
          var found = (r.status === 200 && r.body.ok) ? (r.body.data.records || []) : [];
          if (!found.length) {
            admin("create", { data: locData }, COLL_L).then(function (c) {
              if (c.status === 401) { lock("That key did not work."); return; }
              if (c.status === 200 && c.body.ok) return link(c.body.data.id);
              save.disabled = false; fm.textContent = "Could not save the place: " + lProblems(c);
            });
            return;
          }
          step = "choose"; save.disabled = false; save.textContent = "Continue"; chooser.hidden = false; chooser.textContent = "";
          chooser.appendChild(mk("div", "", "This address is already saved. Use the saved place, so everyone at it shares one record?"));
          found.forEach(function (m, i) {
            var lb = mk("label", "f"), rd2 = mk("input"); rd2.type = "radio"; rd2.name = "usep"; rd2.value = m.id; if (i === 0) rd2.checked = true;
            lb.style.display = "flex"; lb.style.gap = "8px"; lb.style.alignItems = "center"; lb.appendChild(rd2); lb.appendChild(document.createTextNode(" Use: " + locSummary(m))); chooser.appendChild(lb);
          });
          var lb2 = mk("label", "f"), rd3 = mk("input"); rd3.type = "radio"; rd3.name = "usep"; rd3.value = "";
          lb2.style.display = "flex"; lb2.style.gap = "8px"; lb2.style.alignItems = "center"; lb2.appendChild(rd3); lb2.appendChild(document.createTextNode(" No, this is a different place")); chooser.appendChild(lb2);
        });
      });
      return form;
    }
    refresh();
    return wrap;
  }

  window.PeopleStation = {
    show: function () { if (!pLoaded) loadPeople(); }, reset: function () { resetPeople(); }, forget: function () { pLoaded = false; },
    // for the kit: what other pages borrow from People
    list: function () { return peopleList.apply(null, arguments); }, matches: function () { return peopleMatches.apply(null, arguments); },
    full: function () { return pFull.apply(null, arguments); }, problems: function () { return pProblems.apply(null, arguments); },
    dateOut: function () { return pDateOut.apply(null, arguments); }, forgetPick: function () { peopleForPick = null; },
    stale: function () { pLoaded = false; peopleForPick = null; }, words: function () { return { label: PLABEL, issue: PISSUE }; }
  };
})();
