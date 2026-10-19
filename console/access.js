/* Access station for the Console (P-62 step 5): who may sign in, and what each role may do. Super admin only (the server enforces it:
   every call here needs the manage_access capability). Loaded by index.html after the main script; talks to enjoy_admin through ConsoleKit.
   People are invited by Google email. A person is never deleted here: "Switch off" keeps the record and refuses the next request. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var mk = K.mk, root = null;
  var S = { loaded: false, roles: [], persons: [], areas: [], msg: "", editP: null, editR: null, addP: false, addR: false, seq: 0 };

  var CAPS = [
    ["view_console", "Open the Console and read the stations the person is allowed to see. Every role needs it."],
    ["manage_requests", "Registration requests: view, put in a class, delete a request."],
    ["manage_classes", "Scheduled classes and attendance: create, edit, cancel, place people."],
    ["manage_curriculums", "Create and edit curriculum records."],
    ["manage_instructors", "The instructor roster: add, edit, switch off, add an address."],
    ["edit_venues", "Edit venue records (name, contact, hours, rooms, open days) and find GPS."],
    ["activate_venues", "Switch a venue on or off, and withdraw Discovery candidates."],
    ["edit_people", "The People station (full person records)."],
    ["edit_places", "The Places station (locations and links)."],
    ["view_messages", "Read the Messages station (the send log)."],
    ["manage_messages", "Edit message wording and settings, add notes, mark handled."],
    ["run_discovery", "Start, stop and review Discovery runs (spends money)."],
    ["edit_discovery_settings", "Discovery models, areas, types, prompt and limits."],
    ["view_spend", "Read the Spend tab."]
  ];   // manage_access is deliberately not offered: only a super admin manages access (delegation comes later)
  var ISSUE = { required: "Required.", duplicate: "That one is already used.", invalid_format: "That value is not valid.", out_of_range: "Too long or too short.",
    invalid_type: "That value is not valid.", invalid_value: "That value is not valid.", not_allowed: "Not allowed.", immutable: "That cannot be changed once it is saved.",
    not_found: "Not found (is it switched on?).", conflict: "Someone changed this while you were editing. Reload and try again.",
    last_super_admin: "That would leave no active super admin.", in_use: "People still hold this role." };
  var FIELD = { email: "Email", display_name: "Name", role_id: "Role", scope_region_id: "Region", key: "Key", label: "Name", capabilities: "Capabilities", description: "Description", id: "Record" };

  function $(id) { return document.getElementById(id); }
  function ok(res) { return res.status === 200 && res.body && res.body.ok; }
  function adm(op, args, coll) { return K.admin(op, args, coll); }
  function recs(res) { return (ok(res) && res.body.data && res.body.data.records) || []; }
  function why(res) {
    if (res.status === 403) return "Only a super admin may change access.";
    if (res.status === 429) return "Too many tries. Wait a few minutes.";
    if (res.status === 0) return "Could not reach the server.";
    var e = res.body && res.body.error, p = e && e.problems;
    if (p && p.length) return p.map(function (x) { return (FIELD[x.field] || x.field) + ": " + (ISSUE[x.issue] || x.issue); }).join(" ");
    return "Something went wrong. Try again.";
  }
  function roleName(id) { for (var i = 0; i < S.roles.length; i++) if (S.roles[i].id === id) return S.roles[i].label; return "(missing role)"; }
  function areaName(id) { for (var i = 0; i < S.areas.length; i++) if (S.areas[i].id === id) return S.areas[i].name; return id ? "(missing region)" : ""; }
  function sortBy(f) { return function (a, b) { return String(a[f] || "").toLowerCase() < String(b[f] || "").toLowerCase() ? -1 : 1; }; }

  function style() {
    if ($("accessStyle")) return;
    var s = document.createElement("style"); s.id = "accessStyle";
    s.textContent = ".acs{max-width:900px;margin:0 auto}.acs h2{margin:18px 0 6px}.acs .acrow{border:1px solid #d8d2c4;border-radius:10px;padding:10px 12px;margin:8px 0;background:#fff}" +
      ".acs .acrow.off{opacity:.62}.acs .ac1{display:flex;gap:8px;flex-wrap:wrap;align-items:center;justify-content:space-between}.acs .acn{font-weight:700}.acs .acm{font-size:14px;color:var(--muted)}" +
      ".acs .acform{border:2px solid var(--orange);border-radius:10px;padding:12px;margin:10px 0;background:#fffaf0}.acs .acf{margin:10px 0}.acs .acf label{display:block;font-weight:700;margin-bottom:2px}" +
      ".acs .acf input[type=text],.acs .acf input[type=email],.acs .acf select,.acs .acf textarea{width:100%;max-width:560px;box-sizing:border-box;font:inherit;padding:8px;min-height:44px}" +
      ".acs .accaps{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:4px}.acs .accaps label{font-weight:400;display:flex;gap:8px;align-items:flex-start}" +
      ".acs .acerr{color:var(--err);font-weight:600;min-height:1.4em}.acs table{border-collapse:collapse;width:100%;font-size:14px}.acs td,.acs th{border-bottom:1px solid #e4dfd2;text-align:left;padding:5px 6px;vertical-align:top}" +
      ".acs td:first-child{white-space:nowrap;font-family:ui-monospace,Menlo,Consolas,monospace}.acs .acchip{display:inline-block;border-radius:999px;padding:1px 10px;font-size:13px;font-weight:700;border:1px solid #bbb;background:#f2efe6}" +
      ".acs .acchip.on{background:#d9f2c4;border-color:#5c9a00;color:#1d4d00}.acs .acchip.sup{background:#ffe9b3;border-color:#c98a00;color:#6a4500}.acs .acbtns{display:flex;gap:6px;flex-wrap:wrap}";
    document.head.appendChild(s);
  }

  function field(label, input, id) { var d = mk("div", "acf"); var l = mk("label", "", label); if (id) l.htmlFor = id; d.appendChild(l); d.appendChild(input); return d; }
  function input(type, id, val) { var i = mk("input"); i.type = type; i.id = id; i.value = val || ""; i.autocomplete = "off"; return i; }
  function select(id, opts, val) {
    var s = mk("select"); s.id = id;
    opts.forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; s.appendChild(op); });
    s.value = val || ""; return s;
  }
  function btn(text, cls, fn) { var b = mk("button", cls || "", text); b.type = "button"; b.addEventListener("click", fn); return b; }

  function personForm(p) {
    var f = mk("div", "acform"); var editing = !!p;
    f.appendChild(mk("h3", "", editing ? "Edit " + (p.display_name || p.email) : "Invite someone"));
    var email = input("email", "apEmail", p ? p.email : ""); if (editing && p.google_uid) { email.disabled = true; }
    f.appendChild(field("Google email (the account they sign in with)", email, "apEmail"));
    f.appendChild(field("Name (optional)", input("text", "apName", p ? p.display_name : ""), "apName"));
    var roles = S.roles.filter(function (r) { return r.is_active || (p && p.role_id === r.id); }).sort(sortBy("label")).map(function (r) { return [r.id, r.label + (r.is_super_admin ? " (super admin)" : "")]; });
    f.appendChild(field("Role", select("apRole", roles, p ? p.role_id : (roles[0] || [""])[0]), "apRole"));
    var regs = [["", "None (not limited to a region)"]].concat(S.areas.filter(function (a) { return a.kind === "region"; }).sort(sortBy("name")).map(function (a) { return [a.id, a.name + (a.state_code ? ", " + a.state_code : "")]; }));
    f.appendChild(field("Region (saved now; limits are enforced when region territory is built)", select("apRegion", regs, p ? p.scope_region_id : ""), "apRegion"));
    var err = mk("div", "acerr"); err.id = "apErr"; err.setAttribute("role", "alert"); f.appendChild(err);
    var row = mk("div", "acbtns");
    row.appendChild(btn(editing ? "Save" : "Send invitation", "", function () {
      var name = $("apName").value.trim(), reg = $("apRegion").value;
      var req = editing
        ? adm("update", { id: p.id, changes: { display_name: name || null, role_id: $("apRole").value, scope_region_id: reg || null }, expected_updated_at: p.updated_at }, "access_persons")
        : adm("create", { data: Object.assign({ email: $("apEmail").value.trim(), role_id: $("apRole").value, is_active: true }, name ? { display_name: name } : {}, reg ? { scope_region_id: reg } : {}) }, "access_persons");
      req.then(function (res) { if (ok(res)) { S.editP = null; S.addP = false; S.msg = editing ? "Saved." : "Added. They can sign in with that Google account now."; load(); } else err.textContent = why(res); });
    }));
    row.appendChild(btn("Cancel", "quiet", function () { S.editP = null; S.addP = false; draw(); }));
    f.appendChild(row); return f;
  }

  function roleForm(r) {
    var f = mk("div", "acform"); var editing = !!r, sup = !!(r && r.is_super_admin);
    f.appendChild(mk("h3", "", editing ? "Edit role " + r.label : "Add a role"));
    var key = input("text", "arKey", r ? r.key : ""); if (editing) key.disabled = true;
    f.appendChild(field("Short key (letters, numbers, underscore; cannot change later)", key, "arKey"));
    f.appendChild(field("Name shown in lists", input("text", "arLabel", r ? r.label : ""), "arLabel"));
    var ta = mk("textarea"); ta.id = "arDesc"; ta.rows = 2; ta.value = (r && r.description) || "";
    f.appendChild(field("What this role is for (optional)", ta, "arDesc"));
    if (sup) f.appendChild(mk("p", "acm", "A super admin role holds every capability, now and for any added later. It lists none."));
    else {
      var box = mk("div", "accaps"); var have = (r && r.capabilities) || ["view_console"];
      CAPS.forEach(function (c) {
        var l = mk("label"); var cb = mk("input"); cb.type = "checkbox"; cb.value = c[0]; cb.checked = have.indexOf(c[0]) >= 0; l.appendChild(cb);
        var t = mk("span"); t.appendChild(mk("b", "", c[0])); t.appendChild(document.createTextNode(" " + c[1])); l.appendChild(t); box.appendChild(l);
      });
      f.appendChild(field("Capabilities", box));
    }
    var err = mk("div", "acerr"); err.id = "arErr"; err.setAttribute("role", "alert"); f.appendChild(err);
    var row = mk("div", "acbtns");
    row.appendChild(btn("Save", "", function () {
      var changes = { label: $("arLabel").value.trim(), description: $("arDesc").value.trim() || null };
      if (!sup) changes.capabilities = Array.prototype.map.call(root.querySelectorAll(".accaps input:checked"), function (c) { return c.value; });
      var req = editing ? adm("update", { id: r.id, changes: changes, expected_updated_at: r.updated_at }, "access_roles")
        : adm("create", { data: Object.assign({ key: $("arKey").value.trim(), is_super_admin: false, is_active: true, label: changes.label, capabilities: changes.capabilities }, changes.description ? { description: changes.description } : {}) }, "access_roles");
      req.then(function (res) { if (ok(res)) { S.editR = null; S.addR = false; S.msg = "Saved."; load(); } else err.textContent = why(res); });
    }));
    row.appendChild(btn("Cancel", "quiet", function () { S.editR = null; S.addR = false; draw(); }));
    f.appendChild(row); return f;
  }

  function toggle(coll, rec, label) {
    return btn(rec.is_active ? "Switch off" : "Switch on", "quiet", function () {
      adm("update", { id: rec.id, changes: { is_active: !rec.is_active }, expected_updated_at: rec.updated_at }, coll).then(function (res) {
        S.msg = ok(res) ? label + (rec.is_active ? " switched off." : " switched on.") : why(res); load();
      });
    });
  }

  function draw() {
    if (!root) return;
    root.innerHTML = ""; var wrap = mk("div", "acs"); root.appendChild(wrap);
    wrap.appendChild(mk("h2", "", "Access"));
    wrap.appendChild(mk("p", "acm", "Who may sign in with Google, and what each role may do. The admin key still works as a back door."));
    var msg = mk("div", "acerr", S.msg); msg.setAttribute("role", "status"); wrap.appendChild(msg);

    var h = mk("div", "ac1"); h.appendChild(mk("h2", "", "People")); h.appendChild(btn("Invite someone", "", function () { S.addP = true; S.editP = null; S.msg = ""; draw(); })); wrap.appendChild(h);
    if (S.addP) wrap.appendChild(personForm(null));
    S.persons.slice().sort(sortBy("email")).forEach(function (p) {
      if (S.editP === p.id) { wrap.appendChild(personForm(p)); return; }
      var r = mk("div", "acrow" + (p.is_active ? "" : " off")); var top = mk("div", "ac1");
      var who = mk("div"); who.appendChild(mk("div", "acn", p.display_name || p.email)); who.appendChild(mk("div", "acm", p.display_name ? p.email : ""));
      top.appendChild(who);
      var chips = mk("div"); var role = null; S.roles.forEach(function (x) { if (x.id === p.role_id) role = x; });
      chips.appendChild(mk("span", "acchip" + (role && role.is_super_admin ? " sup" : ""), roleName(p.role_id)));
      chips.appendChild(document.createTextNode(" ")); chips.appendChild(mk("span", "acchip" + (p.is_active ? " on" : ""), p.is_active ? "On" : "Off"));
      top.appendChild(chips); r.appendChild(top);
      var bits = []; if (p.scope_region_id) bits.push("Region: " + areaName(p.scope_region_id));
      bits.push(p.last_sign_in_at ? "Last signed in " + K.when(p.last_sign_in_at) : "Has not signed in yet");
      r.appendChild(mk("div", "acm", bits.join(" · ")));
      var b = mk("div", "acbtns"); b.appendChild(btn("Edit", "quiet", function () { S.editP = p.id; S.addP = false; S.msg = ""; draw(); })); b.appendChild(toggle("access_persons", p, "Access")); r.appendChild(b);
      wrap.appendChild(r);
    });
    if (!S.persons.length) wrap.appendChild(mk("p", "acm", "No one yet."));

    var h2 = mk("div", "ac1"); h2.appendChild(mk("h2", "", "Roles")); h2.appendChild(btn("Add a role", "", function () { S.addR = true; S.editR = null; S.msg = ""; draw(); })); wrap.appendChild(h2);
    if (S.addR) wrap.appendChild(roleForm(null));
    S.roles.slice().sort(sortBy("label")).forEach(function (ro) {
      if (S.editR === ro.id) { wrap.appendChild(roleForm(ro)); return; }
      var r = mk("div", "acrow" + (ro.is_active ? "" : " off")); var top = mk("div", "ac1");
      var who = mk("div"); who.appendChild(mk("div", "acn", ro.label)); who.appendChild(mk("div", "acm", ro.key + (ro.description ? " · " + ro.description : ""))); top.appendChild(who);
      var chips = mk("div"); if (ro.is_super_admin) chips.appendChild(mk("span", "acchip sup", "Super admin")); chips.appendChild(document.createTextNode(" "));
      chips.appendChild(mk("span", "acchip" + (ro.is_active ? " on" : ""), ro.is_active ? "On" : "Off")); top.appendChild(chips); r.appendChild(top);
      r.appendChild(mk("div", "acm", ro.is_super_admin ? "Everything, including access." : (ro.capabilities || []).join(", ")));
      var b = mk("div", "acbtns"); b.appendChild(btn("Edit", "quiet", function () { S.editR = ro.id; S.addR = false; S.msg = ""; draw(); })); b.appendChild(toggle("access_roles", ro, "Role")); r.appendChild(b);
      wrap.appendChild(r);
    });

    wrap.appendChild(mk("h2", "", "What each capability allows"));
    var t = mk("table"); var hd = mk("tr"); hd.appendChild(mk("th", "", "Capability")); hd.appendChild(mk("th", "", "Allows")); t.appendChild(hd);
    CAPS.concat([["manage_access", "Invite people, change roles, switch access on and off. Super admin only."]]).forEach(function (c) { var tr = mk("tr"); tr.appendChild(mk("td", "", c[0])); tr.appendChild(mk("td", "", c[1])); t.appendChild(tr); });
    wrap.appendChild(t);
  }

  function load() {
    var my = ++S.seq;
    return Promise.all([adm("list", { limit: 200 }, "access_roles"), adm("list", { limit: 200 }, "access_persons"), adm("list", { limit: 200 }, "discovery_areas")]).then(function (all) {
      if (my !== S.seq) return;
      if (!ok(all[0]) || !ok(all[1])) { S.msg = why(!ok(all[0]) ? all[0] : all[1]); } else { S.roles = recs(all[0]); S.persons = recs(all[1]); S.areas = recs(all[2]); S.loaded = true; }
      draw();
    });
  }

  window.AccessStation = {
    show: function () { style(); root = $("accessView"); draw(); load(); },
    reset: function () { S = { loaded: false, roles: [], persons: [], areas: [], msg: "", editP: null, editR: null, addP: false, addR: false, seq: S.seq + 1 }; var v = $("accessView"); if (v) v.innerHTML = ""; root = null; }
  };
})();
