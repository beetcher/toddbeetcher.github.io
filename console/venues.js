/* Venues station for the Console: the venue list with filters, the one-line scan rows and the opened Details view, Add venue (with an address or a
   saved place), the Edit form built from the published venue schema (Basics, Place, Contact and the rest), the Rooms and Open-days popups, the
   Active/Inactive switch and Delete, GPS lookup. Moved out of console.js (the Venues extraction, V-4): the code is the same; everything it used to
   borrow from the big file now comes through ConsoleKit (K), the form engine (ConsoleForms) or ui.js (UI). The page markup (#venuesView, #editPanel,
   #addForm) stays in index.html and the manual text in the stations list in console.js (DT-7). Loaded by index.html after attendance.js.
   window.VenuesStation = { show, stop, reset, dirty }: show() loads the list once, stop() closes the edit form (leaving the page), reset() empties
   everything (sign-out), dirty() says whether the edit form has unsaved changes. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var $ = function (id) { return document.getElementById(id); };
  var CF = window.ConsoleForms;
  var mk = K.mk, admin = K.admin, lock = K.lock, adminProblem = K.adminProblem, when = K.when, line = K.line, str = K.str, historyBtn = K.historyBtn, attName = K.attName;
  var fmtClock = { format: function (d) { return K.clock(d); } };
  var ISSUE = CF.issue, wholeNum = CF.wholeNum, slugify = CF.slugify, skelOn = UI.skelOn, skelOff = UI.skelOff;
  var lProblems = K.lProblems, placeInput = K.placeInput, placeText = K.placeText, peopleList = K.peopleList, peopleMatches = K.peopleMatches, pFull = K.pFull;
  var statusToggle = K.statusToggle, askDiscard = K.askDiscard;
  var vLoaded = false, vBusy = false, vAgain = false, vNewId = "", vRecs = [], vAreas = null;
  var FIELD_ERR = { name: "eName", slug: "eSlug", is_public_venue: "ePublic" };
  var slugTouched = false, addPlace = null;

  // ---- one line per venue (scan it fast), with Details to open the rest
  var HOURS_PREFIX = "Public hours per the web (check before relying on them): ";
  function vAddrLine(rec) {
    var pl = rec.place, a = pl && pl.address;
    if (!pl) return "No place yet";
    if (!a) return pl.name || "Place saved";
    var st = [a.street_number, a.street].filter(Boolean).join(" "), cs = [a.locality, a.region].filter(Boolean).join(", ");
    return [st, cs].filter(Boolean).join(", ") || pl.name || "Place saved";
  }
  function vHoursShort(rec) {
    var n = String(rec.availability_notes || "");
    if (n.indexOf(HOURS_PREFIX) !== 0) return { text: "", full: "" };
    var t = n.slice(HOURS_PREFIX.length).trim();
    return { text: t.length > 90 ? t.slice(0, 89) + "\u2026" : t, full: t };
  }
  // ---- the opened view of a venue: what people look for first, the raw record folded away
  var DAY_ABBR = { monday: "Mon", tuesday: "Tue", wednesday: "Wed", thursday: "Thu", friday: "Fri", saturday: "Sat", sunday: "Sun" };
  function dRow(label, content) {
    var d = document.createElement("div"); d.className = "vfact";
    var b = document.createElement("b"); b.textContent = label; d.appendChild(b);
    if (typeof content === "string") d.appendChild(document.createTextNode(content)); else d.appendChild(content);
    return d;
  }
  function dLink(text, href, newTab) {
    var a = document.createElement("a"); a.className = "dlink"; a.textContent = text; a.href = href;
    if (newTab) { a.target = "_blank"; a.rel = "noopener noreferrer"; }
    return a;
  }
  function vMapQuery(rec) {
    var pl = rec.place, a = pl && pl.address;
    if (a) { var q = [vAddrLine(rec)].concat(a.postal_code ? [a.postal_code] : []).join(" "); return (rec.name ? rec.name + ", " : "") + q; }
    return rec.name || "";
  }
  function vSourceLabel(u) {
    try {
      var h = new URL(u).hostname.replace(/^www\./, "");
      if (/vertexaisearch\.cloud\.google\.com$|google\.com$/.test(h) && /grounding-api-redirect/.test(u)) return "Google search result";
      return h;
    } catch (e) { return "source"; }
  }
  function vMoney(c) { return "$" + (c / 100).toFixed(c % 100 ? 2 : 0); }
  function venueDetail(rec) {
    var detail = document.createElement("div"); detail.className = "detail";
    detail.appendChild(venueActions(rec));

    var pl = rec.place, hasAddr = !!(pl && pl.address);
    var wh = document.createElement("div"); wh.className = "dlinks";
    wh.appendChild(document.createTextNode((rec.is_public_venue ? "Public venue" : "Private space") + " \u00b7 " + vAddrLine(rec) + (pl && pl.address && pl.address.postal_code ? " " + pl.address.postal_code : "")));
    detail.appendChild(wh);
    var q = vMapQuery(rec);
    if (hasAddr || rec.name) {
      var ml = document.createElement("div"); ml.className = "dlinks";
      ml.appendChild(dLink("Open in map", "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(q), true));
      ml.appendChild(dLink("See photos", "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(q), true));
      detail.appendChild(ml);
    }
    if (pl) detail.appendChild(dRow("GPS: ", pl.has_gps ? (pl.gps_source === "entered" ? "entered" : "looked up") : "none yet"));

    var cl = document.createElement("div"); cl.className = "dlinks";
    if (/^https?:\/\//i.test(String(rec.website_url || ""))) cl.appendChild(dLink("Website", rec.website_url, true));
    if (rec.phone) cl.appendChild(dLink(String(rec.phone), "tel:" + String(rec.phone).replace(/[^+0-9]/g, ""), false));
    if (rec.email) cl.appendChild(dLink(String(rec.email), "mailto:" + rec.email, false));
    if (cl.childNodes.length) detail.appendChild(cl);
    if (rec.main_contact) detail.appendChild(dRow("Contact: ", rec.main_contact.display_name || "(unavailable)"));
    if (rec.description) { var ds = document.createElement("div"); ds.className = "ddesc"; ds.textContent = rec.description; detail.appendChild(ds); }

    // hours: the web's public hours (to check), and the class days we entered
    var hr = vHoursShort(rec);
    detail.appendChild(dRow("Public hours: ", hr.full ? hr.full + " (from the web \u2014 check before relying on it)" : "Not entered"));
    var days = (rec.availability_hours || []).map(function (h) { return (DAY_ABBR[h.day_of_week] || h.day_of_week) + " " + h.opens_at + "\u2013" + h.closes_at; });
    detail.appendChild(dRow("Open days for classes: ", days.length ? days.join(", ") : "Not entered"));

    // can we meet here: only facts we actually hold
    var can = [];
    (rec.rooms || []).forEach(function (r) {
      var n = r.max_occupancy || r.preferred_occupancy;
      can.push(r.label + (n ? " (up to " + n + ")" : ""));
    });
    var facts = [];
    if (rec.is_accessible === true) facts.push("Accessible"); else if (rec.is_accessible === false) facts.push("Not accessible");
    if (rec.has_wifi === true) facts.push("Wi-Fi"); else if (rec.has_wifi === false) facts.push("No Wi-Fi");
    if (rec.allows_minors === true) facts.push("Minors allowed"); else if (rec.allows_minors === false) facts.push("No minors");
    if (rec.parking_description) facts.push("Parking: " + rec.parking_description);
    if (typeof rec.cost_cents === "number") facts.push("Cost: " + (rec.cost_cents === 0 ? "free" : vMoney(rec.cost_cents) + (rec.cost_basis ? " " + String(rec.cost_basis).replace("_", " ") : "")));
    detail.appendChild(dRow("Rooms: ", can.length ? can.join("; ") : "None entered"));
    if (facts.length) detail.appendChild(dRow("Good to know: ", facts.join(" \u00b7 ")));

    var chips = document.createElement("div"); chips.className = "lchips";
    var nr = (rec.rooms && rec.rooms.length) || 0, nh = (rec.availability_hours && rec.availability_hours.length) || 0;
    var rlink = document.createElement("button"); rlink.type = "button"; rlink.className = "btn-secondary"; rlink.textContent = "Rooms: " + nr;
    var hlink = document.createElement("button"); hlink.type = "button"; hlink.className = "btn-secondary"; hlink.textContent = "Open days: " + nh;
    rlink.addEventListener("click", function () { openListDlg(rec, "rooms"); });
    hlink.addEventListener("click", function () { openListDlg(rec, "hours"); });
    var added = document.createElement("span"); added.textContent = "Added: " + when(rec.created_at);
    chips.appendChild(rlink); chips.appendChild(hlink); chips.appendChild(added);
    detail.appendChild(chips);

    // where an AI-found record came from
    var dc = rec.discovery;
    if (dc) {
      var w = document.createElement("details"); w.className = "dfold";
      var ws = document.createElement("summary"); ws.textContent = "Where this came from"; w.appendChild(ws);
      var reasons = (dc.attention_reasons || []);
      w.appendChild(dRow("", "Found by AI search on " + when(dc.found_at) + (reasons.indexOf("operator_unconfirmed") >= 0 ? " \u2014 operator unconfirmed" : "") + "."));
      var srcs = dc.source_urls || [];
      if (srcs.length) {
        var sl = document.createElement("div"); sl.className = "dlinks";
        srcs.slice(0, 8).forEach(function (u) { sl.appendChild(dLink(vSourceLabel(u), u, true)); });
        w.appendChild(sl);
      }
      detail.appendChild(w);
    }

    // everything the record holds, folded
    var raw = document.createElement("details"); raw.className = "dfold";
    var rs = document.createElement("summary"); rs.textContent = "Technical details"; raw.appendChild(rs);
    var done = {};
    ["name", "slug", "status", "is_public_venue", "id"].forEach(function (f) { if (rec[f] !== undefined) { raw.appendChild(line(f, str(rec[f]))); done[f] = 1; } });
    Object.keys(rec).sort().forEach(function (f) { if (!done[f]) raw.appendChild(line(f, str(rec[f]))); });
    detail.appendChild(raw);
    return detail;
  }
  // Ready to host: what a class needs from a venue. Missing items are named; "Not ready" is the same test as a filter.
  function vMissing(rec) {
    var m = [];
    if (!rec.place) m.push("a place");
    else if (rec.is_public_venue && !rec.place.has_gps) m.push("a GPS point");
    if (!(rec.rooms && rec.rooms.length)) m.push("a room");
    if (!(rec.availability_hours && rec.availability_hours.length)) m.push("open days");
    return m;
  }
  function venueRow(rec, isNew) {
    var li = document.createElement("li"); li.className = "vrow" + (isNew ? " isnew" : "");
    var ln = document.createElement("div"); ln.className = "vline";
    var vm = document.createElement("div"); vm.className = "vmain";
    var nm = document.createElement("span"); nm.className = "vname"; nm.textContent = rec.name || "(no name)";
    var ad = document.createElement("span"); ad.className = "vaddr"; ad.textContent = vAddrLine(rec);
    var miss = vMissing(rec), rd = document.createElement("span"); rd.className = "vready" + (miss.length ? " no" : ""); rd.textContent = miss.length ? "Not ready to host: needs " + miss.join(", ") : "Ready to host";
    vm.appendChild(nm); vm.appendChild(ad); vm.appendChild(rd);
    ln.appendChild(vm);
    var acts = document.createElement("div"); acts.className = "vacts";
    var tg = statusToggle(rec, li, { on: "active", off: "inactive", label: "Venue", problem: function (res) { return lProblems(res); } });
    acts.appendChild(tg.btn);
    var dt = document.createElement("button"); dt.type = "button"; dt.className = "head vdetails"; dt.textContent = "Details"; dt.className = "head vdetails btn-secondary"; dt.setAttribute("aria-expanded", "false");
    acts.appendChild(dt);
    ln.appendChild(acts);

    var detail = venueDetail(rec);

    dt.addEventListener("click", function () {
      var open = li.classList.toggle("open");
      dt.setAttribute("aria-expanded", open ? "true" : "false");
    });
    li.appendChild(ln); li.appendChild(tg.msg); li.appendChild(detail);
    if (isNew) setTimeout(function () { li.classList.remove("isnew"); }, 6000);
    return li;
  }

  function loadVenues() {
    if (vBusy) { vAgain = true; return Promise.resolve(); }   // a change came in while loading: load once more when done
    vBusy = true; $("vMsg").textContent = "";
    if (!vLoaded) skelOn($("vList"));
    $("vRetry").hidden = true;
    return admin("list", { filters: {}, limit: 200, expand: true }).then(function (res) {
      vBusy = false;
      if (vAgain) { vAgain = false; return loadVenues(); }
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body.ok) { skelOff($("vList")); $("vMsg").textContent = "Could not load the venues. " + adminProblem(res.status); $("vRetry").hidden = false; return; }
      vRecs = res.body.data.records || [];
      UI.limitNote($("vList"), vRecs.length, 200);
      return (vAreas ? Promise.resolve() : loadAreas()).then(function () {
        fillVenueChips(); renderVenues(); vNewId = ""; vLoaded = true;
        $("vChecked").textContent = "Last checked " + fmtClock.format(new Date());
      });
    });
  }

  // State and Region filters. They narrow the venues already loaded (no extra trip), and combine with the status filter.
  // The regions are the Discovery areas; a venue is in a region when its ZIP is on the region's list.
  function loadAreas() {
    return admin("list", { limit: 200 }, "discovery_areas").then(function (res) {
      vAreas = res.status === 200 && res.body && res.body.ok ? (res.body.data.records || []) : [];
    });
  }
  function vAddr(r) { return (r.place && r.place.address) || {}; }
  function vStateOf(r) { return String(vAddr(r).region || r.state_region || "").toUpperCase(); }
  function vZipOf(r) { return String(vAddr(r).postal_code || r.postal_code || "").slice(0, 5); }
  function vByName(a, b) { return String(a.name).toLowerCase() < String(b.name).toLowerCase() ? -1 : 1; }
  // ---- Filters (shared chip bar): Status, State (one), Region (search list, follows the State), Kind and a "Not ready" switch. Search by name or address.
  // Everything narrows the venues already loaded; sorted by name, 50 at a time. State and Region are the Discovery areas; a venue is in a region when its ZIP is on the region's list.
  var vCf = null, vShow = 50, VSTEP = 50, vLastState = "";
  function vChips() {
    if (vCf) return vCf;
    vCf = UI.chipFilters({
      mount: $("vChips"), label: "Venue filters",
      filters: [
        { id: "status", label: "Status", kind: "multi", options: [{ value: "active", label: "Active" }, { value: "inactive", label: "Inactive" }] },
        { id: "state", label: "State", kind: "one", options: [{ value: "", label: "All states" }] },
        { id: "region", label: "Region", kind: "search-multi", start: "none", options: [] },
        { id: "kind", label: "Kind", kind: "multi", options: [{ value: "public", label: "Public venue" }, { value: "private", label: "Private space" }] },
        { id: "notready", label: "Not ready to host", kind: "toggle", noun: "venues" }],
      onChange: function (sel) {
        var st = (sel.state || [""])[0] || "";
        if (st !== vLastState) { vLastState = st; vRegionOptions(); }
        vShow = VSTEP; $("vNotice").textContent = ""; renderVenues();
      }
    });
    return vCf;
  }
  function vRegionOptions() {
    var areas = vAreas || [], sc = ((vChips().getSelection().state || [""])[0]) || "";
    var regs = areas.filter(function (a) { return a.kind === "region" && a.is_active && (!sc || a.state_code === sc); }).sort(vByName);
    vChips().setOptions("region", regs.map(function (a) { return { value: a.id, label: a.name }; }));
    var keep = (vChips().getSelection().region || []).filter(function (id) { return regs.some(function (a) { return a.id === id; }); });
    vChips().setSelection({ region: keep });
  }
  function fillVenueChips() {
    var c = vChips(), areas = vAreas || [], states = areas.filter(function (a) { return a.kind === "state" && a.is_active; }).sort(vByName);
    c.setOptions("state", [{ value: "", label: "All states" }].concat(states.map(function (s) { return { value: s.state_code, label: s.name }; })));
    vRegionOptions();
    var cs = { active: 0, inactive: 0 }, kc = { public: 0, private: 0 };
    vRecs.forEach(function (r) { if (cs[r.status] !== undefined) cs[r.status]++; kc[r.is_public_venue ? "public" : "private"]++; });
    c.setCounts({ status: cs, kind: kc });
    c.setBadge("notready", vRecs.filter(function (r) { return vMissing(r).length; }).length);
  }
  function renderVenues() {
    var c = vChips(), sel = c.getSelection(), q = $("vSearch").value.trim().toLowerCase(), zips = null;
    var st = sel.status || [], sc = (sel.state || [""])[0] || "", rg = sel.region || [], kd = sel.kind || [], nr = (sel.notready || []).length;
    if (rg.length) { zips = {}; rg.forEach(function (id) { var ra = (vAreas || []).filter(function (a) { return a.id === id; })[0]; ((ra && ra.zip_codes) || []).forEach(function (z) { zips[z] = 1; }); }); }
    var shown = vRecs.filter(function (r) {
      if (st.length < 2 && st.indexOf(r.status) < 0) return false;
      if (kd.length === 1 && kd[0] !== (r.is_public_venue ? "public" : "private")) return false;
      if (sc && vStateOf(r) !== sc) return false;
      if (zips && !zips[vZipOf(r)]) return false;
      if (nr && !vMissing(r).length) return false;
      return !q || [r.name, vAddrLine(r)].join(" ").toLowerCase().indexOf(q) >= 0;
    }).sort(vByName);
    var vis = shown.slice(0, vShow), had = $("vList").children.length;
    skelOff($("vList")); var ul = $("vList"); ul.textContent = "";
    vis.forEach(function (r) { ul.appendChild(venueRow(r, r.id === vNewId)); });
    UI.moreBar($("vMore"), vis.length, shown.length, VSTEP, function () { vShow += VSTEP; renderVenues(); var f = $("vList").children[had]; if (f && f.querySelector("button.vdetails")) f.querySelector("button.vdetails").focus(); }, "venues");
    var word = function (n) { return n + (n === 1 ? " venue" : " venues"); };
    $("vCount").textContent = shown.length !== vRecs.length ? "Showing " + shown.length + " of " + word(vRecs.length) : word(vRecs.length);
    $("vEmpty").hidden = vRecs.length > 0;
    $("vNoMatch").hidden = !(vRecs.length > 0 && shown.length === 0);
  }

  // ---- Edit and delete a venue. The form is built from the published venue schema; the server does all the checking.
  var SCHEMA_URL = "/schemas/venue.schema.json";
  var PRIMARY = ["Basics", "Place", "Contact"];   // shown open; everything else sits under "More details"
  var LAYOUT = [
    ["Basics", ["name", "description", "status", "is_public_venue"]],
    ["Place", []],
    ["Contact", ["email", "phone"]],
    ["Map and access", ["parking_description", "parking_latitude", "parking_longitude",
                        "entry_description", "entry_latitude", "entry_longitude", "transit_description"]],
    ["Booking", ["website_url", "booking_process", "booking_lead_days", "availability_notes", "setup_minutes_before", "teardown_minutes_after"]],
    ["Facilities and rules", ["has_wifi", "wifi_notes", "is_accessible", "has_step_free_entry", "has_elevator", "has_accessible_restroom",
                              "accessibility_notes", "allows_minors", "allows_animals", "allows_food", "allows_alcohol", "requires_insurance", "insurance_notes"]],
    ["Cost", ["cost_cents", "cost_basis", "deposit_cents", "cancellation_terms", "cost_notes"]],
    ["Notes", ["notes"]]
  ];
  var schemaP = null, editSchema = null, editRec = null, editFields = {}, editActive = {}, editAny = [];
  var CF = window.ConsoleForms, LABELS = CF.labels, humanize = CF.humanize, readValue = CF.readValue, openSec = CF.openSec;
  function buildField(name, def, rec, ctx) { return CF.buildField(name, def, rec, ctx || { prefix: "", schema: editSchema, fields: editFields }); }

  function getSchema() {
    if (!schemaP) {
      schemaP = fetch(SCHEMA_URL, { cache: "no-cache" })
        .then(function (r) { if (!r.ok) throw new Error("x"); return r.json(); })
        .catch(function () { schemaP = null; return null; });
    }
    return schemaP;
  }

  var GPS_SAID = {
    found: "GPS found and saved (looked up from the address).",
    no_match: "the lookup did not find that address. Enter a point by hand in Places if you need one.",
    skipped_entered: "this place already has a point someone entered, so it was left alone.",
    skipped_not_public: "private spaces are not looked up.",
    skipped_no_address: "this place has no street address to look up.",
    skipped_off: "the lookup is not turned on."
  };
  function venueActions(rec) {
    var wrap = document.createElement("div");
    var row = document.createElement("div"); row.className = "actions-row";
    var ed = document.createElement("button"); ed.type = "button"; ed.className = "btn-primary"; ed.textContent = "Edit";
    var del = document.createElement("button"); del.type = "button"; del.className = "btn-danger pdel"; del.textContent = "Delete";
    row.appendChild(ed);
    var hv = historyBtn(rec.id, rec.name); if (hv) { hv.className = "btn-link"; row.appendChild(hv); }
    if (rec.is_public_venue && rec.place) {
      var gb = document.createElement("button"); gb.type = "button"; gb.className = "btn-secondary"; gb.textContent = "Find GPS";
      gb.addEventListener("click", function () {
        gb.disabled = true; $("vNotice").textContent = "Looking up GPS for " + (rec.name || "the venue") + "…";
        admin("find_gps", { id: rec.id }).then(function (res) {
          gb.disabled = false;
          if (res.status === 401) { lock("That key did not work."); return; }
          if (res.status === 200 && res.body && res.body.ok) { $("vNotice").textContent = (rec.name || "Venue") + ": " + GPS_SAID[res.body.data.gps]; loadVenues(); }
          else $("vNotice").textContent = adminProblem(res.status);
        });
      });
      row.appendChild(gb);
    }
    row.appendChild(del);

    var box = document.createElement("div"); box.className = "confirm"; box.hidden = true;
    var q = document.createElement("div");
    q.textContent = "Delete this venue? It is hidden from the lists but kept in the database. If a class uses this venue, make it inactive instead.";
    var btns = document.createElement("div"); btns.className = "btns";
    var yes = document.createElement("button"); yes.type = "button"; yes.className = "btn-danger"; yes.textContent = "Delete venue";
    var no = document.createElement("button"); no.type = "button"; no.className = "btn-secondary"; no.textContent = "Cancel";
    var err = document.createElement("div"); err.className = "msg"; err.setAttribute("role", "alert");
    btns.appendChild(yes); btns.appendChild(no); box.appendChild(q); box.appendChild(btns); box.appendChild(err);

    ed.addEventListener("click", function () { openEdit(rec); });
    del.addEventListener("click", function () { box.hidden = !box.hidden; err.textContent = ""; });
    no.addEventListener("click", function () { box.hidden = true; });
    yes.addEventListener("click", function () {
      yes.disabled = true; err.textContent = "";
      admin("soft_delete", { id: rec.id }).then(function (res) {
        yes.disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          $("vNotice").textContent = "Deleted " + (rec.name || "venue") + ".";
          loadVenues();
        } else if (res.status === 404) {
          $("vNotice").textContent = "That venue was already gone.";
          loadVenues();
        } else if (res.status === 409 && res.body && res.body.error && (res.body.error.problems || []).some(function (p) { return p.issue === "in_use"; })) {
          err.textContent = "Classes use this venue, so it cannot be deleted. Set it inactive instead, or move or delete those classes first.";
          admin("list", { filters: { venue_id: rec.id }, limit: 50 }, "scheduled_classes").then(function (r2) {
            var names = (r2.status === 200 && r2.body.ok ? r2.body.data.records : []).map(function (c) { return c.title; });
            if (names.length) err.textContent += " Classes: " + names.join(", ") + ".";
          });
        } else {
          err.textContent = adminProblem(res.status);
        }
      });
    });
    wrap.appendChild(row); wrap.appendChild(box);
    return wrap;
  }

  function activationInfo(schema) {
    editActive = {}; editAny = [];
    (schema.allOf || []).forEach(function (b) {
      var c = b["if"] && b["if"].properties && b["if"].properties.status;
      if (c && c["const"] === "active" && b.then) {
        (b.then.required || []).forEach(function (f) { editActive[f] = 1; });
        (b.then.anyOf || []).forEach(function (br) { (br.required || []).forEach(function (f) { if (editAny.indexOf(f) < 0) editAny.push(f); }); });
      }
    });
  }



  // "What's needed to make this active?": a venue needs only a place (an address or a GPS point).
  function renderReady() {
    var box = $("readyBox"); if (!box) return;
    box.textContent = "";
    var p = editRec && editRec.place, ok = !!(p && (p.address || p.has_gps));
    var sum = document.createElement("div"); sum.className = "sum";
    sum.textContent = ok ? "Everything needed is filled in." : "Still needed: 1";
    box.appendChild(sum);
    var d = document.createElement("div"); d.className = ok ? "ok" : "todo";
    d.textContent = (ok ? "✓ " : "○ ") + "A place with an address or a GPS point";
    box.appendChild(d);
  }
  function addReady(body) {
    var btn = document.createElement("button"); btn.type = "button"; btn.className = "linkbtn"; btn.textContent = "What’s needed to make this active?";
    var box = document.createElement("div"); box.id = "readyBox"; box.className = "ready"; box.hidden = true;
    btn.addEventListener("click", function () { box.hidden = !box.hidden; if (!box.hidden) renderReady(); });
    body.appendChild(btn); body.appendChild(box);
  }

  // Rooms and hours: lists inside the venue record. Edited as rows; the whole list is sent when anything in it changed.
  var editLists = {};
  var DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
  var listUid = 0;

  function canon(v) {
    if (v === null || v === undefined) return "null";
    if (Array.isArray(v)) return "[" + v.map(canon).join(",") + "]";
    if (typeof v === "object") return "{" + Object.keys(v).sort().map(function (k) { return JSON.stringify(k) + ":" + canon(v[k]); }).join(",") + "}";
    return JSON.stringify(v);
  }

  function dayIndex(e) { return DAYS.indexOf(e.day_of_week); }
  function sortDays(a) {
    return a.map(function (e, i) { return [e, i]; }).sort(function (x, y) { return (dayIndex(x[0]) - dayIndex(y[0])) || (x[1] - y[1]); }).map(function (x) { return x[0]; });
  }
  var LIST_ISSUES = {
    rooms: { required: "Add at least one room.", duplicate: "Two rooms have the same name.", in_use: "A class uses this room. Change that class first." },
    availability_hours: { out_of_range: "Each open day must open before it closes." }
  };
  function listIssueText(field, issue) {
    return (LIST_ISSUES[field] && LIST_ISSUES[field][issue]) || ("Check the " + (field === "rooms" ? "rooms" : "hours") + ".");
  }

  function lfield(parent, key, text, node) {
    var w = mk("div"); var id = "lf" + (++listUid) + "_" + key;
    var l = mk("label", "f", text); l.htmlFor = id; node.id = id;
    w.appendChild(l); w.appendChild(node); parent.appendChild(w); return w;
  }
  function lopt(sel, value, text) { var o = mk("option", "", text); o.value = value; sel.appendChild(o); }

  // The fields of one room, appended to box. Returns the inputs.
  function buildRoomFields(box, r) {
    var f = {};
    f.label = mk("input"); f.label.type = "text"; f.label.maxLength = 100; f.label.autocomplete = "off"; f.label.value = r.label || "";
    lfield(box, "label", "Room name (like Main room)", f.label);
    var two = mk("div", "two"); box.appendChild(two);
    f.max = mk("input"); f.max.type = "number"; f.max.inputMode = "numeric"; f.max.step = 1; f.max.value = r.max_occupancy == null ? "" : r.max_occupancy;
    lfield(two, "max", "Most people (optional)", f.max);
    f.pref = mk("input"); f.pref.type = "number"; f.pref.inputMode = "numeric"; f.pref.step = 1; f.pref.value = r.preferred_occupancy == null ? "" : r.preferred_occupancy;
    lfield(two, "pref", "Comfortable number (optional)", f.pref);
    f.acc = mk("select"); lopt(f.acc, "", "Not answered"); lopt(f.acc, "true", "Yes"); lopt(f.acc, "false", "No");
    f.acc.value = r.is_accessible == null ? "" : String(r.is_accessible);
    lfield(box, "acc", "Accessible room", f.acc);
    f.seat = mk("input"); f.seat.type = "text"; f.seat.maxLength = 200; f.seat.autocomplete = "off"; f.seat.value = r.seating_layout || "";
    lfield(box, "seat", "Seating (tables, rows, a circle)", f.seat);
    f.equip = mk("input"); f.equip.type = "text"; f.equip.autocomplete = "off"; f.equip.placeholder = "Screen, projector, whiteboard"; f.equip.value = (r.equipment || []).join(", ");
    lfield(box, "equip", "Equipment (separate with commas)", f.equip);
    f.notes = mk("textarea"); f.notes.maxLength = 500; f.notes.value = r.notes || "";
    lfield(box, "notes", "Notes about this room", f.notes);
    return f;
  }
  function readRoomFields(f) {
    var o = {}, blank = true, bad = false, miss = false;
    var lab = f.label.value.trim(), mx = wholeNum(f.max.value), pf = wholeNum(f.pref.value);
    var seat = f.seat.value.trim(), notes = f.notes.value.trim();
    var eq = f.equip.value.split(",").map(function (x) { return x.trim(); }).filter(function (x) { return x; });
    if (lab || f.max.value.trim() || f.pref.value.trim() || seat || notes || eq.length || f.acc.value) blank = false;
    if (blank) return { blank: true };
    if (lab) o.label = lab; else miss = true;
    if (mx !== null) { if (isNaN(mx)) bad = true; else o.max_occupancy = mx; }
    if (pf !== null) { if (isNaN(pf)) bad = true; else o.preferred_occupancy = pf; }
    if (f.acc.value) o.is_accessible = f.acc.value === "true";
    if (seat) o.seating_layout = seat;
    if (eq.length) o.equipment = eq;
    if (notes) o.notes = notes;
    return { value: o, bad: bad, miss: miss };
  }
  // Seven day rows (tick = open). Returns count, clearErr and read.
  function buildHoursRows(parent, entries) {
    var hours = {}, extras = [], byDay = {};
    (entries || []).forEach(function (e) { if (byDay[e.day_of_week]) extras.push(e); else byDay[e.day_of_week] = e; });
    DAYS.forEach(function (d) {
      var e = byDay[d];
      var row = mk("div", "drow");
      var lab = mk("label", "day"); var cb = mk("input"); cb.type = "checkbox"; cb.checked = !!e;
      lab.appendChild(cb); lab.appendChild(document.createTextNode(d)); row.appendChild(lab);
      var times = mk("div", "times"); times.hidden = !e; row.appendChild(times);
      var o = mk("input"); o.type = "time"; var c = mk("input"); c.type = "time";
      o.value = e ? e.opens_at : ""; c.value = e ? e.closes_at : "";
      var ow = mk("div"); ow.appendChild(mk("span", "", "Opens"));
      var cw = mk("div"); cw.appendChild(mk("span", "", "Closes"));
      o.id = "lf" + (++listUid) + "_o"; c.id = "lf" + (++listUid) + "_c"; o.setAttribute("aria-label", d + " opens"); c.setAttribute("aria-label", d + " closes");
      ow.appendChild(o); cw.appendChild(c); times.appendChild(ow); times.appendChild(cw);
      var re = mk("div", "rowerr"); re.setAttribute("role", "alert"); row.appendChild(re);
      cb.addEventListener("change", function () {
        times.hidden = !cb.checked;
        if (cb.checked) { if (!o.value) o.value = "09:00"; if (!c.value) c.value = "17:00"; }
      });
      hours[d] = { cb: cb, o: o, c: c, err: re };
      parent.appendChild(row);
    });
    return {
      count: function () { return DAYS.filter(function (d) { return hours[d].cb.checked; }).length; },
      clearErr: function () { DAYS.forEach(function (d) { hours[d].err.textContent = ""; }); },
      read: function () {
        var vals = [], bad = false;
        DAYS.forEach(function (d) {
          var h = hours[d]; h.err.textContent = "";
          if (!h.cb.checked) return;
          if (!h.o.value || !h.c.value) { bad = true; h.err.textContent = "Give both an opening and a closing time."; return; }
          vals.push({ day_of_week: d, opens_at: h.o.value, closes_at: h.c.value });
        });
        vals = sortDays(vals.concat(extras));
        return { value: vals.length ? vals : null, bad: bad };
      }
    };
  }

  function buildListEditors(sec, rec) {
    var body = sec.body;
    body.appendChild(mk("div", "note", "Changes are saved when you press Save, along with the rest of the form."));
    function updateSummary() {
      var nr = editLists.rooms ? editLists.rooms.count() : 0, nh = editLists.availability_hours ? editLists.availability_hours.count() : 0;
      sec.sm.textContent = "Rooms and hours (" + nr + (nr === 1 ? " room, " : " rooms, ") + nh + (nh === 1 ? " day open)" : " days open)");
    }

    body.appendChild(mk("div", "lsub", "Rooms"));
    var rlist = mk("div", "rlist");
    var rerr = mk("div", "ferr"); rerr.id = "ee_rooms"; rerr.setAttribute("role", "alert");
    var rooms = [];
    function renumber() { rooms.forEach(function (r, i) { r.title.textContent = "Room " + (i + 1); }); }
    function addRoom(r) {
      r = r || {};
      var box = mk("div", "rcard"), head = mk("div", "rhead"), title = mk("strong", "", "Room");
      var rm = mk("button", "btn-secondary", "Remove"); rm.type = "button";
    var who = attName(r) + (r["class"] && r["class"].title ? ", " + r["class"].title : "");
    rm.setAttribute("aria-label", "Remove (" + who + ")");
      head.appendChild(title); head.appendChild(rm); box.appendChild(head);
      var f = buildRoomFields(box, r);
      var re = mk("div", "rowerr"); re.setAttribute("role", "alert"); box.appendChild(re);
      var row = { box: box, title: title, f: f, err: re };
      rooms.push(row); rlist.appendChild(box); renumber();
      rm.addEventListener("click", function () {
        rooms.splice(rooms.indexOf(row), 1); rlist.removeChild(box); renumber(); updateSummary();
        document.getElementById("editSections").dispatchEvent(new Event("change", { bubbles: true }));
      });
      return row;
    }
    var addRoomBtn = mk("button", "quiet", "Add a room"); addRoomBtn.type = "button";
    addRoomBtn.addEventListener("click", function () { var r = addRoom(); updateSummary(); r.f.label.focus(); });
    (rec.rooms || []).forEach(function (r) { addRoom(r); });
    body.appendChild(rlist); body.appendChild(rerr); body.appendChild(addRoomBtn);

    body.appendChild(mk("div", "lsub", "Open hours"));
    body.appendChild(mk("div", "note", "Tick the days the venue can be used. A day that is not ticked is closed."));
    var hr = buildHoursRows(body, rec.availability_hours);
    var herr = mk("div", "ferr"); herr.id = "ee_availability_hours"; herr.setAttribute("role", "alert"); body.appendChild(herr);

    editLists.rooms = {
      sec: sec.d, summary: sec.sm, el: rerr, msg: "Fix the marked rooms.",
      count: function () { return rooms.filter(function (r) { return !readRoomFields(r.f).blank; }).length; },
      clearRowErrs: function () { rooms.forEach(function (r) { r.err.textContent = ""; }); },
      read: function () {
        var vals = [], bad = false;
        rooms.forEach(function (r) {
          var v = readRoomFields(r.f); r.err.textContent = "";
          if (v.blank) return;
          if (v.bad) { bad = true; r.err.textContent = "Use whole numbers."; }
          else if (v.miss) { bad = true; r.err.textContent = "Give the room a name."; }
          else vals.push(v.value);
        });
        return { value: vals.length ? vals : null, bad: bad, orig: rec.rooms && rec.rooms.length ? rec.rooms : null };
      }
    };
    editLists.availability_hours = {
      sec: sec.d, summary: sec.sm, el: herr, msg: "Fix the marked days.",
      count: hr.count, clearRowErrs: hr.clearErr,
      read: function () {
        var x = hr.read();
        return { value: x.value, bad: x.bad, orig: rec.availability_hours && rec.availability_hours.length ? sortDays(rec.availability_hours) : null };
      }
    };
    sec.d.addEventListener("input", updateSummary);
    sec.d.addEventListener("change", updateSummary);
    updateSummary();
  }

  // ---- Popup on the venue card: view, edit, add and remove rooms; view and edit the open hours.
  var D = { dlg: null, rec: null, kind: "", editing: null, busy: false, body: null, msg: null, title: null };
  function clockLabel(t) {
    var m = /^(\d\d):(\d\d)$/.exec(t || ""); if (!m) return t || "";
    var h = Number(m[1]), ap = h >= 12 ? "PM" : "AM"; h = h % 12; if (h === 0) h = 12;
    return h + ":" + m[2] + " " + ap;
  }
  function cap(t) { return t.charAt(0).toUpperCase() + t.slice(1); }
  function ensureDlg() {
    if (D.dlg) return;
    var d = mk("dialog", "lsdlg"); d.setAttribute("aria-labelledby", "lsTitle");
    var head = mk("div", "lshead"); D.title = mk("h2"); D.title.id = "lsTitle";
    var close = mk("button", "quiet", "Close"); close.type = "button";
    head.appendChild(D.title); head.appendChild(close);
    D.msg = mk("div", "dmsg"); D.msg.setAttribute("role", "status");
    D.body = mk("div", "lsbody");
    d.appendChild(head); d.appendChild(D.msg); d.appendChild(D.body);
    document.body.appendChild(d); D.dlg = d;
    close.addEventListener("click", function () { d.close(); });
    d.addEventListener("close", function () { D.rec = null; D.editing = null; loadVenues(); });
  }
  function dmsg(t, ok) { D.msg.textContent = t || ""; D.msg.className = "dmsg" + (ok ? " ok" : ""); }
  function openListDlg(rec, kind) {
    ensureDlg();
    D.rec = rec; D.kind = kind; D.editing = null; D.busy = false;
    D.title.textContent = (kind === "rooms" ? "Rooms: " : "Open hours: ") + (rec.name || "venue");
    dmsg(""); renderDlg();
    if (!D.dlg.open) D.dlg.showModal();
    D.body.scrollTop = 0;
  }
  function renderDlg() { if (D.kind === "rooms") renderRooms(); else renderHours(); }

  // Sends one list field. onOk runs after a saved change.
  function saveList(field, value, onOk) {
    if (D.busy) return;
    D.busy = true; dmsg("");
    var changes = {}; changes[field] = value;
    admin("update", { id: D.rec.id, changes: changes, expected_updated_at: D.rec.updated_at }).then(function (res) {
      D.busy = false;
      if (res.status === 401) { D.dlg.close(); lock("That key did not work."); return; }
      if (res.status === 200 && res.body && res.body.ok) {
        if (value === null) delete D.rec[field]; else D.rec[field] = value;
        var u = res.body.data && res.body.data.updated_at; if (u) D.rec.updated_at = u;
        dmsg("Saved.", true); onOk(); return;
      }
      var err = res.body && res.body.error;
      if (res.status === 409) { dmsg("This venue changed since you opened this. Nothing was saved. Close this window and open it again."); return; }
      if (res.status === 404) { dmsg("This venue no longer exists. Close this window."); return; }
      if (res.status === 400 && err && err.problems && err.problems.length) {
        var mine = err.problems.filter(function (p) { return p.field === field; })[0];
        dmsg("Not saved. " + (mine ? listIssueText(field, mine.issue) : "Check the values and try again."));
        return;
      }
      dmsg(adminProblem(res.status));
    });
  }

  function roomLines(r) {
    var out = [];
    var nums = [];
    if (r.max_occupancy != null) nums.push("Up to " + r.max_occupancy + " people");
    if (r.preferred_occupancy != null) nums.push("comfortable " + r.preferred_occupancy);
    if (nums.length) out.push(nums.join(", "));
    if (r.is_accessible != null) out.push(r.is_accessible ? "Accessible" : "Not accessible");
    if (r.seating_layout) out.push("Seating: " + r.seating_layout);
    if (r.equipment && r.equipment.length) out.push("Equipment: " + r.equipment.join(", "));
    if (r.notes) out.push("Notes: " + r.notes);
    return out;
  }
  function renderRooms() {
    var body = D.body; body.textContent = "";
    var list = D.rec.rooms || [];
    body.appendChild(mk("div", "note", "Saving a room here saves it right away. It does not wait for the venue form."));
    if (!list.length && D.editing !== "new") body.appendChild(mk("div", "empty", "No rooms yet."));
    list.forEach(function (r, i) {
      if (D.editing === i) { body.appendChild(roomForm(i, r)); return; }
      var e = mk("div", "rentry"); e.appendChild(mk("strong", "", r.label));
      roomLines(r).forEach(function (t) { e.appendChild(mk("div", "rl", t)); });
      var row = mk("div", "actions-row");
      var ed = mk("button", "", "Edit"); ed.type = "button";
      var rm = mk("button", "danger", "Remove"); rm.type = "button";
      row.appendChild(ed); row.appendChild(rm); e.appendChild(row);
      var box = mk("div", "confirm"); box.hidden = true;
      box.appendChild(mk("div", "", "Remove " + r.label + " from this venue?"));
      var bt = mk("div", "btns"); var yes = mk("button", "danger", "Remove room"); yes.type = "button";
      var no = mk("button", "quiet", "Cancel"); no.type = "button"; bt.appendChild(yes); bt.appendChild(no); box.appendChild(bt); e.appendChild(box);
      ed.addEventListener("click", function () { D.editing = i; dmsg(""); renderRooms(); });
      rm.addEventListener("click", function () { box.hidden = !box.hidden; });
      no.addEventListener("click", function () { box.hidden = true; });
      yes.addEventListener("click", function () {
        var next = list.filter(function (x, j) { return j !== i; });
        saveList("rooms", next.length ? next : null, function () { renderRooms(); });
      });
      body.appendChild(e);
    });
    if (D.editing === "new") body.appendChild(roomForm("new", {}));
    else if (D.editing === null) {
      var add = mk("button", "quiet", "Add a room"); add.type = "button";
      add.addEventListener("click", function () { D.editing = "new"; dmsg(""); renderRooms(); var l = D.body.querySelector("input"); if (l) l.focus(); });
      body.appendChild(add);
    }
  }
  function roomForm(idx, r) {
    var box = mk("div", "rcard"); box.appendChild(mk("strong", "", idx === "new" ? "New room" : "Edit room"));
    var f = buildRoomFields(box, r);
    var re = mk("div", "rowerr"); re.setAttribute("role", "alert"); box.appendChild(re);
    var bt = mk("div", "btns"); var save = mk("button", "", "Save room"); save.type = "button";
    var cancel = mk("button", "quiet", "Cancel"); cancel.type = "button"; bt.appendChild(save); bt.appendChild(cancel); box.appendChild(bt);
    cancel.addEventListener("click", function () { D.editing = null; dmsg(""); renderRooms(); });
    save.addEventListener("click", function () {
      var v = readRoomFields(f); re.textContent = "";
      if (v.blank || v.miss) { re.textContent = "Give the room a name."; return; }
      if (v.bad) { re.textContent = "Use whole numbers."; return; }
      var next = (D.rec.rooms || []).slice();
      if (idx === "new") next.push(v.value); else next[idx] = v.value;
      if (idx !== "new" && canon(next[idx]) === canon((D.rec.rooms || [])[idx])) { dmsg("Nothing changed."); return; }
      saveList("rooms", next, function () { D.editing = null; renderRooms(); });
    });
    return box;
  }

  function renderHours() {
    var body = D.body; body.textContent = "";
    var list = D.rec.availability_hours || [];
    body.appendChild(mk("div", "note", "Saving here saves right away. It does not wait for the venue form."));
    if (D.editing === "hours") {
      var wrap = mk("div", "rcard"); wrap.appendChild(mk("div", "note", "Tick the days the venue can be used. A day that is not ticked is closed."));
      var hr = buildHoursRows(wrap, list);
      var bt = mk("div", "btns"); var save = mk("button", "", "Save hours"); save.type = "button";
      var cancel = mk("button", "quiet", "Cancel"); cancel.type = "button"; bt.appendChild(save); bt.appendChild(cancel); wrap.appendChild(bt);
      cancel.addEventListener("click", function () { D.editing = null; dmsg(""); renderHours(); });
      save.addEventListener("click", function () {
        var x = hr.read();
        if (x.bad) { dmsg("Fix the marked days."); return; }
        var orig = list.length ? sortDays(list) : null;
        if (canon(x.value) === canon(orig)) { dmsg("Nothing changed."); return; }
        saveList("availability_hours", x.value, function () { D.editing = null; renderHours(); });
      });
      body.appendChild(wrap); return;
    }
    if (!list.length) body.appendChild(mk("div", "empty", "No hours set. Every day counts as closed."));
    else {
      var box = mk("div", "rentry");
      sortDays(list).forEach(function (e) { box.appendChild(mk("div", "rl", cap(e.day_of_week) + ": " + clockLabel(e.opens_at) + " to " + clockLabel(e.closes_at))); });
      body.appendChild(box);
    }
    var ed = mk("button", "quiet", list.length ? "Edit hours" : "Set hours"); ed.type = "button";
    ed.addEventListener("click", function () { D.editing = "hours"; dmsg(""); renderHours(); });
    body.appendChild(ed);
  }

  function buildSections(rec) {
    var host = $("editSections"); host.textContent = "";
    editFields = {}; editLists = {};
    var props = editSchema.properties, used = {};
    function section(title, open, parent) {
      var d = document.createElement("details"); d.className = "sec"; if (open) d.open = true;
      var sm = document.createElement("summary"); sm.textContent = title; d.appendChild(sm);
      var body = document.createElement("div"); body.className = "body"; d.appendChild(body);
      (parent || host).appendChild(d);
      return { d: d, sm: sm, body: body };
    }
    function eligible(n) { var df = props[n]; return df && !df.readOnly && df.type !== "array" && n !== "slug" && n !== "contact_individual_id" && n !== "backup_contact_individual_id"; }
    function fill(sec, names) {
      names.forEach(function (n) {
        used[n] = 1;
        sec.body.appendChild(buildField(n, props[n], rec));
        editFields[n].sec = sec.d; editFields[n].summary = sec.sm;
      });
    }
    function names(title) { return LAYOUT.filter(function (l) { return l[0] === title; })[0][1].filter(eligible); }

    PRIMARY.forEach(function (t) {
      var s2 = section(t, true);
      fill(s2, names(t));
      if (t === "Basics") addReady(s2.body);
      if (t === "Place") s2.body.appendChild(placePanel(rec));
      if (t === "Contact") {
        s2.body.appendChild(contactPicker("contact_individual_id", "Main contact", rec.main_contact, s2.d, s2.sm));
        s2.body.appendChild(contactPicker("backup_contact_individual_id", "Backup contact", rec.backup_contact, s2.d, s2.sm));
      }
    });
    var sr = section("Rooms and hours", false);
    buildListEditors(sr, rec);

    var more = document.createElement("details"); more.className = "more";
    var msm = document.createElement("summary"); msm.textContent = "More details (map, booking, facilities, cost, notes)"; more.appendChild(msm);
    var mbody = document.createElement("div"); mbody.className = "mbody"; more.appendChild(mbody);
    host.appendChild(more);
    LAYOUT.forEach(function (l) {
      if (PRIMARY.indexOf(l[0]) >= 0) return;
      var nm = names(l[0]);
      if (nm.length) fill(section(l[0], false, mbody), nm);
    });
    var rest = Object.keys(props).filter(function (n) { return !used[n] && eligible(n); });
    if (rest.length) fill(section("Other", false, mbody), rest);
  }

  function collectChanges() {
    var changes = {}, bad = [];
    Object.keys(editFields).forEach(function (n) {
      var v = readValue(editFields[n]);
      if (v === undefined) { bad.push(n); return; }
      var orig = editRec[n] === undefined ? null : editRec[n];
      if (v !== orig) changes[n] = v;
    });
    Object.keys(editLists).forEach(function (n) {
      if (n === "availability_hours" || n === "rooms") {
        var r = editLists[n].read();
        if (r.bad) { bad.push(n); return; }
        if (canon(r.value) !== canon(r.orig)) changes[n] = r.value;
      }
    });
    return { changes: changes, bad: bad };
  }
  function editDirty() {
    if (!editRec) return false;
    var c = collectChanges();
    return c.bad.length > 0 || Object.keys(c.changes).length > 0;
  }
  function clearEditErrs() {
    $("editMsg").textContent = ""; $("editReload").hidden = true;
    Object.keys(editFields).forEach(function (n) {
      $("ee_" + n).textContent = "";
      if (editFields[n].summary) editFields[n].summary.className = "";
    });
    Object.keys(editLists).forEach(function (n) {
      $("ee_" + n).textContent = ""; editLists[n].summary.className = ""; editLists[n].clearRowErrs();
    });
    document.querySelectorAll("details.more > summary").forEach(function (sm) { sm.className = ""; });
  }
  function closeEdit() {
    editRec = null; editFields = {}; editLists = {};
    $("editPanel").hidden = true; $("vMain").hidden = false;
  }
  function openEdit(rec) {
    $("vMsg").textContent = "";
    getSchema().then(function (schema) {
      if (!schema) { $("vMsg").textContent = "Could not load the venue form. Try again."; return; }
      editSchema = schema; editRec = rec; activationInfo(schema);
      $("editTitle").textContent = "Edit " + (rec.name || "venue");
      $("editSub").textContent = "Slug: " + rec.slug + " (cannot be changed)";
      buildSections(rec);
      clearEditErrs();
      $("editPanel").classList.remove("showhelp"); $("helpBtn").textContent = "Show field help";
      $("vMain").hidden = true; $("editPanel").hidden = false;
      window.scrollTo(0, 0);
    });
  }

  function issueText(p, f) {
    var def = f.def;
    if (p.issue === "choose_one") return "Give at least one of the contact options.";
    if (p.issue === "required") return "Required.";
    if (p.issue === "invalid_format") {
      if (def.format === "email") return "That email address does not look right.";
      if (def.format === "uri") return "Start with https://";
      if (p.field === "country") return "Two capital letters, like US.";
      return "That value is not valid.";
    }
    if (p.issue === "out_of_range") return "That number is outside the allowed range.";
    return ISSUE[p.issue] || "That value is not valid.";
  }

  $("editForm").addEventListener("submit", function (e) {
    e.preventDefault();
    if (!editRec) return;
    clearEditErrs();
    var c = collectChanges();
    if (c.bad.length) {
      c.bad.forEach(function (n) {
        var L = editLists[n];
        $("ee_" + n).textContent = L ? L.msg : "Enter a number.";
        if (L) L.summary.className = "haserr";
        openSec(L || editFields[n]);
      });
      $("editMsg").textContent = "Not saved. Fix the marked fields.";
      return;
    }
    if (!Object.keys(c.changes).length) { $("editMsg").textContent = "Nothing changed."; return; }
    $("editSave").disabled = true;
    admin("update", { id: editRec.id, changes: c.changes, expected_updated_at: editRec.updated_at }).then(function (res) {
      $("editSave").disabled = false;
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status === 200 && res.body && res.body.ok) {
        vNewId = editRec.id;
        $("vNotice").textContent = "Saved " + (c.changes.name || editRec.name) + "." + ("name" in c.changes ? " People in upcoming classes here are emailed the new name. Messages shows the result." : "");
        closeEdit(); loadVenues();
        return;
      }
      var err = res.body && res.body.error;
      if (res.status === 409) {
        $("editMsg").textContent = "This venue changed since you opened it. Nothing was saved.";
        $("editReload").hidden = false;
        return;
      }
      if (res.status === 404) {
        $("editMsg").textContent = "This venue no longer exists.";
        $("editReload").hidden = false;
        return;
      }
      if (res.status === 400 && err && err.problems && err.problems.length) {
        var other = [], first = null, n = 0;
        err.problems.forEach(function (p) {
          var f = editFields[p.field] || editLists[p.field];
          if (f) {
            $("ee_" + p.field).textContent = editLists[p.field] ? listIssueText(p.field, p.issue) : issueText(p, f);
            openSec(f); f.summary.className = "haserr"; n++;
            if (!first) first = f.el;
          } else {
            other.push(humanize(p.field) + (p.issue === "required" ? " (required)" : ""));
          }
        });
        $("editMsg").textContent = "Not saved. " + (n ? n + " field" + (n === 1 ? "" : "s") + " need attention, marked below." : "")
          + (other.length ? " Also needed: " + other.join(", ") + "." : "");
        if (first) first.scrollIntoView({ block: "center" });
        return;
      }
      $("editMsg").textContent = adminProblem(res.status);
    });
  });
  function liveReady() { var b = $("readyBox"); if (b && !b.hidden) renderReady(); }
  $("editSections").addEventListener("input", liveReady);
  $("editSections").addEventListener("change", liveReady);
  $("helpBtn").addEventListener("click", function () {
    var on = $("editPanel").classList.toggle("showhelp");
    $("helpBtn").textContent = on ? "Hide field help" : "Show field help";
  });
  $("editCancel").addEventListener("click", function () {
    askDiscard(editDirty(), closeEdit);
  });
  $("editReload").addEventListener("click", function () { closeEdit(); loadVenues(); });


  function resetVenues() {
    vLoaded = false; vBusy = false; vNewId = ""; vRecs = []; vAreas = null; if (vCf) { vLastState = ""; vCf.clearAll(); }
    $("vList").textContent = ""; $("vCount").textContent = ""; $("vChecked").textContent = "";
    $("vMsg").textContent = ""; $("vNotice").textContent = ""; $("vEmpty").hidden = true;
    $("vSearch").value = ""; vShow = VSTEP; $("vMore").textContent = ""; $("vNoMatch").hidden = true; $("vRetry").hidden = true; $("vCount").textContent = ""; closeForm(); closeEdit();
  }

  function clearErrs() { ["eName", "eSlug", "ePublic", "fMsg"].forEach(function (id) { $(id).textContent = ""; }); }
  function openForm() {
    $("addForm").reset(); slugTouched = false; clearErrs(); $("vNotice").textContent = "";
    addPlace = placeInput(true); $("fPlaceHost").textContent = ""; $("fPlaceHost").appendChild(addPlace);
    $("addForm").hidden = false; $("addBtn").hidden = true; $("fName").focus();
  }
  function closeForm() { $("addForm").hidden = true; $("addBtn").hidden = false; }

  $("fName").addEventListener("input", function () { if (!slugTouched) $("fSlug").value = slugify($("fName").value); });
  $("fSlug").addEventListener("input", function () { slugTouched = true; });
  $("addBtn").addEventListener("click", openForm);
  $("cancelBtn").addEventListener("click", closeForm);
  $("vRefresh").addEventListener("click", function () { $("vNotice").textContent = ""; vAreas = null; loadVenues(); });
  $("vSearch").addEventListener("input", function () { vShow = VSTEP; renderVenues(); });
  $("vRetry").addEventListener("click", loadVenues);
  $("vClear").addEventListener("click", function () { $("vSearch").value = ""; vShow = VSTEP; vLastState = ""; vChips().clearAll(); $("vSearch").focus(); });
  $("vGps").addEventListener("click", function () {   // look up GPS for every public venue that has an address but no point
    var b = $("vGps"); b.disabled = true; $("vNotice").textContent = "Looking for venues without GPS…";
    admin("list", { limit: 200, expand: true }).then(function (res) {
      if (res.status === 401) { b.disabled = false; lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body.ok) { b.disabled = false; $("vNotice").textContent = adminProblem(res.status); return; }
      var todo = (res.body.data.records || []).filter(function (v) { return v.is_public_venue && v.place && !v.place.has_gps; });
      if (!todo.length) { b.disabled = false; $("vNotice").textContent = "Every public venue already has GPS."; return; }
      var tally = {}, i = 0;
      (function next() {
        if (i >= todo.length) {
          b.disabled = false;
          $("vNotice").textContent = "Checked " + todo.length + (todo.length === 1 ? " venue" : " venues") + ": " + (tally.found || 0) + " found, " + (tally.no_match || 0) + " not found by the lookup, " + ((todo.length - (tally.found || 0) - (tally.no_match || 0))) + " skipped.";
          loadVenues(); return;
        }
        $("vNotice").textContent = "Looking up " + (i + 1) + " of " + todo.length + "…";
        admin("find_gps", { id: todo[i++].id }).then(function (r) { var k = (r.status === 200 && r.body.ok) ? r.body.data.gps : "skipped_off"; tally[k] = (tally[k] || 0) + 1; next(); });
      })();
    });
  });

  $("addForm").addEventListener("submit", function (e) {
    e.preventDefault(); clearErrs();
    var kind = $("fPublic").value;
    if (!kind) { $("ePublic").textContent = "Choose one."; return; }
    var data = { name: $("fName").value, slug: $("fSlug").value, status: "inactive", is_public_venue: kind === "public" };
    $("saveBtn").disabled = true;
    (addPlace ? addPlace.next() : Promise.resolve({ done: true, args: {} })).then(function (pl) {
      if (!pl.done) { $("saveBtn").disabled = false; return null; }   // address needs fixing, or a saved place is being offered
      var withPlace = pl.args && (pl.args.address || pl.args.location_id);
      return admin(withPlace ? "create_with_place" : "create", withPlace ? Object.assign({ data: data }, pl.args) : { data: data });
    }).then(function (res) {
      if (!res) return;
      $("saveBtn").disabled = false;
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status === 200 && res.body && res.body.ok) {
        vNewId = res.body.data.id;
        $("vNotice").textContent = "Added " + res.body.data.name + " (inactive)" + (res.body.data.place ? ", with its place." : ".");
        closeForm(); loadVenues();
        return;
      }
      var probs = res.status === 400 && res.body && res.body.error && res.body.error.problems;
      if (probs && probs.length) {
        var other = [];
        if (probs.some(function (p) { return p.field === "address" || p.field === "location_id"; })) {
          $("fMsg").textContent = "Nothing was saved. " + lProblems(res);
          return;
        }
        probs.forEach(function (p) {
          var target = FIELD_ERR[p.field];
          var text = (p.field === "slug" && p.issue === "invalid_format") ? "Use lowercase letters, numbers and underscores only."
                   : (ISSUE[p.issue] || "That value is not valid.");
          if (target) $(target).textContent = text; else other.push(p.field + " (" + p.issue + ")");
        });
        if (other.length) $("fMsg").textContent = "Could not save: " + other.join(", ");
        return;
      }
      $("fMsg").textContent = adminProblem(res.status);
    });
  });


  // The Place section of the venue form: where the venue is, and a way to move it.
  function placePanel(rec) {
    var wrap = mk("div"), now = mk("div", "note"), host = mk("div"), msg = mk("div", "msg");
    msg.setAttribute("role", "alert");
    var btn = mk("button", "quiet"); btn.type = "button";
    function show() {
      var pl = editRec && editRec.place;
      now.textContent = pl ? "Where: " + placeText(pl) : "No place yet. A venue needs a place (an address or a GPS point) to be active.";
      btn.textContent = pl ? "Change place" : "Add place";
    }
    show();
    btn.addEventListener("click", function () {
      msg.textContent = "";
      if (host.firstChild) { host.textContent = ""; return; }
      var pin = placeInput(true), row = mk("div", "btns"), save = mk("button", "", "Save place"), cancel = mk("button", "quiet", "Cancel");
      save.type = "button"; cancel.type = "button"; row.appendChild(save); row.appendChild(cancel);
      host.appendChild(mk("div", "hint", "This saves right away. When a venue moves, the old place is kept and only the link changes."));
      host.appendChild(pin); host.appendChild(row);
      cancel.addEventListener("click", function () { host.textContent = ""; msg.textContent = ""; });
      save.addEventListener("click", function () {
        msg.textContent = ""; save.disabled = true;
        pin.next().then(function (pl) {
          if (!pl.done) { save.disabled = false; return null; }
          if (!pl.args.address && !pl.args.location_id) { save.disabled = false; msg.textContent = "Type an address or choose a saved place."; return null; }
          return admin("set_place", Object.assign({ id: rec.id }, pl.args));
        }).then(function (r) {
          if (!r) return;
          save.disabled = false;
          if (r.status === 401) { lock("That key did not work."); return; }
          if (r.status === 200 && r.body.ok) {
            editRec.place = r.body.data.place; host.textContent = ""; show(); K.forgetSavedPlaces();
            $("vNotice").textContent = r.body.data.changed === false ? "That is already the venue's place." : "Moved " + (rec.name || "venue") + " to its new place. People in upcoming classes here are emailed the new address. Messages shows the result.";
            loadVenues(); liveReady();
            return;
          }
          msg.textContent = r.status === 404 ? "This venue no longer exists." : lProblems(r);
        });
      });
    });
    wrap.appendChild(now); wrap.appendChild(btn); wrap.appendChild(host); wrap.appendChild(msg);
    return wrap;
  }

  function contactPicker(field, label, current, sec, summary) {
    var wrap = mk("div"), l = mk("div", "f", label), idEl = mk("input"), cur = mk("div", "note"), results = mk("div");
    idEl.type = "hidden"; idEl.id = "ef_" + field; idEl.value = (editRec && editRec[field]) || "";
    var er = mk("div", "ferr"); er.id = "ee_" + field;
    var pick = mk("button", "quiet", "Choose contact"), clear = mk("button", "quiet", "Clear"); pick.type = "button"; clear.type = "button";
    var search = mk("input"); search.type = "text"; search.placeholder = "Search by name"; search.autocomplete = "off"; search.hidden = true; search.id = "ef_" + field + "_q";
    function show(name) {
      cur.textContent = idEl.value ? (name || "(unavailable)") : "Nobody chosen.";
      clear.hidden = !idEl.value;
    }
    show(current && !current.unavailable ? current.display_name : (current ? "(unavailable)" : ""));
    pick.addEventListener("click", function () { search.hidden = !search.hidden; results.textContent = ""; if (!search.hidden) search.focus(); });
    clear.addEventListener("click", function () { idEl.value = ""; show(""); liveReady(); });
    search.addEventListener("input", function () {
      var q = search.value.trim().toLowerCase(); results.textContent = "";
      if (!q) return;
      peopleList().then(function (list) {
        var m = peopleMatches(list, search.value.trim()), shown = m.exact.length ? m.exact : m.near;
        if (!m.exact.length && m.near.length) results.appendChild(mk("div", "hint", "No one matches every word. Closest matches:"));
        shown.slice(0, 8).forEach(function (p) {
          var b = mk("button", "quiet", pFull(p)); b.type = "button";
          b.addEventListener("click", function () { idEl.value = p.id; show(pFull(p)); results.textContent = ""; search.value = ""; search.hidden = true; liveReady(); });
          results.appendChild(b);
        });
        if (!results.firstChild) results.appendChild(mk("div", "hint", "No one by that name."));
      });
    });
    wrap.appendChild(l); wrap.appendChild(cur); wrap.appendChild(pick); wrap.appendChild(clear); wrap.appendChild(search); wrap.appendChild(results);
    wrap.appendChild(idEl); wrap.appendChild(er);
    editFields[field] = { el: idEl, other: null, kind: "text", def: { type: "string", format: "uuid" }, sec: sec, summary: summary };
    return wrap;
  }

  window.VenuesStation = { show: function () { if (!vLoaded) loadVenues(); }, stop: function () { closeEdit(); }, reset: function () { resetVenues(); }, forget: function () { vLoaded = false; }, dirty: function () { return !!(editRec && editDirty()); } };
})();
