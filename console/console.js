/* Console script (the "legacy" file). Moved out of index.html unchanged (master plan step 0.2). Stations are peeled out of this file one by one in Phase 2. */
(function () {
  "use strict";

  // Settings come from console-config.js. Without them nothing below can run, so say so plainly.
  var CFG = window.CONSOLE_CONFIG;
  if (!CFG || !CFG.appId || !CFG.brandName || !CFG.endpoints || !CFG.endpoints.records || !CFG.endpoints.admin || !CFG.endpoints.discovery) {
    document.body.textContent = "The Console settings file (console-config.js) is missing or incomplete.";
    return;
  }

  var MAX = 100;
  var KEY_STORE = "console_key_" + CFG.appId;

  var $ = function (id) { return document.getElementById(id); };
  var key = "";

  $("appName").textContent = CFG.brandName;

  // Look of this Console (logo, sign-in picture, tab icons) comes from the settings file, so a licensee changes it there and nowhere else.
  (function applyBranding() {
    var hero = CFG.hero || {}, logo = CFG.logo || "assets/launch-tile.webp", small = CFG.logoSmall || logo, icons = CFG.icons || {};
    $("brand").setAttribute("aria-label", CFG.brandName + " Console: go to Home");
    var bi = $("brand").querySelector("img"); if (bi) bi.src = small;
    $("lockLogo").src = logo; $("lockLogo").alt = CFG.brandName;
    $("lockTitle").textContent = CFG.brandName + " Console";
    if (hero.image) {
      $("heroImg").src = hero.image; $("heroImg").alt = hero.alt || "";
      if (hero.caption) { $("heroCap").textContent = hero.caption; $("heroCap").hidden = false; }
      $("lockHero").hidden = false;
    }
    [["icon16", "16"], ["icon32", "32"], ["icon48", "48"], ["iconTouch", "touch"]].forEach(function (p) { if (icons[p[1]]) $(p[0]).href = icons[p[1]]; });
  })();

  // Remember off: the key lives in sessionStorage (gone when the tab closes). On: localStorage (stays until Lock).
  function getKey() {
    try {
      var l = localStorage.getItem(KEY_STORE);
      if (l) return { key: l, remember: true };
      var s = sessionStorage.getItem(KEY_STORE);
      if (s) return { key: s, remember: false };
    } catch (e) {}
    return { key: "", remember: false };
  }
  function setKey(v, remember) {
    try { sessionStorage.removeItem(KEY_STORE); } catch (e) {}
    try { localStorage.removeItem(KEY_STORE); } catch (e) {}
    if (!v) return;
    try { (remember ? localStorage : sessionStorage).setItem(KEY_STORE, v); } catch (e) {}
  }

  // ---- Who is signed in. method "key" = the admin key (the back door); "google" = a Google sign-in (Firebase). While signed in with
  // Google, `key` holds the current Google ID token and every call sends it as the Bearer value, exactly like the key. ME is what the
  // server's `me` op said (or, for the key, a super admin). Hiding stations here is a courtesy: the server decides what is allowed.
  var method = "key", ME = null, auth = null, unlockSeq = 0, timing = null;
  function tnow() { return window.performance && performance.now ? performance.now() : Date.now(); }
  var SDK = "https://www.gstatic.com/firebasejs/10.14.1/";
  var STATION_CAPS = { requests: ["manage_requests", "manage_classes"], venues: ["view_console"], classes: ["view_console"], people: ["edit_people"],
    places: ["edit_places", "edit_venues"], instructors: ["manage_instructors", "manage_classes"], students: ["manage_classes", "manage_requests"],
    curriculums: ["view_console"], attendance: ["manage_classes", "manage_requests"], organizations: ["edit_people"], messages: ["view_messages"],
    discovery: ["run_discovery", "view_spend", "edit_discovery_settings"], access: ["manage_access", "invite_people"], performance: ["view_performance"] };
  function can(c) { return !!ME && (ME.is_super_admin === true || ME.inspector === true || (ME.capabilities || []).indexOf(c) >= 0); }   // an inspector may LOOK at everything; the server refuses every write
  function canAny(list) { for (var i = 0; i < list.length; i++) if (can(list[i])) return true; return false; }
  function stationAllowed(id) { var l = STATION_CAPS[id]; return l ? canAny(l) : !!(ME && (ME.is_super_admin || ME.inspector)); }
  function canPlaced() { return canAny(["manage_requests", "manage_classes"]); }
  function keyMe() { return { name: "Admin key", role_key: "super_admin", method: "key", is_super_admin: true, capabilities: [], email: "", scope_region_id: "" }; }

  var fmtTime = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" });   // the viewer's own zone, named (a class shows its own zone: classWhen)
  var fmtClock = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" });
  function when(iso) { var d = new Date(iso); return isNaN(d) ? String(iso || "") : fmtTime.format(d); }


  // ---- Stations and manuals. To add a station: one SURFACES entry (name, blurb, manual), one view section, one line in route().
  var SURFACES = [
    { id: "requests", name: "Registration requests", short: "Requests", blurb: "Sign-ups arriving from the website, newest first." },
    { id: "venues", name: "Venues", short: "Venues", blurb: "Places where classes happen: where, rooms, hours, rules." },
    { id: "classes", name: "Classes", short: "Classes", blurb: "Scheduled sessions: when, where, how many seats." },
    { id: "people", admin: true, name: "People", short: "People", blurb: "The people behind the sign-ups: names, birth dates, merging duplicates." },
    { id: "places", admin: true, name: "Places", short: "Places", blurb: "Locations on Earth: addresses, GPS points, and who is linked." },
    { id: "instructors", name: "Instructors", short: "Instructors", blurb: "The people who teach: bio, what they teach, where and when." },
    { id: "students", name: "Students", short: "Students", blurb: "Who takes classes: a simple roster with a status and a note." },
    { id: "curriculums", name: "Curriculum", short: "Curriculum", blurb: "What is taught: the portfolio of curricula a class points at." },
    { id: "attendance", name: "Attendance", short: "Attendance", blurb: "Everyone in every class: find, filter and change their status." },
    { id: "organizations", name: "Organizations", short: "Organizations", blurb: "Companies, schools, districts and other organized groups." },
    { id: "messages", name: "Messages", short: "Messages", blurb: "Every message the system sent or tried to send, with notes." },
    { id: "discovery", admin: true, name: "Discovery", short: "Discovery", blurb: "Find venues with AI: pick a model and an area, set a spend cap, review what comes back." },
    { id: "access", admin: true, name: "Access", short: "Access", blurb: "Who may sign in with Google, and what each role may do." },
    { id: "activity", admin: true, name: "Activity", short: "Activity", blurb: "Who changed what, and when. Read only." },
    { id: "performance", admin: true, name: "Performance", short: "Performance", blurb: "How fast the Console is. Read only." },
  ];

  function surfaceById(id) { for (var i = 0; i < SURFACES.length; i++) if (SURFACES[i].id === id) return SURFACES[i]; return null; }
  function buildMenus() {   // the drop-down and the sidebar (the Home tiles are home.js)
    var pick = $("collPick"); pick.innerHTML = "";
    var o = document.createElement("option"); o.value = "home"; o.textContent = "Home"; pick.appendChild(o);
    SURFACES.forEach(function (sf, i) {
      var op = document.createElement("option"); op.value = sf.id; op.textContent = sf.name + (sf.admin ? " (admin)" : ""); if (sf.admin) { op.style.color = "var(--err)"; op.className = "adminstn"; } pick.appendChild(op);
    });
    buildNav();
  }

  // ---- Sidebar (1.2a): the same stations as the drop-down, in five groups. A station not listed in a group lands under "More".
  var NAV_GROUPS = [
    { name: "Today", ids: ["requests", "messages"] },
    { name: "Classes", ids: ["classes", "attendance", "venues", "curriculums", "instructors"] },
    { name: "People", ids: ["people", "students", "organizations", "places"] },
    { name: "Growth and admin", ids: ["discovery", "access", "activity", "performance"] }
  ];
  function navLink(id, label, adm) {
    var li = document.createElement("li"), a = document.createElement("a");
    a.href = "#/" + id; a.dataset.nav = id; a.textContent = label;
    if (adm) { var t = document.createElement("span"); t.className = "nadm"; t.textContent = "admin"; a.appendChild(t); }
    li.appendChild(a); return li;
  }
  function buildNav() {
    var nav = $("sideNav"); nav.innerHTML = "";
    var home = document.createElement("ul"); home.className = "nlist"; home.appendChild(navLink("home", "Home", false)); nav.appendChild(home);
    var used = {}, groups = NAV_GROUPS.map(function (g) { g.ids.forEach(function (i) { used[i] = true; }); return { name: g.name, ids: g.ids }; });
    var rest = SURFACES.filter(function (s) { return !used[s.id]; }).map(function (s) { return s.id; });
    if (rest.length) groups.push({ name: "More", ids: rest });
    groups.forEach(function (g, gi) {
      var sec = document.createElement("div"); sec.className = "ngroup";
      var h = document.createElement("div"); h.className = "nhead"; h.id = "navg" + gi; h.textContent = g.name; sec.appendChild(h);
      var ul = document.createElement("ul"); ul.className = "nlist"; ul.setAttribute("aria-labelledby", h.id);
      g.ids.forEach(function (id) { var sf = surfaceById(id); if (sf) ul.appendChild(navLink(id, sf.short || sf.name, !!sf.admin)); });
      sec.appendChild(ul); nav.appendChild(sec);
    });
  }
  function navAccess() {   // hide what this person's role can never open, and any group left empty
    Array.prototype.forEach.call(document.querySelectorAll("#sideNav a[data-nav]"), function (a) { a.parentNode.style.display = (a.dataset.nav === "home" || stationAllowed(a.dataset.nav)) ? "" : "none"; });
    Array.prototype.forEach.call(document.querySelectorAll("#sideNav .ngroup"), function (g) {
      var any = false; Array.prototype.forEach.call(g.querySelectorAll("li"), function (li) { if (li.style.display !== "none") any = true; });
      g.style.display = any ? "" : "none";
    });
  }
  function markNav(r) {
    Array.prototype.forEach.call(document.querySelectorAll("#sideNav a[data-nav]"), function (a) { if (a.dataset.nav === r) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  }
  function setTopH() { document.documentElement.style.setProperty("--topbar-h", $("topbar").offsetHeight + "px"); }
  var ALL_OPTS = null;
  function applyAccess() {
    var pick = $("collPick");
    if (!ALL_OPTS) ALL_OPTS = Array.prototype.slice.call(pick.options);
    var cur = pick.value;
    pick.innerHTML = "";
    ALL_OPTS.forEach(function (o) { if (o.value === "home" || stationAllowed(o.value)) pick.appendChild(o); });
    pick.value = cur;
    if (window.HomeStation) window.HomeStation.access();
    Array.prototype.forEach.call(document.querySelectorAll(".mbtns button[data-m]"), function (b) { b.style.display = stationAllowed(b.dataset.m) ? "" : "none"; });
    navAccess();
    $("attnBox").hidden = !canPlaced();
    var who = $("who");
    who.textContent = ""; who.title = "";
    if (ME) { who.appendChild(document.createTextNode(ME.name + " · ")); var rl = document.createElement("span"); rl.className = "role"; rl.textContent = (ME.role_key || "").replace(/_/g, " "); who.appendChild(rl); who.title = who.textContent; }
    who.hidden = !ME || ME.method === "key";     // the admin key is no person: nothing to name
    viewOnlyMode(!!(ME && ME.inspector));
    capPass();
    if (!capObs && window.MutationObserver) { capObs = new MutationObserver(function () { capPass(); }); capObs.observe(document.body, { childList: true, subtree: true }); }
  }
  // View only (P-78): a courtesy on top of the server, which refuses every write for an inspector. The banner shows, and the buttons that would
  // change something are switched off as they appear (the words below). A button a screen needs for looking carries data-viewok.
  var VIEW_WRITE = /^(edit|save|delete|remove|add|change|switch|cancel class|merge|undo|publish|resend|invite|put in|create|retire|withdraw|mark|send|assign|activate|deactivate|find gps|restore|rename|new |draft|end$)/i;
  // data-needs="cap1 cap2" on a control that changes data (any one capability is enough). A role that can never use it does not see it;
  // a view-only account sees it switched off with the reason. Stations being ported use this instead of the label list above, which stays
  // only for controls that have not been marked yet (it goes when the last station is ported).
  function canWrite(list) { if (!ME || ME.inspector) return false; if (ME.is_super_admin === true) return true; for (var i = 0; i < list.length; i++) if ((ME.capabilities || []).indexOf(list[i]) >= 0) return true; return false; }
  function capEl(el) {
    var list = (el.getAttribute("data-needs") || "").split(/\s+/).filter(Boolean);
    if (ME && ME.inspector) { el.hidden = false; el.disabled = true; el.setAttribute("data-viewonly", "1"); el.title = "View only: this account cannot change anything."; return; }
    var ok = canWrite(list);
    el.hidden = !ok;
    if (ok && el.getAttribute("data-viewonly")) { el.disabled = false; el.removeAttribute("data-viewonly"); el.removeAttribute("title"); }
  }
  function capPass(root) { Array.prototype.forEach.call((root || document).querySelectorAll("[data-needs]"), capEl); }
  function needs(el, caps) { el.setAttribute("data-needs", caps); capEl(el); return el; }
  var capObs = null;
  var viewObs = null;
  function viewOnlyPass(root) {
    Array.prototype.forEach.call((root || document).querySelectorAll("main button, #manual button"), function (b) {
      if (b.getAttribute("data-viewok") || b.getAttribute("data-viewonly")) return;
      var t = (b.textContent || "").trim();
      if (b.classList.contains("stoggle") || VIEW_WRITE.test(t)) { b.disabled = true; b.setAttribute("data-viewonly", "1"); b.title = "View only: this account cannot change anything."; }
    });
  }
  function viewOnlyMode(on) {
    $("viewOnly").hidden = !on; document.body.classList.toggle("viewonly", on);
    $("viewOnly").innerHTML = (on && ME && ME.method === "code")      // a review code never starts a Discovery run (REVIEW_CODE_GUIDE.md)
      ? "<b>View only.</b> You can look at everything and change nothing. Private details are hidden. This temporary review access ends on its own."
      : "<b>View only.</b> You can look at everything and change nothing. Private details are hidden. You can start a Discovery run (25 cents at most).";
    if (viewObs) { viewObs.disconnect(); viewObs = null; }
    if (!on || !window.MutationObserver) return;
    viewObs = new MutationObserver(function () { viewOnlyPass(); });
    viewObs.observe(document.body, { childList: true, subtree: true });
    viewOnlyPass();
  }
  function closeManual() { if (window.ConsoleHelp) window.ConsoleHelp.close(); }   // the Help drawer is help.js (loads after this file)
  var DISCARD = { title: "Discard your changes?", message: "You have edits that are not saved.", yes: "Discard", no: "Keep editing", danger: true };
  function askDiscard(dirty, go, stay) {   // runs go() at once when nothing is unsaved; otherwise asks first
    if (!dirty) { go(); return; }
    UI.confirm(DISCARD).then(function (ok) { if (ok) go(); else if (stay) stay(); });
  }
  function goTo(id) {
    askDiscard((window.VenuesStation && window.VenuesStation.dirty()) || (window.ClassesStation && window.ClassesStation.dirty()), function () {
      closeManual();
      if (location.hash === "#/" + id) route(); else location.hash = "#/" + id;
    }, function () { $("collPick").value = currentRoute(); });
  }

  function show(locked) {
    $("lockView").hidden = !locked;
    $("lockBtn").hidden = locked;
    $("collPick").hidden = locked;
    $("helpOpen").hidden = locked;
    document.body.classList.toggle("withnav", !locked); setTopH(); if (locked) { lastRoute = null; document.title = "Console"; UI.dismiss(); netOk(); }
    if (locked) { closeManual(); if (window.HomeStation) window.HomeStation.reset(); $("listView").hidden = true; $("venuesView").hidden = true; $("classesView").hidden = true; $("peopleView").hidden = true; $("placesView").hidden = true; $("instructorsView").hidden = true; $("studentsView").hidden = true; $("curriculumsView").hidden = true; $("organizationsView").hidden = true; $("attendanceView").hidden = true; $("messagesView").hidden = true; $("discoveryView").hidden = true; $("accessView").hidden = true; $("activityView").hidden = true; $("performanceView").hidden = true; }
  }

  // Addresses: #/requests (default) and #/venues. A new collection is one more option and one more view.
  var ROUTES = "venues classes requests people places instructors students curriculums organizations attendance messages discovery access activity performance".split(" "); function hashParts() { var h = (location.hash || "").replace(/^#\/?/, "").replace(/^station\//, ""), q = h.indexOf("?"), p = (q < 0 ? h : h.slice(0, q)).split("/"), o = {}; (q < 0 ? "" : h.slice(q + 1)).split("&").forEach(function (kv) { var e = kv.indexOf("="); if (e > 0) try { o[decodeURIComponent(kv.slice(0, e))] = decodeURIComponent(kv.slice(e + 1)); } catch (x) {} }); return { route: p[0], sub: p.slice(1), query: o }; } function currentRoute() { var r = hashParts().route; return ROUTES.indexOf(r) >= 0 ? r : "home"; }   // a station address may carry more after the name: #/access/roles, #/activity?kind=class
  var SELF_TITLED = { requests: 1, messages: 1, attendance: 1, access: 1, activity: 1, performance: 1 };   // these draw their own visible h2
  function stationHead(r) {
    var v = $((r === "requests" ? "list" : r) + "View"), sf = surfaceById(r);
    if (!v || !sf || SELF_TITLED[r] || v.querySelector(":scope > .stnh")) return;
    var h = document.createElement("h2"); h.className = "sr stnh"; h.textContent = sf.name; v.insertBefore(h, v.firstChild);
  }
  var lastRoute = null;
  function route() {
    if (!key) return;
    var r = currentRoute();
    if (r !== "home" && !stationAllowed(r)) { location.hash = "#/home"; return; }
    closeManual();
    $("homeView").hidden = r !== "home";
    if (r !== "venues" && window.VenuesStation) window.VenuesStation.stop();
    if (r !== "classes" && window.ClassesStation) window.ClassesStation.stop();
    $("collPick").value = r;
    markPick(); markNav(r); setTopH();
    var sfr = surfaceById(r);
    document.title = (r === "home" ? "Home" : sfr ? (sfr.short || sfr.name) : r) + " \u00b7 " + CFG.brandName + " Console";
    if (lastRoute !== null && lastRoute !== r) $("main").focus({ preventScroll: true });
    lastRoute = r;
    $("listView").hidden = r !== "requests";
    $("venuesView").hidden = r !== "venues";
    $("classesView").hidden = r !== "classes";
    $("peopleView").hidden = r !== "people";
    $("placesView").hidden = r !== "places";
    $("instructorsView").hidden = r !== "instructors";
    $("studentsView").hidden = r !== "students";
    $("curriculumsView").hidden = r !== "curriculums";
    $("organizationsView").hidden = r !== "organizations";
    $("attendanceView").hidden = r !== "attendance";
    $("messagesView").hidden = r !== "messages";
    $("discoveryView").hidden = r !== "discovery";
    if (r === "discovery" && window.DiscoveryStation) window.DiscoveryStation.show();
    $("accessView").hidden = r !== "access";
    if (r === "access" && window.AccessStation) window.AccessStation.show();
    $("activityView").hidden = r !== "activity";
    if (r === "activity" && window.ActivityStation) window.ActivityStation.show();
    $("performanceView").hidden = r !== "performance";
    if (r === "performance" && window.PerformanceStation) window.PerformanceStation.show();
    if (r === "messages" && window.MessagesStation) window.MessagesStation.show();
    if (r === "attendance" && window.AttendanceStation) window.AttendanceStation.show();
    if (r === "home" && window.HomeStation) window.HomeStation.show();
    if (r === "requests" && window.RequestsStation) window.RequestsStation.show();
    if (r !== "requests") { if (window.RequestsStation) window.RequestsStation.stop(); if (r === "venues" && window.VenuesStation) window.VenuesStation.show(); if (r === "classes" && window.ClassesStation) window.ClassesStation.show(); if (r === "people" && window.PeopleStation) window.PeopleStation.show(); if (r === "places" && window.PlacesStation) window.PlacesStation.show(); if (r === "curriculums" && window.CurriculumStation) window.CurriculumStation.show(); if (r === "instructors" && window.InstructorsStation) window.InstructorsStation.show(); if (r === "students" && window.StudentsStation) window.StudentsStation.show(); if (r === "organizations" && window.OrganizationsStation) window.OrganizationsStation.show(); }
    stationHead(r);   // after the stations that redraw their own page (Discovery) have drawn it
  }

  // Returns {status, records} ; status: ok | unauthorized | limited | network | error
  function fetchRecords(since, opt) {
    var url = CFG.endpoints.records + "?limit=" + MAX + (since ? "&since=" + encodeURIComponent(since) : "") + (opt && opt.q ? "&q=" + encodeURIComponent(opt.q) : "") + (opt && opt.region ? "&region=" + encodeURIComponent(opt.region) : "");
    return fetchT(url, { method: "GET", headers: { "Authorization": "Bearer " + key }, cache: "no-store" }, READ_MS)
      .then(function (r) {
        if (r.ok) netOk();
        if (r.status === 401) return { status: "unauthorized" };
        if (r.status === 429) return { status: "limited" };
        if (!r.ok) return { status: "error" };
        return r.json().then(function (j) {
          return { status: "ok", records: (j && j.data && j.data.records) || [], total: j && j.data && j.data.total };
        });
      })
      .catch(function (e) { netShow(!!(e && e.timedOut)); return { status: "network" }; });
  }

  function line(label, value) {
    var d = document.createElement("div");
    var b = document.createElement("b");
    b.textContent = label + ": ";
    d.appendChild(b);
    d.appendChild(document.createTextNode(value));
    return d;
  }
  function str(v) { return (v !== null && typeof v === "object") ? JSON.stringify(v) : String(v); }
  function problem(status) {
    if (status === "unauthorized") return method === "google" ? "Google sign-in did not work. Try again." : "That key did not work.";
    if (status === "forbidden") return "This Google account has not been invited. Ask the owner.";
    if (status === "limited") return "Too many tries. Wait a few minutes.";
    if (status === "network") return "Could not reach the server.";
    return "Something went wrong. Try again.";
  }

  function lock(message) {
    launchStop();
    if (method === "google") {
      if (message === "That key did not work.") message = "Your Google sign-in ended. Sign in again.";
      method = "key"; try { if (auth) auth.signOut(); } catch (e) {}
    }
    ME = null; $("who").hidden = true; viewOnlyMode(false); idleEnd();
    setKey("", false); key = ""; if (window.RequestsStation) window.RequestsStation.reset(); if (window.VenuesStation) window.VenuesStation.reset(); if (window.ClassesStation) window.ClassesStation.reset(); if (window.CurriculumStation) window.CurriculumStation.reset(); if (window.InstructorsStation) window.InstructorsStation.reset(); if (window.StudentsStation) window.StudentsStation.reset(); resetPlaced(); if (window.PeopleStation) window.PeopleStation.reset(); if (window.PlacesStation) window.PlacesStation.reset(); if (window.OrganizationsStation) window.OrganizationsStation.reset(); if (window.ConsoleNames) window.ConsoleNames.reset(); if (window.AttendanceStation) window.AttendanceStation.reset(); if (window.DiscoveryStation) window.DiscoveryStation.reset(); if (window.AccessStation) window.AccessStation.reset(); if (window.ActivityStation) window.ActivityStation.reset(); if (window.PerformanceStation) window.PerformanceStation.reset(); if (window.MessagesStation) window.MessagesStation.reset();
    $("keyInput").value = ""; $("keyInput").type = "password"; $("keyShow").textContent = "Show"; $("keyShow").setAttribute("aria-pressed", "false");
    $("lockMsg").textContent = message || "";
    show(true);
  }

  // The first call after a key or sign-in: who is this, and may they in? The key proves itself by reading the registration records
  // (as it always did). A Google sign-in asks the server's `me` op; the records are read only if the role may see requests.
  function accessProbe() {
    if (method !== "google") return fetchRecords("").then(function (r) {
      if (r.status !== "ok") return r;
      ME = keyMe();
      // A temporary review code is typed into the same Key box but is view only: ask the server who this really is (anything else stays the admin key).
      return adminCall("me", {}, "access_persons").then(function (m) {
        if (m && m.status === 200 && m.body && m.body.ok && m.body.data && m.body.data.method === "code") ME = m.body.data;
        return r;
      }, function () { return r; });
    });
    return adminCall("me", {}, "access_persons").then(function (r) {
      if (r.status !== 200 || !r.body || !r.body.ok) return { status: r.status === 401 ? "unauthorized" : r.status === 403 ? "forbidden" : r.status === 429 ? "limited" : r.status === 0 ? "network" : "error" };
      ME = r.body.data; launchStage(3); if (timing) timing.tMe = tnow();
      return canPlaced() ? fetchRecords("") : { status: "ok", records: [] };
    });
  }

  // ---- The launch screen: instant feedback while a sign-in is in progress (a spinning tile, a line that follows the real stages, a spinning tab icon).
  // It hides the sign-in buttons so nobody presses twice; a failure or a lock brings the form back.
  var launching = false, launchN = 0, launchTimers = [], launchSaved = null, spinTimer = null, iconKeep = null;
  var LAUNCH_LINES = ["Boarding pass accepted…", "Mission control is checking your clearance…", "Fueling the stations…"];
  var LAUNCH_SLOW = "Still on the launch pad. Slow link or cold engines. Hang tight.";
  function launchStage(n) { if (!launching || n <= launchN) return; launchN = n; $("launchLine").textContent = LAUNCH_LINES[n - 1]; }
  function spinIcons(on) {
    if (!on) {
      if (spinTimer) { clearInterval(spinTimer); spinTimer = null; }
      if (iconKeep) { iconKeep.forEach(function (k) { k.el.setAttribute("href", k.href); }); iconKeep = null; }
      return;
    }
    if (spinTimer || iconKeep) return;
    try { if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return; } catch (e) {}
    var links = document.querySelectorAll('link[rel="icon"]'); if (!links.length) return;
    var img = new Image();
    img.onload = function () {
      if (!launching || spinTimer || iconKeep) return;
      iconKeep = [].map.call(links, function (el) { return { el: el, href: el.getAttribute("href") }; });
      var c = document.createElement("canvas"); c.width = 32; c.height = 32; var x = c.getContext("2d"), a = 0;
      spinTimer = setInterval(function () {
        a += Math.PI / 6; x.clearRect(0, 0, 32, 32); x.save(); x.translate(16, 16); x.rotate(a); x.drawImage(img, -11, -11, 22, 22); x.restore();
        try { var u = c.toDataURL("image/png"); iconKeep.forEach(function (k) { k.el.setAttribute("href", u); }); } catch (e) { spinIcons(false); }
      }, 100);
    };
    img.src = "assets/console-favicon-32.png";
  }
  function launchStart() {
    if (launching) return;
    launching = true; launchN = 0;
    launchSaved = { g: $("googleBox").hidden, k: $("keyBox").hidden, s: $("swapLink").hidden };
    $("googleBox").hidden = true; $("keyBox").hidden = true; $("swapLink").hidden = true; $("lockMsg").textContent = "";
    $("launching").hidden = false; launchStage(1); spinIcons(true);
    launchTimers.push(setTimeout(function () { launchStage(2); }, 700));
    launchTimers.push(setTimeout(function () { if (launching) { launchN = 9; $("launchLine").textContent = LAUNCH_SLOW; } }, 8000));
  }
  function launchStop() {
    launchTimers.forEach(clearTimeout); launchTimers = []; spinIcons(false);
    if (!launching) return;
    launching = false; $("launching").hidden = true;
    if (launchSaved) { $("googleBox").hidden = launchSaved.g; $("keyBox").hidden = launchSaved.k; $("swapLink").hidden = launchSaved.s; launchSaved = null; }
  }
  function launchDone() {   // a short "Liftoff!" before the Console opens, only when the launch screen was showing
    return new Promise(function (ok) {
      if (!launching) { ok(); return; }
      launchTimers.forEach(clearTimeout); launchTimers = []; $("launchLine").textContent = "Liftoff!";
      setTimeout(function () { launchStop(); ok(); }, 350);
    });
  }

  // The Performance log: after a sign-in, send how long each step took (numbers only; the server stamps who). Never for a view-only account; a failure is ignored.
  function sendTiming(tm) {
    if (!tm || !tm.tReady || !ME || ME.inspector) return;
    var ms = function (n) { return Math.max(0, Math.min(600000, Math.round(n))); }, a = { kind: "sign_in", device: window.innerWidth < 700 ? "phone" : "desktop", method: tm.method,
      total_ms: ms(tm.tReady - tm.t0), check_ms: ms(tm.tMe - tm.t0), load_ms: ms(tm.tRecords - tm.tMe) };
    if (tm.method === "google" && typeof ME.server_ms === "number") a.server_ms = ms(ME.server_ms);
    if (tm.method === "google" && typeof ME.cold === "boolean") a.cold = ME.cold;
    try { adminCall("record_timing", a, "performance_events").catch(function () {}); } catch (e) {}
  }

  function unlock(k, remember) {
    var mine = ++unlockSeq;
    timing = { t0: tnow(), method: method === "google" ? "google" : "key" };
    launchStart();
    idleTouch();                                       // a sign-in starts a fresh clock: after a timeout the old "last active" time must not sign this person straight out again
    key = k; if (window.RequestsStation) window.RequestsStation.clearList();
    $("lockMsg").textContent = "";
    $("unlockBtn").disabled = true;
    return accessProbe().then(function (res) {
      $("unlockBtn").disabled = false;
      if (mine !== unlockSeq || !key) return;          // the page was locked, or signed in again, while this was in flight: this answer is out of date
      if (timing) { timing.tRecords = tnow(); if (!timing.tMe) timing.tMe = timing.tRecords; }
      if (res.status !== "ok") {
        key = ""; launchStop();
        $("lockMsg").textContent = "Launch aborted: " + problem(res.status);
        if (method === "google") { method = "key"; try { if (auth) auth.signOut(); } catch (e) {} }
        ME = null;
        show(true);
        return;
      }
      if (method !== "google") setKey(k, remember);
      idleStaleAtLoad = false; idleStart();
      var tm = timing; timing = null; if (tm) tm.tReady = tnow();
      return launchDone().then(function () {
        if (mine !== unlockSeq || !key) return;
        show(false);
        applyAccess();
        if (window.RequestsStation) window.RequestsStation.adopt(res.records);
        route();
        sendTiming(tm);
      });
    });
  }

  // ---- Venues view: list and add, through the admin endpoint (the CRUD handler file does the checking).
  var ADMIN_URL = CFG.endpoints.admin;
  var CF = window.ConsoleForms, LABELS = CF.labels, humanize = CF.humanize, readValue = CF.readValue, buildField = CF.buildField;
  var ISSUE = window.ConsoleForms.issue, wholeNum = window.ConsoleForms.wholeNum, slugify = window.ConsoleForms.slugify, skelOn = UI.skelOn, skelOff = UI.skelOff;   // shared pieces (forms.js, ui.js)

  // Anything that changes data shows a working indicator on the button that was pressed (which then cannot be pressed twice) and a
  // toast at the bottom: "Working…", then "Done" or "Did not go through". Reading (list, get, lookups) stays silent.
  var READ_OPS = { list: 1, get: 1, find_gps: 1 }, lastBtn = null, lastBtnAt = 0, workN = 0, toastTimer = null;
  document.addEventListener("click", function (e) { var b = e.target && e.target.closest && e.target.closest("button"); if (b) { lastBtn = b; lastBtnAt = Date.now(); } }, true);
  function toast(kind, text, ms) {
    var el = document.getElementById("workToast"); if (!el) return;
    clearTimeout(toastTimer); el.className = (kind ? kind + " " : "") + "on"; document.getElementById("workText").textContent = text;
    if (ms) toastTimer = setTimeout(function () { el.className = el.className.replace(/\bon\b/, "").trim(); }, ms);
  }
  var VIEW_READS = { list: 1, get: 1, find_by_address: 1, get_for_individual: 1, suggest: 1, queue: 1 };
  function viewOnlyRefusal() { return { status: 403, body: { ok: false, error: { code: "view_only", message: "View only: this account can look at everything and change nothing." } } }; }
  function admin(op, args, coll) {
    if (ME && ME.inspector && !VIEW_READS[op]) { toast("bad", "View only: nothing was changed.", 3500); return Promise.resolve(viewOnlyRefusal()); }   // the server would refuse it too
    if (READ_OPS[op]) return adminCall(op, args, coll);
    var btn = lastBtn && Date.now() - lastBtnAt < 4000 ? lastBtn : null;
    if (btn) { btn.classList.add("working"); btn.setAttribute("aria-busy", "true"); }
    workN++; toast("", "Working… this can take a few seconds when emails are sent.", 0);
    return adminCall(op, args, coll).then(function (res) {
      workN--; if (btn) { btn.classList.remove("working"); btn.removeAttribute("aria-busy"); }
      if (!workN) { var ok = res.status === 200 && res.body && res.body.ok; if (ok) toast("ok", "Done", 1800); else if (res.status === 401) toast("", "", 1); else toast("bad", "That did not go through. See the message above.", 3500); }
      return res;
    });
  }
  // ---- Time limits and the connection banner (1.3b). A read that gets no answer shows a banner with Try again; a write that gets no answer says it may have gone through.
  var TMO = CFG.timeouts || {}, READ_MS = (TMO.readSeconds || 20) * 1000, WRITE_MS = (TMO.writeSeconds || 60) * 1000, netWhy = "";
  function fetchT(url, opts, ms) {
    var ctl = typeof AbortController === "function" ? new AbortController() : null, t = null;
    if (ctl) { opts.signal = ctl.signal; t = setTimeout(function () { ctl.abort(); }, ms); }
    return fetch(url, opts).then(function (r) { clearTimeout(t); return r; }, function (e) { clearTimeout(t); e.timedOut = !!(ctl && ctl.signal.aborted); throw e; });
  }
  function netShow(timedOut) {
    $("netText").textContent = (timedOut ? "The server did not answer in time." : "Could not reach the server.") + " What is on screen may be out of date.";
    $("netBanner").hidden = false;
  }
  function netOk() { $("netBanner").hidden = true; }
  function netRetry() {   // load the current station again, from scratch
    netOk(); if (window.VenuesStation) window.VenuesStation.forget(); if (window.ClassesStation) window.ClassesStation.forget(); if (window.CurriculumStation) window.CurriculumStation.forget(); if (window.InstructorsStation) window.InstructorsStation.forget(); if (window.StudentsStation) window.StudentsStation.forget(); if (window.PeopleStation) window.PeopleStation.forget(); if (window.PlacesStation) window.PlacesStation.forget();
    if (window.OrganizationsStation) window.OrganizationsStation.forget();
    route();
  }
  function adminCall(op, args, coll) {
    var isRead = !!VIEW_READS[op];
    return fetchT(ADMIN_URL, { method: "POST", cache: "no-store",
        headers: { "Authorization": "Bearer " + key, "Content-Type": "application/json" },
        body: JSON.stringify({ collection: coll || "venues", op: op, args: args }) }, isRead ? READ_MS : WRITE_MS)
      .then(function (r) {
        if (isRead && r.ok) netOk();
        return r.json().catch(function () { return {}; }).then(function (j) { return { status: r.status, body: j }; });
      })
      .catch(function (e) {
        var to = !!(e && e.timedOut);
        netWhy = to ? (isRead ? "read-timeout" : "write-timeout") : "down";
        if (isRead) netShow(to);
        return { status: 0, body: {}, timedOut: to };
      });
  }
  function adminProblem(status) {
    if (status === 429) return "Too many tries. Wait a few minutes.";
    if (status === 0) return netWhy === "write-timeout" ? "No answer after " + (WRITE_MS / 1000) + " seconds. It may still have gone through: check the list before trying again." : netWhy === "read-timeout" ? "The server did not answer in time." : "Could not reach the server.";
    return "Something went wrong. Try again.";
  }

  // A one-tap status switch on a card. Taps are collected: 1.5 seconds after the LAST tap the server is asked once, and only if the
  // final choice differs from what is saved (two taps cancel out). opts: coll (admin collection or undefined), on, off (status words), problem(res).
  var TOGGLE_WAIT = 1500;
  function statusToggle(rec, li, opts) {
    var b = mk("button", "stoggle"); b.type = "button"; b.setAttribute("role", "switch");
    var knob = mk("span", "knob"), word = mk("span", "");
    b.appendChild(knob); b.appendChild(word);
    var want = rec.status === opts.on, timer = null, busy = false;
    var msg = mk("div", "stmsg"); msg.setAttribute("role", "alert");
    function draw() {
      var saved = rec.status === opts.on;
      b.classList.toggle("on", want); b.classList.toggle("pending", want !== saved || !!timer);
      b.setAttribute("aria-checked", want ? "true" : "false");
      word.textContent = want ? (opts.onWord || "Active") : (opts.offWord || "Inactive");
      b.setAttribute("aria-label", (opts.label || "Status") + ": " + (want ? (opts.onWord || "Active") : (opts.offWord || "Inactive")).toLowerCase() + (timer ? ", saving soon" : "") + ". Tap to change.");
    }
    function send() {
      timer = null;
      if (want === (rec.status === opts.on)) { draw(); return; }
      busy = true; b.disabled = true; msg.textContent = "";
      var args = { id: rec.id, changes: { status: want ? opts.on : opts.off }, expected_updated_at: rec.updated_at };
      (opts.coll ? admin("update", args, opts.coll) : admin("update", args)).then(function (res) {
        busy = false; b.disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          rec.status = want ? opts.on : opts.off;
          var u = res.body.data && res.body.data.updated_at; if (u) rec.updated_at = u;
          draw(); return;
        }
        want = rec.status === opts.on; draw();
        msg.textContent = res.status === 409 ? "This changed somewhere else. Tap Refresh, then try again." : res.status === 400 ? opts.problem(res) : adminProblem(res.status);
      });
    }
    b.addEventListener("click", function () {
      if (busy) return;
      want = !want; if (timer) clearTimeout(timer);
      timer = setTimeout(send, TOGGLE_WAIT); draw();
    });
    li.classList.add("hasToggle"); draw();
    return { btn: b, msg: msg };
  }

  function mk(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  // The History button on a card: opens the Activity station on this one record. Only a super admin gets it (the server decides; this is courtesy).
  function historyBtn(id, label) {
    if (!id || !ME || (ME.is_super_admin !== true && ME.inspector !== true)) return null;
    var b = mk("button", "quiet", "Change history"); b.type = "button"; b.setAttribute("data-history", id); b.setAttribute("data-viewok", "1");
    b.addEventListener("click", function (ev) { ev.stopPropagation(); if (window.ActivityStation) window.ActivityStation.openFor(id, label || ""); });
    return b;
  }
  // What a station that lives in its own file (console/discovery.js) may use from this page. Nothing here exposes the key except to that file's own calls.
  window.ConsoleKit = { mk: mk, admin: admin, toast: toast, lock: lock, key: function () { return key; }, can: can, me: function () { return ME; }, when: when, clock: function (d) { return fmtClock.format(d); },
                        go: function (id) { goTo(id); }, hash: hashParts, setHash: function (path, query) { var q = Object.keys(query || {}).filter(function (k) { return query[k] !== "" && query[k] != null; }).map(function (k) { return encodeURIComponent(k) + "=" + encodeURIComponent(query[k]); }).join("&"); try { history.replaceState(null, "", "#/" + path + (q ? "?" + q : "")); } catch (x) {} }, sessionMinutes: function (n) { if (n === undefined) return idleMinutes; idleMinutes = idleClamp(n); idleSet(IDLE_MIN, idleMinutes); return idleMinutes; }, lastButton: function () { return lastBtn && Date.now() - lastBtnAt < 4000 ? lastBtn : null; },
                        // Added for station files (M-1, the Messages extraction). Functions, not values, because the things they read are filled in later or replaced.
                        adminProblem: function (status) { return adminProblem(status); },
                        time: function (d) { return fmtTime.format(d); },
                        attName: function (r) { return attName(r); },
                        classChoices: function () { return window.ClassesStation.choices(); },
                        classById: function (id) { return window.ClassesStation ? window.ClassesStation.byId(id) : undefined; },
                        openAttendance: function (cls, host) { openAttendance(cls, host); },
                        requests: function () { var have = window.RequestsStation ? window.RequestsStation.records() : []; return have.length ? Promise.resolve(have) : fetchRecords("").then(function (r) { return r.status === "ok" ? r.records : []; }); },
                        words: function () { return { corrKind: CORR_KIND, reasonWord: REASON_WORD, attWord: ATT_WORD, roleWord: ROLE_WORD }; }, historyBtn: function (id, label) { return historyBtn(id, label); }, fetchT: function (url, opts, ms) { return fetchT(url, opts, ms); }, netShow: function (t) { netShow(t); }, canPlaced: function () { return canPlaced(); }, fetchRecords: function (since, opt) { return fetchRecords(since, opt); }, putInClass: function (rec, host, said) { window.ClassesStation.putInClass(rec, host, said); }, line: function (l, v) { return line(l, v); }, str: function (v) { return str(v); }, problem: function (st) { return problem(st); }, consts: function () { return { MAX: MAX, READ_MS: READ_MS, ATT_RANK: ATT_RANK, ATT_GONE: ATT_GONE, RECORDS_URL: CFG.endpoints.records }; }, attConsts: function () { return { ATT: ATT, ATT_STATUSES: ATT_STATUSES, ATT_WORD: ATT_WORD, ROLE_WORD: ROLE_WORD, ATT_TONE: ATT_TONE, ATT_OPEN: ATT_OPEN, ATT_OFF: ATT_OFF, CORR_KIND: CORR_KIND, REASON_WORD: REASON_WORD, leftOpen: leftOpen }; }, attFail: function (res) { return window.AttendanceStation.fail(res); }, classWhen: function (c) { return window.ClassesStation.classWhen(c); }, refreshPlaced: function () { return refreshPlaced(); }, assignForm: function (opts) { return window.ClassesStation.assignForm(opts); },
                        // Added for the Classes station (C-2): openWorkflows, attLine (straight to the Attendance station), afNext (the shared id counter), forgetPeople.
                        openWorkflows: function () { return window.ConsoleHelp.openWorkflows.apply(null, arguments); }, surfaces: function () { return SURFACES; }, allowed: function (id) { return stationAllowed(id); }, attLine: function (r, withClass) { return window.AttendanceStation.attLine(r, withClass); }, afNext: function () { return ++afSeq; }, forgetPeople: function () { window.PeopleStation.forgetPick(); },
                        // Added for the Venues station (V-4). Functions that point at the places, people and shared helpers still in this file.
                        lProblems: function () { return window.ConsoleAddresses.lProblems.apply(null, arguments); }, placeInput: function () { return window.ConsoleAddresses.placeInput.apply(null, arguments); }, placeText: function () { return window.ConsoleAddresses.placeText.apply(null, arguments); },
                        forgetSavedPlaces: function () { window.ConsoleAddresses.forgetSaved(); }, peopleList: function () { return window.PeopleStation.list.apply(null, arguments); }, peopleMatches: function () { return window.PeopleStation.matches.apply(null, arguments); },
                        pFull: function () { return window.PeopleStation.full.apply(null, arguments); }, statusToggle: function () { return statusToggle.apply(null, arguments); }, askDiscard: function () { return askDiscard.apply(null, arguments); },
                        // Added for the Instructors and Students stations (RO-2): the address form, the People problem words, the Places refresh, the collection names, and People's stale flags.
                        addrForm: function () { return window.ConsoleAddresses.addrForm.apply(null, arguments); }, pProblems: function () { return window.PeopleStation.problems.apply(null, arguments); }, refreshPlaces: function () { window.PlacesStation.refresh(); },
                        peopleStale: function () { window.PeopleStation.stale(); },
                        // Added for the Organizations station (OR-2): People's date words, Places' one-line address, the Places relation words (a function: defined later in this file).
                        pDateOut: function () { return window.PeopleStation.dateOut.apply(null, arguments); }, locAddr: function () { return window.ConsoleAddresses.locAddr.apply(null, arguments); },
                        // Added for the Places station (PP-2): the skeleton helpers and the current page, which it needs and cannot own.
                        skelOn: function () { return skelOn.apply(null, arguments); }, skelOff: function () { return skelOff.apply(null, arguments); }, currentRoute: function () { return currentRoute(); },
                        // Added for the People station (PP-5): the person history forwarder, and the person relation list (data, stays here).
                        personHistory: function () { return personHistory.apply(null, arguments); } };   // R-2 (Journal): attWord, roleWord, historyBtn. R-3 (Requests): fetchT to consts. consts holds constants only. A-1 (Attendance): attConsts to assignForm.
  $("lockForm").addEventListener("submit", function (e) {
    e.preventDefault(); if (launching) return;
    var k = $("keyInput").value.trim();
    if (!k) { $("lockMsg").textContent = "That key did not work."; return; }
    unlock(k, $("rememberBox").checked);
  });
  $("keyShow").addEventListener("click", function () {      // see what you typed or pasted; starts hidden again after every lock
    var i = $("keyInput"), reveal = i.type === "password";
    i.type = reveal ? "text" : "password"; this.textContent = reveal ? "Hide" : "Show"; this.setAttribute("aria-pressed", reveal ? "true" : "false"); i.focus();
  });
  $("lockBtn").addEventListener("click", function () { lock(""); });
  $("refreshBtn").addEventListener("click", function () { if (window.RequestsStation) { window.RequestsStation.check(true); window.RequestsStation.loadPlaced(); } });
  document.addEventListener("visibilitychange", function () { if (!document.hidden && key && currentRoute() === "requests" && window.RequestsStation) window.RequestsStation.check(false); });
  window.addEventListener("hashchange", route);
  $("netRetry").addEventListener("click", netRetry);
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a.skip"); if (!a) return;
    e.preventDefault(); $("main").focus();
  });
  function markPick() { var o = $("collPick").selectedOptions[0]; $("collPick").classList.toggle("adm", !!(o && o.className === "adminstn")); }
  $("collPick").addEventListener("change", function () { markPick(); goTo($("collPick").value); });
  $("brand").addEventListener("click", function (e) { e.preventDefault(); goTo("home"); });
  $("sideNav").addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("a[data-nav]") : null;
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;   // modified clicks keep their normal meaning (new tab)
    e.preventDefault(); goTo(a.dataset.nav);
  });
  window.addEventListener("resize", setTopH);
  document.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target.closest("[data-go]") : null;
    if (!t) return;
    goTo(t.dataset.go);
  });
  buildMenus();


  function refreshPlaced() { return window.RequestsStation ? window.RequestsStation.loadPlaced() : Promise.resolve(); }   // Classes and Attendance call this after they place or remove someone


  // ================= Attendance: who is in which class =================
  var ATT = "attendances";
  var ROLE_WORD = { student: "Student", primary_instructor: "Lead instructor", instructor: "Instructor" };
  var ATT_STATUSES = ["assigned", "waitlisted", "confirmed", "attended", "late", "no_show", "declined", "withdrawn", "cancelled"];
  var ATT_WORD = { assigned: "Assigned", confirmed: "Confirmed", waitlisted: "On the waiting list", declined: "Declined", withdrawn: "Withdrawn", cancelled: "Cancelled", attended: "Attended", late: "Late", no_show: "Did not show" };
  var ATT_RANK = { assigned: 1, waitlisted: 1, confirmed: 2, attended: 3, late: 3, no_show: 3 };   // how far a placement has come: placed, confirmed, then the class happened
  var ATT_GONE = { declined: 1, withdrawn: 1, cancelled: 1 };   // a request with only these is back to waiting
  var ATT_OPEN = { assigned: 1, waitlisted: 1, confirmed: 1 };   // a placement still open: ending it sends emails
  function leftOpen(from, to) { return !!ATT_OPEN[from] && !!ATT_GONE[to]; }
  var ATT_OFF = { waitlisted: 1, declined: 1, withdrawn: 1, cancelled: 1 };   // statuses that do not hold a seat
  var afSeq = 0;

  // The card's tone, chip words and "Next" line, by status (the cue rules in console/DESIGN-RULES.md)
  var ATT_TONE = {
    assigned: { tone: "wait", next: "Next: wait for them to confirm." },
    waitlisted: { tone: "wait", next: "Next: they stay waiting until a seat opens." },
    confirmed: { tone: "ok", next: "Next: take attendance on class day." },
    attended: { tone: "ok", next: "Done: they came to class." },
    late: { tone: "ok", next: "Done: they came late." },
    no_show: { tone: "done", next: "Closed: they did not show." },
    declined: { tone: "done", next: "Closed: they declined." },
    withdrawn: { tone: "done", next: "Closed: they withdrew." },
    cancelled: { tone: "done", next: "Closed: this was cancelled." }
  };
  function attName(r) { return (r.person && r.person.display_name) || "(person not found)"; }



  // Attendance lives in attendance.js. These forwarders keep the callers that are still here (Classes, People, Put in a class) unchanged; they go when the placing machinery moves (DT-18).
  function openAttendance(cls, host) { if (window.AttendanceStation) window.AttendanceStation.openAttendance(cls, host); }
  function personHistory(rec, host) { if (window.AttendanceStation) window.AttendanceStation.personHistory(rec, host); }
  var CORR_KIND = { placement_confirmation: "Placement confirmation", request_received: "Request received" };
  var REASON_WORD = { no_contact: "no email or phone on file", channel_unavailable: "they prefer a text, so contact them by hand", no_template: "no message is set up for this",
                      incomplete: "a detail the message needs is missing", invalid_context: "the details were not valid", unknown_kind: "unknown kind of message",
                      time_budget: "ran out of time", internal_error: "a problem on our side", cms_off: "messaging is off", log_only: "test mode, nothing is really sent",
                      duplicate: "already sent", excluded: "left out on purpose", muted: "they asked not to be contacted" };


  function resetPlaced() {
    try { $("atDlg").close(); } catch (e) {} try { $("jrDlg").close(); $("wfDlg").close(); } catch (e) {}
    $("attnBody").textContent = "Checking the requests…"; $("attnBadge").hidden = true; $("attnBox").className = "attn";
  }
  $("atClose").addEventListener("click", function () { $("atDlg").close(); });


  // ---- Google sign-in. Only switched on when console/firebase-config.js holds the project's public web key; until then the page is key-only.
  function loadScript(src) { return new Promise(function (ok, no) { var s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = no; document.head.appendChild(s); }); }
  function onToken(user) {
    if (!user) { if (method === "google" && key) lock("You have been signed out."); return; }
    user.getIdToken().then(function (t) {
      if (method === "google" && key) { key = t; return; }   // a refreshed token for the session already open
      if (key) return;                                       // already in with the admin key
      if (idleStaleAtLoad) { idleStaleAtLoad = false; idleDrop(IDLE_AT); try { auth.signOut(); } catch (e) {} $("lockMsg").textContent = idleStaleMessage(); show(true); return; }   // a restored session that sat idle too long
      method = "google"; unlock(t, false);
    }).catch(function () {});
  }
  function refreshToken() {
    if (method === "google" && auth && auth.currentUser) auth.currentUser.getIdToken().then(function (t) { if (method === "google") key = t; }).catch(function () {});
  }
  function showGoogle(on) {
    $("googleBox").hidden = !on; $("keyBox").hidden = on; $("swapLink").textContent = on ? "Use admin key" : "Use Google sign-in"; $("swapLink").hidden = false;
  }
  function initGoogle() {
    var cfg = window.CONSOLE_FIREBASE;
    if (!cfg || !cfg.apiKey) return;
    var ready = window.firebase ? Promise.resolve() : loadScript(SDK + "firebase-app-compat.js").then(function () { return loadScript(SDK + "firebase-auth-compat.js"); });
    ready.then(function () {
      var fb = window.firebase;
      if (!fb.apps || !fb.apps.length) fb.initializeApp(cfg);
      auth = fb.auth();
      showGoogle(true);
      auth.onIdTokenChanged(onToken);
    }).catch(function () { /* stays key-only */ });
  }
  $("googleBtn").addEventListener("click", function () {
    if (!auth || launching) return;
    $("lockMsg").textContent = ""; idleStaleAtLoad = false;       // a deliberate sign-in is never dropped as stale
    var p = new window.firebase.auth.GoogleAuthProvider();
    p.setCustomParameters({ prompt: "select_account" });
    auth.signInWithPopup(p).catch(function (e) {
      $("lockMsg").textContent = e && e.code === "auth/popup-closed-by-user" ? "" : "Google sign-in did not complete. Try again.";
    });
  });
  $("swapLink").addEventListener("click", function (e) { e.preventDefault(); showGoogle($("googleBox").hidden); });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) refreshToken(); });
  setInterval(refreshToken, 20 * 60 * 1000);
  initGoogle();

  // ---- Automatic sign-out after inactivity (console_setting.session_timeout_minutes, set by a super admin in Access > Sign-in).
  // This locks the page in this browser; it is not a server session (the admin key itself stays valid until it is changed). The clock
  // is shared by every Console tab in this browser (localStorage); a Discovery run in progress counts as activity (it is driven from this
  // page); a remembered key or Google session that has sat idle past the limit is dropped when the page loads instead of signing in.
  // If the number cannot be read, the last known one is used, and 10 minutes if none was ever known: it fails closed, never open.
  var IDLE_AT = "console_last_active", IDLE_MIN = "console_timeout_minutes", IDLE_DEFAULT = 10, IDLE_WARN_MS = 60000;
  var idleMinutes = IDLE_DEFAULT, idleLast = Date.now(), idleWrote = 0, idleTimer = null, idleShown = false, idleStaleAtLoad = false;
  function idleGet(k) { try { return parseInt(localStorage.getItem(k) || "", 10) || 0; } catch (e) { return 0; } }
  function idleSet(k, v) { try { localStorage.setItem(k, String(v)); } catch (e) {} }
  function idleDrop(k) { try { localStorage.removeItem(k); } catch (e) {} }
  function idleClamp(n) { n = Math.round(Number(n)); return n >= 1 && n <= 480 ? n : IDLE_DEFAULT; }
  idleMinutes = idleClamp(idleGet(IDLE_MIN) || IDLE_DEFAULT);
  function idleTouch() { var t = Date.now(); idleLast = t; if (t - idleWrote > 5000) { idleWrote = t; idleSet(IDLE_AT, t); } }
  function idleLastActive() { return Math.max(idleLast, idleGet(IDLE_AT)); }
  function idleBusy() { return !!(window.DiscoveryStation && window.DiscoveryStation.busy && window.DiscoveryStation.busy()); }
  function idleWarn(ms) {
    var w = $("idleWarn"); if (!w) return;
    if (!ms) { if (idleShown) { w.hidden = true; idleShown = false; } return; }
    var sec = Math.max(1, Math.ceil(ms / 1000)); $("idleCount").textContent = (sec >= 60 ? Math.floor(sec / 60) + ":" + ("0" + (sec % 60)).slice(-2) : sec + " second" + (sec === 1 ? "" : "s"));
    if (!idleShown) { w.hidden = false; idleShown = true; }
  }
  function idleTick() {
    if (!key) { idleWarn(0); return; }
    if (idleBusy()) idleTouch();
    var left = idleMinutes * 60000 - (Date.now() - idleLastActive());
    if (left <= 0) { idleWarn(0); lock("You were signed out after " + idleMinutes + " minute" + (idleMinutes === 1 ? "" : "s") + " without activity. Sign in again."); return; }
    idleWarn(left <= IDLE_WARN_MS ? left : 0);
  }
  function idleStart() {   // a person is signed in: start the clock and read the super admin's number
    idleTouch();
    if (!idleTimer) idleTimer = setInterval(idleTick, 1000);
    if (!can("view_console")) return;                                  // this person may not read the setting: keep the last known number (no refused call)
    adminCall("list", { limit: 1 }, "console_settings").then(function (r) {
      var recs = r.status === 200 && r.body && r.body.ok && r.body.data && r.body.data.records;
      if (!recs) return;                                              // could not read: keep the last known number
      idleMinutes = idleClamp(recs.length ? recs[0].session_timeout_minutes : IDLE_DEFAULT); idleSet(IDLE_MIN, idleMinutes);
    });
  }
  function idleEnd() { idleWarn(0); idleDrop(IDLE_AT); idleLast = Date.now(); }   // locked: forget the old activity time too (a later sign-in must not inherit it)
  ["pointerdown", "keydown", "wheel", "touchstart", "scroll"].forEach(function (ev) {
    document.addEventListener(ev, function () { if (!key) return; idleTouch(); if (idleShown) idleWarn(0); }, { capture: true, passive: true });
  });
  $("idleStay").addEventListener("click", function () { idleTouch(); idleWarn(0); });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) idleTick(); });
  idleStaleAtLoad = idleGet(IDLE_AT) > 0 && Date.now() - idleGet(IDLE_AT) > idleMinutes * 60000;   // a saved session that sat idle past the limit
  function idleStaleMessage() { return "You were signed out after " + idleMinutes + " minute" + (idleMinutes === 1 ? "" : "s") + " without activity. Sign in again."; }

  var saved = getKey();
  if (saved.key && idleStaleAtLoad) { idleStaleAtLoad = false; setKey('', false); idleDrop(IDLE_AT); $("lockMsg").textContent = idleStaleMessage(); show(true); }
  else if (saved.key) { $("rememberBox").checked = saved.remember; unlock(saved.key, saved.remember); } else show(true);
})();
