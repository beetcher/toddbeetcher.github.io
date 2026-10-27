/* Activity station for the Console (P-46): who changed what, and when. Read-only. Super admin only (the server enforces it: the activity log is
   readable by a super admin and nobody else). Loaded by index.html after the main script; talks to enjoy_admin through ConsoleKit.
   Every entry is written by the server in the same step as the change it records. Personal values are never in an entry: a personal field
   is shown as changed, with its values marked "not recorded". */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var mk = K.mk, root = null, COLL = "activity_events", MAXN = 50;   // one page; "Load 50 more" asks the server for entries older than the last one shown

  // The server takes ONE filter. Everything else (the search box) narrows what came back.
  var S = freshState(0);

  var TYPES = [["venue", "Venue"], ["scheduled_class", "Class"], ["registration_request", "Registration request"], ["individual", "Person"],
    ["location", "Place"], ["instructor_roster", "Instructor"], ["student_roster", "Student"], ["attendance", "Attendance"], ["organization", "Organization"],
    ["curriculum", "Curriculum"], ["registration_assignment", "Assignment"], ["location_link", "Place link"], ["organization_link", "Organization link"],
    ["transaction_record", "Payment record"], ["merge_event", "Merge"], ["message_template", "Message wording"], ["comms_setting", "Message setting"],
    ["access_person", "Access person"], ["access_role", "Access role"], ["discovery_area", "Discovery area"], ["discovery_model", "Discovery model"],
    ["discovery_type", "Discovery type"], ["discovery_prompt", "Discovery prompt"], ["discovery_setting", "Discovery setting"], ["console_setting", "Console setting"], ["individual_restricted_detail", "Sensitive details"]];
  var ACTIONS = [["created", "Created"], ["edited", "Edited"], ["deleted", "Deleted"], ["restored", "Restored"]];
  // What the chips offer. The server takes one filter, so the page narrows the entries it has loaded; the kinds of record are grouped for people.
  var GROUPS = [["all", "Everything"], ["requests", "Requests"], ["classes", "Classes"], ["people", "People"], ["places", "Venues and places"], ["access", "Access"], ["other", "Other"]];
  var GROUP_OF = { registration_request: "requests", registration_assignment: "requests", transaction_record: "requests", scheduled_class: "classes", attendance: "classes", curriculum: "classes",
    individual: "people", individual_restricted_detail: "people", merge_event: "people", instructor_roster: "people", student_roster: "people", organization: "people", organization_link: "people",
    venue: "places", location: "places", location_link: "places", access_person: "access", access_role: "access", console_setting: "access" };
  // Where a kind of record is worked on, for "Open Venues". The link goes to the station; each station finds the record itself.
  var STATION = { venue: ["venues", "Venues"], scheduled_class: ["classes", "Classes"], registration_request: ["requests", "Requests"], individual: ["people", "People"], location: ["places", "Places"],
    instructor_roster: ["instructors", "Instructors"], student_roster: ["students", "Students"], organization: ["organizations", "Organizations"], curriculum: ["curriculums", "Curriculum"],
    access_person: ["access", "Access"], access_role: ["access", "Access"], attendance: ["attendance", "Attendance"] };
  function groupOf(t) { return GROUP_OF[t] || "other"; }
  var WHENS = [["any", "Any time"], ["today", "Today"], ["d7", "Last 7 days"], ["d30", "Last 30 days"]];
  function freshState(seq) { return { checked: "", recId: "", recLabel: "", records: [], more: false, marker: null, paging: false, loaded: false, busy: false, msg: "", q: "", seq: seq, pending: null, openIds: {}, names: {}, tried: {}, sel: null, cf: null }; }
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

  function serverFilter() { return S.recId ? { related_ids: S.recId } : {}; }

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
    var st = STATION[e.record_type];
    if (st && !S.recId) { var open = mk("a", "btn-link avopen", "Open " + st[1]); open.href = "#/" + st[0]; open.setAttribute("aria-label", "Open " + st[1] + " (" + typeName(e.record_type) + (e.record_label ? " " + e.record_label : "") + ")"); right.appendChild(open); }
    right.appendChild(btn("Change history", "btn-link avhist", function () { openFor(e.record_id, e.record_label || typeName(e.record_type)); })); top.appendChild(right); r.appendChild(top);
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

  // ---- the chips: What (grouped kinds), Change, When, Who. They narrow the entries already loaded; the choice lives in the address.
  function dayStart(d) { var x = new Date(d); x.setHours(0, 0, 0, 0); return x; }
  function sinceFor(w) { var n = new Date(); return w === "today" ? dayStart(n) : w === "d7" ? new Date(n.getTime() - 7 * 864e5) : w === "d30" ? new Date(n.getTime() - 30 * 864e5) : null; }
  function selNow() { var g = S.cf ? S.cf.getSelection() : null; if (g) S.sel = g; return S.sel || { kind: ["all"], change: ACTIONS.map(function (a) { return a[0]; }), when: ["any"] }; }
  function chipMatch(e, g, since) {
    if (g.kind && g.kind[0] && g.kind[0] !== "all" && groupOf(e.record_type) !== g.kind[0]) return false;
    if (g.change && g.change.indexOf(e.action) < 0) return false;
    if (since && !(new Date(e.created_at) >= since)) return false;
    if (g.who && g.who.length < whoOptions().length && g.who.indexOf(String(e.created_by || "")) < 0) return false;
    return true;
  }
  function whoOptions() {
    var seen = {}, out = []; S.records.forEach(function (e) { var a = String(e.created_by || ""); if (a && !seen[a]) { seen[a] = 1; out.push({ value: a, label: actorName(a) }); } });
    var n = {}; out.forEach(function (o) { n[o.label] = (n[o.label] || 0) + 1; });
    out.forEach(function (o) { if (n[o.label] > 1) o.label += " (ends " + String(o.value).slice(-4) + ")"; });   // two people with one name stay two choices
    return out.sort(function (x, y) { return x.label.toLowerCase() < y.label.toLowerCase() ? -1 : 1; });
  }
  function syncHash() {
    if (S.recId) return;
    var g = selNow(), q = {};
    if (g.kind && g.kind[0] !== "all") q.kind = g.kind[0];
    if (g.change && g.change.length < ACTIONS.length) q.change = g.change.join(",");
    if (g.when && g.when[0] !== "any") q.when = g.when[0];
    if (g.who && g.who.length && g.who.length < whoOptions().length) q.who = g.who.join(",");
    if (S.q.trim()) q.q = S.q.trim();
    K.setHash("activity", q);
  }
  function readHash() {
    var h = K.hash(); if (h.route !== "activity") return;
    var q = h.query, sel = { kind: [q.kind && GROUP_OF && GROUPS.some(function (x) { return x[0] === q.kind; }) ? q.kind : "all"], when: [WHENS.some(function (x) { return x[0] === q.when; }) ? q.when : "any"] };
    sel.change = q.change ? q.change.split(",").filter(function (v) { return ACTIONS.some(function (a) { return a[0] === v; }); }) : ACTIONS.map(function (a) { return a[0]; });
    if (q.who) sel.who = q.who.split(",");
    S.sel = sel; S.q = q.q || "";
  }
  function buildChips(mount) {
    if (S.cf) { try { S.cf.destroy(); } catch (e) {} }
    var keep = S.sel, wn = whoOptions().length;
    if (keep && keep.who && S.whoN != null && keep.who.length >= S.whoN) { keep = Object.assign({}, keep); delete keep.who; }   // "everyone" stays everyone when new people appear in the entries
    S.whoN = wn;
    S.cf = UI.chipFilters({
      mount: mount, label: "Activity filters",
      filters: [
        { id: "kind", label: "What", kind: "one", options: GROUPS.map(function (x) { return { value: x[0], label: x[1] }; }) },
        { id: "change", label: "Change", kind: "multi", options: ACTIONS.map(function (a) { return { value: a[0], label: a[1] }; }) },
        { id: "when", label: "When", kind: "one", options: WHENS.map(function (x) { return { value: x[0], label: x[1] }; }) },
        { id: "who", label: "Who", kind: "search-multi", options: whoOptions() }
      ],
      onChange: function () { selNow(); syncHash(); list(); }
    });
    if (keep) { var set = { kind: keep.kind, change: keep.change, when: keep.when }; if (keep.who) set.who = keep.who; S.cf.setSelection(set); }
  }

  // ---- bursts: one source making the same kind of change over and over (a Discovery run, the time zone fix-up) folds into one line.
  var BURST_MIN = 3, BURST_GAP = 60000;
  function sameRun(a, b) { return a.created_by === b.created_by && a.action === b.action && a.record_type === b.record_type && Math.abs(new Date(a.created_at) - new Date(b.created_at)) <= BURST_GAP; }
  function foldBursts(entries) {
    var out = [], i = 0;
    while (i < entries.length) {
      var j = i + 1; while (j < entries.length && sameRun(entries[j - 1], entries[j])) j++;
      if (j - i >= BURST_MIN) out.push({ burst: entries.slice(i, j) }); else for (var k = i; k < j; k++) out.push(entries[k]);
      i = j;
    }
    return out;
  }
  function span(ms) { var s = Math.round(ms / 1000); return s < 60 ? s + " second" + (s === 1 ? "" : "s") : Math.floor(s / 60) + " min " + (s % 60) + " s"; }
  function burstCard(list) {
    var e = list[0], last = list[list.length - 1], r = mk("div", "avrow avburst"), top = mk("div", "av1"), left = mk("div");
    left.appendChild(mk("div", "avwho", list.length + " " + typeName(e.record_type) + " entries"));
    left.appendChild(mk("div", "avm", K.when(last.created_at) + " to " + K.when(e.created_at) + " · " + actorName(e.created_by)));
    top.appendChild(left); var right = mk("div", "avbtns"); right.appendChild(mk("span", "avchip " + e.action, VERB[e.action] || e.action)); top.appendChild(right); r.appendChild(top);
    r.appendChild(mk("div", "avwhat", list.length + " " + String(VERB[e.action] || e.action).toLowerCase() + " within " + span(new Date(e.created_at) - new Date(last.created_at)) + ", one after another."));
    var d = mk("details"); d.appendChild(mk("summary", "avm", "Show all " + list.length + " entries")); var built = false, key = "burst:" + e.id;
    if (S.openIds[key]) d.open = true;
    function build() { if (built || !d.open) return; built = true; var wrap = mk("div", "avburstlist"); list.forEach(function (x) { wrap.appendChild(entryCard(x)); }); d.appendChild(wrap); }
    d.addEventListener("toggle", function () { S.openIds[key] = d.open; build(); }); build(); r.appendChild(d); return r;
  }

  function dayLabel(d) {
    var t = dayStart(new Date()), y = new Date(t.getTime() - 864e5), x = dayStart(d);
    if (x.getTime() === t.getTime()) return "Today";
    if (x.getTime() === y.getTime()) return "Yesterday";
    return x.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: x.getFullYear() === t.getFullYear() ? undefined : "numeric" });
  }

  function draw() {
    if (!root) return;
    var keepQ = document.activeElement && document.activeElement.id === "avSearch";
    root.textContent = "";
    var wrap = mk("div", "acv");
    var hd = mk("div", "bar phead"), pt = mk("div", "ptext"); pt.appendChild(mk("h2", "ptitle", "Activity"));
    var count = mk("div", "count"); count.id = "avCount"; count.setAttribute("role", "status"); pt.appendChild(count);
    var chk = mk("div", "meta"); chk.id = "avChecked"; chk.textContent = S.checked ? "Last checked " + S.checked : ""; pt.appendChild(chk);
    hd.appendChild(pt); var ac = mk("div", "actions"); ac.appendChild(btn("Refresh", "btn-secondary", function () { load(); })); hd.appendChild(ac); wrap.appendChild(hd);
    wrap.appendChild(mk("p", "avm", "Every change made in the Console, newest first. Nothing here can be edited."));
    if (S.recId) {
      var fo = mk("div", "avfocus"); fo.appendChild(mk("span", "", "History of " + (S.recLabel || "one record")));
      fo.appendChild(btn("Show everything", "quiet", function () { S.recId = ""; S.recLabel = ""; load(); })); wrap.appendChild(fo);
    } else {
      var sb = mk("div", "avbar"); var q = mk("input"); q.type = "search"; q.id = "avSearch"; q.value = S.q; q.placeholder = "Search what is shown"; q.autocomplete = "off";
      q.addEventListener("input", function () { S.q = q.value; syncHash(); list(); });
      sb.appendChild(field("Search", q, "avSearch")); wrap.appendChild(sb);
      var chips = mk("div", "avchips"); chips.id = "avChips"; wrap.appendChild(chips);
    }
    wrap.appendChild(mk("div", "avmsg", S.msg)); var role = wrap.lastChild; role.setAttribute("role", "alert");
    if (S.msg) { var rt = btn("Try again", "btn-secondary", function () { load(); }); rt.id = "avRetry"; role.appendChild(rt); }
    var host = mk("div"); host.id = "avList"; wrap.appendChild(host);
    root.appendChild(wrap);
    if (!S.recId) buildChips($("avChips"));
    list();
    if (keepQ) { try { q.focus(); q.setSelectionRange(q.value.length, q.value.length); } catch (e) {} }
  }

  function list() {
    var host = $("avList"), count = $("avCount"); if (!host) return;
    host.textContent = "";
    if (S.busy && !S.loaded) { count.textContent = "Loading…"; host.appendChild(UI.skeleton(5)); return; }
    if (!S.loaded) { count.textContent = ""; return; }
    var q = S.q.trim().toLowerCase(), g = S.recId ? {} : selNow(), since = sinceFor(g.when && g.when[0]);
    var narrowed = !!q || (!S.recId && S.cf && S.cf.isNarrowed());
    var shown = S.records.filter(function (e) { return (S.recId || chipMatch(e, g, since)) && matches(e, q); });
    if (S.cf && !S.recId) {
      var by = {}; S.records.forEach(function (e) { var k = groupOf(e.record_type); by[k] = (by[k] || 0) + 1; }); by.all = S.records.length;
      var ch = {}; S.records.forEach(function (e) { ch[e.action] = (ch[e.action] || 0) + 1; });
      S.cf.setCounts({ kind: by, change: ch }); S.cf.setResult(shown.length + " of " + S.records.length + " entries");
    }
    var n = S.records.length;
    count.textContent = narrowed ? shown.length + " of " + n + " loaded entries" + (S.more ? " (searched the newest " + n + ")" : "") : shown.length + (shown.length === 1 ? " entry" : " entries") + (S.more ? " loaded, older ones are not shown yet" : "");
    function pager() { if (!S.more) return; var b = btn(narrowed ? "Search older entries" : "Load " + MAXN + " more", "quiet avmorebtn", function () { more(); }); b.id = "avMore"; b.disabled = S.paging; if (S.paging) b.textContent = "Loading…"; var w = mk("div", "avmore"); w.appendChild(b); host.appendChild(w); }
    if (!shown.length) { host.appendChild(mk("div", "avm", narrowed ? (S.more ? "No entries match these filters among the " + n + " loaded." : "No entries match these filters.") : "Nothing has been recorded here yet.")); pager(); return; }
    var lastDay = "";
    foldBursts(shown).forEach(function (item) {
      var first = item.burst ? item.burst[0] : item, d = new Date(first.created_at), key = isNaN(d) ? "" : d.toDateString();
      if (key && key !== lastDay) { lastDay = key; host.appendChild(mk("h3", "avday", dayLabel(d))); }
      var card = item.burst ? burstCard(item.burst) : entryCard(item);
      if (S.fresh && first.id === S.fresh) { card.tabIndex = -1; card.id = "avFirstNew"; }
      host.appendChild(card);
    });
    pager();
  }

  function why(res) {
    if (res.status === 403) return "Only a super admin may read the activity log.";
    if (res.status === 429) return "Too many tries. Wait a few minutes.";
    if (res.status === 0) return "Could not reach the server.";
    return "Something went wrong. Try again.";
  }

  function load() {
    var my = ++S.seq; S.busy = true; S.msg = "";
    draw();
    return K.admin("list", { filters: serverFilter(), order: "-created_at", limit: MAXN }, COLL).then(function (res) {
      if (my !== S.seq) return;
      S.busy = false;
      if (!ok(res)) { S.msg = why(res); S.records = []; S.loaded = true; }
      else { var dd = res.body.data || {}; S.records = dd.records || []; S.more = !!dd.more; S.marker = dd.marker == null ? null : dd.marker; S.loaded = true; S.checked = K.clock(new Date()); }
      draw();
      if (S.records.length) return nameThem(S.records).then(function (got) { if (got && my === S.seq) draw(); });
    });
  }

  // "Load 50 more": the next page is the entries older than the last one we hold. Focus moves to the first new entry.
  function more() {
    if (S.paging || !S.more || S.marker == null) return; var my = S.seq; S.paging = true; list();
    var f = serverFilter();
    return K.admin("list", { filters: f, order: "-created_at", limit: MAXN, before: S.marker }, COLL).then(function (res) {
      if (my !== S.seq) return; S.paging = false;
      if (!ok(res)) { S.msg = why(res); draw(); return; }
      var dd = res.body.data || {}, add = dd.records || []; S.fresh = add.length ? add[0].id : ""; S.records = S.records.concat(add); S.more = !!dd.more; S.marker = dd.marker == null ? S.marker : dd.marker;
      draw(); var el = $("avFirstNew"); if (el) { el.focus(); } S.fresh = "";
      return nameThem(add).then(function (got) { if (got && my === S.seq) draw(); });
    });
  }

  // Called from the History button on a card (and on an entry): the station opens on that one record.
  function openFor(id, label) {
    S.pending = { id: id, label: label || "" };
    K.go("activity");
  }

  function show() {
    root = $("activityView");
    if (S.pending) { S.recId = S.pending.id; S.recLabel = S.pending.label; S.sel = null; S.q = ""; S.pending = null; } else { S.recId = ""; S.recLabel = ""; readHash(); }
    S.loaded = false; load();
  }

  window.ActivityStation = {
    show: show, openFor: openFor,
    reset: function () { S = freshState(S.seq + 1); var v = $("activityView"); if (v) v.innerHTML = ""; root = null; }
  };
})();
