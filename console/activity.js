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
  var S = { mode: "all", value: "", recId: "", recLabel: "", records: [], loaded: false, busy: false, msg: "", q: "", seq: 0, pending: null, openIds: {} };

  var TYPES = [["venue", "Venue"], ["scheduled_class", "Class"], ["registration_request", "Registration request"], ["individual", "Person"],
    ["location", "Place"], ["instructor_roster", "Instructor"], ["student_roster", "Student"], ["attendance", "Attendance"], ["organization", "Organization"],
    ["curriculum", "Curriculum"], ["registration_assignment", "Assignment"], ["location_link", "Place link"], ["organization_link", "Organization link"],
    ["transaction_record", "Payment record"], ["merge_event", "Merge"], ["message_template", "Message wording"], ["comms_setting", "Message setting"],
    ["access_person", "Access person"], ["access_role", "Access role"], ["discovery_area", "Discovery area"], ["discovery_model", "Discovery model"],
    ["discovery_type", "Discovery type"], ["discovery_prompt", "Discovery prompt"], ["discovery_setting", "Discovery setting"], ["individual_restricted_detail", "Sensitive details"]];
  var ACTIONS = [["created", "Created"], ["edited", "Edited"], ["deleted", "Deleted"], ["restored", "Restored"]];
  var MODES = [["all", "Everything"], ["record_type", "One kind of record"], ["action", "One kind of change"], ["created_by", "One person or source"]];
  var VERB = { created: "Created", edited: "Edited", deleted: "Deleted", restored: "Restored" };

  function $(id) { return document.getElementById(id); }
  function ok(res) { return res.status === 200 && res.body && res.body.ok; }
  function typeName(t) { for (var i = 0; i < TYPES.length; i++) if (TYPES[i][0] === t) return TYPES[i][1]; return String(t || "").replace(/_/g, " "); }
  function human(f) { var s = String(f || "").replace(/_/g, " "); return s.charAt(0).toUpperCase() + s.slice(1); }

  // user:admin -> "Admin key", web:enjoy -> "Website form", system:x -> "System (x)", user:<id> -> the id as stored
  function actorName(a) {
    a = String(a || "");
    if (a === "user:admin") return "Admin key";
    if (a === "web:enjoy") return "Website form";
    if (a === "web:completion") return "Completion link";
    if (a === "system:unattributed") return "System (no name recorded)";
    var i = a.indexOf(":"); if (i < 0) return a || "Unknown";
    var kind = a.slice(0, i), rest = a.slice(i + 1);
    return kind === "system" ? "System (" + rest + ")" : kind === "web" ? "Website (" + rest + ")" : rest;
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

  function style() {
    if ($("activityStyle")) return;
    var s = document.createElement("style"); s.id = "activityStyle";
    s.textContent = ".acv{max-width:900px;margin:0 auto}.acv .avbar{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;margin:10px 0}.acv .avf{display:flex;flex-direction:column;gap:2px}" +
      ".acv .avf label{font-weight:700;font-size:14px}.acv select,.acv input[type=text],.acv input[type=search]{font:inherit;padding:8px;min-height:44px;box-sizing:border-box;max-width:100%}" +
      ".acv .avrow{border:1px solid #d8d2c4;border-radius:10px;padding:10px 12px;margin:8px 0;background:#fff}.acv .av1{display:flex;gap:8px;flex-wrap:wrap;align-items:center;justify-content:space-between}" +
      ".acv .avwho{font-weight:700}.acv .avm{font-size:14px;color:var(--muted)}.acv .avchip{display:inline-block;border-radius:999px;padding:1px 10px;font-size:13px;font-weight:700;border:1px solid #bbb;background:#eee}" +
      ".acv .avchip.created{background:#d9f2c4;border-color:#5c9a00;color:#1d4d00}.acv .avchip.edited{background:#e1ecff;border-color:#4a76c9;color:#12326b}" +
      ".acv .avchip.deleted{background:#fbd9d4;border-color:#c0392b;color:#6b1208}.acv .avchip.restored{background:#ffe9b3;border-color:#c98a00;color:#6a4500}" +
      ".acv .avch{margin:6px 0 0;padding:0;list-style:none}.acv .avch li{padding:4px 0;border-top:1px solid #eee;font-size:15px;overflow-wrap:anywhere}" +
      ".acv .avfield{font-weight:700}.acv .avold{text-decoration:line-through;color:#8a3b30}.acv .avnew{color:#1d4d00}.acv .avw{font-style:italic;color:var(--muted)}" +
      ".acv .avfocus{border:2px solid var(--orange);border-radius:10px;padding:8px 12px;margin:10px 0;background:#fffaf0;display:flex;gap:8px;flex-wrap:wrap;align-items:center;justify-content:space-between}" +
      ".acv .avmsg{color:var(--err);font-weight:600;min-height:1.4em}";
    document.head.appendChild(s);
  }

  function btn(text, cls, fn) { var b = mk("button", cls || "", text); b.type = "button"; b.addEventListener("click", fn); return b; }
  function field(label, input, id) { var d = mk("div", "avf"); var l = mk("label", "", label); if (id) l.htmlFor = id; d.appendChild(l); d.appendChild(input); return d; }
  function select(id, opts, val) {
    var s = mk("select"); s.id = id;
    opts.forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; s.appendChild(op); });
    s.value = val || opts[0][0]; return s;
  }

  function serverFilter() {
    if (S.recId) return { related_ids: S.recId };
    if (S.mode !== "all" && S.value) { var f = {}; f[S.mode] = S.value; return f; }
    return {};
  }

  function matches(e, q) {
    if (!q) return true;
    var hay = [e.record_label, typeName(e.record_type), e.record_type, e.action, actorName(e.created_by), e.created_by, e.record_id];
    (e.changes || []).forEach(function (c) { hay.push(c.field, human(c.field), c.old_value, c.new_value); });
    return hay.join(" \n ").toLowerCase().indexOf(q) >= 0;
  }

  function changeLine(e, c) {
    var li = mk("li"); li.appendChild(mk("span", "avfield", human(c.field) + ": "));
    if (c.values_withheld) { li.appendChild(mk("span", "avw", "changed (personal details are not recorded)")); return li; }
    var hasOld = c.old_value != null, hasNew = c.new_value != null;
    if (e.action === "created" || !hasOld) { li.appendChild(mk("span", "avnew", valueText(c.new_value))); }
    else if (!hasNew) { li.appendChild(mk("span", "avold", valueText(c.old_value))); li.appendChild(document.createTextNode(" → removed")); }
    else { li.appendChild(mk("span", "avold", valueText(c.old_value))); li.appendChild(document.createTextNode(" → ")); li.appendChild(mk("span", "avnew", valueText(c.new_value))); }
    if (c.truncated) li.appendChild(mk("span", "avm", " (long value, cut short)"));
    return li;
  }

  function entryCard(e) {
    var r = mk("div", "avrow"); var top = mk("div", "av1");
    var left = mk("div"); left.appendChild(mk("div", "avwho", typeName(e.record_type) + (e.record_label ? " · " + e.record_label : "")));
    left.appendChild(mk("div", "avm", K.when(e.created_at) + " · " + actorName(e.created_by) + (e.record_label ? "" : " · ref " + String(e.record_id).slice(0, 8)))); top.appendChild(left);
    var right = mk("div", "avbtns"); right.appendChild(mk("span", "avchip " + e.action, VERB[e.action] || e.action)); right.appendChild(document.createTextNode(" "));
    right.appendChild(btn("Change history", "quiet", function () { openFor(e.record_id, e.record_label || typeName(e.record_type)); })); top.appendChild(right); r.appendChild(top);
    var ch = e.changes || [];
    if (ch.length) {
      var ul = mk("ul", "avch");
      var more = ch.length > 6 ? ch.slice(6) : [];
      ch.slice(0, 6).forEach(function (c) { ul.appendChild(changeLine(e, c)); });
      if (more.length) {
        var d = mk("details"); d.appendChild(mk("summary", "avm", "Show " + more.length + " more field" + (more.length === 1 ? "" : "s")));
        var ul2 = mk("ul", "avch"); more.forEach(function (c) { ul2.appendChild(changeLine(e, c)); }); d.appendChild(ul2);
        if (S.openIds[e.id]) d.open = true; d.addEventListener("toggle", function () { S.openIds[e.id] = d.open; });
        r.appendChild(ul); r.appendChild(d);
      } else r.appendChild(ul);
      if (e.fields_omitted) r.appendChild(mk("div", "avm", "+ " + e.fields_omitted + " more fields not listed."));
    }
    return r;
  }

  function valueControl() {
    if (S.mode === "record_type") { var t = select("avValue", [["", "Choose…"]].concat(TYPES), S.value); t.addEventListener("change", function () { S.value = t.value; load(); }); return field("Kind of record", t, "avValue"); }
    if (S.mode === "action") { var a = select("avValue", [["", "Choose…"]].concat(ACTIONS), S.value); a.addEventListener("change", function () { S.value = a.value; load(); }); return field("Kind of change", a, "avValue"); }
    var i = mk("input"); i.type = "text"; i.id = "avValue"; i.value = S.value; i.placeholder = "such as user:admin or web:enjoy"; i.autocomplete = "off";
    i.addEventListener("keydown", function (ev) { if (ev.key === "Enter") { S.value = i.value.trim(); load(); } });
    var f = field("Person or source (press Enter)", i, "avValue"); return f;
  }

  function draw() {
    if (!root) return;
    var keepQ = document.activeElement && document.activeElement.id === "avSearch";
    root.textContent = "";
    var wrap = mk("div", "acv");
    var h = mk("div", "av1"); h.appendChild(mk("h2", "", "Activity")); h.appendChild(btn("Refresh", "quiet", function () { load(); })); wrap.appendChild(h);
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
    var count = mk("div", "avm"); count.id = "avCount"; wrap.appendChild(count);
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
    return K.admin("list", { filters: serverFilter(), order: "-created_at", limit: MAXN }, COLL).then(function (res) {
      if (my !== S.seq) return;
      S.busy = false;
      if (!ok(res)) { S.msg = why(res); S.records = []; S.loaded = true; }
      else { S.records = (res.body.data && res.body.data.records) || []; S.loaded = true; }
      draw();
    });
  }

  // Called from the History button on a card (and on an entry): the station opens on that one record.
  function openFor(id, label) {
    S.pending = { id: id, label: label || "" };
    K.go("activity");
  }

  function show() {
    style(); root = $("activityView");
    if (S.pending) { S.recId = S.pending.id; S.recLabel = S.pending.label; S.mode = "all"; S.value = ""; S.q = ""; S.pending = null; }
    S.loaded = false; load();
  }

  window.ActivityStation = {
    show: show, openFor: openFor,
    reset: function () { S = { mode: "all", value: "", recId: "", recLabel: "", records: [], loaded: false, busy: false, msg: "", q: "", seq: S.seq + 1, pending: null, openIds: {} }; var v = $("activityView"); if (v) v.innerHTML = ""; root = null; }
  };
})();
