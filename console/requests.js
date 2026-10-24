/* Requests station for the Console: the registration requests, newest first, each a card with its steps (placed, confirmed, attended), Put in a class,
   History, Mark handled and Delete; the Show filter with its counts; the banner for requests waiting for a trainer; the Deleted list with Restore;
   the 20 second check for new requests; and, for Home, the "Waiting to be placed" panel. It also holds the placed-requests data (P, loadPlaced)
   that Classes and Attendance refresh after they place or remove someone.
   Moved out of console.js (the Requests run, R-4): the code is the same; everything it used to borrow from the big file now comes through
   ConsoleKit, the venue and curriculum names through ConsoleNames and the Journal through ConsoleDialogs. The page markup (#listView) lives in index.html
   and the manual text in the stations list in console.js (DT-7). Loaded by index.html after console.js, names.js and dialogs.js. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var $ = function (id) { return document.getElementById(id); };
  var C = K.consts();   // true constants only
  var MAX = C.MAX, READ_MS = C.READ_MS, ATT_RANK = C.ATT_RANK, ATT_GONE = C.ATT_GONE;
  var mk = K.mk, admin = K.admin, lock = K.lock, adminProblem = K.adminProblem, when = K.when, can = K.can, canPlaced = K.canPlaced,
      fetchRecords = K.fetchRecords, fetchT = K.fetchT, netShow = K.netShow, putInClass = K.putInClass, line = K.line, str = K.str, problem = K.problem, goTo = K.go;

  var known = {};        // id -> record
  var rows = {};         // id -> <li>
  var timer = null;
  var busy = false;
  var firstLoadDone = false;
  var REFRESH_MS = 20000;
  var TYPES = { private: "One on one", group: "Small group", "class": "Workshop" };
  var FIRST_FIELDS = ["confirmation_number", "registration_type", "created_at", "processing_status", "first_name", "last_name",
                      "email", "phone", "attendee_count", "program_slug", "source", "id"];

  function newest() {
    var best = "";
    Object.keys(known).forEach(function (id) { if (known[id].created_at > best) best = known[id].created_at; });
    return best;
  }


  function buildRow(rec, isNew) {
    var li = document.createElement("li");
    if (isNew) li.className = "isnew";
    li.setAttribute("data-tone", rec.coverage_waiting ? "wait" : rec.coverage_handled_at ? "done" : "none");

    var head = document.createElement("button");
    head.className = "head";
    head.type = "button";
    head.setAttribute("aria-expanded", "false");

    var top = document.createElement("div"); top.className = "top";
    var conf = document.createElement("span"); conf.className = "conf"; conf.textContent = rec.confirmation_number || rec.id || "";
    var type = document.createElement("span"); type.className = "type"; type.textContent = TYPES[rec.registration_type] || rec.registration_type || "";
    top.appendChild(conf); top.appendChild(type);

    var w = document.createElement("div"); w.className = "when"; w.textContent = when(rec.created_at);
    var who = document.createElement("div"); who.className = "who";
    who.textContent = [rec.first_name, rec.last_name].filter(Boolean).join(" ") || "(no name)";
    var email = document.createElement("div"); email.className = "sub"; email.textContent = rec.email || "";

    var chips = document.createElement("div"); chips.className = "chips";
    if (rec.attendee_count != null && rec.attendee_count > 1) { var ppl = document.createElement("span"); ppl.textContent = rec.attendee_count + " people"; chips.appendChild(ppl); }
    if (rec.postal_code) { var zc = document.createElement("span"); zc.textContent = "ZIP: " + rec.postal_code; chips.appendChild(zc); }
    if (rec.regions) { var rg = document.createElement("span"); rg.className = "rtag"; rg.textContent = "Region: " + (rec.regions.length ? rec.regions.map(function (x) { return x.name; }).join(", ") : "none yet"); chips.appendChild(rg); }
    if (rec.coverage_waiting) { var nc = document.createElement("span"); nc.className = "nochip"; nc.textContent = "No active trainer"; chips.appendChild(nc); }
    else if (rec.coverage_handled_at) { var hc = document.createElement("span"); hc.className = "donechip"; hc.textContent = "Handled: no trainer"; chips.appendChild(hc); }
    if (rec.preferred_venue_id) {
      var vc = document.createElement("span"); vc.className = "venuechip";
      vc.textContent = "Venue asked for: " + (ConsoleNames.venueAsked(rec.preferred_venue_id) || "picked on the form");
      vc.setAttribute("data-vid", rec.preferred_venue_id);
      chips.appendChild(vc);
      ConsoleNames.ensureVenueChips();
    }

    if (rec.curriculum_id) {   // the topic the requester picked on the form
      var cc = document.createElement("span"); cc.className = "curchip";
      cc.textContent = "Interested in: " + (ConsoleNames.curriculumAsked(rec.curriculum_id) || "picked on the form");
      cc.setAttribute("data-cid", rec.curriculum_id);
      chips.appendChild(cc);
      ConsoleNames.ensureCurriculumChips();
    }

    [top, w, who, email, chips].forEach(function (n) { head.appendChild(n); });

    var detail = document.createElement("div"); detail.className = "detail";
    // A short plain summary first; every stored field stays available under "All details".
    var sum = document.createElement("div"); sum.className = "dsum";
    function srow(k, v) { if (v === undefined || v === null || v === "") return; sum.appendChild(line(k, String(v))); }
    srow("Name", [rec.first_name, rec.last_name].filter(Boolean).join(" "));
    srow("Email", rec.email); srow("Phone", rec.phone);
    srow("Kind", TYPES[rec.registration_type] || rec.registration_type);
    srow("People", rec.attendee_count);
    srow("ZIP", rec.postal_code);
    srow("Sent", rec.created_at ? when(rec.created_at) : "");
    srow("Notes", rec.notes || rec.message || rec.comments);
    detail.appendChild(sum);
    var raw = document.createElement("details"); raw.className = "rawd";
    var rsum = document.createElement("summary"); rsum.textContent = "All details"; raw.appendChild(rsum);
    var done = {};
    FIRST_FIELDS.forEach(function (f) { if (rec[f] !== undefined) { raw.appendChild(line(f, str(rec[f]))); done[f] = 1; } });
    Object.keys(rec).sort().forEach(function (f) { if (!done[f]) raw.appendChild(line(f, str(rec[f]))); });
    detail.appendChild(raw);

    head.addEventListener("click", function () {
      var open = li.classList.toggle("open");
      head.setAttribute("aria-expanded", open ? "true" : "false");
    });

    var qrow = document.createElement("div"); qrow.className = "qrow"; qrow.hidden = true;
    var putrow = document.createElement("div"); putrow.className = "qrow qacts";
    var who2 = personOf(rec);   // every button names the request it acts on, for a screen reader
    var pb = document.createElement("button"); pb.type = "button"; pb.className = "btn-primary"; pb.textContent = "Put in a class…"; pb.setAttribute("aria-label", "Put in a class… (" + who2 + ")");
    var phost = document.createElement("div"); phost.className = "putbox"; phost.hidden = true;
    pb.addEventListener("click", function () {
      $("reqDone").hidden = true;
      if (!phost.hidden) { phost.hidden = true; phost.textContent = ""; return; }
      phost.hidden = false; putInClass(rec, phost);
    });
    var ob = document.createElement("button"); ob.type = "button"; ob.className = "btn-primary"; ob.textContent = "Open class"; ob.hidden = true; ob.setAttribute("aria-label", "Open class (" + who2 + ")");
    ob.addEventListener("click", function () { location.hash = "#/classes"; });
    putrow.appendChild(ob); putrow.appendChild(pb); li._pb = pb; li._ob = ob;
    // One History link: the journal of what happened to this request; people allowed to see it also get a link inside to every recorded change.
    var jb = document.createElement("button"); jb.type = "button"; jb.className = "btn-link"; jb.textContent = "History"; jb.setAttribute("aria-label", "History (" + who2 + ")");
    jb.addEventListener("click", function () { ConsoleDialogs.openJournal({ request_id: rec.id }, "History: " + personOf(rec), { id: rec.id, label: "this request" }); });
    putrow.appendChild(jb);
    // Mark handled (P-83): a request no active region could take. A note saying what was done is required. Not for a view-only account.
    var covbox = document.createElement("div"); covbox.className = "covbox"; covbox.hidden = true;
    if (rec.coverage_waiting && can("manage_requests") && !(K.me() && K.me().inspector)) {
      var mh = document.createElement("button"); mh.type = "button"; mh.className = "btn-secondary"; mh.textContent = "Mark handled…"; mh.setAttribute("aria-label", "Mark handled… (" + who2 + ")");
      mh.addEventListener("click", function () { covbox.hidden = !covbox.hidden; if (!covbox.hidden) { covbox.textContent = ""; fillCovBox(covbox, rec, li); } });
      putrow.appendChild(mh);
    }
    // Delete: two presses (the second says "Really delete?"). The request is marked deleted and disappears; the record is kept.
    var db = document.createElement("button"); db.type = "button"; db.className = "btn-danger"; db.textContent = "Delete"; db.style.marginLeft = "auto"; db.setAttribute("aria-label", "Delete (" + who2 + ")");
    var armedT = null;
    function disarm() { clearTimeout(armedT); db.className = "btn-danger"; db.textContent = "Delete"; db.setAttribute("aria-label", "Delete (" + who2 + ")"); db.removeAttribute("data-armed"); }
    db.addEventListener("click", function () {
      if (!db.getAttribute("data-armed")) {
        db.setAttribute("data-armed", "1"); db.className = "btn-danger"; db.textContent = "Really delete?"; db.setAttribute("aria-label", "Really delete the request from " + who2 + "?");
        armedT = setTimeout(disarm, 6000); return;
      }
      clearTimeout(armedT);
      admin("delete_request", { id: rec.id }, "attendances").then(function (res) {
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          delete known[rec.id]; delete rows[rec.id]; if (li.parentNode) li.parentNode.removeChild(li);
          $("reqDone").textContent = "Request " + (rec.confirmation_number || "") + " deleted. It is hidden from this list; the record is kept for now. ";
          var ub = document.createElement("button"); ub.type = "button"; ub.className = "btn-secondary"; ub.textContent = "Undo"; ub.setAttribute("aria-label", "Undo the delete of " + personOf(rec));
          ub.addEventListener("click", function () {
            ub.disabled = true;
            admin("restore_request", { id: rec.id }, "attendances").then(function (r2) {
              if (r2.status === 401) { lock("That key did not work."); return; }
              if (r2.status === 200 && r2.body && r2.body.ok) { $("reqDone").textContent = "Request " + (rec.confirmation_number || "") + " is back in the list."; check(true); return; }
              ub.disabled = false; $("reqDone").appendChild(document.createTextNode(" Could not undo. " + adminProblem(r2.status)));
            });
          });
          $("reqDone").appendChild(ub);
          $("reqDone").hidden = false; applyReqFilter();
          return;
        }
        disarm();
        var probs = (res.body && res.body.error && res.body.error.problems) || [];
        $("reqDone").textContent = probs.some(function (x) { return x.issue === "has_placements"; })
          ? "Not deleted: someone from this request is still in a class. Cancel or remove them in the class Attendance first, then delete the request."
          : res.status === 404 ? "That request is already gone. Refresh the list." : adminProblem(res.status);
        $("reqDone").hidden = false;
      });
    });
    putrow.appendChild(db);
    li.appendChild(head); li.appendChild(qrow); li.appendChild(putrow); li.appendChild(phost); li.appendChild(covbox); li.appendChild(detail);
    li._q = qrow; li._rec = rec;
    fillQRow(qrow, rec);
    if (isNew) setTimeout(function () { li.classList.remove("isnew"); }, 6000);
    return li;
  }

  // The Mark handled form on a request with no active trainer: what was done (required), then the server stamps who and when.
  function fillCovBox(box, rec, li) {
    var lab = mk("label", "f", "What was done about this request? (required)"); var id = "cov" + rec.id.slice(0, 8); lab.setAttribute("for", id);
    var ta = document.createElement("textarea"); ta.id = id; ta.maxLength = 2000;
    var err = mk("div", "ferr", ""); err.setAttribute("role", "alert");
    var btns = mk("div", "btns"); var go = mk("button", "btn-primary", "Mark handled"); go.type = "button";
    var no = mk("button", "btn-secondary", "Cancel"); no.type = "button";
    no.addEventListener("click", function () { box.hidden = true; box.textContent = ""; });
    go.addEventListener("click", function () {
      var note = ta.value.trim(); err.textContent = "";
      if (!note) { err.textContent = "Say what was done, so the next person knows."; ta.focus(); return; }
      go.disabled = true;
      admin("mark_request_handled", { id: rec.id, note: note }, "attendances").then(function (res) {
        go.disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          var d = res.body.data || {}; delete rec.coverage_waiting; rec.coverage_handled_at = d.coverage_handled_at || new Date().toISOString(); rec.coverage_handled_note = note;
          var fresh = buildRow(rec, false); if (li.parentNode) li.parentNode.replaceChild(fresh, li); rows[rec.id] = fresh;
          $("reqDone").textContent = "Request " + (rec.confirmation_number || "") + " marked handled."; $("reqDone").hidden = false; applyReqFilter();
          return;
        }
        var probs = (res.body && res.body.error && res.body.error.problems) || [];
        err.textContent = probs.some(function (x) { return x.issue === "not_waiting"; }) ? "This request is no longer waiting for a trainer. Refresh the list."
          : res.status === 403 ? "You may not mark this request handled." : res.status === 404 ? "That request is gone. Refresh the list." : adminProblem(res.status);
      });
    });
    btns.appendChild(go); btns.appendChild(no);
    box.appendChild(lab); box.appendChild(ta); box.appendChild(err); box.appendChild(btns);
  }

  // Add records we have not seen. Existing rows are never rebuilt, so nothing moves while reading.
  function merge(records, quiet) {
    var list = $("list");
    var fresh = records.filter(function (r) { return r && r.id && !known[r.id]; });
    fresh.sort(function (a, b) { return a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0; }); // oldest first, then each goes on top
    fresh.forEach(function (r) {
      known[r.id] = r;
      var li = buildRow(r, firstLoadDone && !quiet);
      rows[r.id] = li;
      list.insertBefore(li, list.firstChild);
    });
    // First load arrives newest first from the server; sort the whole list once to be safe.
    if (!firstLoadDone || quiet) {
      Object.keys(rows).sort(function (a, b) {
        var x = known[a].created_at, y = known[b].created_at;
        return x < y ? 1 : x > y ? -1 : 0;
      }).forEach(function (id) { list.appendChild(rows[id]); });
    }
    if (fresh.length && firstLoadDone && !quiet) loadPlaced();
    if (fresh.length) regionOptions();
    applyReqFilter();
  }


  function check(manual) {
    if (busy) return Promise.resolve();
    busy = true;
    return fetchRecords(firstLoadDone ? newest() : "").then(function (res) {
      busy = false;
      if (res.status === "ok") {
        $("listMsg").textContent = "";
        merge(res.records);
        if (!firstLoadDone) UI.limitNote($("list"), res.records.length, MAX, "Showing the newest " + MAX + " requests. Older ones are not listed here.");
        firstLoadDone = true;
        $("checkedText").textContent = "Last checked " + K.clock(new Date());
      } else if (res.status === "unauthorized") {
        lock("That key did not work.");
      } else if (manual || !firstLoadDone || res.status !== "network") {
        $("listMsg").textContent = problem(res.status);
      } else {
        $("listMsg").textContent = "Could not reach the server. Will try again.";
      }
      return res;
    });
  }

  function startTimer() {
    stopTimer();
    timer = setInterval(function () { if (!document.hidden) check(false); }, REFRESH_MS);
  }
  function stopTimer() { if (timer) { clearInterval(timer); timer = null; } }

  function reset() {
    known = {}; rows = {}; firstLoadDone = false;
    $("list").textContent = "";
    $("countText").textContent = ""; $("checkedText").textContent = ""; $("listMsg").textContent = "";
    $("empty").hidden = true;
    RS.seq++; clearTimeout(RS.timer); RS.total = null; RS.regions = {}; $("rSearch").value = "";
    if (RS.cf) { RS.cf.destroy(); RS.cf = null; $("rChips").textContent = ""; }
  }

  // ======== Placed requests: a request is placed once attendance exists for it (old seat decisions are retired) ========
  var P = { loaded: false, ids: {}, cls: {}, num: {}, st: {}, reqs: [], error: "" };
  var qSeq = 0;
  function personOf(it) { return [it.first_name, it.last_name].filter(Boolean).join(" ") || "(no name)"; }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

  function loadPlaced() {
    if (!canPlaced()) return Promise.resolve();
    var my = ++qSeq;
    return Promise.all([admin("list", { limit: 200, expand: true }, "attendances"), firstLoadDone ? Promise.resolve(null) : fetchRecords("")]).then(function (both) {
      if (my !== qSeq || !K.key()) return;
      var res = both[0];
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body.ok) { P.error = adminProblem(res.status); P.loaded = P.loaded && true; }
      else {
        P.error = ""; P.loaded = true; P.ids = {}; P.cls = {}; P.num = {}; P.st = {};
        (res.body.data.records || []).forEach(function (r) { if (r.request_id && !ATT_GONE[r.status]) { var rk = ATT_RANK[r.status] || 1; if (rk > (P.st[r.request_id] || 0)) P.st[r.request_id] = rk; P.ids[r.request_id] = (P.ids[r.request_id] || 0) + 1; P.cls[r.request_id] = (r["class"] && r["class"].title) || P.cls[r.request_id] || "a class"; } });
      }
      if (both[1] && both[1].status === "ok") P.reqs = both[1].records || [];
      else if (firstLoadDone) P.reqs = Object.keys(known).map(function (id) { return known[id]; });
      decorateCards(); renderAttention();
    });
  }
  function decorateCards() { Object.keys(rows).forEach(function (id) { if (rows[id]._q) fillQRow(rows[id]._q, known[id]); }); applyReqFilter(); }
  function fillQRow(box, rec) {
    box.textContent = "";
    if (!P.loaded) { box.hidden = true; return; }
    box.hidden = false;
    var n = P.ids[rec.id];
    var rli = box.parentNode;
    if (rli) rli.setAttribute("data-tone", n ? "ok" : rec.coverage_waiting ? "wait" : rec.coverage_handled_at ? "done" : "none");   // a quiet edge and tint; the chip carries the words   // the card: once placed, "Open class" is the main button and "Put in a class" steps back
    if (rli && rli._pb) { rli._ob.hidden = !n; rli._pb.className = n ? "btn-secondary" : "btn-primary"; }
    if (n) box.appendChild(mk("span", "qchip ok", "Closed · placed in " + (P.cls[rec.id] || "a class")));
    else if (!rec.coverage_waiting && !rec.coverage_handled_at) box.appendChild(mk("span", "qchip warn", "Open · not placed yet"));   // a handled request already shows "Handled: …" above, so no second status chip   // a request with no trainer already shows its own chip above
    // One plain line saying what to do next, from fields the card already has.
    var next = n ? "Next: nothing. Open the class to see attendance."
      : rec.coverage_waiting ? "Next: find a trainer for this ZIP, then Mark handled."
      : rec.coverage_handled_at ? "Next: put this request in a class when a trainer is found."
      : "Next: put this request in a class.";
    box.appendChild(mk("span", "qnext", next));
    // Where the request is on its way: New, Placed, Confirmed, Attended (the furthest placement counts).
    var at = n ? (P.st[rec.id] || 1) : 0, strip = mk("div", "qstrip");
    strip.setAttribute("role", "group"); strip.setAttribute("aria-label", "Progress of this request");
    ["New", "Placed", "Confirmed", "Attended"].forEach(function (w, i) {
      var li2 = mk("span", i < at ? "done" : i === at ? "now" : "", w); if (i === at) li2.setAttribute("aria-current", "step"); strip.appendChild(li2);
    });
    box.appendChild(strip);
  }
  // Which requests the list shows: open ones (not yet in a class) by default. Closed means a class holds the student.
  // The Show filter is a segmented control (a radio group). The hidden #reqShow select stays as the one place the choice is kept, so code elsewhere can set it and call applyReqFilter().
  function buildReqSeg() {
    var host = $("reqSeg"); host.textContent = "";
    Array.prototype.forEach.call($("reqShow").options, function (o) {
      var b = mk("button", "", o.textContent.replace(/ requests$/, "").replace(/^No active trainer$/, "No active trainer")); b.type = "button"; b.dataset.v = o.value;
      b.setAttribute("role", "radio"); b.setAttribute("aria-checked", "false"); b.tabIndex = -1;
      host.appendChild(b);
    });
  }
  function syncReqSeg() {
    var v = $("reqShow").value;
    Array.prototype.forEach.call($("reqSeg").children, function (b) { var on = b.dataset.v === v; b.setAttribute("aria-checked", on ? "true" : "false"); b.tabIndex = on ? 0 : -1; });
  }
  // How many each choice would show, written on the choice itself ("Open 3"). A count we cannot know yet is left off.
  function setSegCounts(c) {
    Array.prototype.forEach.call($("reqSeg").children, function (b) {
      var sp = b.querySelector(".segn"); if (!sp) { sp = mk("span", "segn", ""); b.appendChild(sp); }
      var v = c[b.dataset.v]; sp.textContent = (v === null || v === undefined) ? "" : String(v);
    });
  }
  function pickReq(v, focus) { $("reqShow").value = v; applyReqFilter(); if (focus) { var t = $("reqSeg").querySelector('[data-v="' + v + '"]'); if (t) t.focus(); } }
  function applyReqFilter() {
    syncReqSeg();
    var mode = $("reqShow").value, shown = 0, open = 0, isDel = mode === "deleted";
    Object.keys(rows).forEach(function (id) {
      var closed = P.loaded && !!P.ids[id];
      if (!closed) open++;
      var show = !isDel && srMatch(known[id]) && (mode === "all" || (mode === "notrainer" ? !!(known[id] && known[id].coverage_waiting) : mode === "closed" ? closed : !closed));
      rows[id].style.display = show ? "" : "none";
      if (show) shown++;
    });
    var n = Object.keys(known).length;
    setSegCounts({ open: open, closed: P.loaded ? Object.keys(rows).length - open : null, all: Object.keys(rows).length, notrainer: Object.keys(known).filter(function (id) { return known[id].coverage_waiting; }).length });
    var wait = Object.keys(known).filter(function (id) { return known[id].coverage_waiting; }).length, cb = $("covBanner");
    cb.textContent = "";
    if (wait) {
      cb.appendChild(document.createTextNode(wait + (wait === 1 ? " request is" : " requests are") + " waiting for a trainer"));
      if (mode !== "notrainer") { var sb = mk("button", "btn-secondary", "Show them"); sb.type = "button"; sb.addEventListener("click", function () { $("reqShow").value = "notrainer"; applyReqFilter(); }); cb.appendChild(sb); }
      if (K.me() && !K.me().inspector && (K.me().is_super_admin || K.me().role_key === "admin")) {   // Send reminders now: the daily reminder, by hand (the server checks too)
        var rb = mk("button", "btn-secondary", "Send reminders now"); rb.type = "button";
        rb.addEventListener("click", function () {
          rb.disabled = true;
          admin("send_coverage_reminders", {}, "attendances").then(function (res) {
            rb.disabled = false;
            if (res.status === 401) { lock("That key did not work."); return; }
            var d = res.status === 200 && res.body && res.body.ok ? res.body.data : null;
            $("reqDone").textContent = d ? (d.sent ? "Reminders sent to " + plural(d.sent, "person", "people") + " about " + plural(d.waiting, "request", "requests") + " waiting for a trainer."
              + (d.not_sent ? " " + plural(d.not_sent, "message was", "messages were") + " not sent: see Messages." : "") : "No reminders went out. " + (d.waiting ? "See Messages for why." : "Nothing is waiting for a trainer."))
              : res.status === 403 ? "Only a super admin or an admin may send reminders." : adminProblem(res.status);
            $("reqDone").hidden = false;
          });
        });
        cb.appendChild(rb);
      }
    }
    cb.hidden = !wait || isDel;
    $("countText").textContent = mode === "notrainer" ? wait + (wait === 1 ? " request with no active trainer" : " requests with no active trainer") : !P.loaded ? n + (n === 1 ? " request" : " requests")
      : mode === "open" ? open + (open === 1 ? " open request" : " open requests") + (n > open ? " (" + (n - open) + " closed)" : "")
      : mode === "closed" ? shown + (shown === 1 ? " closed request" : " closed requests") : n + (n === 1 ? " request" : " requests");
    $("empty").textContent = mode === "notrainer" ? "No request is waiting for a trainer. Nothing to do here." : mode === "open" ? "No open requests. Every request is in a class. New sign-ups from the website show up here by themselves." : mode === "closed" ? "No closed requests yet." : "No requests yet.";
    var sr = srActive();
    if (sr && !isDel) $("countText").textContent = shown + (shown === 1 ? " request matches" : " requests match") + (RS.total != null && RS.total > shown ? " (" + RS.total.toLocaleString() + " in all, counting every Show choice)" : "");
    if (sr && shown === 0 && !isDel) $("empty").textContent = "No request matches. Clear the search or the region to see them all.";
    $("rQuick").hidden = isDel; $("rChips").hidden = isDel;
    $("empty").hidden = shown > 0 || isDel;
    if (isDel) { $("countText").textContent = "Deleted requests"; loadDeleted(); } else { $("delList").hidden = true; $("delEmpty").hidden = true; }
  }
  // ---- Search and Region: the box and the Region chip narrow what is loaded at once; after a short pause the server is asked to look through the older requests too.
  var RS = { cf: null, total: null, seq: 0, timer: null, regions: {} };
  function srChips() {
    if (RS.cf) return RS.cf;
    RS.cf = UI.chipFilters({
      mount: $("rChips"), label: "Request filters",
      filters: [{ id: "region", label: "Region", kind: "search-multi", options: [{ value: "none", label: "No region yet" }] }],
      onChange: function () { srChanged(); }
    });
    return RS.cf;
  }
  function regionOptions() {   // the regions seen on the loaded requests, plus No region yet
    var seen = false;
    Object.keys(known).forEach(function (id) { (known[id].regions || []).forEach(function (r) { if (r.id && !RS.regions[r.id]) { RS.regions[r.id] = r.name || r.id; seen = true; } }); });
    var opts = Object.keys(RS.regions).sort(function (a, b) { return RS.regions[a].toLowerCase() < RS.regions[b].toLowerCase() ? -1 : 1; }).map(function (id) { return { value: id, label: RS.regions[id] }; });
    if (seen || !RS.cf) srChips().setOptions("region", opts.concat([{ value: "none", label: "No region yet" }]));
  }
  function srSel() {   // null when every region is ticked
    var g = srChips().getSelection().region, all = Object.keys(RS.regions).length + 1;
    if (g.length >= all) return null;
    var o = {}; g.forEach(function (v) { o[v] = 1; }); return o;
  }
  function srText(rec) {
    return [rec.first_name, rec.last_name, rec.email, rec.phone, rec.postal_code, rec.confirmation_number, rec.preferred_location, rec.organization_name].concat((rec.regions || []).map(function (r) { return r.name; })).filter(Boolean).join(" ").toLowerCase();
  }
  function srActive() { return !!($("rSearch").value.trim() || srSel()); }
  function srMatch(rec) {
    if (!rec) return true;
    var sel = srSel(), q = $("rSearch").value.trim().toLowerCase();
    if (sel && rec.regions) {
      var ids = rec.regions.length ? rec.regions.map(function (r) { return r.id; }) : ["none"];
      if (!ids.some(function (i) { return sel[i]; })) return false;
    }
    if (!q) return true;
    var hay = srText(rec);
    return q.split(/\s+/).every(function (w) { return hay.indexOf(w) >= 0; });
  }
  function srChanged() {
    applyReqFilter();
    clearTimeout(RS.timer);
    var q = $("rSearch").value.trim(), sel = srSel(), pick = sel ? Object.keys(sel) : [];
    RS.total = null;
    if (!q && pick.length !== 1) return;
    var mySeq = ++RS.seq;
    RS.timer = setTimeout(function () {
      fetchRecords("", { q: q, region: pick.length === 1 ? pick[0] : "" }).then(function (res) {
        if (mySeq !== RS.seq || res.status !== "ok") return;
        RS.total = typeof res.total === "number" ? res.total : null;
        merge(res.records, true);
        applyReqFilter();
      });
    }, 400);
  }
  $("rSearch").addEventListener("input", srChanged);

  // Deleted requests (for Restore): fetched on their own, because the normal list never carries them. Each card has a Restore button.
  var delSeq = 0;
  function loadDeleted() {
    var my = ++delSeq, ul = $("delList");
    ul.textContent = ""; $("delEmpty").hidden = true; ul.hidden = false;
    var url = C.RECORDS_URL + "?limit=" + MAX + "&deleted=1";
    fetchT(url, { method: "GET", headers: { "Authorization": "Bearer " + K.key() }, cache: "no-store" }, READ_MS).then(function (r) {
      if (r.status === 401) { lock("That key did not work."); return null; }
      if (!r.ok) { $("listMsg").textContent = "Could not load the deleted requests. Try Refresh."; return null; }
      return r.json();
    }).catch(function (e) { netShow(!!(e && e.timedOut)); return null; }).then(function (j) {
      if (my !== delSeq || !j) return;
      $("listMsg").textContent = "";
      var recs = (j.data && j.data.records) || [];
      $("countText").textContent = recs.length + (recs.length === 1 ? " deleted request" : " deleted requests");
      $("delEmpty").hidden = recs.length > 0;
      recs.forEach(function (rec) {
        var li = mk("li", ""); li.setAttribute("data-tone", "done"); li.setAttribute("data-deleted", rec.id);
        var who = personOf(rec), box = mk("div", "qrow");
        box.appendChild(mk("b", "", rec.confirmation_number || ""));
        box.appendChild(mk("span", "qchip", "Deleted"));
        var meta = [who, rec.email, rec.zip_code ? "ZIP: " + rec.zip_code : "", rec.deleted_at ? "deleted " + K.time(new Date(rec.deleted_at)) : ""].filter(Boolean).join(" · ");
        box.appendChild(mk("span", "qnext", meta));
        if (can("manage_requests") && !(K.me() && K.me().inspector)) {
          var rb = mk("button", "btn-primary", "Restore"); rb.type = "button"; rb.setAttribute("aria-label", "Restore (" + who + ")");
          rb.addEventListener("click", function () {
            rb.disabled = true;
            admin("restore_request", { id: rec.id }, "attendances").then(function (r2) {
              if (r2.status === 401) { lock("That key did not work."); return; }
              if (r2.status === 200 && r2.body && r2.body.ok) { if (li.parentNode) li.parentNode.removeChild(li); $("reqDone").textContent = "Request " + (rec.confirmation_number || "") + " is back in the list."; $("reqDone").hidden = false; $("delEmpty").hidden = $("delList").children.length > 0; check(true); return; }
              rb.disabled = false; $("reqDone").textContent = "Could not restore it. " + adminProblem(r2.status); $("reqDone").hidden = false;
            });
          });
          box.appendChild(rb);
        }
        li.appendChild(box); ul.appendChild(li);
      });
    });
  }
  $("reqShow").addEventListener("change", applyReqFilter);
  buildReqSeg(); syncReqSeg();
  $("reqSeg").addEventListener("click", function (e) { var b = e.target.closest ? e.target.closest("button[data-v]") : null; if (b) pickReq(b.dataset.v, false); });
  $("reqSeg").addEventListener("keydown", function (e) {   // radio-group keys: arrows move and choose, Home and End jump
    var k = e.key, bs = Array.prototype.slice.call($("reqSeg").children), i = bs.indexOf(document.activeElement);
    if (i < 0 || ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"].indexOf(k) < 0) return;
    e.preventDefault();
    var j = k === "Home" ? 0 : k === "End" ? bs.length - 1 : (i + (k === "ArrowRight" || k === "ArrowDown" ? 1 : -1) + bs.length) % bs.length;
    pickReq(bs[j].dataset.v, true);
  });

  // Home: the "Waiting to be placed" panel.
  function renderAttention() {
    var box = $("attnBox"), body = $("attnBody"), badge = $("attnBadge");
    body.textContent = "";
    if (!P.loaded && P.error) {
      body.appendChild(document.createTextNode("Could not check the requests. " + P.error + " "));
      var rb = mk("button", "", "Try again"); rb.type = "button"; rb.addEventListener("click", function () { loadPlaced(); }); body.appendChild(rb);
      badge.hidden = true; box.className = "attn"; return;
    }
    if (!P.loaded) { body.textContent = "Checking the requests…"; badge.hidden = true; box.className = "attn"; return; }
    var noTrainer = P.reqs.filter(function (r) { return r.coverage_waiting; }).length;
    if (noTrainer) {
      var cov = mk("div", "aitem"); cov.appendChild(mk("b", "", noTrainer + (noTrainer === 1 ? " request is" : " requests are") + " waiting for a trainer"));
      var crow = mk("div", "arow"); var cg = mk("button", "", "Show them"); cg.type = "button"; cg.addEventListener("click", function () { $("reqShow").value = "notrainer"; goTo("requests"); applyReqFilter(); });
      crow.appendChild(cg); cov.appendChild(crow); body.appendChild(cov);
    }
    var waiting = P.reqs.filter(function (r) { return !P.ids[r.id]; }).sort(function (a, b) { return (a.created_at || "") < (b.created_at || "") ? 1 : -1; });
    badge.hidden = !waiting.length; badge.textContent = waiting.length;
    box.className = "attn" + (waiting.length ? " hot" : "");
    if (!waiting.length) body.appendChild(mk("div", "", "All clear. Every request is closed: its student is in a class."));
    waiting.slice(0, 8).forEach(function (it) {
      var d = mk("div", "aitem");
      var t = mk("div", ""); t.appendChild(mk("b", "", personOf(it)));
      t.appendChild(document.createTextNode(" · " + (TYPES[it.registration_type] || it.registration_type || "") + " · " + plural(it.attendee_count || 1, "person", "people") + " · " + (it.confirmation_number || "")));
      d.appendChild(t);
      var row = mk("div", "arow");
      var g = mk("button", "", "Open requests"); g.type = "button"; g.addEventListener("click", function () { goTo("requests"); });
      row.appendChild(g); d.appendChild(row); body.appendChild(d);
    });
    if (waiting.length > 8) body.appendChild(mk("div", "quietline", "and " + (waiting.length - 8) + " more. Open Requests to see them all."));
  }

  // The hooks console.js calls. show: Requests was opened. start/stop: the 20 second check. reset: the Console locked or signed out (empties the page and the placed data).
  // clearList: a new sign-in begins (the list only, as before). adopt: the first records, read while signing in. records: what is loaded (Messages reads it through the kit).
  function resetPlaced() { P = { loaded: false, ids: {}, reqs: [], error: "" }; qSeq++; }
  window.RequestsStation = {
    show: function () { loadPlaced(); startTimer(); },
    start: startTimer, stop: stopTimer, check: check, loadPlaced: loadPlaced,
    reset: function () { stopTimer(); reset(); resetPlaced(); },
    clearList: reset,
    adopt: function (recs) { merge(recs); firstLoadDone = true; $("checkedText").textContent = "Last checked " + K.clock(new Date()); },
    records: function () { return Object.keys(known).map(function (k) { return known[k]; }); }
  };
})();
