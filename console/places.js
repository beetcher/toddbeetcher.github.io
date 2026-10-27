/* Places station (window.PlacesStation: show, reset, forget, refresh): the list, filter, search, Add, GPS point and address editing, retire and delete,
   and who is linked to a place. Moved out of console.js without changing what it does (PP-2). It reaches the big file only through window.ConsoleKit;
   the address form and place words come from console/addresses.js. #placesView is in index.html. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  var $ = function (id) { return document.getElementById(id); };
  var mk = K.mk, admin = K.admin, lock = K.lock, adminProblem = K.adminProblem, line = K.line, str = K.str, statusToggle = K.statusToggle, historyBtn = K.historyBtn;
  var pDateOut = K.pDateOut, skelOn = K.skelOn, skelOff = K.skelOff, currentRoute = K.currentRoute;
  var COLL_P = K.colls().P, COLL_L = K.colls().L, COLL_LK = K.colls().LK, REL = K.rel();
  var A = window.ConsoleAddresses, addrForm = A.addrForm, lProblems = A.lProblems, locAddr = A.locAddr, locSummary = A.locSummary;
  var fmtClock = { format: function (d) { return K.clock(d); } };

  var lAll = [], lLoaded = false, lSeq = 0, lNewId = "";
  function refreshPlaces() { lLoaded = false; if (currentRoute() === "places") loadPlaces(); }

  // ---- Places station
  function loadPlaces() {
    var my = ++lSeq;
    $("lMsg").textContent = ""; $("lRetry").hidden = true;
    if (!lLoaded) skelOn($("lList"));
    return admin("list", { filters: {}, limit: 200 }, COLL_L).then(function (res) {
      if (my !== lSeq) return;
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body.ok) { skelOff($("lList")); $("lMsg").textContent = "Could not load the places. " + adminProblem(res.status); $("lRetry").hidden = false; return; }
      lAll = res.body.data.records || []; lLoaded = true;
      UI.limitNote($("lList"), lAll.length, 200);
      fillChips();
      renderPlaces();
      $("lChecked").textContent = "Last checked " + fmtClock.format(new Date());
    });
  }
  // ---- Filters (shared chip bar): Status (Active by default), State, and a switch for places with no time zone. Everything is filtered in the page.
  var lCf = null, lShow = 50, STEP = 50;
  function stateOf(r) {
    var as = r.addresses || [], a = null; as.forEach(function (x) { if (!a && x.is_primary) a = x; }); if (!a) a = as[0];
    return (a && a.region) ? String(a.region).toUpperCase() : "none";
  }
  function chips() {
    if (lCf) return lCf;
    lCf = UI.chipFilters({
      mount: $("lChips"), label: "Place filters",
      filters: [
        { id: "status", label: "Status", kind: "multi", options: [{ value: "active", label: "Active" }, { value: "retired", label: "Retired" }] },
        { id: "state", label: "State", kind: "search-multi", options: [{ value: "none", label: "No state" }] },
        { id: "zone", label: "Needs a time zone", kind: "toggle", noun: "places" }],
      onChange: function () { lShow = STEP; $("lNotice").textContent = ""; renderPlaces(); }
    });
    lCf.setSelection({ status: ["active"] });
    return lCf;
  }
  function fillChips() {
    var cf = chips(), by = {}, cs = { active: 0, retired: 0 }, noZone = 0;
    lAll.forEach(function (r) { var st = stateOf(r); by[st] = (by[st] || 0) + 1; if (cs[r.status] !== undefined) cs[r.status]++; if (!r.time_zone) noZone++; });
    var opts = Object.keys(by).filter(function (k) { return k !== "none"; }).sort().map(function (k) { return { value: k, label: k }; }).concat([{ value: "none", label: "No state" }]);
    cf.setOptions("state", opts);   // choices already made are kept; new states start ticked
    cf.setCounts({ status: cs, state: by });
    cf.setBadge("zone", noZone || "");
  }
  function renderPlaces() {
    var q = $("lSearch").value.trim().toLowerCase(), list = $("lList"), sel = chips().getSelection();
    var st = sel.status || [], sts = sel.state || [], needZone = !!(sel.zone && sel.zone.length);
    var shown = lAll.filter(function (r) {
      if (st.indexOf(r.status) < 0) return false;
      if (sts.indexOf(stateOf(r)) < 0) return false;
      if (needZone && r.time_zone) return false;
      return !q || (locSummary(r) + " " + (r.aliases || []).join(" ")).toLowerCase().indexOf(q) >= 0;
    }).sort(function (a, b) { var x = locSummary(a).toLowerCase(), y = locSummary(b).toLowerCase(); return x < y ? -1 : x > y ? 1 : 0; });
    var vis = shown.slice(0, lShow), had = list.children.length;
    list.textContent = "";
    vis.forEach(function (r) { list.appendChild(placeRow(r, r.id === lNewId)); });
    lNewId = "";
    UI.moreBar($("lMore"), vis.length, shown.length, STEP, function () {
      lShow += STEP; renderPlaces();
      var fresh = $("lList").children[had]; if (fresh && fresh.querySelector("button.head")) fresh.querySelector("button.head").focus();
    }, "places");
    $("lCount").textContent = shown.length + (shown.length === 1 ? " place" : " places");
    var narrowed = shown.length !== lAll.length;
    chips().setCount(narrowed && lAll.length ? shown.length + " of " + lAll.length + " places" : "");
    $("lEmpty").hidden = lAll.length > 0;
    $("lNoMatch").hidden = !(lAll.length > 0 && shown.length === 0);
  }
  var USAGE_WORDS = { civic: "Street address", mailing: "Mailing address", po_box: "PO box", former: "Former address" }, ROLE_WORDS = { center: "center of the place", entrance: "an entrance", other: "something else" };
  var KIND_WORDS = { site: "Building or campus", point: "Doorway or spot", parcel: "Legal lot", route: "Street or trail" };
  function primaryAddr(rec) {
    var pick = null;
    (rec.addresses || []).forEach(function (a) { if (!pick || (a.is_primary && !pick.is_primary)) pick = a; });
    return locAddr(pick);
  }
  function placeRow(rec, isNew) {
    var li = mk("li", isNew ? "isnew" : "");
    var head = mk("button", "head"); head.type = "button"; head.setAttribute("aria-expanded", "false");
    var top = mk("div", "top");
    var addrText = primaryAddr(rec);
    top.appendChild(mk("span", "vname", rec.name || addrText || "(details removed)"));
    var tgl = (rec.status === "active" || rec.status === "retired") ? statusToggle(rec, li, { coll: COLL_L, on: "active", off: "retired", offWord: "Retired", label: "Place", problem: function (res) { return lProblems(res); } }) : null;
    if (!tgl) top.appendChild(mk("span", "type", rec.status || ""));
    head.appendChild(top);
    if (rec.name && addrText) head.appendChild(mk("div", "sub paddr", addrText));
    var bits = [];
    if (rec.kind) bits.push(KIND_WORDS[rec.kind] || rec.kind);
    if ((rec.geometries || []).length) bits.push(rec.geometries.length + (rec.geometries.length === 1 ? " GPS point" : " GPS shapes"));
    if ((rec.addresses || []).length > 1) bits.push(rec.addresses.length + " addresses");
    if (rec.is_residential) bits.push("someone lives here");
    if (bits.length) head.appendChild(mk("div", "sub", bits.join(" · ")));
    var detail = mk("div", "detail");
    detail.appendChild(placeActions(rec));
    function group(title) { var g = mk("div", "dgroup"); g.appendChild(mk("h3", "dgh", title)); detail.appendChild(g); return g; }
    var ag1 = rec.addresses && rec.addresses.length ? group("Addresses") : null;
    (rec.addresses || []).forEach(function (a) { ag1.appendChild(line((USAGE_WORDS[a.usage] || "Address") + (a.is_primary ? " (main)" : ""), locAddr(a) || "(no text)")); });
    var gg = rec.geometries && rec.geometries.length ? group("GPS points") : null;
    (rec.geometries || []).forEach(function (g) {
      var c = g.geometry.coordinates, t = g.geometry.type === "Point" ? c[1] + ", " + c[0] : "A shape on the map";
      gg.appendChild(line("GPS point" + (g.role ? ": " + (ROLE_WORDS[g.role] || g.role) : "") + (g.label ? " (" + g.label + ")" : ""), t));
    });
    var dd = group("Details");
    dd.appendChild(line("Time zone", rec.time_zone ? UI.zoneName(rec.time_zone) : "Not set yet"));
    if (rec.aliases && rec.aliases.length) dd.appendChild(line("Also known as", rec.aliases.join(", ")));
    if (rec.description) dd.appendChild(line("Description", rec.description));
    var lg = group("Linked to"), who = mk("div"), wb = mk("button", "btn-link", "Show who is linked here"); wb.type = "button"; who.appendChild(wb);
    wb.addEventListener("click", function () { wb.disabled = true; showLinked(rec, who, wb); });
    lg.appendChild(who);
    head.addEventListener("click", function () { var open = li.classList.toggle("open"); head.setAttribute("aria-expanded", open ? "true" : "false"); });
    li.appendChild(head); if (tgl) { li.appendChild(tgl.btn); li.appendChild(tgl.msg); } li.appendChild(detail);
    if (isNew) setTimeout(function () { li.classList.remove("isnew"); }, 6000);
    return li;
  }
  function showLinked(rec, host, btn) {
    admin("list", { filters: { location_id: rec.id }, limit: 100 }, COLL_LK).then(function (res) {
      if (res.status === 401) { lock("That key did not work."); return; }
      btn.remove();
      if (res.status !== 200 || !res.body.ok) { host.appendChild(mk("div", "msg", "Could not load. " + adminProblem(res.status))); return; }
      var links = res.body.data.records || [];
      if (!links.length) { host.appendChild(mk("div", "hint", "Nobody is linked to this place.")); return; }
      links.forEach(function (l) {
        var coll = l.subject_type === "venue" ? "venues" : l.subject_type === "organization" ? "organizations" : COLL_P, d = mk("div");
        d.textContent = "Loading...";
        host.appendChild(d);
        admin("get", { id: l.subject_id }, coll).then(function (r) {
          var nm = r.status === 200 && r.body.ok ? (r.body.data.display_name || r.body.data.name || r.body.data.given_name) : "(not available)";
          d.textContent = nm + " · " + (REL[l.relationship] || l.relationship) + (l.valid_from ? " from " + pDateOut(l.valid_from) : "") + (l.valid_to ? " until " + pDateOut(l.valid_to) : "") + (l.status === "ended" ? " (ended)" : "");
        });
      });
    });
  }
  function placeActions(rec) {
    var wrap = mk("div"), row = mk("div", "actions-row"), host = mk("div"), box = mk("div", "confirm"); box.hidden = true;
    var err = mk("div", "msg"); err.setAttribute("role", "alert");
    function btn(label, cls) { var b = mk("button", cls || "", label); b.type = "button"; row.appendChild(b); return b; }
    // Cues (DESIGN-RULES.md): Edit is the one orange button, three outlined actions, the two links, then Delete red, last and set apart.
    var ed = btn("Edit", "btn-primary"), aa = btn("Add address", "btn-secondary"), ag = btn("Add GPS point", "btn-secondary");
    var rt = btn(rec.status === "retired" ? "Restore" : "Retire", "btn-secondary");
    var hl = historyBtn(rec.id, rec.name || rec.label || "this place"); if (hl) { hl.className = "btn-link"; row.appendChild(hl); }
    var ra = btn("Remove an address or GPS point", "btn-link"), del = btn("Delete", "btn-danger pdel");
    function open(builder) { box.hidden = true; err.textContent = ""; if (host.firstChild) { host.textContent = ""; return; } host.appendChild(builder()); }
    function save(changes, done) {
      admin("update", { id: rec.id, changes: changes, expected_updated_at: rec.updated_at }, COLL_L).then(function (r) {
        if (r.status === 401) { lock("That key did not work."); return; }
        if (r.status === 200 && r.body.ok) { lNewId = rec.id; $("lNotice").textContent = "Saved changes. If an address changed, people in upcoming classes at venues here are emailed the new address. Messages shows the result."; loadPlaces(); return; }
        if (r.status === 409 && r.body.error && r.body.error.code === "conflict" && lProblems(r).indexOf("still linked") >= 0) { err.textContent = lProblems(r); return; }
        err.textContent = r.status === 409 ? "Someone changed this place while you were editing. Tap Refresh and try again." : lProblems(r);
        if (done) done();
      });
    }
    ed.addEventListener("click", function () { open(function () {
      var form = mk("form", "eform"); form.noValidate = true;
      var isSuper = K.me().is_super_admin === true;
      var defs = [["name", "Name", "text"], ["description", "Description", "area"]].concat(isSuper ? [["time_zone", "Time zone", "zone"]] : []).concat([["kind", "Kind", "kind"]]), els = {};
      defs.forEach(function (d) {
        var id = "pl_" + rec.id + "_" + d[0], l = mk("label", "f", d[1]); l.htmlFor = id; form.appendChild(l); var el;
        if (d[2] === "kind") { el = mk("select"); [["point", "Point (a doorway or a spot)"], ["site", "Site (a building, campus or property)"], ["parcel", "Parcel (a legal lot)"], ["route", "Route (a street or trail)"]].forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; el.appendChild(op); }); el.value = rec.kind || "site"; }
        else if (d[2] === "zone") {
          el = mk("select");
          [["", "(none)"], ["America/New_York", "Eastern"], ["America/Chicago", "Central"], ["America/Denver", "Mountain"], ["America/Phoenix", "Arizona (no daylight saving)"], ["America/Los_Angeles", "Pacific"], ["America/Anchorage", "Alaska"], ["America/Adak", "Aleutian (Alaska islands)"], ["Pacific/Honolulu", "Hawaii"]].forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; el.appendChild(op); });
          if (rec.time_zone && !Array.prototype.some.call(el.options, function (o) { return o.value === rec.time_zone; })) { var oo = mk("option", "", rec.time_zone); oo.value = rec.time_zone; el.appendChild(oo); }
          el.value = rec.time_zone || "";
        }
        else if (d[2] === "area") { el = mk("textarea"); el.maxLength = 2000; el.value = rec[d[0]] || ""; }
        else { el = mk("input"); el.type = "text"; el.maxLength = 200; el.value = rec[d[0]] || ""; }
        el.id = id; form.appendChild(el); els[d[0]] = el;
      });
      var btns = mk("div", "btns"), s = mk("button", "", "Save changes"), c = mk("button", "quiet", "Cancel"); s.type = "submit"; c.type = "button"; btns.appendChild(s); btns.appendChild(c); form.appendChild(btns);
      c.addEventListener("click", function () { host.textContent = ""; });
      form.addEventListener("submit", function (e) {
        e.preventDefault(); err.textContent = ""; var ch = {};
        defs.forEach(function (d) { var v = els[d[0]].value.trim(), cur = rec[d[0]]; if (v === "") { if (cur !== undefined && d[0] !== "kind") ch[d[0]] = null; } else if (v !== cur) ch[d[0]] = v; });
        if (!Object.keys(ch).length) { host.textContent = ""; $("lNotice").textContent = "Nothing changed."; return; }
        save(ch);
      });
      return form;
    }); });
    aa.addEventListener("click", function () { open(function () {
      var form = mk("form", "eform"); form.noValidate = true; var block = addrForm({ usageChoice: true }); form.appendChild(block);
      var pl = mk("label", "f"), pc = mk("input"); pc.type = "checkbox"; pc.id = "pa_" + rec.id; pl.htmlFor = pc.id; pl.appendChild(pc); pl.appendChild(document.createTextNode(" This is the main address")); pl.style.display = "flex"; pl.style.gap = "8px"; pl.style.alignItems = "center"; form.appendChild(pl);
      var btns = mk("div", "btns"), s = mk("button", "", "Add address"), c = mk("button", "quiet", "Cancel"); s.type = "submit"; c.type = "button"; btns.appendChild(s); btns.appendChild(c); form.appendChild(btns);
      c.addEventListener("click", function () { host.textContent = ""; });
      form.addEventListener("submit", function (e) {
        e.preventDefault(); err.textContent = ""; var rd = block.read();
        if (rd.ok && !rd.data.addresses) { err.textContent = "Enter a street or a PO box."; return; }
        if (!rd.ok) return;
        var a = rd.data.addresses[0], cur = (rec.addresses || []).map(function (x) { var y = JSON.parse(JSON.stringify(x)); if (pc.checked) delete y.is_primary; return y; });
        if (pc.checked) a.is_primary = true; else delete a.is_primary;
        save({ addresses: cur.concat([a]) });
      });
      return form;
    }); });
    ag.addEventListener("click", function () { open(function () {
      var form = mk("form", "eform"); form.noValidate = true;
      var rl = mk("label", "f", "What does this point mark?"), rs = mk("select"); rs.id = "gr_" + rec.id; rl.htmlFor = rs.id;
      [["center", "Center of the place"], ["entrance", "An entrance"], ["other", "Something else"]].forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; rs.appendChild(op); });
      var ll = mk("label", "f", "Label (optional)"), li2 = mk("input"); li2.type = "text"; li2.maxLength = 100; li2.id = "gl_" + rec.id; ll.htmlFor = li2.id; li2.placeholder = "for example: north gate";
      var a1 = mk("label", "f", "Latitude"), i1 = mk("input"); i1.type = "text"; i1.id = "ga_" + rec.id; a1.htmlFor = i1.id;
      var a2 = mk("label", "f", "Longitude"), i2 = mk("input"); i2.type = "text"; i2.id = "go_" + rec.id; a2.htmlFor = i2.id;
      [rl, rs, ll, li2, a1, i1, a2, i2].forEach(function (n) { form.appendChild(n); });
      var btns = mk("div", "btns"), s = mk("button", "", "Add GPS point"), c = mk("button", "quiet", "Cancel"); s.type = "submit"; c.type = "button"; btns.appendChild(s); btns.appendChild(c); form.appendChild(btns);
      c.addEventListener("click", function () { host.textContent = ""; });
      form.addEventListener("submit", function (e) {
        e.preventDefault(); err.textContent = "";
        var la = Number(i1.value.trim()), lo = Number(i2.value.trim());
        if (!i1.value.trim() || !i2.value.trim() || isNaN(la) || isNaN(lo) || la < -90 || la > 90 || lo < -180 || lo > 180) { err.textContent = "Latitude is -90 to 90 and longitude is -180 to 180."; return; }
        var g = { role: rs.value, geometry: { type: "Point", coordinates: [lo, la] } }; if (li2.value.trim()) g.label = li2.value.trim();
        save({ geometries: (rec.geometries || []).concat([g]) });
      });
      return form;
    }); });
    ra.addEventListener("click", function () { open(function () {
      var f = mk("div", "eform"), items = [];
      (rec.addresses || []).forEach(function (a, i) { items.push({ label: "Address: " + (locAddr(a) || a.usage), key: "addresses", idx: i }); });
      (rec.geometries || []).forEach(function (g, i) { items.push({ label: "GPS " + g.role + (g.label ? " (" + g.label + ")" : "") + ": " + (g.geometry.type === "Point" ? g.geometry.coordinates[1] + ", " + g.geometry.coordinates[0] : g.geometry.type), key: "geometries", idx: i }); });
      if (!items.length) f.appendChild(mk("div", "hint", "Nothing to remove."));
      items.forEach(function (it) {
        var r = mk("div", "actions-row"); r.appendChild(mk("span", "", it.label));
        var b = mk("button", "danger", "Remove"); b.type = "button"; r.appendChild(b); f.appendChild(r);
        b.addEventListener("click", function () {
          if (b.dataset.sure !== "1") { b.dataset.sure = "1"; b.textContent = "Tap again to remove"; setTimeout(function () { b.dataset.sure = ""; b.textContent = "Remove"; }, 4000); return; }
          var list = (rec[it.key] || []).slice(); list.splice(it.idx, 1);
          var ch = {}; ch[it.key] = list.length ? list : null; save(ch);
        });
      });
      var c = mk("button", "quiet", "Close"); c.type = "button"; c.addEventListener("click", function () { host.textContent = ""; }); f.appendChild(c);
      return f;
    }); });
    rt.addEventListener("click", function () { host.textContent = ""; box.hidden = true; err.textContent = ""; save({ status: rec.status === "retired" ? "active" : "retired" }); });
    box.appendChild(mk("div", "", "Delete this place? It is hidden from the lists but the record is kept. A place with a live link cannot be deleted."));
    var bb = mk("div", "btns"), yes = mk("button", "btn-danger", "Delete place"), no = mk("button", "btn-secondary", "Cancel"); yes.type = "button"; no.type = "button"; bb.appendChild(yes); bb.appendChild(no); box.appendChild(bb);
    del.addEventListener("click", function () { host.textContent = ""; err.textContent = ""; box.hidden = !box.hidden; });
    no.addEventListener("click", function () { box.hidden = true; });
    yes.addEventListener("click", function () {
      yes.disabled = true;
      admin("soft_delete", { id: rec.id }, COLL_L).then(function (r) {
        yes.disabled = false; if (r.status === 401) { lock("That key did not work."); return; }
        if (r.status === 200 || r.status === 404) { $("lNotice").textContent = "Deleted the place."; loadPlaces(); return; }
        err.textContent = r.status === 409 ? "People or venues are still linked to this place. End those links first." : lProblems(r);
      });
    });
    wrap.appendChild(row); wrap.appendChild(host); wrap.appendChild(box); wrap.appendChild(err);
    return wrap;
  }
  function resetPlaces() {
    lLoaded = false; lAll = []; lNewId = "";
    $("lList").textContent = ""; $("lCount").textContent = ""; $("lChecked").textContent = ""; $("lMsg").textContent = ""; $("lNotice").textContent = "";
    $("lEmpty").hidden = true; $("lNoMatch").hidden = true; $("lSearch").value = ""; lShow = STEP; $("lMore").textContent = "";
    if (lCf) { lCf.setSelection({ status: ["active"], zone: [] }); }
    $("lAddForm").hidden = true; $("lAddBtn").hidden = false; $("lAddFields").textContent = "";
  }
  var lBlock = null;
  $("lAddBtn").addEventListener("click", function () {
    $("lAddFields").textContent = ""; lBlock = addrForm({ name: true, description: true, tz: K.me().is_super_admin === true, gps: true, usageChoice: false }); $("lAddFields").appendChild(lBlock);
    $("lFMsg").textContent = ""; $("lNotice").textContent = ""; $("lAddForm").hidden = false; $("lAddBtn").hidden = true;
  });
  $("lCancelBtn").addEventListener("click", function () { $("lAddForm").hidden = true; $("lAddBtn").hidden = false; });
  $("lAddForm").addEventListener("submit", function (e) {
    e.preventDefault(); $("lFMsg").textContent = "";
    var rd = lBlock.read(); if (!rd.ok) return;
    $("lSaveBtn").disabled = true;
    admin("create", { data: rd.data }, COLL_L).then(function (res) {
      $("lSaveBtn").disabled = false;
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status === 200 && res.body.ok) {
        var d = res.body.data, same = d.address_matches || [];
        lNewId = d.id; $("lNotice").textContent = "Saved " + locSummary(d) + "." + (same.length ? " Heads up: " + same.length + " other saved " + (same.length === 1 ? "place has" : "places have") + " this same address. Nothing was merged." : "");
        $("lAddForm").hidden = true; $("lAddBtn").hidden = false;
        lLoaded = false; chips().setSelection({ status: ["active"] });
        loadPlaces(); return;
      }
      $("lFMsg").textContent = "Could not save: " + lProblems(res);
    });
  });
  $("lRefresh").addEventListener("click", function () { $("lNotice").textContent = ""; loadPlaces(); });
  $("lRetry").addEventListener("click", loadPlaces);
  $("lClear").addEventListener("click", function () { $("lSearch").value = ""; lShow = STEP; chips().clearAll(); chips().setSelection({ status: ["active"], zone: [] }); renderPlaces(); $("lSearch").focus(); });
  $("lSearch").addEventListener("input", function () { lShow = STEP; renderPlaces(); });



  window.PlacesStation = { show: function () { if (!lLoaded) loadPlaces(); }, reset: function () { resetPlaces(); }, forget: function () { lLoaded = false; }, refresh: function () { refreshPlaces(); } };
})();
