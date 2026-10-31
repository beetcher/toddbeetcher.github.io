/* Attendance station for the Console: every attendance record (who is in which class, in any role), newest first, with chip filters (UI.chipFilters,
   filters.js) that apply at once, Search, Refresh; the attendance dialog for one class (opened from Classes, Messages, Home and from here: instructors,
   students, seat summary, add a person, change status, remove, messages sent, Send confirmation email); and a person's class history.
   Moved out of console.js (the Attendance extraction, A-2): the code is the same; everything it used to borrow from the big file now comes through
   ConsoleKit. The placing machinery (assignForm, Put in a class, the class builder) stays in console.js for now (DT-18); the shared word tables stay
   there too and are read through K.attConsts(). The page markup (#attendanceView, #atDlg) lives in index.html and the manual text in the stations list in
   console.js (DT-7). Loaded by index.html after console.js and requests.js. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var $ = function (id) { return document.getElementById(id); };
  var mk = K.mk, admin = K.admin, lock = K.lock, adminProblem = K.adminProblem, attName = K.attName, classWhen = K.classWhen,
      refreshPlaced = K.refreshPlaced, assignForm = K.assignForm;
  var A = K.attConsts();   // the shared tables (constants) and leftOpen
  var ATT = A.ATT, ATT_STATUSES = A.ATT_STATUSES, ATT_WORD = A.ATT_WORD, ROLE_WORD = A.ROLE_WORD, ATT_TONE = A.ATT_TONE, ATT_OPEN = A.ATT_OPEN, ATT_OFF = A.ATT_OFF,
      CORR_KIND = A.CORR_KIND, REASON_WORD = A.REASON_WORD, leftOpen = A.leftOpen;

  function attLine(r, withClass) {
    var row = mk("div", "rrow");
    row.appendChild(mk("span", "", withClass ? ((r.class && r.class.title) || "(class not found)") + (r.class && r.class.starts_at ? " · " + classWhen(r.class) : "") : attName(r)));
    row.appendChild(mk("span", "", ROLE_WORD[r.role] + " · " + (ATT_WORD[r.status] || r.status) + (r.reference_number ? " · " + r.reference_number : "") + (r.confirmation_number ? " · request " + r.confirmation_number : "")));
    return row;
  }

  var SEND_WHY = { not_a_student: "Only students get this email.", not_placed: "They are not placed right now (waiting, or no longer in the class).",
                   class_not_scheduled: "The class has no date and start time yet. Finish it in Classes first.", no_venue: "The class has no venue yet.", no_time_zone: "The class has no time zone, and neither has its place. Set the place's time zone first.",
                   no_email: "This person has no email address on file.", class_not_found: "The class could not be found.", not_found: "That record could not be found." };
  function sendFail(res) {
    var ps = (res.body && res.body.error && res.body.error.problems) || [];
    if (ps.length && ps[0].field === "email" && ps[0].issue === "not_enabled") return "Email is turned off on the server, so nothing was sent.";
    if (ps.length && ps[0].field === "id") return SEND_WHY[ps[0].issue] || "That email cannot be sent.";
    return attFail(res);
  }
  // Why the CMS did not send, in plain words (the closed reason list of the message log).
  // One display shape for a message-log entry (communication_logs) and for an older line from the retired correspondence list.
  function corrNorm(e) {
    if (e.status) return { when: e.created_at, kind: e.kind, channel: e.channel, to: e.to, status: e.status, reason: e.reason, code: e.error_code, manual: e.trigger === "manual" };
    return { when: e.at, kind: e.kind, channel: e.channel, to: e.to, status: e.result, code: e.error_code, manual: e.trigger === "manual", older: true };
  }
  function corrLine(raw) {
    var e = corrNorm(raw);
    var when = e.when ? new Date(e.when).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "";
    var code = e.code ? " (" + e.code.replace(/_/g, " ") + ")" : "";
    var res = e.status === "sent" ? "Sent" : e.status === "failed" ? "Failed" + code : e.status === "unknown" ? "Unknown, may not have been sent" + code
            : (e.status === "not_sent" ? "Not sent: " : "Skipped: ") + (REASON_WORD[e.reason] || String(e.reason || "").replace(/_/g, " "));
    var bad = e.status === "failed" || e.status === "unknown" || e.status === "not_sent";
    return mk("div", "alogline" + (bad ? " bad" : ""), [when, CORR_KIND[e.kind] || e.kind, e.to ? (e.channel === "email" ? "Email to " : "") + e.to : "", res,
      e.manual ? "sent by hand" : "automatic", e.older ? "earlier record" : ""].filter(Boolean).join(" · "));
  }
  // Students only: the message log for this placement (newest first, plus older lines kept from before the CMS) and a button to send the confirmation now.
  function attCorrespondence(r, row, say, redraw) {
    var box = mk("div", "alog"); box.setAttribute("data-corr", r.id);
    box.appendChild(mk("div", "alogh", "Messages sent"));
    var body = mk("div", ""); body.appendChild(mk("div", "alogline none", "Loading…")); box.appendChild(body);
    row.appendChild(box);
    admin("list", { filters: { attendance_id: r.id } }, "communication_logs").then(function (lr) {
      body.textContent = "";
      var fresh = (lr.body && lr.body.data && lr.body.data.records) || [];
      var all = fresh.concat((r.correspondence || []).slice().reverse());
      all.sort(function (x, y) { return String(corrNorm(y).when || "").localeCompare(String(corrNorm(x).when || "")); });
      if (lr.status !== 200 && !all.length) { body.appendChild(mk("div", "alogline none", "Could not load the messages.")); return; }
      if (!all.length) body.appendChild(mk("div", "alogline none", "None yet."));
      all.forEach(function (e) { body.appendChild(corrLine(e)); });
    });
    var b = mk("button", "btn-secondary asend", "Send confirmation email"); b.type = "button";
    b.setAttribute("aria-label", "Send confirmation email (" + attName(r) + ")");
    b.addEventListener("click", function () {
      b.disabled = true; b.textContent = "Sending…";
      admin("send_confirmation", { id: r.id }, ATT).then(function (res) {
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          var out = res.body.data;
          say(out.status === "sent" ? "Confirmation email sent to " + attName(r) + "."
            : "The email was not sent (" + (out.status === "failed" || out.status === "unknown" ? out.status : (REASON_WORD[out.reason] || String(out.reason).replace(/_/g, " "))) + "). It is noted in the log.");
          redraw(); return;
        }
        b.disabled = false; b.textContent = "Send confirmation email"; say(sendFail(res));
      });
    });
    row.appendChild(b);
  }

  function attRow(r, say, redraw) {
    var row = mk("div", "arow");
    var top = mk("div", "atop");
    var nm = mk("span", "aname", attName(r) + (r.role === "primary_instructor" ? " (lead)" : "") + (r.order ? " · place " + r.order : ""));
    var refs = [r.reference_number ? "ref " + r.reference_number : "", r.confirmation_number ? "request " + r.confirmation_number : ""].filter(Boolean).join(" · ");
    if (refs) nm.appendChild(mk("span", "aref", refs));
    top.appendChild(nm);
    var sel = mk("select"); sel.setAttribute("aria-label", "Status for " + attName(r));
    ATT_STATUSES.forEach(function (s) { var o = mk("option", "", ATT_WORD[s]); o.value = s; sel.appendChild(o); });
    sel.value = r.status;
    var rm = mk("button", "btn-secondary", "Remove"); rm.type = "button";
    var who = attName(r) + (r["class"] && r["class"].title ? ", " + r["class"].title : "");
    rm.setAttribute("aria-label", "Remove (" + who + ")");
    top.appendChild(sel); top.appendChild(rm);
    row.appendChild(top);
    if (r.role === "student") attCorrespondence(r, row, say, redraw);
    sel.addEventListener("change", function () {
      var want = sel.value;
      function apply() {
        sel.disabled = true;
        admin("update", { id: r.id, changes: { status: want }, expected_updated_at: r.updated_at }, ATT).then(function (res) {
          sel.disabled = false;
          if (res.status === 401) { lock("That key did not work."); return; }
          if (res.status === 200 && res.body && res.body.ok) { say(attName(r) + ": " + ATT_WORD[want].toLowerCase() + "." + (leftOpen(r.status, want) ? " They were emailed" + (r.role === "student" ? ", and so were the instructors" : "") + ". Messages shows the result." : "")); redraw(); return; }
          sel.value = r.status; say(attFail(res));
        });
      }
      if (!leftOpen(r.status, want)) { apply(); return; }
      UI.confirm({ title: "Change " + attName(r) + " to " + ATT_WORD[want].toLowerCase() + "?",
        message: attName(r) + " will be set to " + ATT_WORD[want].toLowerCase() + " and emailed" + (r.role === "student" ? ", and the instructors too" : "") + ".",
        yes: "Go ahead", no: "Cancel" }).then(function (ok) { if (ok) apply(); else sel.value = r.status; });
    });
    var armed = false;
    rm.addEventListener("click", function () {
      if (!armed) { armed = true; rm.textContent = "Really remove?"; rm.setAttribute("aria-label", "Really remove? (" + who + ")"); rm.className = "btn-danger"; return; }
      rm.disabled = true;
      admin("soft_delete", { id: r.id }, ATT).then(function (res) {
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) { say(attName(r) + " was removed from this class. Their record is kept." + (ATT_OPEN[r.status] ? " They were emailed" + (r.role === "student" ? ", and so were the instructors" : "") + ". Messages shows the result." : "")); refreshPlaced(); redraw(); return; }
        rm.disabled = false; armed = false; rm.textContent = "Remove"; rm.setAttribute("aria-label", "Remove (" + who + ")"); rm.className = "btn-secondary"; say(attFail(res));
      });
    });
    return row;
  }

  // In the class dialog a row carries the same tone edge and chip words as the station cards.
  function attRowDlg(r, say, redraw) {
    var row = attRow(r, say, redraw), tn = ATT_TONE[r.status] || ATT_TONE.assigned;
    row.setAttribute("data-tone", tn.tone);
    var nm = row.querySelector(".aname");
    if (nm) nm.insertBefore(mk("span", "qchip" + (tn.tone === "wait" ? " warn" : tn.tone === "ok" ? " ok" : ""), ATT_WORD[r.status] || r.status), nm.querySelector(".aref"));
    return row;
  }
  // With no host this opens the Attendance dialog. With a host (the class page's Attendance tab) the same roster is drawn there instead.
  function openAttendance(cls, host) {
    var inline = !!host, dlg = $("atDlg"), body, msg;
    if (inline) {
      host.textContent = "";
      msg = mk("div", "msg"); msg.setAttribute("role", "status"); body = mk("div", "atinline");
      host.appendChild(msg); host.appendChild(body);
    } else {
      body = $("atBody"); msg = $("atMsg");
      $("atTitle").textContent = "Attendance: " + (cls.title || "class");
    }
    msg.textContent = ""; body.textContent = "Loading…";
    if (!inline && !dlg.open) dlg.showModal();
    function say(t) { msg.textContent = t; }
    var only = "";
    function draw() {
      var args = { filters: { scheduled_class_id: cls.id }, limit: 200, expand: true, order: "created_at" };
      if (only) args.filters.status = only;
      admin("list", args, ATT).then(function (res) {
        body.textContent = "";
        var bShow = mk("section", "atband show"), bInst = mk("section", "atband inst"), bStu = mk("section", "atband stu");
        bShow.appendChild(mk("div", "bandname", "Show"));
        var fl = mk("label", "f", "Who to show"), fs = mk("select"); fs.id = inline ? "atOnlyTab" : "atOnly"; fl.htmlFor = fs.id; fl.className = "sr";
        var o0 = mk("option", "", "Everyone"); o0.value = ""; fs.appendChild(o0);
        ATT_STATUSES.forEach(function (st) { var o = mk("option", "", ATT_WORD[st] + " only"); o.value = st; fs.appendChild(o); });
        fs.value = only; fs.addEventListener("change", function () { only = fs.value; draw(); });
        bShow.appendChild(fl); bShow.appendChild(fs);
        body.appendChild(bShow); body.appendChild(bInst); body.appendChild(bStu);
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status !== 200 || !res.body.ok) { say("Could not load the attendance. " + adminProblem(res.status)); return; }
        var recs = res.body.data.records || [];
        var inst = recs.filter(function (r) { return r.role !== "student"; }).sort(function (a, b) {
          function k(r) { return (r.role === "primary_instructor" ? 0 : 1) * 1000 + (r.order || 999); }
          return k(a) - k(b);
        });
        var stu = recs.filter(function (r) { return r.role === "student"; });
        bInst.appendChild(mk("div", "bandname", "Instructors (" + inst.length + ")"));
        inst.forEach(function (r) { bInst.appendChild(attRowDlg(r, say, draw)); });
        if (!inst.length) bInst.appendChild(mk("div", "empty", "No instructor yet."));
        bStu.appendChild(mk("div", "bandname", "Students (" + stu.length + ")"));
        stu.forEach(function (r) { bStu.appendChild(attRowDlg(r, say, draw)); });
        if (!stu.length) bStu.appendChild(mk("div", "empty", "No students yet."));
        var seats = stu.filter(function (r) { return !ATT_OFF[r.status]; }).length, wait = stu.filter(function (r) { return r.status === "waitlisted"; }).length;
        bStu.appendChild(mk("div", "rsum", seats + " of up to " + cls.capacity_max + " seats taken" + (wait ? ", " + wait + " waiting" : "") + ". Target " + cls.capacity_target + "."));
        if (!inline) {   // the class page keeps its add form on the People tab
          var det = mk("details", "addbox"); det.id = "atAddBox";
          det.appendChild(mk("summary", "", "Add a student or instructor"));
          det.appendChild(assignForm({ cls: cls, onCancel: function () { det.open = false; }, onAdded: function (d, said) { say(said); draw(); } }));
          bStu.appendChild(det);
        }
      });
    }
    draw();
  }

  // ---- Attendance station: every record, with chip filters (UI.chipFilters, filters.js) that apply at once. Refresh asks the server again.
  var AS = { recs: [], capped: false, loaded: false, seq: 0, cf: null };
  function asChips() {
    if (AS.cf) return AS.cf;
    AS.cf = UI.chipFilters({
      mount: $("aChips"), label: "Attendance filters",
      filters: [
        { id: "status", label: "Status", kind: "multi", options: ATT_STATUSES.map(function (s) { return { value: s, label: ATT_WORD[s] }; }) },
        { id: "role", label: "Role", kind: "multi", options: Object.keys(ROLE_WORD).map(function (r) { return { value: r, label: ROLE_WORD[r] }; }) },
        { id: "source", label: "Came from", kind: "multi", options: [{ value: "request", label: "A registration request" }, { value: "direct", label: "Added by us" }] }
      ],
      onChange: function () { asRender(); }
    });
    return AS.cf;
  }
  function asCounts() {
    var by = {}; AS.recs.forEach(function (r) { by[r.status] = (by[r.status] || 0) + 1; });
    var cnt = {}; ATT_STATUSES.forEach(function (s) { cnt[s] = by[s] || 0; });
    asChips().setCounts(AS.loaded ? { status: cnt } : {});
  }
  function asSelected() {
    var g = asChips().getSelection(), set = function (a) { var o = {}; a.forEach(function (v) { o[v] = 1; }); return o; };
    return { status: set(g.status), role: set(g.role), source: set(g.source) };
  }
  function asMatches(r, sel, q) {
    if (!sel.status[r.status] || !sel.role[r.role] || !sel.source[r.request_id ? "request" : "direct"]) return false;
    if (!q) return true;
    var hay = [attName(r), r["class"] && r["class"].title, r.reference_number, r.confirmation_number, ROLE_WORD[r.role], ATT_WORD[r.status]].filter(Boolean).join(" ").toLowerCase();
    return q.toLowerCase().split(/\s+/).every(function (w) { return hay.indexOf(w) >= 0; });
  }
  // The chips and the search box are read every time the list is drawn: on load, on Refresh, and as each one changes.
  function asRender() {
    var sel = asSelected(), q = $("aSearch").value.trim(), list = $("aList");
    list.textContent = "";
    var shown = AS.recs.filter(function (r) { return asMatches(r, sel, q); });
    shown.forEach(function (r) {
      var li = mk("li", "attrec");
      var top = mk("div", "lchips");
      var cl = mk("button", "btn-link", ((r["class"] && r["class"].title) || "(class not found)") + (r["class"] && r["class"].starts_at ? " · " + classWhen(r["class"]) : ""));
      cl.type = "button"; cl.setAttribute("aria-label", "Open class attendance: " + cl.textContent);
      cl.addEventListener("click", function () { var c = K.classById(r.scheduled_class_id); if (c) openAttendance(c); else $("aMsg").textContent = "That class could not be found."; });
      top.appendChild(cl); top.appendChild(mk("span", "", ROLE_WORD[r.role] || r.role));
      var tn = ATT_TONE[r.status] || ATT_TONE.assigned;
      top.appendChild(mk("span", "qchip" + (tn.tone === "wait" ? " warn" : tn.tone === "ok" ? " ok" : ""), ATT_WORD[r.status] || r.status));
      li.setAttribute("data-tone", tn.tone);
      li.appendChild(top);
      var nx = mk("div", "qnext", tn.next); nx.style.padding = "0 var(--space-7) var(--space-2)"; li.appendChild(nx);
      var holder = mk("div", "qhold"); holder.style.padding = "0 14px 8px";
      holder.appendChild(attRow(r, function (m) { $("aNotice").textContent = m; }, loadAttendanceStation));
      li.appendChild(holder);
      list.appendChild(li);
    });
    $("aCount").textContent = shown.length + (shown.length === 1 ? " record" : " records") + (shown.length !== AS.recs.length ? " of " + AS.recs.length : "");
    $("aEmpty").hidden = shown.length > 0 || !AS.loaded;
    asCounts(); asChips().setResult(AS.loaded ? $("aCount").textContent : "");   // the same line as the head, repeated inside each list so a tick can be watched
  }
  function loadAttendanceStation() {
    asChips();
    var my = ++AS.seq;
    $("aMsg").textContent = "";
    Promise.all([K.classChoices(), admin("list", { limit: 200, expand: true, order: "-created_at" }, ATT)]).then(function (both) {
      if (my !== AS.seq || !K.key()) return;
      var res = both[1];
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body || !res.body.ok) { $("aMsg").textContent = "Could not load the attendance. " + adminProblem(res.status); return; }
      AS.recs = res.body.data.records || []; AS.loaded = true; AS.capped = AS.recs.length >= 200;
      $("aChecked").textContent = "Last checked " + K.clock(new Date()) + (AS.capped ? ". Showing the newest 200: narrow it with the filters or search." : "");
      asRender();
    });
  }
  $("aRefresh").addEventListener("click", function () { $("aNotice").textContent = ""; loadAttendanceStation(); });
  $("aSearch").addEventListener("input", function () { asRender(); });
  $("aSearch").addEventListener("keydown", function (e) { if (e.key === "Enter") e.preventDefault(); });

  // On a person's card: every class they are in, in any role.
  function personHistory(rec, host) {
    host.textContent = "Loading…";
    admin("list", { filters: { individual_id: rec.id }, limit: 200, expand: true }, ATT).then(function (res) {
      host.textContent = "";
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body.ok) { host.appendChild(mk("div", "msg", "Could not load the history. " + adminProblem(res.status))); return; }
      var recs = (res.body.data.records || []).sort(function (a, b) { return ((b.class && b.class.starts_at) || "") < ((a.class && a.class.starts_at) || "") ? -1 : 1; });
      host.appendChild(mk("div", "rhead", "Classes (" + recs.length + ")"));
      recs.forEach(function (r) { host.appendChild(attLine(r, true)); });
      if (!recs.length) host.appendChild(mk("div", "empty", "Not in any class yet."));
    });
  }

  // The hooks console.js calls. show: Attendance was opened. reset: the Console locked or signed out (empties the page: list, counts, message, search).
  // openAttendance, personHistory, attLine: used by Classes, Messages, Home, People and Put in a class, which still live in console.js (small forwarders there).
  // The plain sentence for a failed attendance write (moved from console.js, DT-34; the person words come from data.js). Classes asks for it through the kit.
  function attFail(res) {
    var ps = (res.body && res.body.error && res.body.error.problems) || [];
    if (res.status === 409 && !ps.length) return "Someone changed this a moment ago. Close this window and open it again.";
    if (!ps.length) return adminProblem(res.status);
    return ps.map(function (p) {
      if (p.issue === "duplicate") return "They are already in this class in that role.";
      if (p.issue === "choose_one") return "Choose someone we know or add someone new, not both.";
      if (/^person\./.test(p.field)) return (window.ConsoleData.PLABEL[p.field.slice(7)] || p.field) + ": " + (p.issue === "invalid_format" && /email$/.test(p.field) ? "That email address does not look right." : (window.ConsoleData.PISSUE[p.issue] || "That value is not valid."));
      if (p.field === "scheduled_class_id") return "Choose a class.";
      if (p.field === "role") return "Choose a role.";
      if (p.field === "individual_id" && p.issue === "address_required") return "An instructor needs an address first. Add the person in the Instructors station with their address, then add them here.";
      if (p.field === "individual_id") return p.issue === "required" ? "Choose someone." : "We could not find them.";
      if (p.field === "order") return "Place has to be a whole number from 1 to 50.";
      return p.field + ": " + (window.ConsoleData.PISSUE[p.issue] || p.issue);
    }).join(" ");
  }

  window.AttendanceStation = {
    fail: function (res) { return attFail(res); },
    show: function () { loadAttendanceStation(); },
    reset: function () {
      AS.seq++; AS.recs = []; AS.loaded = false; AS.capped = false;
      $("aList").textContent = ""; $("aMsg").textContent = ""; $("aNotice").textContent = ""; $("aChecked").textContent = ""; $("aCount").textContent = "";
      $("aSearch").value = ""; $("aEmpty").hidden = true;
      if (AS.cf) { AS.cf.setCounts({}); AS.cf.setResult(""); }
    },
    openAttendance: openAttendance, personHistory: personHistory, attLine: attLine
  };
})();
