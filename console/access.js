/* Access station for the Console (P-62 step 5): who may sign in, and what each role may do. Super admin only (the server enforces it:
   every call here needs the manage_access capability). Loaded by index.html after the main script; talks to enjoy_admin through ConsoleKit.
   People are invited by Google email. A person is never deleted here: "Switch off" keeps the record and refuses the next request. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var mk = K.mk, root = null;
  var S = { loaded: false, roles: [], persons: [], areas: [], msg: "", rowMsg: null, editP: null, editR: null, addP: false, addR: false, seq: 0, view: "region", draft: null, cs: { rec: null, msg: "", ok: false }, rv: { st: null, msg: "", good: false } };

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
  var TERR = CAPS.filter(function (c) { return c[2]; }).map(function (c) { return c[0]; });
  var ISSUE = { required: "Required.", duplicate: "That one is already used.", invalid_format: "That value is not valid.", out_of_range: "Too long or too short.",
    invalid_type: "That value is not valid.", invalid_value: "That value is not valid.", not_allowed: "Not allowed.", immutable: "That cannot be changed once it is saved.",
    not_found: "Not found (is it switched on?).", conflict: "Someone changed this while you were editing. Reload and try again.",
    last_super_admin: "That would leave no active super admin.", in_use: "People still hold this role.", not_territorial: "That capability is not one a territory can hold.", wrong_state: "A region must belong to the state of its grant.", duplicate_region: "A region can be in only one grant of the same person.",
    not_enabled: "Email sending is not switched on here.", switched_off: "That person is switched off. Switch them on first." };
  // Why an invitation email did not go, in words (the codes are the CMS's reasons; see CMS_GUIDE.md).
  var MAIL_WHY = { cms_off: "email sending is switched off on the server", log_only: "email is in test mode, so it was only logged", no_template: "the invitation wording has not been added yet",
    adapter_error: "the email service refused it", timeout: "the email service did not answer in time", channel_unavailable: "email is not available", no_contact: "there is no email address",
    incomplete: "the wording is missing a detail", role_not_found: "their role could not be found", internal_error: "something went wrong while sending", duplicate: "it was already sent" };
  function mailWords(inv) { return (inv && MAIL_WHY[inv.reason]) || "the email could not be sent"; }
  function inviteNote(inv, email, added) {   // what to tell the person after an invitation or a resend
    var sent = inv && inv.status === "sent";
    if (added) return sent ? "Added. An invitation email went to " + email + "." : "Added. They can sign in with that Google account, but the invitation email did not go (" + mailWords(inv) + "). Use Resend invite email on their row.";
    return sent ? "Invitation email sent to " + email + "." : "The invitation email did not go (" + mailWords(inv) + ").";
  }
  var FIELD = { email: "Email", display_name: "Name", role_id: "Role", scope_region_id: "Region", grants: "Territory", key: "Key", label: "Name", capabilities: "Capabilities", description: "Description", id: "Record" };

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
      ".acs .acgive{margin-top:6px;font-weight:700}.acs #acReviewShown{font-family:ui-monospace,Menlo,Consolas,monospace;font-weight:800;font-size:1.15rem;color:#1d4ed8;background:#e8eefc;padding:3px 10px;border-radius:6px;user-select:all;overflow-wrap:anywhere}.acs .acerr.acok{color:#2f5d00}.acs .acf input[type=number]{width:140px;box-sizing:border-box;font:inherit;font-size:1.2rem;padding:8px 10px;min-height:44px;border:2px solid #1c1a17;border-radius:8px}.acs .acf input[type=text],.acs .acf input[type=email],.acs .acf select,.acs .acf textarea{width:100%;max-width:560px;box-sizing:border-box;font:inherit;padding:8px;min-height:44px}" +
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


  // ---- territory (grants): P-60. A person holds grants: the whole US, a whole state, or some regions of one state with their own capabilities.
  function areaByKind(kind) { return S.areas.filter(function (a) { return a.kind === kind; }); }
  function stateName(code) { var st = areaByKind("state").filter(function (a) { return a.state_code === code; })[0]; return st ? st.name : (code || "?"); }
  function regionsOf(code) { return areaByKind("region").filter(function (a) { return a.state_code === code; }).sort(sortBy("name")); }
  function roleOf(p) { for (var i = 0; i < S.roles.length; i++) if (S.roles[i].id === p.role_id) return S.roles[i]; return null; }
  function terrOfRole(r) { return ((r && r.capabilities) || []).filter(function (c) { return TERR.indexOf(c) >= 0; }); }
  function legacyGrant(p) {   // the retired single region, counted as one regions grant with the role's territorial capabilities
    var a = null; S.areas.forEach(function (x) { if (x.id === p.scope_region_id && x.kind === "region") a = x; });
    return a ? { kind: "regions", state_code: a.state_code, region_ids: [a.id], capabilities: terrOfRole(roleOf(p)) } : null;
  }
  function grantsOf(p) {   // what the person holds now, as the server reads it
    var r = roleOf(p);
    if (r && r.is_super_admin) return [{ kind: "all" }];
    if (p.grants && p.grants.length) return p.grants;
    var l = p.scope_region_id ? legacyGrant(p) : null; return l ? [l] : [];
  }
  function regionNames(g) { return (g.region_ids || []).map(function (id) { return areaName(id); }).join(", "); }
  function grantText(g) {
    if (g.kind === "all") return "Whole US";
    if (g.kind === "state") return "Whole state: " + stateName(g.state_code);
    return "Regions in " + stateName(g.state_code) + ": " + regionNames(g);
  }
  function viewOnlyRole(role) { return !!(role && !role.is_super_admin && (role.capabilities || []).indexOf("inspect_everything") >= 0); }   // an inspector: sees everywhere, changes nothing
  function titleOf(p, role) {
    if (role && role.is_super_admin) return "Super admin: everywhere";
    if (viewOnlyRole(role)) return "Inspector: sees everything, changes nothing";
    var gl = grantsOf(p), out = [];
    gl.forEach(function (g) {
      if (g.kind === "all") out.push("Whole US");
      else if (g.kind === "state") out.push("State lead: " + stateName(g.state_code));
      else out.push("Region head: " + (g.region_ids || []).length + (((g.region_ids || []).length === 1) ? " region" : " regions") + " in " + stateName(g.state_code));
    });
    return out.length ? out.join(" · ") : "No territory yet";
  }
  // A delegate (someone who holds invite_people but is not a super admin) works only inside their own territory: regions grants, regions they
  // cover, capabilities they hold. The server enforces it; this just keeps the form honest.
  function me() { return K.me() || {}; }
  function isDelegate() { var m = me(); return !!m.name && m.is_super_admin !== true && m.inspector !== true && m.method !== "key"; }
  function invGrants() { return (me().grants || []).filter(function (g) { return (g.capabilities || []).indexOf("invite_people") >= 0; }); }
  function delCovers(a) {
    return invGrants().some(function (g) { return g.kind === "all" || (g.kind === "state" && g.state_code === a.state_code) || (g.kind === "regions" && (g.region_ids || []).indexOf(a.id) >= 0); });
  }
  function delCaps() {
    var out = {}; invGrants().forEach(function (g) { (g.capabilities || []).forEach(function (c) { out[c] = true; }); });
    return TERR.filter(function (c) { return c !== "invite_people" && out[c]; });
  }
  function grantCaps(g) { return g.kind === "regions" ? (g.capabilities || []) : TERR; }
  function copyGrants(list) { return JSON.parse(JSON.stringify(list || [])); }

  function grantsEditor(p, roleSel) {
    var box = mk("div", "acf"); box.id = "agBox";
    var key = p ? p.id : "new";
    if (!S.draft || S.draft.key !== key) S.draft = { key: key, editing: null, grants: p ? copyGrants(p.grants && p.grants.length ? p.grants : (p.scope_region_id && legacyGrant(p) ? [legacyGrant(p)] : [])) : [] };
    function render() {
      box.innerHTML = "";
      box.appendChild(mk("label", "", "Territory"));
      var picked = roleSel && (function () { var r = null; S.roles.forEach(function (x) { if (x.id === roleSel.value) r = x; }); return r; })();
      var sup = picked && picked.is_super_admin;
      if (sup) { box.appendChild(mk("p", "acm", "A super admin works everywhere with every capability. Territory is not needed.")); return; }
      if (viewOnlyRole(picked)) { box.appendChild(mk("p", "acm", "Territory: not needed. A view-only role sees everywhere and changes nothing.")); return; }
      if (!S.draft.grants.length) box.appendChild(mk("p", "acm", "No territory yet: this person can sign in but sees nothing in any region."));
      S.draft.grants.forEach(function (g, i) {
        var row = mk("div", "acgrant"); row.appendChild(mk("b", "", grantText(g) + (g.group ? "  [" + g.group + "]" : "")));
        row.appendChild(mk("div", "acm", g.kind === "regions" ? (g.capabilities || []).join(", ") : "Every capability in " + (g.kind === "all" ? "the whole US" : stateName(g.state_code)) + (g.kind === "state" ? ", including ZIPs no region has claimed (state administrator)." : ".")));
        row.appendChild(btn(S.draft.editing === i ? "Editing below" : "Edit", "quiet", function () { S.draft.editing = i; render(); }));
        row.appendChild(btn("Remove", "quiet", function () { S.draft.grants.splice(i, 1); S.draft.editing = null; render(); }));
        box.appendChild(row);
      });
      var ed = S.draft.editing, eg = ed != null ? S.draft.grants[ed] : null, fresh = !!eg;     // fresh: the form still shows the grant being edited
      var add = mk("div", "acadd"); add.appendChild(mk("b", "", eg ? "Edit this territory" : "Add territory"));
      var DEL = isDelegate();
      var kind = select("agKind", DEL ? [["regions", "Some regions in a state"]] : [["regions", "Some regions in a state"], ["state", "A whole state (state administrator)"], ["all", "The whole US"]], eg ? eg.kind : "regions");
      var states = areaByKind("state").sort(sortBy("name")).filter(function (a) { return !DEL || regionsOf(a.state_code).some(delCovers); }).map(function (a) { return [a.state_code, a.name]; });
      var st = select("agState", states, eg && eg.state_code ? eg.state_code : (states[0] || [""])[0]);
      var regionBox = mk("div", "accaps"); var capBox = mk("div", "accaps"); var copy = select("agCopy", [["", "Start from this role's defaults"]].concat(S.draft.grants.map(function (g, i) { return g.kind === "regions" ? [String(i), "Copy from: " + grantText(g)] : null; }).filter(Boolean)), "");
      var group = input("text", "agGroup", eg && eg.group ? eg.group : ""); group.placeholder = "Label for the list (optional), such as Wisconsin team";
      var err = mk("div", "acerr"); err.id = "agErr"; err.setAttribute("role", "alert");
      var used = {}; S.draft.grants.forEach(function (g, gi) { if (gi === ed) return; (g.region_ids || []).forEach(function (id) { used[id] = true; }); });
      function roleCaps() { var r = null; if (roleSel) S.roles.forEach(function (x) { if (x.id === roleSel.value) r = x; }); return terrOfRole(r); }
      function fillRegions() {
        regionBox.innerHTML = "";
        regionsOf(st.value).filter(function (a) { return !DEL || delCovers(a); }).forEach(function (a) {
          var l = mk("label"), cb = mk("input"); cb.type = "checkbox"; cb.value = a.id; cb.disabled = !!used[a.id]; cb.checked = !!(fresh && eg.region_ids && eg.state_code === st.value && eg.region_ids.indexOf(a.id) >= 0); l.appendChild(cb);
          l.appendChild(mk("span", "", " " + a.name + (used[a.id] ? " (already in a grant)" : ""))); regionBox.appendChild(l);
        });
        if (!regionBox.firstChild) regionBox.appendChild(mk("span", "acm", "This state has no regions yet."));
      }
      function fillCaps() {
        var have = fresh && eg.capabilities ? eg.capabilities : copy.value !== "" ? (S.draft.grants[+copy.value].capabilities || []) : roleCaps();
        capBox.innerHTML = "";
        (DEL ? delCaps() : TERR).forEach(function (c) { var l = mk("label"), cb = mk("input"); cb.type = "checkbox"; cb.value = c; cb.checked = have.indexOf(c) >= 0; l.appendChild(cb); l.appendChild(mk("span", "", " " + c)); capBox.appendChild(l); });
      }
      function show() {
        var k = kind.value; st.parentNode.hidden = k === "all"; regionBox.parentNode.hidden = k !== "regions"; capBox.parentNode.hidden = k !== "regions"; copy.parentNode.hidden = k !== "regions";
      }
      kind.addEventListener("change", show); st.addEventListener("change", function () { fresh = false; fillRegions(); }); copy.addEventListener("change", function () { fresh = false; fillCaps(); });
      add.appendChild(field("What kind", kind, "agKind")); add.appendChild(field("State", st, "agState"));
      add.appendChild(field("Regions", regionBox)); add.appendChild(field("Capabilities in these regions (to give two regions different capabilities, add them one grant at a time)", copy, "agCopy"));
      add.lastChild.appendChild(capBox);
      add.appendChild(field("Label", group, "agGroup")); add.appendChild(err);
      add.appendChild(btn(eg ? "Save this territory" : "Add this territory", "quiet", function () {
        var k = kind.value, g = { kind: k };
        if (k !== "all") g.state_code = st.value;
        if (k === "regions") {
          g.region_ids = Array.prototype.map.call(regionBox.querySelectorAll("input:checked"), function (c) { return c.value; });
          g.capabilities = Array.prototype.map.call(capBox.querySelectorAll("input:checked"), function (c) { return c.value; });
          if (!g.region_ids.length) { err.textContent = "Pick at least one region."; return; }
          if (!g.capabilities.length) { err.textContent = "Pick at least one capability."; return; }
        } else if (k === "state" && S.draft.grants.some(function (x) { return x.kind === "state" && x.state_code === g.state_code && S.draft.grants.indexOf(x) !== ed; })) { err.textContent = "That state is already added."; return; }
        else if (k === "all" && S.draft.grants.some(function (x) { return x.kind === "all" && S.draft.grants.indexOf(x) !== ed; })) { err.textContent = "The whole US is already added."; return; }
        if (group.value.trim()) g.group = group.value.trim();
        if (ed != null) { S.draft.grants[ed] = g; S.draft.editing = null; } else S.draft.grants.push(g);
        render();
      }));
      if (eg) add.appendChild(btn("Cancel editing", "quiet", function () { S.draft.editing = null; render(); }));
      box.appendChild(add); fillRegions(); fillCaps(); show();
    }
    if (roleSel) roleSel.addEventListener("change", render);
    render(); return box;
  }
  function cleanGrants(list) { return (list || []).map(function (g) { var o = { kind: g.kind }; ["state_code", "region_ids", "capabilities", "group"].forEach(function (k) { if (g[k] != null && g[k] !== "" && !(Array.isArray(g[k]) && !g[k].length)) o[k] = g[k]; }); return o; }); }

  function personForm(p) {
    var f = mk("div", "acform"); var editing = !!p;
    f.appendChild(mk("h3", "", editing ? "Edit " + (p.display_name || p.email) : "Invite someone"));
    var email = input("email", "apEmail", p ? p.email : ""); if (editing && p.google_uid) { email.disabled = true; }
    f.appendChild(field("Google email (the account they sign in with)", email, "apEmail"));
    f.appendChild(field("Name (optional)", input("text", "apName", p ? p.display_name : ""), "apName"));
    var roles = S.roles.filter(function (r) { return r.is_active || (p && p.role_id === r.id); }).sort(sortBy("label")).map(function (r) { return [r.id, r.label + (r.is_super_admin ? " (super admin)" : "")]; });
    var lost = p && !roles.some(function (r) { return r[0] === p.role_id; });     // never fall back silently to the first role in the list
    if (lost) roles.unshift(["", "(role not found: choose one)"]);
    f.appendChild(field("Role (what they can do everywhere; their territory is set below)", select("apRole", roles, p ? (lost ? "" : p.role_id) : (roles[0] || [""])[0]), "apRole"));
    f.appendChild(grantsEditor(p, f.querySelector("#apRole")));
    var err = mk("div", "acerr"); err.id = "apErr"; err.setAttribute("role", "alert"); f.appendChild(err);
    var row = mk("div", "acbtns");
    row.appendChild(btn(editing ? "Save" : "Send invitation", "", function () {
      var name = $("apName").value.trim(), gr = cleanGrants(S.draft ? S.draft.grants : []);
      var changes = { display_name: name || null, role_id: $("apRole").value, grants: gr.length ? gr : null };
      if (editing && p.scope_region_id) changes.scope_region_id = null;   // the retired single region is replaced by grants
      var req = editing
        ? adm("update", { id: p.id, changes: changes, expected_updated_at: p.updated_at }, "access_persons")
        : adm("create", { data: Object.assign({ email: $("apEmail").value.trim(), role_id: $("apRole").value, is_active: true }, name ? { display_name: name } : {}, gr.length ? { grants: gr } : {}) }, "access_persons");
      req.then(function (res) { if (ok(res)) { S.editP = null; S.addP = false; S.draft = null; S.msg = editing ? "Saved." : inviteNote(res.body.data && res.body.data.invite_email, res.body.data && res.body.data.email, true); load(); } else err.textContent = why(res); });
    }));
    row.appendChild(btn("Cancel", "quiet", function () { S.editP = null; S.addP = false; S.draft = null; draw(); }));
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
      f.appendChild(mk("p", "acm", "Global capabilities (view_console, manage_curriculums, edit_discovery_settings, view_spend, view_performance, inspect_everything) apply everywhere. The others are only the starting choice offered when you give this role territory; what a person may do in a region comes from their territory."));
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


  // ---- the two views of the same grants: by region (rows = places) and by capability (rows = what people may do)
  function whoName(p) { return p.display_name || p.email; }
  function territoryView(wrap) {
    var h = mk("div", "ac1"); h.appendChild(mk("h2", "", "Who works where"));
    var tabs = mk("div", "acbtns");
    [["region", "By region"], ["capability", "By capability"]].forEach(function (t) { tabs.appendChild(btn(t[1], S.view === t[0] ? "" : "quiet", function () { S.view = t[0]; draw(); })); });
    h.appendChild(tabs); wrap.appendChild(h);
    var live = S.persons.filter(function (p) { return p.is_active; });
    var holders = function (test) { var out = []; live.forEach(function (p) { var r = roleOf(p); if (r && r.is_super_admin) { out.push({ p: p, caps: TERR, why: "super admin" }); return; }
      grantsOf(p).forEach(function (g) { var res = test(g); if (res) out.push({ p: p, caps: grantCaps(g), why: res }); }); }); return out; };
    var box = mk("div", "acterr"); box.id = "acTerr";
    if (S.view === "region") {
      var allU = holders(function (g) { return g.kind === "all" ? "whole US" : null; });
      box.appendChild(mk("div", "acm", "Whole US: " + (allU.length ? allU.map(function (h) { return whoName(h.p); }).join(", ") : "nobody")));
      areaByKind("state").sort(sortBy("name")).forEach(function (stA) {
        var d = mk("details"); d.open = false; var sm = mk("summary", "", stA.name); d.appendChild(sm);
        var admins = holders(function (g) { return g.kind === "state" && g.state_code === stA.state_code ? "state" : null; }).filter(function (h) { return h.why !== "super admin"; });
        d.appendChild(mk("div", "acm", "State administrators (every region and every ZIP, including ZIPs in no region): " + (admins.length ? admins.map(function (h) { return whoName(h.p); }).join(", ") : "nobody")));
        regionsOf(stA.state_code).forEach(function (rg) {
          var row = mk("div", "acrow"); row.appendChild(mk("div", "acn", rg.name + "  (" + ((rg.zip_codes || []).length) + " ZIPs)"));
          var hs = holders(function (g) { return g.kind === "regions" && (g.region_ids || []).indexOf(rg.id) >= 0 ? "region" : null; }).filter(function (h) { return h.why !== "super admin"; });
          if (!hs.length) row.appendChild(mk("div", "acm", "No one is given this region by name."));
          hs.forEach(function (h) { row.appendChild(mk("div", "acm", whoName(h.p) + ": " + h.caps.join(", "))); });
          d.appendChild(row);
        });
        if (!regionsOf(stA.state_code).length) d.appendChild(mk("div", "acm", "No regions in this state yet."));
        box.appendChild(d);
      });
    } else {
      TERR.forEach(function (c) {
        var d = mk("details"); d.appendChild(mk("summary", "", c));
        var found = 0;
        live.forEach(function (p) { var r = roleOf(p), where = [];
          if (r && r.is_super_admin) where.push("everywhere");
          else grantsOf(p).forEach(function (g) { if (grantCaps(g).indexOf(c) < 0) return; where.push(g.kind === "all" ? "whole US" : g.kind === "state" ? "all of " + stateName(g.state_code) : regionNames(g) + " (" + g.state_code + ")"); });
          if (where.length) { found++; d.appendChild(mk("div", "acm", whoName(p) + ": " + where.join("; "))); } });
        if (!found) d.appendChild(mk("div", "acm", "No one holds this."));
        box.appendChild(d);
      });
    }
    wrap.appendChild(box);
  }

  function toggle(coll, rec, label) {
    return btn(rec.is_active ? "Switch off" : "Switch on", "quiet", function () {
      adm("update", { id: rec.id, changes: { is_active: !rec.is_active }, expected_updated_at: rec.updated_at }, coll).then(function (res) {
        S.rowMsg = null; S.msg = ok(res) ? label + (rec.is_active ? " switched off." : " switched on.") : why(res); load();
      });
    });
  }

  function draw() {
    if (!root) return;
    root.innerHTML = ""; var wrap = mk("div", "acs"); root.appendChild(wrap);
    wrap.appendChild(mk("h2", "", "Access"));
    wrap.appendChild(mk("p", "acm", "Who may sign in with Google, and what each role may do. The admin key still works as a back door."));
    var msg = mk("div", "acerr" + (/^Added\. An invitation email went/.test(S.msg) ? " acok" : ""), S.msg); msg.setAttribute("role", "status"); wrap.appendChild(msg);

    if (!isDelegate()) { wrap.appendChild(signInBox()); var rb = reviewBox(); if (rb) wrap.appendChild(rb); }
    var h = mk("div", "ac1"); h.appendChild(mk("h2", "", "People")); h.appendChild(btn("Invite someone", "", function () { S.addP = true; S.editP = null; S.msg = ""; S.rowMsg = null; draw(); })); wrap.appendChild(h);
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
      var bits = [];
      bits.push(p.last_sign_in_at ? "Last signed in " + K.when(p.last_sign_in_at) : "Has not signed in yet");
      r.appendChild(mk("div", "acm", bits.join(" · ")));
      r.appendChild(mk("div", "acm actitle", "Title (from their territory): " + titleOf(p, role)));
      var gl = grantsOf(p);
      if (role && role.is_super_admin) r.appendChild(mk("div", "acm", "Territory: everywhere."));
      else if (viewOnlyRole(role)) r.appendChild(mk("div", "acm", "Territory: not needed. A view-only role sees everywhere and changes nothing."));
      else if (!gl.length) r.appendChild(mk("div", "acm", "Territory: none yet (signs in, sees nothing in any region)."));
      else gl.forEach(function (g) { r.appendChild(mk("div", "acm acg", "Territory: " + grantText(g) + (g.group ? "  [" + g.group + "]" : "") + (!(p.grants && p.grants.length) ? "  (from the old single-region setting; Edit then Save to convert)" : ""))); });
      var b = mk("div", "acbtns"); b.appendChild(btn("Edit", "quiet", function () { S.editP = p.id; S.addP = false; S.msg = ""; S.rowMsg = null; draw(); })); b.appendChild(toggle("access_persons", p, "Access"));
      if (p.is_active) b.appendChild(btn("Resend invite email", "quiet", function () {
        adm("send_invite", { id: p.id }, "access_persons").then(function (res) {   // the answer shows on THIS person's row, where the button was pressed
          S.msg = ""; S.rowMsg = { id: p.id, good: ok(res) && res.body.data && res.body.data.status === "sent", text: ok(res) ? inviteNote(res.body.data, p.email, false) : why(res) }; draw();
        });
      }));
      r.appendChild(b);
      if (S.rowMsg && S.rowMsg.id === p.id) { var rm = mk("div", "acerr acrowmsg" + (S.rowMsg.good ? " acok" : ""), S.rowMsg.text); rm.setAttribute("role", "status"); r.appendChild(rm); }
      wrap.appendChild(r);
    });
    if (!S.persons.length) wrap.appendChild(mk("p", "acm", "No one yet."));

    if (isDelegate()) { wrap.appendChild(mk("p", "acm", "You can invite people into your own regions and manage the people you invited. Roles and anything outside your regions are looked after by a super admin.")); return; }
    territoryView(wrap);

    var h2 = mk("div", "ac1"); h2.appendChild(mk("h2", "", "Roles")); h2.appendChild(btn("Add a role", "", function () { S.addR = true; S.editR = null; S.msg = ""; S.rowMsg = null; draw(); })); wrap.appendChild(h2);
    if (S.addR) wrap.appendChild(roleForm(null));
    S.roles.slice().sort(sortBy("label")).forEach(function (ro) {
      if (S.editR === ro.id) { wrap.appendChild(roleForm(ro)); return; }
      var r = mk("div", "acrow" + (ro.is_active ? "" : " off")); var top = mk("div", "ac1");
      var who = mk("div"); who.appendChild(mk("div", "acn", ro.label)); who.appendChild(mk("div", "acm", ro.key + (ro.description ? " · " + ro.description : ""))); top.appendChild(who);
      var chips = mk("div"); if (ro.is_super_admin) chips.appendChild(mk("span", "acchip sup", "Super admin")); chips.appendChild(document.createTextNode(" "));
      chips.appendChild(mk("span", "acchip" + (ro.is_active ? " on" : ""), ro.is_active ? "On" : "Off")); top.appendChild(chips); r.appendChild(top);
      r.appendChild(mk("div", "acm", ro.is_super_admin ? "Everything, including access." : (ro.capabilities || []).join(", ")));
      var b = mk("div", "acbtns"); b.appendChild(btn("Edit", "quiet", function () { S.editR = ro.id; S.addR = false; S.msg = ""; S.rowMsg = null; draw(); })); b.appendChild(toggle("access_roles", ro, "Role")); r.appendChild(b);
      wrap.appendChild(r);
    });

    wrap.appendChild(mk("h2", "", "What each capability allows"));
    var t = mk("table"); var hd = mk("tr"); hd.appendChild(mk("th", "", "Capability")); hd.appendChild(mk("th", "", "Allows")); hd.appendChild(mk("th", "", "Applies")); t.appendChild(hd);
    CAPS.concat([["manage_access", "Invite people, change roles, switch access on and off. Super admin only.", false]]).forEach(function (c) { var tr = mk("tr"); tr.appendChild(mk("td", "", c[0])); tr.appendChild(mk("td", "", c[1])); tr.appendChild(mk("td", "", c[2] ? "Inside a person's territory" : "Everywhere (from the role)")); t.appendChild(tr); });
    wrap.appendChild(t);
  }

  // ---- Sign-in box: how long the Console waits before it signs a person out (console_setting.session_timeout_minutes). Super admin only.
  // The page that holds the timer is index.html; ConsoleKit.sessionMinutes applies a saved number to this window at once, other windows
  // take it the next time they sign in or reload.
  function signInBox() {
    var rec = S.cs.rec, mins = rec ? rec.session_timeout_minutes : K.sessionMinutes();
    var box = mk("div", "acform"); box.id = "acSignIn";
    box.appendChild(mk("h2", "", "Sign-in"));
    box.appendChild(mk("p", "acm", "Sign people out of the Console after this many minutes without a click, key press, scroll or touch. Everyone is held to the same number. A Discovery run in progress counts as activity."));
    var f = mk("div", "acf"); var l = mk("label", "", "Minutes of inactivity before sign-out (1 to 480)"); l.htmlFor = "acMinutes";
    var i = mk("input"); i.type = "number"; i.id = "acMinutes"; i.min = "1"; i.max = "480"; i.step = "1"; i.value = String(mins); i.setAttribute("inputmode", "numeric");
    f.appendChild(l); f.appendChild(i); box.appendChild(f);
    if (!rec && S.cs.ok) box.appendChild(mk("p", "acm", "Not set yet, so the Console uses 10 minutes."));
    if (!S.cs.ok && S.loaded) box.appendChild(mk("p", "acm", "The current setting could not be read. Saving will still work."));
    var save = btn("Save minutes", "", function () { saveMinutes(i.value); }); save.id = "acMinutesSave"; box.appendChild(save);
    var m = mk("div", /^Saved/.test(S.cs.msg || "") ? "acerr acok" : "acerr", S.cs.msg); m.id = "acMinutesMsg"; m.setAttribute("role", "status"); box.appendChild(m);
    return box;
  }
  function saveMinutes(raw) {
    var t = String(raw).trim();
    if (!/^\d{1,3}$/.test(t) || +t < 1 || +t > 480) { S.cs.msg = "Enter a whole number of minutes from 1 to 480."; draw(); return Promise.resolve(); }
    var n = +t, rec = S.cs.rec;
    var call = rec ? adm("update", { id: rec.id, changes: { session_timeout_minutes: n }, expected_updated_at: rec.updated_at }, "console_settings")
                   : adm("create", { data: { session_timeout_minutes: n } }, "console_settings");
    return call.then(function (res) {
      if (!ok(res)) {
        var code = res.body && res.body.error && res.body.error.code;
        S.cs.msg = res.status === 403 ? "Only a super admin may change this." : code === "conflict" ? "Someone changed this while you were editing. Reload and try again." : why(res);
        draw(); return;
      }
      return adm("list", { limit: 1 }, "console_settings").then(function (r2) {
        S.cs.rec = recs(r2)[0] || null; S.cs.ok = ok(r2);
        K.sessionMinutes(n);
        S.cs.msg = "Saved: " + n + " minute" + (n === 1 ? "" : "s") + ". This window uses it now; every other Console window takes it the next time it signs in or reloads.";
        draw();
      });
    });
  }

  // ---- Review access code (REVIEW_CODE_GUIDE.md): ONE temporary view-only code a super admin sets for a reviewer. 24 hours; a new code replaces the old one.
  // The server keeps only a hash, so the code is shown once, in the message after it is set. The box appears only when the server lets this person read the status (super admin).
  var REVIEW_WHY = { too_short: "Use at least 8 characters.", too_long: "Use 64 characters at most.", bad_characters: "Use letters, numbers, spaces and punctuation only.",
    looks_like_a_token: "That looks like a sign-in token. Use a plain phrase.", same_as_the_admin_key: "That is the admin key. Use a different phrase." };
  function mountain(stamp) {
    var d = new Date(stamp); if (isNaN(d.getTime())) return String(stamp || "");
    try { return d.toLocaleString("en-US", { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/Denver" }) + " Mountain"; } catch (e) { return d.toString(); }
  }
  function reviewBox() {
    var st = S.rv.st; if (!st) return null;
    var box = mk("div", "acform"); box.id = "acReview";
    box.appendChild(mk("h2", "", "Review access code"));
    box.appendChild(mk("p", "acm", "Lets one reviewer look at everything for 24 hours. It is view only: they can open every screen but change nothing, and private contact details stay hidden. They type the code into the Key box on the sign-in screen. A new code replaces the old one and starts the 24 hours again. Only one code works at a time."));
    var line = mk("p", "acm", st.active ? "A code is active until " + mountain(st.expires_at) + "." : "No code is active."); line.id = "acReviewStatus"; box.appendChild(line);
    var f = mk("div", "acf"); var l = mk("label", "", "New code (8 to 64 characters; spaces are fine)"); l.htmlFor = "acReviewCode";
    var i = mk("input"); i.type = "text"; i.id = "acReviewCode"; i.maxLength = 64; i.autocomplete = "off"; i.autocapitalize = "off"; i.spellcheck = false;
    f.appendChild(l); f.appendChild(i); box.appendChild(f);
    var save = btn("Set code (24 hours)", "", function () { saveReviewCode(i.value); }); save.id = "acReviewSave"; box.appendChild(save);
    var m = mk("div", S.rv.good ? "acerr acok" : "acerr", S.rv.msg); m.id = "acReviewMsg"; m.setAttribute("role", "status"); box.appendChild(m);
    if (S.rv.good && S.rv.code) {      // the code itself, on its own line, easy to see and to select
      var g = mk("div", "acgive"); g.appendChild(mk("span", "acgivel", "Give them exactly this: ")); var cs = mk("span", "", S.rv.code); cs.id = "acReviewShown"; g.appendChild(cs); box.appendChild(g);
    }
    return box;
  }
  function saveReviewCode(raw) {
    var code = String(raw || "").trim();
    if (code.length < 8) { S.rv.msg = REVIEW_WHY.too_short; S.rv.good = false; S.rv.code = ""; draw(); return Promise.resolve(); }
    return adm("set_review_code", { code: code }, "console_settings").then(function (res) {
      if (!ok(res)) {
        var p = res.body && res.body.error && res.body.error.problems;
        S.rv.msg = res.status === 403 ? "Only a super admin may set this." : (p && p.length && REVIEW_WHY[p[0].issue]) || (res.status === 429 ? "Too many tries. Wait a few minutes." : "Could not set the code. Try again.");
        S.rv.good = false; S.rv.code = ""; draw(); return;
      }
      return loadReviewStatus().then(function () {
        S.rv.msg = "Code set. It lasts until " + mountain(res.body.data.expires_at) + " and cannot be shown again. Any earlier code no longer works.";
        S.rv.code = code; S.rv.good = true; draw();
      });
    });
  }
  function loadReviewStatus() {      // only a super admin (or the admin key) may read it, so nobody else is even asked: no refused call, no box
    var m = me(); if (m.is_super_admin !== true || m.inspector === true) { S.rv.st = null; return Promise.resolve(); }
    return adm("review_code_status", {}, "console_settings").then(function (res) { S.rv.st = ok(res) && res.body.data ? res.body.data : null; });
  }

  function load() {
    var my = ++S.seq;
    return Promise.all([adm("list", { limit: 200 }, "access_roles"), adm("list", { limit: 200 }, "access_persons"), adm("list", { limit: 200 }, "discovery_areas"), adm("list", { limit: 1 }, "console_settings")]).then(function (all) {
      if (my !== S.seq) return;
      S.cs.ok = ok(all[3]); S.cs.rec = ok(all[3]) ? (recs(all[3])[0] || null) : null;
      if (!ok(all[0]) || !ok(all[1])) { S.msg = why(!ok(all[0]) ? all[0] : all[1]); } else { S.roles = recs(all[0]); S.persons = recs(all[1]); S.areas = recs(all[2]); S.loaded = true; }
      draw();
      return loadReviewStatus().then(function () { if (my === S.seq) draw(); });
    });
  }

  window.AccessStation = {
    show: function () { style(); root = $("accessView"); draw(); load(); },
    reset: function () { S = { loaded: false, roles: [], persons: [], areas: [], msg: "", rowMsg: null, editP: null, editR: null, addP: false, addR: false, seq: S.seq + 1, view: "region", draft: null, cs: { rec: null, msg: "", ok: false }, rv: { st: null, msg: "", good: false } }; var v = $("accessView"); if (v) v.innerHTML = ""; root = null; }
  };
})();
