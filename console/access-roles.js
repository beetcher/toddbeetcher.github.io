/* Access: the Roles tab and the permission list (P-62). Loaded before access.js; access.js hands in what it owns (state, helpers) when it draws.
   A role is a named set of permissions. Roles are never deleted here: "Switch off" keeps the record. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var mk = K.mk, C = null, S = null, root = null, $ = null, btn = null, field = null, input = null, adm = null, ok = null, why = null, load = null, draw = null, toggle = null, sortBy = null;
  function bind(c) { C = c; S = c.S; root = c.root; $ = c.$; btn = c.btn; field = c.field; input = c.input; adm = c.adm; ok = c.ok; why = c.why; load = c.load; draw = c.draw; toggle = c.toggle; sortBy = c.sortBy; }

  // [name, what it allows, territorial?]. Territorial ones apply only inside a person's territory (their grants); global ones come from the role.
  var CAPS = [
    ["view_console", "Open the Console and read the stations the person is allowed to see. Every role needs it.", false],
    ["manage_requests", "Registration requests: view, put in a class, delete a request.", true],
    ["manage_classes", "Scheduled classes and attendance: create, edit, cancel, place people.", true],
    ["manage_curriculums", "Create and edit curriculum records.", false],
    ["manage_instructors", "The instructor roster: add, edit, switch off, add an address.", true],
    ["edit_venues", "Edit venue records (name, contact, hours, rooms, open days) and find GPS.", true],
    ["activate_venues", "Switch a venue on or off, and withdraw Discovery candidates.", true],
    ["edit_people", "The People station (full person records).", true],
    ["edit_places", "The Places station (locations and links).", true],
    ["edit_regions", "Create and edit regions (names and ZIP lists). A whole-state grant may create regions in its state.", true],
    ["view_messages", "Read the Messages station (the send log).", true],
    ["manage_messages", "Edit message wording and settings, add notes, mark handled.", true],
    ["run_discovery", "Start, stop and review Discovery runs (spends money).", true],
    ["invite_people", "Invite people into this territory and manage the people they invited. They get only regions inside this territory, and nothing this person does not hold.", true],
    ["edit_discovery_settings", "Discovery models, areas, types, prompt and limits.", false],
    ["view_spend", "Read the Spend tab.", false],
    ["view_performance", "Performance: open the Performance station (how fast the Console is). Read only.", false],
    ["inspect_everything", "View only: look at everything (private details hidden or masked) and change nothing. May start a Discovery run, capped at 25 cents. For demos.", false]
  ];   // manage_access is deliberately not offered: only a super admin manages access (delegation comes later)
  // Plain names for the permissions. The technical name (the key) is kept for the records and shown only as small grey text.
  var PLAIN = { view_console: "Open the Console", manage_requests: "Manage registration requests", manage_classes: "Manage classes and attendance", manage_curriculums: "Manage curriculum",
    manage_instructors: "Manage instructors", edit_venues: "Edit venues", activate_venues: "Switch venues on and off", edit_people: "Edit people", edit_places: "Edit places",
    edit_regions: "Edit regions", view_messages: "Read messages", manage_messages: "Manage messages", run_discovery: "Run Discovery", invite_people: "Invite people",
    edit_discovery_settings: "Change Discovery settings", view_spend: "See Discovery spending", view_performance: "See Performance", inspect_everything: "View everything (view only)",
    manage_access: "Manage access" };
  function capName(k) { return PLAIN[k] || String(k || "").replace(/_/g, " "); }
  function capNames(list) { return (list || []).map(capName); }
  var TERR = CAPS.filter(function (c) { return c[2]; }).map(function (c) { return c[0]; });

  function roleForm(r) {
    var f = mk("div", "acform"); var editing = !!r, sup = !!(r && r.is_super_admin);
    f.appendChild(mk("h3", "", editing ? "Edit role " + r.label : "Add a role"));
    var key = input("text", "arKey", r ? r.key : ""); if (editing) key.disabled = true;
    f.appendChild(field("Short key (letters, numbers, underscore; cannot change later)", key, "arKey"));
    f.appendChild(field("Name shown in lists", input("text", "arLabel", r ? r.label : ""), "arLabel"));
    var ta = mk("textarea"); ta.id = "arDesc"; ta.rows = 2; ta.value = (r && r.description) || "";
    f.appendChild(field("What this role is for (optional)", ta, "arDesc"));
    if (sup) f.appendChild(mk("p", "acm", "A super admin role holds every permission, now and for any added later. It lists none."));
    else {
      var box = mk("div", "accaps"); var have = (r && r.capabilities) || ["view_console"];
      CAPS.forEach(function (c) {
        var l = mk("label"); var cb = mk("input"); cb.type = "checkbox"; cb.value = c[0]; cb.checked = have.indexOf(c[0]) >= 0; l.appendChild(cb);
        var t = mk("span"); t.appendChild(mk("b", "", capName(c[0]))); t.appendChild(document.createTextNode(" " + c[1])); l.title = "Technical name: " + c[0]; l.appendChild(t); box.appendChild(l);
      });
      f.appendChild(mk("p", "acm", "Some permissions apply everywhere: " + capNames(CAPS.filter(function (c) { return !c[2]; }).map(function (c) { return c[0]; })).join(", ") + ". The others are only the starting choice offered when you give this role a territory; what a person may do in a region comes from their territory."));
      f.appendChild(field("Permissions", box));
    }
    var err = mk("div", "acerr"); err.id = "arErr"; err.setAttribute("role", "alert"); f.appendChild(err);
    var row = mk("div", "acbtns");
    row.appendChild(btn("Save", "", function () {
      var changes = { label: $("arLabel").value.trim(), description: $("arDesc").value.trim() || null };
      if (!sup) changes.capabilities = Array.prototype.map.call(root().querySelectorAll(".accaps input:checked"), function (c) { return c.value; });
      var req = editing ? adm("update", { id: r.id, changes: changes, expected_updated_at: r.updated_at }, "access_roles")
        : adm("create", { data: Object.assign({ key: $("arKey").value.trim(), is_super_admin: false, is_active: true, label: changes.label, capabilities: changes.capabilities }, changes.description ? { description: changes.description } : {}) }, "access_roles");
      req.then(function (res) { if (ok(res)) { S.editR = null; S.addR = false; S.msg = "Saved."; load(); } else err.textContent = why(res); });
    }));
    row.appendChild(btn("Cancel", "quiet", function () { S.editR = null; S.addR = false; draw(); }));
    f.appendChild(row); return f;
  }


  // "Can: A, B, C, D and 9 more" with the full list one click away.
  var SHOW = 4;
  function canLine(ro) {
    if (ro.is_super_admin) return mk("div", "acm", "Can do everything, including managing access.");
    var names = capNames(ro.capabilities), d = mk("div", "acm");
    if (names.length <= SHOW + 1) { d.textContent = "Can: " + (names.join(", ") || "nothing yet"); return d; }
    d.appendChild(document.createTextNode("Can: " + names.slice(0, SHOW).join(", ") + " and " + (names.length - SHOW) + " more "));
    var more = mk("details", "acmore"); more.appendChild(mk("summary", "", "See all " + names.length)); more.appendChild(mk("div", "", names.join(", "))); d.appendChild(more); return d;
  }

  // The Roles tab: the role cards, then the list of what each permission allows.
  function drawRoles(wrap, c) {
    bind(c);
    var h2 = mk("div", "ac1"); h2.appendChild(mk("h2", "", "Roles")); h2.appendChild(btn("Add a role", S.addR || S.editR ? "btn-secondary" : "", function () { S.addR = true; S.editR = null; S.msg = ""; S.rowMsg = null; draw(); })); wrap.appendChild(h2);
    if (S.addR) wrap.appendChild(roleForm(null));
    S.roles.slice().sort(sortBy("label")).forEach(function (ro) {
      if (S.editR === ro.id) { wrap.appendChild(roleForm(ro)); return; }
      var r = mk("div", "acrow" + (ro.is_active ? "" : " off")); var top = mk("div", "ac1");
      var who = mk("div"); who.appendChild(mk("div", "acn", ro.label)); var nm = mk("div", "acn", ro.label); nm.title = "Technical name: " + ro.key; who.removeChild(who.firstChild); who.appendChild(nm); if (ro.description) who.appendChild(mk("div", "acm", ro.description)); top.appendChild(who);
      var chips = mk("div"); if (ro.is_super_admin) chips.appendChild(mk("span", "acchip sup", "Super admin")); chips.appendChild(document.createTextNode(" "));
      chips.appendChild(mk("span", "acchip" + (ro.is_active ? " on" : ""), ro.is_active ? "On" : "Off")); top.appendChild(chips); r.appendChild(top);
      r.appendChild(canLine(ro));
      var b = mk("div", "acbtns"); b.appendChild(btn("Edit", "quiet", function () { S.editR = ro.id; S.addR = false; S.msg = ""; S.rowMsg = null; draw(); })); b.appendChild(toggle("access_roles", ro, "Role")); r.appendChild(b);
      wrap.appendChild(r);
    });
  }
  function drawCaps(wrap, c) {
    bind(c);
    wrap.appendChild(mk("h2", "", "What each permission allows"));
    var t = mk("table"); var hd = mk("tr"); hd.appendChild(mk("th", "", "Permission")); hd.appendChild(mk("th", "", "Allows")); hd.appendChild(mk("th", "", "Applies")); t.appendChild(hd);
    CAPS.concat([["manage_access", "Invite people, change roles, switch access on and off. Super admin only.", false]]).forEach(function (c) { var tr = mk("tr"); var td0 = mk("td"); td0.appendChild(mk("div", "acn", capName(c[0]))); td0.appendChild(mk("code", "ackey", c[0])); tr.appendChild(td0); tr.appendChild(mk("td", "", c[1])); tr.appendChild(mk("td", "", c[2] ? "Inside a person's territory" : "Everywhere (from the role)")); t.appendChild(tr); });
    wrap.appendChild(t);
  }
  window.ConsoleAccessRoles = { CAPS: CAPS, TERR: TERR, capName: capName, capNames: capNames, drawRoles: drawRoles, drawCaps: drawCaps, roleForm: roleForm };
})();
