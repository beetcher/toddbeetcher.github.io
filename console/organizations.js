/* Organizations station (window.OrganizationsStation: show, reset, forget): the list with its status filter and search, Add, the Edit form, the active/inactive switch, Delete,
   and the links panel (people, venues, organizations and places linked to an organization). Moved out of console.js without changing what it does.
   It reaches the big file only through window.ConsoleKit. Builds its own page into #organizationsView at load. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  var $ = function (id) { return document.getElementById(id); };
  var mk = K.mk, admin = K.admin, lock = K.lock, adminProblem = K.adminProblem, line = K.line, when = K.when, statusToggle = K.statusToggle;
  var peopleList = K.peopleList, refreshPlaces = K.refreshPlaces, pDateOut = K.pDateOut, locAddr = K.locAddr, REL = K.rel(), COLL_LK = K.colls().LK;
  var fmtClock = { format: function (d) { return K.clock(d); } };

  var OISSUE = { required: "Required.", invalid_format: "Check the format.", out_of_range: "That is too long, too short or out of range.", invalid_type: "That value is not valid.",
                 invalid_value: "That value is not valid.", not_allowed: "Not allowed.", immutable: "That cannot be changed.", duplicate: "Already used." };
  var OKINDS = [["business", "Business"], ["nonprofit", "Nonprofit"], ["school", "School"], ["school_district", "School district"], ["college_university", "College or university"],
                ["government", "Government"], ["governing_body", "Governing body (a board)"], ["association", "Association"], ["club", "Club"],
                ["training_provider", "Training provider"], ["community_group", "Community group"], ["other", "Other"]];
  var OKIND_LABEL = {}; OKINDS.forEach(function (k) { OKIND_LABEL[k[0]] = k[1]; });
  function buildOrganization() {
    var P = "ro", S = { all: [], loaded: false, seq: 0, newId: "" }, g = function (s) { return $(P + s); };
    var root = $("organizationsView");
    root.innerHTML =
      '<div class="bar phead"><div class="ptext"><h2 class="ptitle" id="roTitle">Organizations</h2><div class="count" id="roCount"></div><div class="meta" id="roChecked"></div></div>' +
      '<div class="actions"><button type="button" class="btn-link manualBtn" data-m="organizations">Manual</button><button id="roRefresh" class="btn-link" type="button">Refresh</button>' +
      '<button id="roAddBtn" type="button" class="btn-primary">Add organization</button></div></div>' +
      '<form class="panel" id="roAddForm" hidden autocomplete="off" novalidate><h2>Add an organization</h2>' +
      '<div class="hint">Only the name is needed. Everything else can be added later.</div>' +
      '<div id="roAddFields"></div>' +
      '<div class="btns"><button type="submit" id="roSaveBtn">Save organization</button><button type="button" class="quiet" id="roCancelBtn">Cancel</button></div>' +
      '<div class="msg" id="roFMsg" role="alert"></div></form>' +
      '<input type="search" id="roSearch" class="psearch" placeholder="Find by name" aria-label="Find an organization by name" autocomplete="off">' +
      '<div id="roChips"></div>' +
      '<div class="notice" id="roNotice" role="status"></div><div class="msg" id="roMsg" role="alert"></div>' +
      '<button type="button" class="btn-secondary" id="roRetry" hidden>Try again</button><ul id="roList"></ul><div id="roMore"></div><div class="empty" id="roEmpty" hidden><b>No organizations yet.</b><br>Add the schools, companies or groups you work with.</div>' +
      '<div class="empty" id="roNoMatch" hidden><b>No organization matches that.</b><br>Try fewer words, or <button type="button" class="btn-link" id="roClear">clear the filters and the search</button>.</div>';
    // t: text | area | kinds | lines (one per line) | ids (type: value per line) | date
    var FIELDS = [
      { k: "name", label: "Name", t: "text", add: true, max: 200, hint: "What people call it, for example Ozo Coffee." },
      { k: "kinds", label: "Kind (tick all that fit)", t: "kinds", add: true },
      { k: "short_name", label: "Short name (optional)", t: "text", add: true, max: 60, hint: "For example BVSD." },
      { k: "website_url", label: "Web address (optional)", t: "text", add: true, max: 300, hint: "Starts with http:// or https://" },
      { k: "email", label: "Email (optional)", t: "text", add: true, max: 200 },
      { k: "phone", label: "Phone (optional)", t: "text", add: true, max: 40 },
      { k: "legal_name", label: "Legal name (optional)", t: "text", add: false, max: 200, more: true },
      { k: "aliases", label: "Other names (optional)", t: "lines", add: false, more: true, hint: "One per line: former names, trade names, abbreviations." },
      { k: "description", label: "Description (optional)", t: "area", add: false, more: true, max: 2000 },
      { k: "identifiers", label: "Outside identifiers (optional)", t: "ids", add: false, more: true, hint: "One per line as type: value, for example ein: 00-0000000." },
      { k: "founded_date", label: "Founded (optional)", t: "date", add: false, more: true, hint: "YYYY, YYYY-MM or YYYY-MM-DD." },
      { k: "closed_date", label: "Closed (optional)", t: "date", add: false, more: true, hint: "YYYY, YYYY-MM or YYYY-MM-DD." },
      { k: "notes", label: "Notes (optional)", t: "area", add: false, more: true, max: 2000, hint: "Visible to operators only." }
    ];
    var LAB = { name: "Name", kinds: "Kind", short_name: "Short name", website_url: "Web address", email: "Email", phone: "Phone", legal_name: "Legal name", aliases: "Other names",
                description: "Description", identifiers: "Identifiers", founded_date: "Founded", closed_date: "Closed", notes: "Notes", status: "Status" };
    function idsText(list) { return (list || []).map(function (i) { return i.type + ": " + i.value; }).join("\n"); }
    function mkF(f, idp, cur) {
      var wrap = mk("div"), l = mk("label", "f", f.label), el;
      if (f.t === "kinds") {
        el = mk("div"); el.id = idp + f.k; el.setAttribute("role", "group"); el.setAttribute("aria-label", f.label); l.removeAttribute("for");
        OKINDS.forEach(function (kk) {
          var lab = mk("label"), cb = mk("input"); cb.type = "checkbox"; cb.value = kk[0]; cb.checked = (cur || []).indexOf(kk[0]) >= 0;
          lab.style.display = "flex"; lab.style.gap = "8px"; lab.style.alignItems = "center"; lab.style.padding = "2px 0";
          lab.appendChild(cb); lab.appendChild(document.createTextNode(kk[1])); el.appendChild(lab);
        });
      } else if (f.t === "area" || f.t === "lines" || f.t === "ids") {
        el = mk("textarea"); el.maxLength = f.max || 2000; el.value = f.t === "lines" ? (cur || []).join("\n") : f.t === "ids" ? idsText(cur) : (cur == null ? "" : cur);
        if (f.t !== "area") el.rows = 3;
      } else {
        el = mk("input"); el.type = "text"; el.maxLength = f.t === "date" ? 10 : (f.max || 200); el.value = cur == null ? "" : String(cur);
        if (f.k === "email") el.inputMode = "email"; if (f.k === "website_url") el.inputMode = "url";
      }
      el.id = idp + f.k; if (f.t !== "kinds") l.htmlFor = el.id; wrap.appendChild(l); wrap.appendChild(el);
      if (f.hint) wrap.appendChild(mk("div", "hint", f.hint));
      var er = mk("div", "ferr"); wrap.appendChild(er);
      return { wrap: wrap, el: el, err: er, f: f };
    }
    function val(x, rec) {   // -> {v} (v = "" means empty) or {bad}
      var f = x.f, el = x.el;
      if (f.t === "kinds") { var ks = []; Array.prototype.forEach.call(el.querySelectorAll("input"), function (cb) { if (cb.checked) ks.push(cb.value); }); return ks.length ? { v: ks } : { v: "" }; }
      if (f.t === "lines") { var ls = el.value.split("\n").map(function (s) { return s.trim(); }).filter(Boolean); return ls.length ? { v: ls } : { v: "" }; }
      if (f.t === "ids") {
        var out = [], bad = false;
        el.value.split("\n").map(function (s) { return s.trim(); }).filter(Boolean).forEach(function (s) {
          var m = /^([A-Za-z][A-Za-z0-9_ ]*?)\s*:\s*(.+)$/.exec(s);
          if (!m) { bad = true; return; }
          var type = m[1].trim().toLowerCase().replace(/\s+/g, "_"), value = m[2].trim(), o = { type: type, value: value };
          ((rec && rec.identifiers) || []).forEach(function (old) { if (old.type === type && old.value === value && old.description) o.description = old.description; });
          out.push(o);
        });
        if (bad) return { bad: "Use type: value on each line, for example ein: 00-0000000." };
        return out.length ? { v: out } : { v: "" };
      }
      return { v: el.value.trim() };
    }
    function problems(res, els) {
      var ps = (res.body && res.body.error && res.body.error.problems) || [], out = [], mine = {};
      ps.forEach(function (p) { var t = OISSUE[p.issue] || "That value is not valid."; if (els[p.field]) mine[p.field] = t; else out.push((LAB[p.field] || p.field) + ": " + t); });
      if (!ps.length) out.push(adminProblem(res.status));
      return { fields: mine, other: out };
    }
    var addEls = {};
    FIELDS.forEach(function (f) { if (!f.add) return; var x = mkF(f, "roA_", null); g("AddFields").appendChild(x.wrap); addEls[f.k] = x; });

    function load() {
      var my = ++S.seq; g("Msg").textContent = ""; g("Retry").hidden = true; if (!S.loaded) UI.skelOn(g("List"));
      return admin("list", { limit: 200 }, "organizations").then(function (res) {
        if (my !== S.seq) return;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status !== 200 || !res.body.ok) { UI.skelOff(g("List")); g("Msg").textContent = "Could not load the organizations. " + adminProblem(res.status); g("Retry").hidden = false; return; }
        S.all = res.body.data.records || []; S.loaded = true; UI.limitNote(g("List"), S.all.length, 200); fillChips(); render(); g("Checked").textContent = "Last checked " + fmtClock.format(new Date());
      });
    }
    S.load = load;
    function matches(r, q) {
      if (!q) return true;
      var hay = [r.name, r.short_name, r.legal_name].concat(r.aliases || []).join(" ").toLowerCase();
      return hay.indexOf(q) >= 0;
    }
    var cf = null, show = 50, STEP = 50;
    function chips() {
      if (cf) return cf;
      cf = UI.chipFilters({
        mount: g("Chips"), label: "Organization filters",
        filters: [
          { id: "status", label: "Status", kind: "multi", options: [{ value: "active", label: "Active" }, { value: "inactive", label: "Inactive" }, { value: "closed", label: "Closed" }] },
          { id: "kind", label: "Kind", kind: "multi", options: OKINDS.map(function (k) { return { value: k[0], label: k[1] }; }).concat([{ value: "none", label: "No kind yet" }]) }],
        onChange: function () { show = STEP; g("Notice").textContent = ""; render(); }
      });
      cf.setSelection({ status: ["active"] });
      cf.setNote("An organization counts under each of its kinds.");
      return cf;
    }
    function fillChips() {
      var c = chips(), st = { active: 0, inactive: 0, closed: 0 }, kd = { none: 0 };
      S.all.forEach(function (r) { if (st[r.status] !== undefined) st[r.status]++; var ks = r.kinds || []; if (!ks.length) kd.none++; ks.forEach(function (k) { kd[k] = (kd[k] || 0) + 1; }); });
      c.setCounts({ status: st, kind: kd });
    }
    S.fillChips = fillChips;
    function render() {
      var q = g("Search").value.trim().toLowerCase(), list = g("List"), sel = chips().getSelection(), sts = sel.status || [], kds = sel.kind || [];
      var shown = S.all.filter(function (r) {
        if (sts.indexOf(r.status) < 0) return false;
        var ks = r.kinds || []; if (!(ks.length ? ks.some(function (k) { return kds.indexOf(k) >= 0; }) : kds.indexOf("none") >= 0)) return false;
        return matches(r, q);
      }).sort(function (a, b) { var x = (a.name || "").toLowerCase(), y = (b.name || "").toLowerCase(); return x < y ? -1 : x > y ? 1 : 0; });
      var vis = shown.slice(0, show), had = list.children.length; list.textContent = "";
      vis.forEach(function (r) { list.appendChild(row(r)); });
      S.newId = "";
      UI.moreBar(g("More"), vis.length, shown.length, STEP, function () { show += STEP; render(); var f = g("List").children[had]; if (f && f.querySelector("button.head")) f.querySelector("button.head").focus(); }, "organizations");
      g("Count").textContent = shown.length + (shown.length === 1 ? " organization" : " organizations") + (shown.length !== S.all.length ? " shown of " + S.all.length : "");
      chips().setCount("");
      g("Empty").hidden = S.all.length > 0;
      g("NoMatch").hidden = !(S.all.length > 0 && shown.length === 0);
    }
    var IDWORDS = { ein: "EIN (tax number)", duns: "D-U-N-S number", nces: "NCES school number", uei: "UEI (federal vendor number)" };
    function kindsLine(rec) { return (rec.kinds || []).map(function (k) { return OKIND_LABEL[k] || k; }).join(", "); }
    function row(rec) {
      var li = mk("li", rec.id === S.newId ? "isnew" : ""), head = mk("button", "head"); head.type = "button"; head.setAttribute("aria-expanded", "false");
      var top = mk("div", "top"); top.appendChild(mk("span", "vname", rec.name || "(no name)"));
      var tgl = (rec.status === "active" || rec.status === "inactive") ? statusToggle(rec, li, { coll: "organizations", on: "active", off: "inactive", label: "Organization", problem: function (res) { return problems(res, {}).other.join(" "); } }) : null;
      if (!tgl) top.appendChild(mk("span", "type", rec.status ? rec.status.charAt(0).toUpperCase() + rec.status.slice(1) : ""));
      head.appendChild(top);
      var sub = [kindsLine(rec), rec.short_name].filter(Boolean).join(" · ");
      if (sub) head.appendChild(mk("div", "sub", sub));
      var detail = mk("div", "detail"), wrap = mk("div"), r = mk("div", "actions-row"), host = mk("div"), box = mk("div", "confirm"); box.hidden = true;
      var ed = mk("button", "btn-primary", "Edit"), del = mk("button", "btn-danger pdel", "Delete"); ed.type = "button"; del.type = "button"; r.appendChild(ed); r.appendChild(del);   // cues: Edit orange first, Delete red, last and set apart
      box.appendChild(mk("div", "", "Delete " + (rec.name || "this organization") + "? It disappears from the list but the record is kept. To stop using it without deleting, set it to inactive or closed."));
      var b = mk("div", "btns"), yes = mk("button", "btn-danger", "Delete organization"), no = mk("button", "btn-secondary", "Cancel"), err = mk("div", "msg"); yes.type = "button"; no.type = "button"; err.setAttribute("role", "alert");
      b.appendChild(yes); b.appendChild(no); box.appendChild(b); box.appendChild(err);
      ed.addEventListener("click", function () { box.hidden = true; if (host.firstChild) host.textContent = ""; else host.appendChild(editForm(rec, host)); });
      del.addEventListener("click", function () { host.textContent = ""; box.hidden = !box.hidden; err.textContent = ""; });
      no.addEventListener("click", function () { box.hidden = true; });
      yes.addEventListener("click", function () {
        yes.disabled = true;
        admin("soft_delete", { id: rec.id }, "organizations").then(function (res) {
          yes.disabled = false;
          if (res.status === 401) { lock("That key did not work."); return; }
          if (res.status === 200 && res.body && res.body.ok) { g("Notice").textContent = "Deleted " + rec.name + "."; load(); }
          else if (res.status === 404) { g("Notice").textContent = "That organization was already gone."; load(); }
          else err.textContent = problems(res, {}).other.join(" ");
        });
      });
      wrap.appendChild(r); wrap.appendChild(host); wrap.appendChild(box); detail.appendChild(wrap);
      if (rec.legal_name) detail.appendChild(line("Legal name", rec.legal_name));
      if (rec.aliases && rec.aliases.length) detail.appendChild(line("Also known as", rec.aliases.join(", ")));
      if (rec.description) detail.appendChild(line("Description", rec.description));
      if (rec.website_url) detail.appendChild(line("Web", rec.website_url));
      if (rec.email) detail.appendChild(line("Email", rec.email));
      if (rec.phone) detail.appendChild(line("Phone", rec.phone));
      (rec.identifiers || []).forEach(function (i) { detail.appendChild(line(IDWORDS[i.type] || (String(i.type || "Identifier").replace(/_/g, " ").replace(/^./, function (c) { return c.toUpperCase(); })), i.value)); });
      if (rec.founded_date) detail.appendChild(line("Founded", pDateOut(rec.founded_date)));
      if (rec.closed_date) detail.appendChild(line("Closed", pDateOut(rec.closed_date)));
      if (rec.status === "active" || rec.status === "inactive") { /* shown by the switch */ }
      if (rec.notes) detail.appendChild(line("Notes", rec.notes));
      detail.appendChild(line("Added", when(rec.created_at)));
      detail.appendChild(linksPanel(rec));
      head.addEventListener("click", function () { var open = li.classList.toggle("open"); head.setAttribute("aria-expanded", open ? "true" : "false"); });
      li.appendChild(head); if (tgl) { li.appendChild(tgl.btn); li.appendChild(tgl.msg); } li.appendChild(detail);
      if (rec.id === S.newId) setTimeout(function () { li.classList.remove("isnew"); }, 6000);
      return li;
    }
    // ---- Links on the card: people, venues and other organizations (organization_links), and places (location_links) ----
    var COLL_OL = "organization_links";
    var OREL = [["leads", "Leads"], ["works_for", "Works for"], ["member_of", "Member of"], ["volunteers_for", "Volunteers for"], ["teaches_for", "Teaches for"],
                ["contact_for", "Contact for"], ["part_of", "Part of"], ["affiliated_with", "Affiliated with"], ["sponsored_by", "Sponsored by"],
                ["operated_by", "Operated by"], ["succeeded_by", "Succeeded by"], ["other", "Other"]];
    var OREL_LABEL = {}; OREL.forEach(function (r) { OREL_LABEL[r[0]] = r[1]; });
    var OSUBJ = { individual: ["Person", "individuals"], venue: ["Venue", "venues"], organization: ["Organization", "organizations"] };
    var PLACE_RELS = ["operates_at", "owns", "manages", "works_at", "mailing_address_for", "billing_address_for", "delivers_to", "other"];
    var LINK_ISSUE = { required: "Required.", not_found: "That one was not found.", invalid_format: "Check the format (YYYY, YYYY-MM or YYYY-MM-DD).", invalid_value: "That value is not allowed.",
                       out_of_range: "That is too long or out of order.", duplicate: "That link already exists for these dates.", retired: "That place is retired.", not_allowed: "Not allowed.", immutable: "That cannot be changed." };
    var nameCache = {};
    function subjName(type, id) {
      var key = type + ":" + id;
      if (nameCache[key]) return Promise.resolve(nameCache[key]);
      return admin("get", { id: id }, type === "location" ? "locations" : OSUBJ[type][1]).then(function (r) {
        var d = r.status === 200 && r.body && r.body.ok ? r.body.data : null;
        var nm = d ? (d.display_name || d.name || d.given_name || (type === "location" && d.addresses && d.addresses[0] ? locAddr(d.addresses[0]) : "") || "(no name)") : "(not available)";
        if (d) nameCache[key] = nm;
        return nm;
      });
    }
    function todayStr() { var d = new Date(); return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }
    function span(l) { return (l.valid_from ? " from " + pDateOut(l.valid_from) : "") + (l.valid_to ? " until " + pDateOut(l.valid_to) : ""); }
    function linkProblems(res) {
      var ps = (res.body && res.body.error && res.body.error.problems) || [];
      if (!ps.length) return adminProblem(res.status);
      return ps.map(function (p) { return ((LAB[p.field] || { subject_id: "Who", organization_id: "Organization", relationship: "Kind of link", valid_from: "From", valid_to: "Until", title: "Title", location_id: "Place" }[p.field] || p.field)) + ": " + (LINK_ISSUE[p.issue] || "not valid."); }).join(" ");
    }
    function labeled(parent, text, el, idv) { var l = mk("label", "f", text); if (idv) { el.id = idv; l.htmlFor = idv; } parent.appendChild(l); parent.appendChild(el); return el; }
    function selectOf(opts) { var s = mk("select"); opts.forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; s.appendChild(op); }); return s; }
    function textIn(max, ph) { var i = mk("input"); i.type = "text"; i.maxLength = max; if (ph) i.placeholder = ph; i.autocomplete = "off"; return i; }

    function linksPanel(rec) {
      var wrap = mk("div", "olinks"), row2 = mk("div", "actions-row"), host = mk("div"), msg = mk("div", "msg"); msg.setAttribute("role", "alert");
      function btn(label, cls) { var b = mk("button", cls || "quiet", label); b.type = "button"; row2.appendChild(b); return b; }
      var bShow = btn("Show links"), bAdd = btn("Add link"), bPl = btn("Show places"), bAddPl = btn("Add place");
      wrap.appendChild(mk("div", "hint", "Links: who and what belongs to this organization, and where it is.")); wrap.appendChild(row2); wrap.appendChild(host); wrap.appendChild(msg);
      function open(builder) { msg.textContent = ""; if (host.firstChild && host.dataset.k === builder.k) { host.textContent = ""; host.dataset.k = ""; return; } host.textContent = ""; host.dataset.k = builder.k; builder(); }
      function actions(l, coll, li, reload) {
        var r = mk("span", "olact");
        if (!l.valid_to) {
          var e = mk("button", "quiet", "End"); e.type = "button"; r.appendChild(e);
          e.addEventListener("click", function () {
            e.disabled = true;
            var p = coll === COLL_LK ? admin("end", { id: l.id }, coll) : admin("update", { id: l.id, changes: { valid_to: todayStr() }, expected_updated_at: l.updated_at }, coll);
            p.then(function (res) { if (res.status === 401) { lock("That key did not work."); return; } if (res.status === 200 && res.body.ok) { reload(); } else { e.disabled = false; msg.textContent = res.status === 409 ? "This changed somewhere else. Show the list again." : linkProblems(res); } });
          });
        }
        var d = mk("button", "danger", "Delete"); d.type = "button"; r.appendChild(d);
        d.addEventListener("click", function () {
          if (d.dataset.sure !== "1") { d.dataset.sure = "1"; d.textContent = "Tap again to delete"; setTimeout(function () { d.dataset.sure = ""; d.textContent = "Delete"; }, 4000); return; }
          d.disabled = true;
          admin("soft_delete", { id: l.id }, coll).then(function (res) { if (res.status === 401) { lock("That key did not work."); return; } if (res.status === 200 || res.status === 404) reload(); else { d.disabled = false; msg.textContent = linkProblems(res); } });
        });
        li.appendChild(r);
      }
      function showLinks() {
        host.textContent = ""; host.dataset.k = "show"; host.appendChild(mk("div", "hint", "Loading..."));
        Promise.all([admin("list", { filters: { organization_id: rec.id }, limit: 100 }, COLL_OL), admin("list", { filters: { subject_id: rec.id }, limit: 100 }, COLL_OL)]).then(function (rs) {
          if (rs[0].status === 401 || rs[1].status === 401) { lock("That key did not work."); return; }
          host.textContent = ""; host.dataset.k = "show";
          if (rs.some(function (r) { return r.status !== 200 || !r.body.ok; })) { host.appendChild(mk("div", "msg", "Could not load. " + adminProblem(rs[0].status !== 200 ? rs[0].status : rs[1].status))); return; }
          var into = (rs[0].body.data.records || []).filter(function (l) { return !(l.subject_type === "organization" && l.subject_id === rec.id); }), outof = rs[1].body.data.records || [];
          host.appendChild(mk("div", "hint", "Linked to " + rec.name + ":"));
          if (!into.length) host.appendChild(mk("div", "empty2", "Nobody and nothing yet."));
          into.forEach(function (l) {
            var li = mk("div", "olrow"), t = mk("span", "", "Loading..."); li.appendChild(t); host.appendChild(li);
            subjName(l.subject_type, l.subject_id).then(function (nm) { t.textContent = nm + " (" + OSUBJ[l.subject_type][0].toLowerCase() + ") · " + (OREL_LABEL[l.relationship] || l.relationship) + (l.title ? " · " + l.title : "") + span(l); });
            actions(l, COLL_OL, li, showLinks);
          });
          host.appendChild(mk("div", "hint", rec.name + " is linked to:"));
          if (!outof.length) host.appendChild(mk("div", "empty2", "No other organization yet."));
          outof.forEach(function (l) {
            var li = mk("div", "olrow"), t = mk("span", "", "Loading..."); li.appendChild(t); host.appendChild(li);
            subjName("organization", l.organization_id).then(function (nm) { t.textContent = (OREL_LABEL[l.relationship] || l.relationship) + ": " + nm + (l.title ? " · " + l.title : "") + span(l); });
            actions(l, COLL_OL, li, showLinks);
          });
        });
      }
      showLinks.k = "show";
      function showPlaces() {
        host.textContent = ""; host.dataset.k = "places"; host.appendChild(mk("div", "hint", "Loading..."));
        admin("list", { filters: { subject_id: rec.id }, limit: 100 }, COLL_LK).then(function (res) {
          if (res.status === 401) { lock("That key did not work."); return; }
          host.textContent = ""; host.dataset.k = "places";
          if (res.status !== 200 || !res.body.ok) { host.appendChild(mk("div", "msg", "Could not load. " + adminProblem(res.status))); return; }
          var links = res.body.data.records || [];
          if (!links.length) { host.appendChild(mk("div", "empty2", "No place is linked to " + rec.name + ".")); return; }
          links.forEach(function (l) {
            var li = mk("div", "olrow"), t = mk("span", "", "Loading..."); li.appendChild(t); host.appendChild(li);
            subjName("location", l.location_id).then(function (nm) { t.textContent = nm + " · " + (REL[l.relationship] || l.relationship) + (l.is_primary ? " (main)" : "") + (l.description ? " · " + l.description : "") + span(l); });
            actions(l, COLL_LK, li, showPlaces);
          });
        });
      }
      showPlaces.k = "places";
      function addLink() {
        var form = mk("form", "eform"), pid = rec.id + "_al_"; form.noValidate = true; form.autocomplete = "off";
        var type = labeled(form, "What is being linked to " + rec.name + "?", selectOf([["individual", "A person"], ["venue", "A venue"], ["organization", "Another organization"]]), pid + "t");
        var q = labeled(form, "Find it by name", textIn(100, "type to search"), pid + "q"), opts = mk("div"), chosen = mk("div", "note", "Nothing chosen."), cid = "";
        form.appendChild(opts); form.appendChild(chosen);
        var rel = labeled(form, "How is it linked?", selectOf(OREL), pid + "r");
        var title = labeled(form, "Role or title (optional)", textIn(100, "for example Superintendent"), pid + "ti");
        var from = labeled(form, "From (optional)", textIn(10, "YYYY, YYYY-MM or YYYY-MM-DD"), pid + "f");
        var to = labeled(form, "Until (optional, leave empty if it still applies)", textIn(10, "YYYY, YYYY-MM or YYYY-MM-DD"), pid + "u");
        var btns = mk("div", "btns"), s = mk("button", "", "Save link"), c = mk("button", "quiet", "Cancel"); s.type = "submit"; c.type = "button"; btns.appendChild(s); btns.appendChild(c); form.appendChild(btns);
        var fm = mk("div", "msg"); fm.setAttribute("role", "alert"); form.appendChild(fm);
        function source() {
          if (type.value === "individual") return peopleList().then(function (l) { return l.map(function (p) { return { id: p.id, name: p.display_name || p.given_name || "(no name)" }; }); });
          if (type.value === "venue") return admin("list", { limit: 200 }, "venues").then(function (r) { return (r.status === 200 && r.body.ok ? r.body.data.records : []).map(function (v) { return { id: v.id, name: v.name }; }); });
          return Promise.resolve(S.all.filter(function (o) { return o.id !== rec.id; }).map(function (o) { return { id: o.id, name: o.name }; }));
        }
        function find() {
          var term = q.value.trim().toLowerCase(), kind = type.value; opts.textContent = "";
          source().then(function (list) {
            if (type.value !== kind || q.value.trim().toLowerCase() !== term) return;
            var m = list.filter(function (x) { return !term || (x.name || "").toLowerCase().indexOf(term) >= 0; }).slice(0, 8);
            if (!m.length) opts.appendChild(mk("div", "hint", "Nothing found."));
            m.forEach(function (x) { var b = mk("button", "quiet", x.name); b.type = "button"; b.addEventListener("click", function () { cid = x.id; chosen.textContent = "Chosen: " + x.name; opts.textContent = ""; }); opts.appendChild(b); });
          });
        }
        q.addEventListener("input", find); type.addEventListener("change", function () { cid = ""; chosen.textContent = "Nothing chosen."; q.value = ""; opts.textContent = ""; find(); });
        c.addEventListener("click", function () { host.textContent = ""; host.dataset.k = ""; });
        form.addEventListener("submit", function (e) {
          e.preventDefault(); fm.textContent = "";
          if (!cid) { fm.textContent = "Choose who or what to link first."; return; }
          var data = { subject_type: type.value, subject_id: cid, organization_id: rec.id, relationship: rel.value };
          if (title.value.trim()) data.title = title.value.trim(); if (from.value.trim()) data.valid_from = from.value.trim(); if (to.value.trim()) data.valid_to = to.value.trim();
          s.disabled = true;
          admin("create", { data: data }, COLL_OL).then(function (res) {
            s.disabled = false;
            if (res.status === 401) { lock("That key did not work."); return; }
            if (res.status === 200 && res.body.ok) { g("Notice").textContent = "Link saved."; showLinks(); return; }
            fm.textContent = "Could not save: " + linkProblems(res);
          });
        });
        host.appendChild(form); find();
      }
      addLink.k = "add";
      function addPlace() {
        var form = mk("form", "eform"), pid = rec.id + "_ap_"; form.noValidate = true; form.autocomplete = "off";
        var sel = labeled(form, "Which place?", selectOf([["", "Loading places..."]]), pid + "p"), places = [];
        admin("list", { limit: 200 }, "locations").then(function (r) {
          places = (r.status === 200 && r.body.ok ? r.body.data.records : []).filter(function (p) { return p.status !== "retired"; });
          sel.textContent = "";
          var first = mk("option", "", places.length ? "Choose a place" : "No places yet. Add one in Places."); first.value = ""; sel.appendChild(first);
          places.forEach(function (p) { var op = mk("option", "", p.name || (p.addresses && p.addresses[0] ? locAddr(p.addresses[0]) : "(no name)")); op.value = p.id; sel.appendChild(op); });
        });
        var rel = labeled(form, "How is it linked?", selectOf(PLACE_RELS.map(function (k) { return [k, REL[k] || k]; })), pid + "r");
        var prim = mk("input"); prim.type = "checkbox"; var pl = mk("label", "f"); pl.style.display = "flex"; pl.style.gap = "8px"; pl.style.alignItems = "center"; pl.appendChild(prim); pl.appendChild(document.createTextNode("This is the main place (for example headquarters)")); form.appendChild(pl);
        var desc = labeled(form, "A few words (optional)", textIn(300, "for example headquarters, factory"), pid + "d");
        var from = labeled(form, "From (optional)", textIn(10, "YYYY, YYYY-MM or YYYY-MM-DD"), pid + "f");
        var to = labeled(form, "Until (optional)", textIn(10, "YYYY, YYYY-MM or YYYY-MM-DD"), pid + "u");
        var btns = mk("div", "btns"), s = mk("button", "", "Save place link"), c = mk("button", "quiet", "Cancel"); s.type = "submit"; c.type = "button"; btns.appendChild(s); btns.appendChild(c); form.appendChild(btns);
        var fm = mk("div", "msg"); fm.setAttribute("role", "alert"); form.appendChild(fm);
        c.addEventListener("click", function () { host.textContent = ""; host.dataset.k = ""; });
        form.addEventListener("submit", function (e) {
          e.preventDefault(); fm.textContent = "";
          if (!sel.value) { fm.textContent = "Choose a place first."; return; }
          var data = { subject_type: "organization", subject_id: rec.id, location_id: sel.value, relationship: rel.value };
          if (prim.checked) data.is_primary = true; if (desc.value.trim()) data.description = desc.value.trim(); if (from.value.trim()) data.valid_from = from.value.trim(); if (to.value.trim()) data.valid_to = to.value.trim();
          s.disabled = true;
          admin("create", { data: data }, COLL_LK).then(function (res) {
            s.disabled = false;
            if (res.status === 401) { lock("That key did not work."); return; }
            if (res.status === 200 && res.body.ok) { g("Notice").textContent = "Place linked."; refreshPlaces(); showPlaces(); return; }
            fm.textContent = "Could not save: " + linkProblems(res);
          });
        });
        host.appendChild(form);
      }
      addPlace.k = "addplace";
      bShow.addEventListener("click", function () { open(showLinks); });
      bAdd.addEventListener("click", function () { open(addLink); });
      bPl.addEventListener("click", function () { open(showPlaces); });
      bAddPl.addEventListener("click", function () { open(addPlace); });
      return wrap;
    }
    function editForm(rec, host) {
      var form = mk("form", "eform"), els = {}; form.noValidate = true; form.autocomplete = "off";
      var more = mk("details"); more.appendChild(mk("summary", "", "More details"));
      FIELDS.forEach(function (f) { var x = mkF(f, "roe_" + rec.id + "_", rec[f.k]); (f.more ? more : form).appendChild(x.wrap); els[f.k] = x; });
      var sl = mk("label", "f", "Status"), ss = mk("select"); ss.id = "rost_" + rec.id; sl.htmlFor = ss.id;
      [["active", "Active"], ["inactive", "Inactive (kept, not used)"], ["closed", "Closed (no longer exists)"]].forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; ss.appendChild(op); });
      ss.value = rec.status === "merged" ? "active" : (rec.status || "active");
      var sw = mk("div"); sw.appendChild(sl); sw.appendChild(ss); form.appendChild(sw);
      form.appendChild(more);
      var btns = mk("div", "btns"), save = mk("button", "", "Save changes"), cancel = mk("button", "quiet", "Cancel"); save.type = "submit"; cancel.type = "button"; btns.appendChild(save); btns.appendChild(cancel); form.appendChild(btns);
      var msg = mk("div", "msg"); msg.setAttribute("role", "alert"); form.appendChild(msg);
      cancel.addEventListener("click", function () { host.textContent = ""; });
      form.addEventListener("submit", function (e) {
        e.preventDefault(); msg.textContent = ""; var changes = {}, bad = false;
        Object.keys(els).forEach(function (k) { els[k].err.textContent = ""; });
        Object.keys(els).forEach(function (k) {
          var x = els[k], v = val(x, rec), cur = rec[k];
          if (v.bad) { x.err.textContent = v.bad; bad = true; more.open = true; return; }
          if (v.v === "") { if (cur !== undefined) { if (k === "name") { x.err.textContent = "Required."; bad = true; } else changes[k] = null; } }
          else if (JSON.stringify(v.v) !== JSON.stringify(cur)) changes[k] = v.v;
        });
        if (ss.value !== (rec.status === "merged" ? "merged" : (rec.status || "active"))) changes.status = ss.value;
        if (bad) return;
        if (!Object.keys(changes).length) { host.textContent = ""; g("Notice").textContent = "Nothing changed."; return; }
        save.disabled = true;
        admin("update", { id: rec.id, changes: changes, expected_updated_at: rec.updated_at }, "organizations").then(function (res) {
          save.disabled = false;
          if (res.status === 401) { lock("That key did not work."); return; }
          if (res.status === 200 && res.body && res.body.ok) { S.newId = rec.id; g("Notice").textContent = "Saved changes to " + (changes.name || rec.name) + "."; load(); return; }
          if (res.status === 409) { msg.textContent = "Someone changed this organization while you were editing. Close this, tap Refresh, and try again. Nothing was overwritten."; return; }
          if (res.status === 404) { msg.textContent = "That organization is gone. Tap Refresh."; return; }
          var pr = problems(res, els); Object.keys(pr.fields).forEach(function (k) { els[k].err.textContent = pr.fields[k]; if (FIELDS.filter(function (f) { return f.k === k && f.more; }).length) more.open = true; });
          if (pr.other.length) msg.textContent = "Could not save: " + pr.other.join(" ");
        });
      });
      return form;
    }
    g("AddBtn").addEventListener("click", function () {
      g("AddForm").reset(); Object.keys(addEls).forEach(function (k) { addEls[k].err.textContent = ""; }); g("FMsg").textContent = ""; g("Notice").textContent = "";
      g("AddForm").hidden = false; g("AddBtn").hidden = true; addEls.name.el.focus();
    });
    g("CancelBtn").addEventListener("click", function () { g("AddForm").hidden = true; g("AddBtn").hidden = false; });
    g("AddForm").addEventListener("submit", function (e) {
      e.preventDefault(); g("FMsg").textContent = ""; var data = {}, bad = false;
      Object.keys(addEls).forEach(function (k) { addEls[k].err.textContent = ""; });
      Object.keys(addEls).forEach(function (k) {
        var v = val(addEls[k], null);
        if (v.bad) { addEls[k].err.textContent = v.bad; bad = true; return; }
        if (v.v !== "") data[k] = v.v;
      });
      if (!data.name) { addEls.name.err.textContent = "Required."; bad = true; }
      if (bad) return;
      g("SaveBtn").disabled = true;
      admin("create", { data: data }, "organizations").then(function (res) {
        g("SaveBtn").disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          S.newId = res.body.data.id; g("Notice").textContent = "Added " + res.body.data.name + "."; g("AddForm").hidden = true; g("AddBtn").hidden = false;
          chips().setSelection({ status: ["active"] }); g("Search").value = ""; show = STEP; load(); return;
        }
        var pr = problems(res, addEls); Object.keys(pr.fields).forEach(function (k) { addEls[k].err.textContent = pr.fields[k]; });
        if (pr.other.length) g("FMsg").textContent = "Could not save: " + pr.other.join(" ");
      });
    });
    g("Search").addEventListener("input", function () { show = STEP; render(); });
    g("Clear").addEventListener("click", function () { g("Search").value = ""; show = STEP; chips().clearAll(); chips().setSelection({ status: ["active"] }); render(); g("Search").focus(); });
    g("Refresh").addEventListener("click", function () { g("Notice").textContent = ""; load(); });
    g("Retry").addEventListener("click", load);
    S.reset = function () { S.loaded = false; S.all = []; S.newId = ""; g("List").textContent = ""; g("Count").textContent = ""; g("Checked").textContent = ""; g("Msg").textContent = ""; g("Notice").textContent = ""; g("Empty").hidden = true; g("NoMatch").hidden = true; g("More").textContent = ""; show = STEP; if (cf) cf.setSelection({ status: ["active"] }); g("Search").value = ""; g("AddForm").hidden = true; g("AddBtn").hidden = false; };
    return S;
  }

  var S = buildOrganization();

  window.OrganizationsStation = { show: function () { if (!S.loaded) S.load(); }, reset: function () { S.reset(); }, forget: function () { S.loaded = false; } };
})();
