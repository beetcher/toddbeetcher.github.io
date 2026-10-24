/* Curriculum station for the Console: what is taught. The list with an Active/Inactive/All filter, Add curriculum, Edit, the active/inactive toggle,
   Delete (the record is kept). Moved out of console.js (the Curriculum extraction, CU-2): the code is the same; the one change is that it no longer
   registers itself in the big file's roster table and hands its state back, so console.js reaches it through window.CurriculumStation
   (route show, sign-out reset, Try again forget). Everything it used to borrow from the big file now comes through ConsoleKit (K) or the form engine
   (ConsoleForms). The page markup (#curriculumsView) is still built here at load, and the manual text stays in the stations list in console.js.
   Loaded by index.html after classes.js.
   window.CurriculumStation = { show, reset, forget }. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var $ = function (id) { return document.getElementById(id); };
  var mk = K.mk, admin = K.admin, lock = K.lock, adminProblem = K.adminProblem, line = K.line, when = K.when, statusToggle = K.statusToggle;
  var slugify = window.ConsoleForms.slugify;
  var fmtClock = { format: function (d) { return K.clock(d); } };

  // ---- Curriculum station: what is taught. A class points at one curriculum; each session of a series is its own class.
  var RCISSUE = { required: "Required.", duplicate: "That identifier is already used.", invalid_format: "Use lowercase letters, digits and underscores.",
                 out_of_range: "That number is out of range.", invalid_type: "That value is not valid.", invalid_value: "That value is not valid.",
                 immutable: "That cannot be changed.", not_allowed: "Not allowed." };
  var CLABEL = { slug: "Identifier", title: "Title", tagline: "Tagline", description: "Description", session_count: "Sessions", minutes_per_session: "Minutes per session", status: "Status", notes: "Notes" };
  function currLine(rec) {
    var bits = [rec.slug];
    var n = rec.session_count || 1;
    bits.push(n + (n === 1 ? " session" : " sessions") + (rec.minutes_per_session ? " of " + rec.minutes_per_session + " min" : ""));
    return bits.join(" · ");
  }
  function buildCurriculum() {
    var P = "rc", S = { all: [], loaded: false, seq: 0, newId: "" }, g = function (s) { return $(P + s); };
    var root = $("curriculumsView");
    root.innerHTML =
      '<div class="bar"><div><div class="count" id="rcCount"></div><div class="meta" id="rcChecked"></div></div>' +
      '<div class="actions"><select id="rcFilter" aria-label="Filter by status"><option value="active">Active</option><option value="inactive">Inactive</option><option value="">All</option></select>' +
      '<button type="button" class="quiet manualBtn" data-m="curriculums">Manual</button><button id="rcRefresh" class="quiet" type="button">Refresh</button>' +
      '<button id="rcAddBtn" type="button">Add curriculum</button></div></div>' +
      '<form class="panel" id="rcAddForm" hidden autocomplete="off" novalidate><h2>Add a curriculum</h2>' +
      '<div class="hint">A title and a short identifier are needed. Sessions and length can be added now or later.</div>' +
      '<div id="rcAddFields"></div>' +
      '<div class="btns"><button type="submit" id="rcSaveBtn">Save curriculum</button><button type="button" class="quiet" id="rcCancelBtn">Cancel</button></div>' +
      '<div class="msg" id="rcFMsg" role="alert"></div></form>' +
      '<div class="notice" id="rcNotice" role="status"></div><div class="msg" id="rcMsg" role="alert"></div>' +
      '<button type="button" class="quiet" id="rcRetry" hidden>Retry</button><ul id="rcList"></ul><div class="empty" id="rcEmpty" hidden>No curricula yet.</div>';
    var FIELDS = [
      { k: "title", label: "Title", t: "text", add: true, hint: "What people see, for example Introduction to AI Use." },
      { k: "slug", label: "Short identifier", t: "text", add: true, addOnly: true, hint: "Lowercase letters, digits and underscores. It cannot be changed later." },
      { k: "tagline", label: "Tagline (optional)", t: "text", add: true, max: 120, hint: "One short marketing line shown with the title." },
      { k: "description", label: "Description (optional)", t: "area", add: true },
      { k: "session_count", label: "Number of sessions (optional)", t: "num", add: true, hint: "1 for a single session. Each session becomes its own class." },
      { k: "minutes_per_session", label: "Minutes per session (optional)", t: "num", add: true },
      { k: "notes", label: "Notes (optional)", t: "area", add: false, hint: "Visible to operators only." }
    ];
    function mkF(f, idp, cur) {
      var wrap = mk("div"), l = mk("label", "f", f.label), el;
      if (f.t === "area") { el = mk("textarea"); el.maxLength = 2000; el.value = cur == null ? "" : cur; }
      else { el = mk("input"); el.type = "text"; el.maxLength = f.t === "num" ? 4 : (f.max || 200); el.value = cur == null ? "" : String(cur); if (f.t === "num") el.inputMode = "numeric"; }
      el.id = idp + f.k; l.htmlFor = el.id; wrap.appendChild(l); wrap.appendChild(el);
      if (f.hint) wrap.appendChild(mk("div", "hint", f.hint));
      var er = mk("div", "ferr"); wrap.appendChild(er);
      return { wrap: wrap, el: el, err: er, f: f };
    }
    function val(x) {   // -> {v} or {bad}
      var s = x.el.value.trim();
      if (x.f.t !== "num") return { v: s };
      if (s === "") return { v: "" };
      if (!/^\d+$/.test(s)) return { bad: "Use a whole number." };
      return { v: parseInt(s, 10) };
    }
    function problems(res, els) {
      var ps = (res.body && res.body.error && res.body.error.problems) || [], out = [], mine = {};
      ps.forEach(function (p) { var t = RCISSUE[p.issue] || "That value is not valid."; if (els[p.field]) mine[p.field] = t; else out.push((CLABEL[p.field] || p.field) + ": " + t); });
      if (!ps.length) out.push(adminProblem(res.status));
      return { fields: mine, other: out };
    }
    var addEls = {}, slugTouched = false;
    FIELDS.forEach(function (f) { if (!f.add) return; var x = mkF(f, "rcA_", null); g("AddFields").appendChild(x.wrap); addEls[f.k] = x; });
    addEls.title.el.addEventListener("input", function () { if (!slugTouched) addEls.slug.el.value = slugify(addEls.title.el.value); });
    addEls.slug.el.addEventListener("input", function () { slugTouched = true; });

    function load() {
      var my = ++S.seq; g("Msg").textContent = ""; g("Retry").hidden = true;
      return admin("list", { limit: 200 }, "curriculums").then(function (res) {
        if (my !== S.seq) return;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status !== 200 || !res.body.ok) { g("Msg").textContent = "Could not load the curricula. " + adminProblem(res.status); g("Retry").hidden = false; return; }
        S.all = res.body.data.records || []; S.loaded = true; render(); g("Checked").textContent = "Last checked " + fmtClock.format(new Date());
      });
    }
    S.load = load;
    function render() {
      var f = g("Filter").value, list = g("List"); list.textContent = "";
      S.all.filter(function (r) { return !f || r.status === f; }).forEach(function (r) { list.appendChild(row(r)); });
      S.newId = "";
      g("Count").textContent = S.all.length + (S.all.length === 1 ? " curriculum" : " curricula");
      g("Empty").hidden = S.all.length > 0;
    }
    function row(rec) {
      var li = mk("li", rec.id === S.newId ? "isnew" : ""), head = mk("button", "head"); head.type = "button"; head.setAttribute("aria-expanded", "false");
      var top = mk("div", "top"); top.appendChild(mk("span", "vname", rec.title || "(no title)"));
      var tgl = (rec.status === "active" || rec.status === "inactive") ? statusToggle(rec, li, { coll: "curriculums", on: "active", off: "inactive", label: "Curriculum", problem: function (res) { return problems(res, {}).other.join(" "); } }) : null;
      if (!tgl) top.appendChild(mk("span", "type", rec.status || ""));
      head.appendChild(top);
      if (rec.tagline) head.appendChild(mk("div", "sub", rec.tagline));
      head.appendChild(mk("div", "sub", currLine(rec)));
      var detail = mk("div", "detail"), wrap = mk("div"), r = mk("div", "actions-row"), host = mk("div"), box = mk("div", "confirm"); box.hidden = true;
      var ed = mk("button", "", "Edit"), del = mk("button", "danger", "Delete"); ed.type = "button"; del.type = "button"; r.appendChild(ed); r.appendChild(del);
      box.appendChild(mk("div", "", "Delete " + (rec.title || "this curriculum") + "? It disappears from the list but the record is kept. To stop offering it without deleting, set it to inactive."));
      var b = mk("div", "btns"), yes = mk("button", "danger", "Delete curriculum"), no = mk("button", "quiet", "Cancel"), err = mk("div", "msg"); yes.type = "button"; no.type = "button"; err.setAttribute("role", "alert");
      b.appendChild(yes); b.appendChild(no); box.appendChild(b); box.appendChild(err);
      ed.addEventListener("click", function () { box.hidden = true; if (host.firstChild) host.textContent = ""; else host.appendChild(editForm(rec, host)); });
      del.addEventListener("click", function () { host.textContent = ""; box.hidden = !box.hidden; err.textContent = ""; });
      no.addEventListener("click", function () { box.hidden = true; });
      yes.addEventListener("click", function () {
        yes.disabled = true;
        admin("soft_delete", { id: rec.id }, "curriculums").then(function (res) {
          yes.disabled = false;
          if (res.status === 401) { lock("That key did not work."); return; }
          if (res.status === 200 && res.body && res.body.ok) { g("Notice").textContent = "Deleted " + rec.title + "."; load(); }
          else if (res.status === 404) { g("Notice").textContent = "That curriculum was already gone."; load(); }
          else err.textContent = problems(res, {}).other.join(" ");
        });
      });
      wrap.appendChild(r); wrap.appendChild(host); wrap.appendChild(box); detail.appendChild(wrap);
      if (rec.description) detail.appendChild(line("Description", rec.description));
      if (rec.notes) detail.appendChild(line("Notes", rec.notes));
      detail.appendChild(line("Added", when(rec.created_at)));
      head.addEventListener("click", function () { var open = li.classList.toggle("open"); head.setAttribute("aria-expanded", open ? "true" : "false"); });
      li.appendChild(head); if (tgl) { li.appendChild(tgl.btn); li.appendChild(tgl.msg); } li.appendChild(detail);
      if (rec.id === S.newId) setTimeout(function () { li.classList.remove("isnew"); }, 6000);
      return li;
    }
    function editForm(rec, host) {
      var form = mk("form", "eform"), els = {}; form.noValidate = true; form.autocomplete = "off";
      FIELDS.forEach(function (f) { if (f.addOnly) return; var x = mkF(f, "rce_" + rec.id + "_", rec[f.k]); form.appendChild(x.wrap); els[f.k] = x; });
      var sl = mk("label", "f", "Status"), ss = mk("select"); ss.id = "rcst_" + rec.id; sl.htmlFor = ss.id;
      [["active", "Active"], ["inactive", "Inactive (kept, not offered)"]].forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; ss.appendChild(op); });
      ss.value = rec.status || "active"; form.appendChild(sl); form.appendChild(ss);
      var btns = mk("div", "btns"), save = mk("button", "", "Save changes"), cancel = mk("button", "quiet", "Cancel"); save.type = "submit"; cancel.type = "button"; btns.appendChild(save); btns.appendChild(cancel); form.appendChild(btns);
      var msg = mk("div", "msg"); msg.setAttribute("role", "alert"); form.appendChild(msg);
      cancel.addEventListener("click", function () { host.textContent = ""; });
      form.addEventListener("submit", function (e) {
        e.preventDefault(); msg.textContent = ""; var changes = {}, bad = false;
        Object.keys(els).forEach(function (k) { els[k].err.textContent = ""; });
        Object.keys(els).forEach(function (k) {
          var x = els[k], v = val(x), cur = rec[k];
          if (v.bad) { x.err.textContent = v.bad; bad = true; return; }
          if (v.v === "") { if (cur !== undefined) { if (k === "title") { x.err.textContent = "Required."; bad = true; } else changes[k] = null; } }
          else if (v.v !== cur) changes[k] = v.v;
        });
        if (ss.value !== (rec.status || "active")) changes.status = ss.value;
        if (bad) return;
        if (!Object.keys(changes).length) { host.textContent = ""; g("Notice").textContent = "Nothing changed."; return; }
        save.disabled = true;
        admin("update", { id: rec.id, changes: changes, expected_updated_at: rec.updated_at }, "curriculums").then(function (res) {
          save.disabled = false;
          if (res.status === 401) { lock("That key did not work."); return; }
          if (res.status === 200 && res.body && res.body.ok) { S.newId = rec.id; g("Notice").textContent = "Saved changes to " + (changes.title || rec.title) + "."; load(); return; }
          if (res.status === 409) { msg.textContent = "Someone changed this curriculum while you were editing. Close this, tap Refresh, and try again. Nothing was overwritten."; return; }
          if (res.status === 404) { msg.textContent = "That curriculum is gone. Tap Refresh."; return; }
          var pr = problems(res, els); Object.keys(pr.fields).forEach(function (k) { els[k].err.textContent = pr.fields[k]; });
          if (pr.other.length) msg.textContent = "Could not save: " + pr.other.join(" ");
        });
      });
      return form;
    }
    g("AddBtn").addEventListener("click", function () { g("AddForm").reset(); slugTouched = false; Object.keys(addEls).forEach(function (k) { addEls[k].err.textContent = ""; }); g("FMsg").textContent = ""; g("Notice").textContent = ""; g("AddForm").hidden = false; g("AddBtn").hidden = true; addEls.title.el.focus(); });
    g("CancelBtn").addEventListener("click", function () { g("AddForm").hidden = true; g("AddBtn").hidden = false; });
    g("AddForm").addEventListener("submit", function (e) {
      e.preventDefault(); g("FMsg").textContent = ""; var data = {}, bad = false;
      Object.keys(addEls).forEach(function (k) { addEls[k].err.textContent = ""; });
      Object.keys(addEls).forEach(function (k) {
        var x = addEls[k], v = val(x);
        if (v.bad) { x.err.textContent = v.bad; bad = true; return; }
        if (v.v !== "") data[k] = v.v;
      });
      if (!data.title) { addEls.title.err.textContent = "Required."; bad = true; }
      if (!data.slug) { addEls.slug.err.textContent = "Required."; bad = true; }
      if (bad) return;
      g("SaveBtn").disabled = true;
      admin("create", { data: data }, "curriculums").then(function (res) {
        g("SaveBtn").disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          S.newId = res.body.data.id; g("Notice").textContent = "Added " + res.body.data.title + "."; g("AddForm").hidden = true; g("AddBtn").hidden = false;
          if (g("Filter").value === "inactive") g("Filter").value = "active"; load(); return;
        }
        var pr = problems(res, addEls); Object.keys(pr.fields).forEach(function (k) { addEls[k].err.textContent = pr.fields[k]; });
        if (pr.other.length) g("FMsg").textContent = "Could not save: " + pr.other.join(" ");
      });
    });
    g("Filter").addEventListener("change", function () { g("Notice").textContent = ""; render(); });
    g("Refresh").addEventListener("click", function () { g("Notice").textContent = ""; load(); });
    g("Retry").addEventListener("click", load);
    S.reset = function () { S.loaded = false; S.all = []; S.newId = ""; g("List").textContent = ""; g("Count").textContent = ""; g("Checked").textContent = ""; g("Msg").textContent = ""; g("Notice").textContent = ""; g("Empty").hidden = true; g("Filter").value = "active"; g("AddForm").hidden = true; g("AddBtn").hidden = false; };
    return S;
  }
  var S = buildCurriculum();

  window.CurriculumStation = {
    show: function () { if (!S.loaded) S.load(); },   // the person opened the page: load it once
    reset: function () { S.reset(); },                // the Console locked or signed out: empty the page
    forget: function () { S.loaded = false; }         // Try again: load it afresh
  };
})();
