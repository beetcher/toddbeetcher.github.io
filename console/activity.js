/* Activity station for the Console (P-46): who changed what, and when. Read-only. Super admin only (the server enforces it: the activity log is
   readable by a super admin and nobody else). Loaded by index.html after the main script; talks to enjoy_admin through ConsoleKit.
   Every entry is written by the server in the same step as the change it records. Personal values are never in an entry: a personal field
   is shown as changed, with its values marked "not recorded". */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var mk = K.mk, root = null, COLL = "activity_events", MAXN = 200;

  // The server takes ONE filter. Everything else (the search box) narrows what came back.
  var S = { checked: "", mode: "all", value: "", recId: "", recLabel: "", records: [], loaded: false, busy: false, msg: "", q: "", seq: 0, pending: null, openIds: {}, names: {}, tried: {}, allNames: false };

  var TYPES = [["venue", "Venue"], ["scheduled_class", "Class"], ["registration_request", "Registration request"], ["individual", "Person"],
    ["location", "Place"], ["instructor_roster", "Instructor"], ["student_roster", "Student"], ["attendance", "Attendance"], ["organization", "Organization"],
    ["curriculum", "Curriculum"], ["registration_assignment", "Assignment"], ["location_link", "Place link"], ["organization_link", "Organization link"],
    ["transaction_record", "Payment record"], ["merge_event", "Merge"], ["message_template", "Message wording"], ["comms_setting", "Message setting"],
    ["access_person", "Access person"], ["access_role", "Access role"], ["discovery_area", "Discovery area"], ["discovery_model", "Discovery model"],
    ["discovery_type", "Discovery type"], ["discovery_prompt", "Discovery prompt"], ["discovery_setting", "Discovery setting"], ["console_setting", "Console setting"], ["individual_restricted_detail", "Sensitive details"]];
  var ACTIONS = [["created", "Created"], ["edited", "Edited"], ["deleted", "Deleted"], ["restored", "Restored"]];
  var MODES = [["all", "Everything"], ["record_type", "One kind of record"], ["action", "One kind of change"], ["created_by", "One person or source"]];
  var VERB = { created: "Created", edited: "Edited", deleted: "Deleted", restored: "Restored" };

  function $(id) { return document.getElementById(id); }
  function ok(res) { return res.status === 200 && res.body && res.body.ok; }
  function typeName(t) { for (var i = 0; i < TYPES.length; i++) if (TYPES[i][0] === t) return TYPES[i][1]; return String(t || "").replace(/_/g, " "); }
  function human(f) { var s = String(f || "").replace(/_/g, " "); return s.charAt(0).toUpperCase() + s.slice(1); }
  // Plain names for the engine's field names (anything not listed here is the name with spaces: "Home phone").
  var LABELS = { found_at: "Found on", allows_minors: "Open to under 18", has_wifi: "Wi-Fi", is_accessible: "Accessible", is_public_venue: "Public venue",
    postal_code: "ZIP code", website_url: "Website", model_name: "AI model", prompt_version: "Prompt version", run_id: "Run", time_zone: "Time zone", is_active: "Switched on",
    role_id: "Role", display_name: "Name", given_name: "First name", family_name: "Last name", name_to_use: "Name to use", scope_region_id: "Region", state_code: "State",
    region_ids: "Regions", capabilities: "Can do", is_super_admin: "Super admin", record_label: "Name", expected_updated_at: "Version", created_by: "Created by",
    updated_by: "Updated by", deleted_by: "Deleted by", decided_by: "Decided by", handled_by: "Handled by", published_by: "Published by", unmerged_by: "Unmerged by",
    withdrawn_by: "Withdrawn by", google_uid: "Google sign-in", last_sign_in_at: "Last sign-in", session_timeout_minutes: "Sign-out minutes", zip_codes: "ZIP codes",
    zips: "ZIP codes", lat: "Latitude", lng: "Longitude", venue_id: "Venue", class_id: "Class", location_id: "Place", organization_id: "Organization" };
  function fieldLabel(f) { return LABELS[f] || human(f); }

  // Fields that hold who did something. Their values are actors (user:<id>, user:admin, web:enjoy ...) and are shown as names.
  var ACTOR_FIELDS = { created_by: 1, updated_by: 1, deleted_by: 1, decided_by: 1, handled_by: 1, published_by: 1, unmerged_by: 1, withdrawn_by: 1 };

  // A signed-in person is stored as user:<person id>. Not the admin key.
  function personId(a) { a = String(a || ""); return a.indexOf("user:") === 0 && a !== "user:admin" ? a.slice(5) : ""; }

  // user:admin -> "Admin key", web:enjoy -> "Website form", system:x -> "System (x)", user:<id> -> that person's name,
  // or the user id itself when no name can be found (never a role, never a vague label).
  function actorName(a) {
    a = String(a || "");
    if (a === "user:admin") return "Admin key";
    if (a === "web:enjoy") return "Website form";
    if (a === "web:completion") return "Completion link";
    if (a === "system:unattributed") return "Automatic job";
    var i = a.indexOf(":"); if (i < 0) return a || "Unknown";
    var kind = a.slice(0, i), rest = a.slice(i + 1);
    if (kind === "user") return S.names[rest] || rest;
    return kind === "system" ? "Automatic job (" + rest.replace(/_/g, " ") + ")" : kind === "web" ? "Website (" + rest.replace(/_/g, " ") + ")" : rest;
  }

  // The stored actor for a name typed in the "Person or source" box: a person's name (or part of an id), "Admin key", "Website form" ...
  function actorId(typed) {
    var t = String(typed || "").trim(); if (!t) return "";
    if (t.indexOf(":") >= 0) return t;
    var low = t.toLowerCase(), fixed = { "admin key": "user:admin", "website form": "web:enjoy", "completion link": "web:completion" };
    if (fixed[low]) return fixed[low];
    var hits = nameHits(low);
    return hits.length === 1 ? "user:" + hits[0] : t;
  }
  function nameHits(low) { return Object.keys(S.names).filter(function (id) { return String(S.names[id]).toLowerCase() === low; }); }

  // Every person actor in what came back that we have not yet tried to name.
  function unknownPeople(records) {
    var seen = {};
    (records || []).forEach(function (e) {
      [e.created_by].concat((e.changes || []).filter(function (c) { return ACTOR_FIELDS[c.field]; }).reduce(function (a, c) { return a.concat([jsonStr(c.old_value), jsonStr(c.new_value)]); }, []))
        .forEach(function (a) { var id = personId(a); if (id && !S.names[id] && !S.tried[id]) seen[id] = 1; });
    });
    return Object.keys(seen);
  }
  function jsonStr(t) { try { var v = JSON.parse(t); return typeof v === "string" ? v : ""; } catch (e) { return ""; } }

  // Look up the names of the people in the entries on screen (one call, only when some are not known yet). A failure leaves the ids showing.
  function nameThem(records) {
    var need = unknownPeople(records); if (!need.length) return Promise.resolve(false);
    need.forEach(function (id) { S.tried[id] = 1; });
    return fetchNames();
  }
  function fetchNames() {
    return K.admin("list", { limit: 200 }, "access_persons").then(function (res) {
      if (!ok(res)) return false;
      var rows = (res.body.data && res.body.data.records) || [], got = false;
      rows.forEach(function (p) { if (p && p.id && p.display_name && String(p.display_name).trim()) { S.names[p.id] = String(p.display_name).trim(); got = true; } });
      return got;
    }, function () { return false; });
  }

  // A value is stored as JSON text. Show it the way a person would write it.
  function valueText(text) {
    if (text == null) return "(empty)";
    var v;
    try { v = JSON.parse(text); } catch (e) { return String(text) + "…"; }     // cut in the middle: the text is not whole JSON
    if (v === null || v === "") return "(empty)";
    if (typeof v === "string") return /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(v) ? K.when(v) : v;
    if (typeof v === "boolean") return v ? "Yes" : "No";
    if (typeof v === "number") return String(v);
    if (Array.isArray(v)) return v.length ? v.map(function (x) { return typeof x === "object" ? JSON.stringify(x) : String(x); }).join(", ") : "(empty list)";
    return JSON.stringify(v);
  }

  function btn(text, cls, fn) { var b = mk("button", cls === "quiet" ? "btn-secondary" : cls || "", text); b.type = "button"; b.addEventListener("click", fn); return b; }
  function field(label, input, id) { var d = mk("div", "avf"); var l = mk("label", "", label); if (id) l.htmlFor = id; d.appendChild(l); d.appendChild(input); return d; }
  function select(id, opts, val) {
    var s = mk("select"); s.id = id;
    opts.forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; s.appendChild(op); });
    s.value = val || opts[0][0]; return s;
  }

  function serverFilter() {
    if (S.recId) return { related_ids: S.recId };
    if (S.mode !== "all" && S.value) { var f = {}; f[S.mode] = S.mode === "created_by" ? actorId(S.value) : S.value; return f; }
    return {};
  }

  function matches(e, q) {
    if (!q) return true;
    var hay = [e.record_label, typeName(e.record_type), e.record_type, e.action, actorName(e.created_by), e.created_by, e.record_id];
    (e.changes || []).forEach(function (c) { hay.push(c.field, human(c.field), c.old_value, c.new_value); });
    return hay.join(" \n ").toLowerCase().indexOf(q) >= 0;
  }

  // A list with more than a handful of items reads "59 ZIP codes" with a Show all link; an object reads as "label: value" pairs.
  var LONG = 6;
  function listNoun(field, n) { var f = String(field || ""); return /zip|postal/i.test(f) ? (n === 1 ? "ZIP code" : "ZIP codes") : /region/i.test(f) ? (n === 1 ? "region" : "regions") : /capab/i.test(f) ? (n === 1 ? "permission" : "permissions") : (n === 1 ? "item" : "items"); }
  function pairs(o) { return Object.keys(o).map(function (k) { var v = o[k]; return fieldLabel(k) + ": " + (v && typeof v === "object" ? (Array.isArray(v) ? v.join(", ") : pairs(v)) : v === true ? "Yes" : v === false ? "No" : v == null || v === "" ? "(empty)" : String(v)); }).join("; "); }
  function changeValue(c, text) {
    if (ACTOR_FIELDS[c.field]) { var a = jsonStr(text); if (a) return document.createTextNode(actorName(a)); }
    var v; try { v = text == null ? null : JSON.parse(text); } catch (e) { v = undefined; }
    if (Array.isArray(v) && v.length > LONG && v.every(function (x) { return typeof x !== "object" || x === null; })) {
      var span = mk("span"), sum = mk("span", "", v.length + " " + listNoun(c.field, v.length) + " "), full = mk("span", "avm", v.join(", ")); full.hidden = true;
      var b = btn("Show all", "quiet avlink", function () { full.hidden = !full.hidden; b.textContent = full.hidden ? "Show all" : "Hide"; });
      span.appendChild(sum); span.appendChild(b); span.appendChild(full); return span;
    }
    if (v && typeof v === "object" && !Array.isArray(v)) return document.createTextNode(pairs(v));
    if (Array.isArray(v) && v.length && v.some(function (x) { return x && typeof x === "object"; })) return document.createTextNode(v.map(function (x) { return x && typeof x === "object" ? pairs(x) : String(x); }).join(" | "));
    return document.createTextNode(valueText(text));
  }

  function changeLine(e, c) {
    var li = mk("li"); li.appendChild(mk("span", "avfield", fieldLabel(c.field) + ": "));
    if (c.values_withheld) { li.appendChild(mk("span", "avw", "changed (personal details are not recorded)")); return li; }
    var hasOld = c.old_value != null, hasNew = c.new_value != null;
    function val(cls, t) { var sp = mk("span", cls); sp.appendChild(changeValue(c, t)); return sp; }
    if (e.action === "created" || !hasOld) { li.appendChild(val("avnew", c.new_value)); }
    else if (!hasNew) { li.appendChild(val("avold", c.old_value)); li.appendChild(document.createTextNode(" → removed")); }
    else { li.appendChild(mk("span", "avsr", "was ")); li.appendChild(val("avold", c.old_value)); li.appendChild(document.createTextNode(" → now ")); li.appendChild(val("avnew", c.new_value)); }
    if (c.truncated) li.appendChild(mk("span", "avm", " (long value, cut short)"));
    return li;
  }

  // The "what" line: a short sentence in plain words. Small edits show the change itself; bigger ones name the fields and fold the rest under Details.
  function whatLine(e) {
    var ch = e.changes || [], names = ch.map(function (c) { return fieldLabel(c.field); });
    var priv = ch.some(function (c) { return c.values_withheld; });
    if (e.action === "deleted") return "Moved out of use";
    if (e.action === "restored") return "Put back in use";
    var head = e.action === "created" ? "Created with " + ch.length + " field" + (ch.length === 1 ? "" : "s") : "Changed " + names.slice(0, 3).join(", ") + (names.length > 3 ? " and " + (names.length - 3) + " more" : "");
    return ch.length ? head + (priv ? ". Personal details are not recorded." : "") : head;
  }

  function entryCard(e) {
    var r = mk("div", "avrow"); var top = mk("div", "av1");
    var left = mk("div"); left.appendChild(mk("div", "avwho", typeName(e.record_type) + (e.record_label ? " · " + e.record_label : "")));
    var by = mk("div", "avm", K.when(e.created_at) + " · " + actorName(e.created_by) + (e.record_label ? "" : " · Record without a name")); by.title = String(e.created_by || "") + (e.record_label ? "" : " · " + String(e.record_id)); left.appendChild(by); top.appendChild(left);
    var right = mk("div", "avbtns"); right.appendChild(mk("span", "avchip " + e.action, VERB[e.action] || e.action)); right.appendChild(document.createTextNode(" "));
    right.appendChild(btn("Change history", "quiet", function () { openFor(e.record_id, e.record_label || typeName(e.record_type)); })); top.appendChild(right); r.appendChild(top);
    var ch = e.changes || [], small = (e.action === "edited" || e.action === "deleted" || e.action === "restored") && ch.length <= 2;
    r.appendChild(mk("div", "avwhat", whatLine(e)));
    if (small) { var ul = mk("ul", "avch"); ch.forEach(function (c) { ul.appendChild(changeLine(e, c)); }); r.appendChild(ul); }
    else if (ch.length) {
      var d = mk("details"); d.appendChild(mk("summary", "avm", "Details (" + ch.length + " field" + (ch.length === 1 ? "" : "s") + (e.fields_omitted ? ", " + e.fields_omitted + " more not listed" : "") + ")"));
      var built = false; if (S.openIds[e.id]) d.open = true;
      function build() { if (built || !d.open) return; built = true; var ul2 = mk("ul", "avch"); ch.forEach(function (c) { ul2.appendChild(changeLine(e, c)); }); d.appendChild(ul2); }
      d.addEventListener("toggle", function () { S.openIds[e.id] = d.open; build(); }); build(); r.appendChild(d);
    }
    return r;
  }

  function valueControl() {
    if (S.mode === "record_type") { var t = select("avValue", [["", "Choose…"]].concat(TYPES), S.value); t.addEventListener("change", function () { S.value = t.value; load(); }); return field("Kind of record", t, "avValue"); }
    if (S.mode === "action") { var a = select("avValue", [["", "Choose…"]].concat(ACTIONS), S.value); a.addEventListener("change", function () { S.value = a.value; load(); }); return field("Kind of change", a, "avValue"); }
    var i = mk("input"); i.type = "text"; i.id = "avValue"; i.value = S.value; i.placeholder = "a person's name, Admin key or Website form"; i.autocomplete = "off";
    i.addEventListener("keydown", function (ev) { if (ev.key === "Enter") { S.value = i.value.trim(); load(); } });
    var f = field("Person or source (press Enter)", i, "avValue"); return f;
  }

  function draw() {
    if (!root) return;
    var keepQ = document.activeElement && document.activeElement.id === "avSearch";
    root.textContent = "";
    var wrap = mk("div", "acv");
    var hd = mk("div", "bar phead"), pt = mk("div", "ptext"); pt.appendChild(mk("h2", "ptitle", "Activity"));
    var count = mk("div", "count"); count.id = "avCount"; pt.appendChild(count);
    var chk = mk("div", "meta"); chk.id = "avChecked"; chk.textContent = S.checked ? "Last checked " + S.checked : ""; pt.appendChild(chk);
    hd.appendChild(pt); var ac = mk("div", "actions"); ac.appendChild(btn("Refresh", "btn-secondary", function () { load(); })); hd.appendChild(ac); wrap.appendChild(hd);
    wrap.appendChild(mk("p", "avm", "Every change made in the Console, newest first. Nothing here can be edited."));
    if (S.recId) {
      var fo = mk("div", "avfocus"); fo.appendChild(mk("span", "", "History of " + (S.recLabel || "one record")));
      fo.appendChild(btn("Show everything", "quiet", function () { S.recId = ""; S.recLabel = ""; load(); })); wrap.appendChild(fo);
    } else {
      var bar = mk("div", "avbar"); var m = select("avMode", MODES, S.mode);
      m.addEventListener("change", function () { S.mode = m.value; S.value = ""; if (S.mode === "all") load(); else draw(); });
      bar.appendChild(field("Show", m, "avMode"));
      if (S.mode !== "all") bar.appendChild(valueControl());
      wrap.appendChild(bar);
    }
    var sb = mk("div", "avbar"); var q = mk("input"); q.type = "search"; q.id = "avSearch"; q.value = S.q; q.placeholder = "Search what is shown"; q.autocomplete = "off";
    q.addEventListener("input", function () { S.q = q.value; list(); });
    sb.appendChild(field("Search", q, "avSearch")); wrap.appendChild(sb);
    wrap.appendChild(mk("div", "avmsg", S.msg)); var role = wrap.lastChild; role.setAttribute("role", "alert");
    var host = mk("div"); host.id = "avList"; wrap.appendChild(host);
    root.appendChild(wrap);
    list();
    if (keepQ) { try { q.focus(); q.setSelectionRange(q.value.length, q.value.length); } catch (e) {} }
  }

  function list() {
    var host = $("avList"), count = $("avCount"); if (!host) return;
    host.textContent = "";
    var q = S.q.trim().toLowerCase(), shown = S.records.filter(function (e) { return matches(e, q); });
    if (S.busy && !S.loaded) { count.textContent = "Loading…"; return; }
    if (!S.loaded) { count.textContent = ""; return; }
    count.textContent = shown.length + (q ? " of " + S.records.length : "") + " entr" + (shown.length === 1 ? "y" : "ies") + (S.records.length >= MAXN ? " (the newest " + MAXN + " are loaded)" : "");
    if (!shown.length) { host.appendChild(mk("div", "avm", q ? "Nothing matches that search." : "Nothing has been recorded here yet.")); return; }
    shown.forEach(function (e) { host.appendChild(entryCard(e)); });
  }

  function why(res) {
    if (res.status === 403) return "Only a super admin may read the activity log.";
    if (res.status === 429) return "Too many tries. Wait a few minutes.";
    if (res.status === 0) return "Could not reach the server.";
    return "Something went wrong. Try again.";
  }

  function load() {
    var my = ++S.seq; S.busy = true; S.msg = "";
    if (S.mode !== "all" && !S.recId && !S.value) { S.records = []; S.loaded = true; S.busy = false; draw(); return Promise.resolve(); }
    draw();
    // Typing a person's name in "Person or source": we need the names before we can turn it into the stored id.
    var pre = (S.mode === "created_by" && !S.recId && S.value && S.value.indexOf(":") < 0 && !S.allNames) ? (S.allNames = true, fetchNames()) : Promise.resolve(false);
    return pre.then(function () {
      if (S.mode === "created_by" && !S.recId && S.value && S.value.indexOf(":") < 0 && nameHits(S.value.trim().toLowerCase()).length > 1) S.msg = "More than one person has that name. Type the user id instead.";
      return K.admin("list", { filters: serverFilter(), order: "-created_at", limit: MAXN }, COLL);
    }).then(function (res) {
      if (my !== S.seq) return;
      S.busy = false;
      if (!ok(res)) { S.msg = why(res); S.records = []; S.loaded = true; }
      else { S.records = (res.body.data && res.body.data.records) || []; S.loaded = true; S.checked = K.clock(new Date()); }
      draw();
      if (S.records.length) return nameThem(S.records).then(function (got) { if (got && my === S.seq) draw(); });
    });
  }

  // Called from the History button on a card (and on an entry): the station opens on that one record.
  function openFor(id, label) {
    S.pending = { id: id, label: label || "" };
    K.go("activity");
  }

  function show() {
    root = $("activityView");
    if (S.pending) { S.recId = S.pending.id; S.recLabel = S.pending.label; S.mode = "all"; S.value = ""; S.q = ""; S.pending = null; }
    S.loaded = false; load();
  }

  window.ActivityStation = {
    show: show, openFor: openFor,
    reset: function () { S = { checked: "", mode: "all", value: "", recId: "", recLabel: "", records: [], loaded: false, busy: false, msg: "", q: "", seq: S.seq + 1, pending: null, openIds: {}, names: {}, tried: {}, allNames: false }; var v = $("activityView"); if (v) v.innerHTML = ""; root = null; }
  };
})();
