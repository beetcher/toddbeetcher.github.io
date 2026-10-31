/* Messages station for the Console: the whole message log (communication_logs), newest first, with chip filters (UI.chipFilters in filters.js),
   search across the whole log, notes (add only), Mark handled for a message that was not sent, and Copy. The message text itself is never kept.
   Moved out of console.js (the Messages extraction, M-2): the code is the same, except that everything it used to borrow from the big file now comes
   through ConsoleKit. Loaded by index.html after console.js. The page markup (#messagesView) lives in index.html and the manual text in the stations
   list in console.js, the same as Activity and Performance. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var $ = function (id) { return document.getElementById(id); };
  var mk = K.mk, admin = K.admin, lock = K.lock, adminProblem = K.adminProblem, attName = window.ConsoleFormat.attName;
  function W() { return window.ConsoleWords; }   // the word tables are shared with Requests, so they are read when needed, not copied

  // ---- Messages station: the whole message log (communication_logs), chip filters (UI.chipFilters, filters.js), notes (add only), copy
  var MS = { recs: [], loaded: false, capped: false, seq: 0, open: {}, conf: {}, person: {}, att: {}, cf: null };
  function mConf(e) { return MS.conf[e.id] || ""; }   // the request's confirmation number, worked out when the log loads
  var M_STATUS = ["sent", "failed", "unknown", "not_sent", "skipped"];
  var M_STATUS_WORD = { sent: "Sent", failed: "Failed", unknown: "Unknown", not_sent: "Not sent", skipped: "Skipped" };
  function mKindWord(k) { return W().corrKind[k] || String(k || "").replace(/_/g, " ").replace(/^./, function (c) { return c.toUpperCase(); }); }
  function mReasonWord(r) { return W().reasonWord[r] || String(r || "").replace(/_/g, " "); }
  function mNeedsAttention(e) { return e.status === "failed" || e.status === "unknown" || (e.status === "not_sent" && !e.handled_at); }
  function mWhen(e) { return e.created_at ? window.ConsoleFormat.time(new Date(e.created_at)) : ""; }
  // The filter chips: one shared control (filters.js). The page only says which filters it has and what to do when the person changes one.
  function mChips() {
    if (MS.cf) return MS.cf;
    MS.cf = UI.chipFilters({
      mount: $("mChips"), label: "Message filters",
      filters: [
        { id: "attention", label: "Needs attention", kind: "toggle", noun: "messages", title: "Failed, unknown, or not sent and not yet handled" },
        { id: "status", label: "Status", kind: "multi", options: M_STATUS.map(function (s) { return { value: s, label: M_STATUS_WORD[s] }; }) },
        { id: "kind", label: "Message", kind: "multi", options: [] },
        { id: "how", label: "How it was sent", kind: "multi", options: [{ value: "automatic", label: "Automatic" }, { value: "manual", label: "By hand" }] },
        { id: "only", label: "Only show", kind: "multi", start: "none", options: [{ value: "notes", label: "Has notes" }, { value: "redir", label: "Went to a test address" }] }
      ],
      onChange: function () { mRender(); }
    });
    return MS.cf;
  }
  function mBuildChips() {
    // The kinds come from the log itself, so a new kind of message appears here without changing this page. A kind the person has unticked stays unticked.
    var kinds = {}; MS.recs.forEach(function (e) { if (e.kind) kinds[e.kind] = 1; });
    mChips().setOptions("kind", Object.keys(kinds).sort().map(function (k) { return { value: k, label: mKindWord(k) }; }));
  }
  function mSelected() {
    var g = mChips().getSelection(), set = function (a) { var o = {}; a.forEach(function (v) { o[v] = 1; }); return o; };
    return { attn: g.attention.length > 0, status: set(g.status), kind: set(g.kind), how: set(g.how), notes: g.only.indexOf("notes") >= 0, redir: g.only.indexOf("redir") >= 0 };
  }
  function mText(e) {
    return [e.to, e.subject, e.kind, mKindWord(e.kind), e.status, M_STATUS_WORD[e.status], e.reason, mReasonWord(e.reason), e.error_code, e.message_ref, e.id, e.request_id,
      e.attendance_id, e.scheduled_class_id, e.individual_id, mConf(e)].concat((e.notes || []).map(function (n) { return n.text; })).filter(Boolean).join(" ").toLowerCase();
  }
  function mMatches(e, sel, q) {
    if (q) {
      var hay = mText(e);
      return q.toLowerCase().split(/\s+/).every(function (w) { return hay.indexOf(w) >= 0; });
    }
    if (!sel.status[e.status] || !sel.kind[e.kind] || !sel.how[e.trigger === "manual" ? "manual" : "automatic"]) return false;
    if (sel.attn && !mNeedsAttention(e)) return false;
    if (sel.notes && !(e.notes && e.notes.length)) return false;
    if (sel.redir && !e.is_redirected) return false;
    return true;
  }
  // Names for the ids in a log entry, worked out when the log loads (the log itself keeps ids, never names).
  function mWho(e) {
    var rows = [], me = MS.person[e.individual_id], a = e.attendance_id ? MS.att[e.attendance_id] : null;
    if (me) rows.push(["Sent to", me + (e.audience ? " (" + e.audience + ")" : "")]);
    if (a && a.name && (a.name !== me || e.kind === "participant_left")) rows.push([e.kind === "participant_left" ? (a.role === "student" ? "Student who left" : "Left") : a.role === "student" ? "Student" : "Instructor", a.name]);
    var c = e.scheduled_class_id && K.classById(e.scheduled_class_id);
    if (c) rows.push(["Class", (c.title || "(no title)") + (c.starts_at ? " · " + window.ConsoleFormat.time(new Date(c.starts_at)) : "")]);
    if (mConf(e)) rows.push(["Confirmation number", mConf(e)]);
    return rows;
  }
  function mFactsText(e) {
    var L = mWho(e).concat([["When", e.created_at], ["Message", mKindWord(e.kind) + " (" + e.kind + ")"], ["For", e.audience], ["Channel", e.channel],
      ["To", e.to ? e.to + (e.is_redirected ? " (test address, not the real recipient)" : "") : ""], ["Subject", e.subject],
      ["Status", (M_STATUS_WORD[e.status] || e.status) + " (" + e.status + ")"], ["Why", e.reason + (mReasonWord(e.reason) !== e.reason ? ": " + mReasonWord(e.reason) : "")],
      ["Error code", e.error_code], ["Template version", e.template_version], ["Message-ID", e.message_ref], ["How", e.trigger === "manual" ? "By hand" : "Automatic"],
      ["Caused by", e.created_by], ["Class id", e.scheduled_class_id], ["Attendance id", e.attendance_id], ["Request id", e.request_id], ["Person id", e.individual_id],
      ["Log id", e.id]]);
    if (e.handled_at) L.push(["Handled", e.handled_at + " by " + (e.handled_by || "")]);
    return L.filter(function (x) { return x[1] !== undefined && x[1] !== null && x[1] !== ""; });
  }
  function mCopy(text, what, btn) {
    var done = function () {
      $("mNotice").textContent = what + " copied.";
      if (btn) { var was = btn.getAttribute("data-was") || btn.textContent; btn.setAttribute("data-was", was); var wasL = btn.getAttribute("data-wasl") || btn.getAttribute("aria-label") || ""; btn.setAttribute("data-wasl", wasL); btn.textContent = "Copied ✓"; if (wasL) btn.setAttribute("aria-label", "Copied ✓ " + wasL); btn.classList.add("copied");
        clearTimeout(btn._t); btn._t = setTimeout(function () { btn.textContent = was; if (wasL) btn.setAttribute("aria-label", wasL); btn.removeAttribute("data-wasl"); btn.classList.remove("copied"); btn.removeAttribute("data-was"); }, 2000); }
    };
    var fallback = function () {
      var t = document.createElement("textarea"); t.value = text; t.style.position = "fixed"; t.style.opacity = "0"; document.body.appendChild(t); t.select();
      var ok = false; try { ok = document.execCommand("copy"); } catch (x) { ok = false; }
      document.body.removeChild(t);
      if (ok) done(); else $("mMsg").textContent = "Could not copy. Select the text and copy it yourself.";
    };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, fallback); else fallback();
  }
  function mEntryText(e) {
    var t = mFactsText(e).map(function (x) { return x[0] + ": " + x[1]; });
    (e.notes || []).forEach(function (n) { t.push("Note (" + n.at + ", " + n.by + "): " + n.text); });
    return t.join("\n");
  }
  function mDetail(e) {
    var box = mk("div", "mdetail"), desc = mKindWord(e.kind) + (e.to ? " to " + e.to : "");
    function say(b, t) { b.setAttribute("aria-label", t + " (" + desc + ")"); return b; }
    var dl = mk("dl", ""); mFactsText(e).forEach(function (x) { dl.appendChild(mk("dt", "", x[0])); dl.appendChild(mk("dd", "", String(x[1]))); });
    box.appendChild(dl);
    var nb = mk("div", "mnotes"); nb.appendChild(mk("b", "", "Notes (" + (e.notes ? e.notes.length : 0) + ")"));
    (e.notes || []).forEach(function (n) {
      var d = mk("div", "mnote"); d.appendChild(mk("div", "", n.text));
      d.appendChild(mk("div", "who", (n.at ? window.ConsoleFormat.time(new Date(n.at)) : "") + " · " + (n.by || ""))); nb.appendChild(d);
    });
    if (!(e.notes && e.notes.length)) nb.appendChild(mk("div", "empty2", "No notes yet."));
    box.appendChild(nb);
    var lab = mk("label", "f", "Add a note"); var ta = document.createElement("textarea"); ta.maxLength = 1000; ta.id = "mNote-" + e.id; lab.htmlFor = ta.id;
    ta.placeholder = "What did you find out? The next person will read this.";
    box.appendChild(lab); box.appendChild(ta);
    var err = mk("div", "msg", ""); err.setAttribute("role", "alert");
    var btns = mk("div", "btns");
    var add = mk("button", "btn-secondary", "Add note"); add.type = "button"; say(add, "Add note");
    add.addEventListener("click", function () {
      var text = ta.value.trim(); err.textContent = "";
      if (!text) { err.textContent = "Write the note first."; return; }
      add.disabled = true;
      admin("add_note", { id: e.id, text: text }, "communication_logs").then(function (res) {
        add.disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status !== 200 || !res.body || !res.body.ok) { err.textContent = res.status === 409 ? "Someone else changed this message. Refresh and try again." : "The note was not saved. " + adminProblem(res.status); return; }
        e.notes = res.body.data.notes; $("mNotice").textContent = "Note added."; mRender();
      });
    });
    btns.appendChild(add);
    if (e.status === "not_sent" && !e.handled_at) {
      var h = mk("button", "btn-primary", "Mark handled"); h.type = "button"; say(h, "Mark handled");
      h.title = "Say what you did about it, for example phoned her. The note box above is used as the comment.";
      h.addEventListener("click", function () {
        err.textContent = ""; h.disabled = true;
        var args = { id: e.id }; if (ta.value.trim()) args.note = ta.value.trim().slice(0, 500);
        admin("mark_handled", args, "communication_logs").then(function (res) {
          h.disabled = false;
          if (res.status === 401) { lock("That key did not work."); return; }
          if (res.status !== 200 || !res.body || !res.body.ok) { err.textContent = "Could not mark it handled. " + adminProblem(res.status); return; }
          $("mNotice").textContent = "Marked handled."; loadMessagesStation();
        });
      });
      btns.appendChild(h);
    }
    var c1 = mk("button", "btn-link", "Copy entry"); c1.type = "button"; say(c1, "Copy entry"); c1.addEventListener("click", function () { mCopy(mEntryText(e), "Entry", c1); });
    var c2 = mk("button", "btn-link", "Copy as JSON"); c2.type = "button"; say(c2, "Copy as JSON"); c2.addEventListener("click", function () { mCopy(JSON.stringify(e, null, 2), "JSON", c2); });
    btns.appendChild(c1); btns.appendChild(c2);
    if (e.scheduled_class_id) {
      var j = mk("button", "btn-link", "Open the class attendance"); j.type = "button"; say(j, "Open the class attendance");
      j.addEventListener("click", function () { var c = K.classById(e.scheduled_class_id); if (c) K.openAttendance(c); else $("mMsg").textContent = "That class could not be found."; });
      btns.appendChild(j);
    }
    box.appendChild(btns); box.appendChild(err);
    return box;
  }
  function mRender() {
    var sel = mSelected(), q = $("mSearch").value.trim(), list = $("mList");
    list.textContent = "";
    var shown = MS.recs.filter(function (e) { return mMatches(e, sel, q); });
    shown.forEach(function (e) {
      var tone = mNeedsAttention(e) ? "bad" : e.status === "sent" ? "ok" : "mid";
      var li = mk("li", "mrec " + tone); li.setAttribute("data-log", e.id);
      var head = mk("button", "mhead"); head.type = "button"; head.setAttribute("aria-expanded", MS.open[e.id] ? "true" : "false");
      var l1 = mk("div", "mline1");
      l1.appendChild(mk("span", "", mWhen(e)));
      l1.appendChild(mk("span", "", mKindWord(e.kind)));
      l1.appendChild(mk("span", "mchip " + e.status, M_STATUS_WORD[e.status] || e.status));
      if (e.trigger === "manual") l1.appendChild(mk("span", "mtag", "by hand"));
      if (e.is_redirected) l1.appendChild(mk("span", "mtag", "test address"));
      if (e.handled_at) l1.appendChild(mk("span", "mtag", "handled"));
      if (e.notes && e.notes.length) l1.appendChild(mk("span", "mtag", "📝 " + e.notes.length + (e.notes.length === 1 ? " note" : " notes")));
      l1.appendChild(mConf(e) ? mk("span", "mconf", mConf(e)) : mk("span", "mconf none", "—"));
      head.appendChild(l1);
      var why = e.status === "sent" ? "" : (e.status === "failed" || e.status === "unknown" ? M_STATUS_WORD[e.status] + (e.error_code ? " (" + e.error_code.replace(/_/g, " ") + ")" : "") : mReasonWord(e.reason));
      var nx = !mNeedsAttention(e) ? "" : e.status === "failed" ? "Next: check the address, send it again if needed, and add a note." : e.status === "unknown" ? "Next: find out if it arrived, then add a note." : "Next: reach them another way, then mark it as dealt with.";
      head.appendChild(mk("div", "mline2", [e.to ? "To " + e.to : "", e.subject || "", why].filter(Boolean).join(" · ")));
      if (nx) head.appendChild(mk("div", "mnext", nx));
      head.addEventListener("click", function () {
        MS.open[e.id] = !MS.open[e.id]; mRender();
        var again = $("mList").querySelector('[data-log="' + e.id + '"] .mhead'); if (again) again.focus();
      });
      li.appendChild(head);
      if (MS.open[e.id]) li.appendChild(mDetail(e));
      list.appendChild(li);
    });
    $("mCount").textContent = shown.length + (shown.length === 1 ? " message" : " messages") + (shown.length !== MS.recs.length ? " of " + MS.recs.length : "");
    $("mEmpty").hidden = shown.length > 0 || !MS.loaded;
    var n = {}; MS.recs.forEach(function (e) { n[e.status] = (n[e.status] || 0) + 1; });
    var cnt = {}; M_STATUS.forEach(function (s) { cnt[s] = n[s] || 0; });
    mChips().setCounts(MS.loaded ? { status: cnt } : {});
    var attn = MS.recs.filter(mNeedsAttention).length;
    $("mSummary").textContent = MS.recs.length ? M_STATUS.filter(function (s) { return n[s]; }).map(function (s) { return n[s] + " " + M_STATUS_WORD[s].toLowerCase(); }).join(" · ") + (attn ? " · " + attn + " need" + (attn === 1 ? "s" : "") + " attention" : " · nothing needs attention") : "";
    mChips().setNote(q ? "Searching the whole log for \u201c" + q + "\u201d: the filters are ignored." : "");
    mChips().setBadge("attention", MS.loaded ? attn : "");
    mChips().setResult(MS.loaded ? $("mCount").textContent : "");   // the same line as the head, repeated inside the popover so a tick can be watched while it covers the list
  }
  function loadMessagesStation() {
    var my = ++MS.seq;
    $("mMsg").textContent = "";
    mBuildChips();
    Promise.all([K.classChoices(), admin("list", { limit: 200, order: "-created_at" }, "communication_logs"),
                 K.requests(), admin("list", { limit: 200, order: "-created_at", expand: true }, "attendances"), admin("list", { limit: 200 }, "individuals")]).then(function (both) {
      if (my !== MS.seq || !K.key()) return;
      var res = both[1];
      // Confirmation numbers: a log entry names its request directly, or (older entries) through its attendance.
      var rq = {}, at = {}, got = function (r) { return r.status === 200 && r.body && r.body.ok ? r.body.data.records || [] : []; };
      (both[2] || []).forEach(function (r) { rq[r.id] = r.confirmation_number; });
      MS.person = {}; MS.att = {};
      got(both[4]).forEach(function (p) { MS.person[p.id] = p.display_name || [p.given_name, p.family_name].filter(Boolean).join(" "); });
      got(both[3]).forEach(function (a) { at[a.id] = a.request_id; var nm = attName(a); if (a.person) { MS.att[a.id] = { name: nm, role: a.role }; MS.person[a.individual_id] = MS.person[a.individual_id] || nm; } });
      MS.conf = {};
      (res.body && res.body.data && res.body.data.records || []).forEach(function (e) {
        var c = rq[e.request_id] || rq[at[e.attendance_id]]; if (c) MS.conf[e.id] = c;
      });
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body || !res.body.ok) { $("mMsg").textContent = "Could not load the messages. " + adminProblem(res.status); return; }
      MS.recs = res.body.data.records || []; MS.loaded = true; MS.capped = MS.recs.length >= 200;
      $("mChecked").textContent = "Last checked " + window.ConsoleFormat.clock(new Date()) + (MS.capped ? ". Showing the newest 200: narrow it with the filters or search." : "");
      mBuildChips(); mRender();
      // A student who left (or was removed) is no longer in the live list, so ask for those placements by id and fill in the names.
      var gone = []; MS.recs.forEach(function (e) { if (e.attendance_id && !MS.att[e.attendance_id] && gone.indexOf(e.attendance_id) < 0 && gone.length < 60) gone.push(e.attendance_id); });
      if (!gone.length) return;
      Promise.all(gone.map(function (id) { return admin("get", { id: id, include_deleted: true, expand: true }, "attendances"); })).then(function (rs) {
        if (my !== MS.seq) return;
        rs.forEach(function (r) { var a = r.status === 200 && r.body && r.body.ok ? r.body.data : null; if (a && a.person) { MS.att[a.id] = { name: attName(a), role: a.role }; MS.person[a.individual_id] = MS.person[a.individual_id] || attName(a); } });
        mRender();
      });
    });
  }
  $("mRefresh").addEventListener("click", function () { $("mNotice").textContent = ""; loadMessagesStation(); });
  $("mSearch").addEventListener("input", function () { mRender(); });

  // Called by console.js: show() when the person opens Messages, reset() when the Console locks or signs out (the log leaves the page with them).
  window.MessagesStation = {
    show: function () { loadMessagesStation(); },
    reset: function () {
      MS.seq++; MS.recs = []; MS.loaded = false; MS.capped = false; MS.open = {}; MS.conf = {}; MS.person = {}; MS.att = {};
      ["mList", "mSummary", "mMsg", "mNotice", "mChecked", "mCount"].forEach(function (id) { var n = $(id); if (n) n.textContent = ""; });
      var s = $("mSearch"); if (s) s.value = "";
      if ($("mEmpty")) $("mEmpty").hidden = true;
      if (MS.cf) { MS.cf.setCounts({}); MS.cf.setBadge("attention", ""); MS.cf.setResult(""); MS.cf.setNote(""); }   // the numbers beside the chips came from the log too
    }
  };
})();
