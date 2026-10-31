/* Shared dialogs for the Console: the Journal (the append-only log of placing, status changes and cancellations), opened from a request card
   and from a class. One owner, so neither page reaches into the other. Moved out of console.js (the Requests run, R-2): the code is the same;
   what it borrowed (word tables, the Change history button) now comes through ConsoleKit.
   Put in a class is NOT here: it is the placing flow and uses eight things that belong to Attendance (see claude/detangling-parking-lot.md, DT-18);
   it moves with Attendance. The dialog markup (#jrDlg) stays in index.html. Not a station: no show, nothing to empty
   (the dialog itself is closed by console.js when the Console locks). Loaded by index.html after console.js and before the stations. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var $ = function (id) { return document.getElementById(id); };
  var mk = K.mk, admin = K.admin, lock = K.lock, adminProblem = K.adminProblem, when = K.when, historyBtn = K.historyBtn;
  function W() { return window.ConsoleWords; }

  // ---- Journal: the append-only log of placing, status changes and cancellations
  var JR_WORD = { placed: "Placed in a class", status_changed: "Status changed", removed: "Removed from a class", class_cancelled: "Class cancelled", class_removed: "Class deleted", request_unassigned: "Request back to waiting to be placed" };
  function openJournal(filter, title, hist) {
    var dlg = $("jrDlg"), body = $("jrBody"), msg = $("jrMsg");
    $("jrTitle").textContent = title || "Journal"; msg.textContent = ""; body.textContent = "Loading…";
    if (!dlg.open) dlg.showModal();
    admin("list", { filters: filter, limit: 200, expand: true, order: "-created_at" }, "journal_events").then(function (res) {
      body.textContent = "";
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body.ok) { msg.textContent = "Could not load the journal. " + adminProblem(res.status); return; }
      var hb = hist && historyBtn(hist.id, hist.label);
      if (hb) { hb.className = "btn-link"; hb.textContent = "See every recorded change"; hb.addEventListener("click", function () { dlg.close(); }); body.appendChild(hb); }
      var recs = res.body.data.records || [];
      if (!recs.length) { body.appendChild(mk("div", "empty", "Nothing has happened here yet.")); return; }
      recs.forEach(function (e) {
        var d = mk("div", "jline");
        d.appendChild(mk("div", "jwhen", when(e.created_at) + (e.created_by ? " · " + e.created_by : "")));
        d.appendChild(mk("div", "jwhat", JR_WORD[e.event_type] || e.event_type));
        var bits = [];
        if (e.person && e.person.display_name) bits.push(e.person.display_name);
        if (e.role) bits.push((W().roleWord[e.role] || e.role).toLowerCase());
        if (e["class"] && e["class"].title) bits.push(e["class"].title);
        if (e.from_status || e.to_status) bits.push((e.from_status ? W().attWord[e.from_status] || e.from_status : "new") + " → " + (W().attWord[e.to_status] || e.to_status || ""));
        if (bits.length) d.appendChild(mk("div", "", bits.join(" · ")));
        if (e.note) d.appendChild(mk("div", "note", e.note));
        body.appendChild(d);
      });
    });
  }
  $("jrClose").addEventListener("click", function () { $("jrDlg").close(); });

  window.ConsoleDialogs = { openJournal: openJournal };
})();
