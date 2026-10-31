/* The Home page for the Console: the station tiles (Daily work, Records, Admin, and the "Coming soon" tile) and the page's hooks. Moved out of console.js
   (H-2) with the code unchanged. The station list comes through ConsoleKit.surfaces(). The waiting-to-be-placed card on Home is drawn by the Requests
   station; Home only asks for it to be refreshed (ConsoleKit.refreshPlaced). Loaded by index.html after console.js and the shared files. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var $ = function (id) { return document.getElementById(id); };
  var SURFACES = K.surfaces();
  var COMING = [
    { name: "More stations", blurb: "New collections dock here as they are built." }
  ];

  // ---- The tiles (built once, at load)
  var tiles = $("stationTiles");
  SURFACES.forEach(function (sf) {
    var t = document.createElement("button"); t.type = "button"; t.className = "tile" + (sf.admin ? " adm" : ""); t.dataset.go = sf.id;
    t.innerHTML = '<span class="tno"></span><span class="tname"></span><span class="tdesc"></span>';
    t.querySelector(".tname").textContent = sf.name; t.querySelector(".tno").textContent = sf.admin ? "Admin" : ["requests", "messages", "attendance"].indexOf(sf.id) >= 0 ? "Daily work" : "Records"; t.querySelector(".tdesc").textContent = sf.blurb;
    tiles.appendChild(t);
  });
  COMING.forEach(function (c) {
    var d = document.createElement("div"); d.className = "tile soon";
    d.innerHTML = '<span class="tno">Coming soon</span><span class="tname"></span><span class="tdesc"></span>';
    d.querySelector(".tname").textContent = c.name; d.querySelector(".tdesc").textContent = c.blurb;
    tiles.appendChild(d);
  });

  // ---- "Needs you now" (P-102): messages that did not go out, and people invited who have not signed in yet. Each row has one button to the screen that fixes it.
  // Shown only to a role that may open that screen; the box stays hidden when nothing needs anyone. The message rule is the one on the Messages switch "Needs attention".
  var needSeq = 0;
  function needsAttention(e) { return e.status === "failed" || e.status === "unknown" || (e.status === "not_sent" && !e.handled_at); }
  function okRes(res) { return !!res && res.status === 200 && !!res.body && !!res.body.ok; }
  function needRow(text, go, label) {
    var d = document.createElement("div"); d.className = "aitem";
    var t = document.createElement("div"), b = document.createElement("b"); b.textContent = text; t.appendChild(b); d.appendChild(t);
    var row = document.createElement("div"); row.className = "arow";
    var btn = document.createElement("button"); btn.type = "button"; btn.className = "btn-secondary"; btn.dataset.go = go; btn.textContent = label; row.appendChild(btn); d.appendChild(row);
    return d;
  }
  function loadNeeds() {
    var my = ++needSeq, box = $("needBox"), body = $("needBody"), badge = $("needBadge");
    var canMsg = K.can("view_messages"), canAcc = K.can("manage_access");
    if (!canMsg && !canAcc) { box.hidden = true; return; }
    Promise.all([canMsg ? K.admin("list", { limit: 200, order: "-created_at" }, "communication_logs") : null, canAcc ? K.admin("list", { limit: 200 }, "access_persons") : null]).then(function (r) {
      if (my !== needSeq || !K.key()) return;
      body.textContent = ""; var total = 0;
      if (r[0] && okRes(r[0])) {
        var logs = r[0].body.data.records || [], n = logs.filter(needsAttention).length;
        if (n) { total += n; body.appendChild(needRow(n + (n === 1 ? " message did not go out" : " messages did not go out") + (logs.length >= 200 ? " (of the newest 200)" : ""), "messages", "Open Messages")); }
      }
      if (r[1] && okRes(r[1])) {
        var m = (r[1].body.data.records || []).filter(function (p) { return p.is_active && !p.last_sign_in_at; }).length;
        if (m) { total += m; body.appendChild(needRow(m + (m === 1 ? " person was invited and has not signed in yet" : " people were invited and have not signed in yet"), "access", "Open Access")); }
      }
      badge.textContent = total; badge.hidden = !total; box.hidden = !total;
    }, function () { if (my === needSeq) box.hidden = true; });
  }

  window.HomeStation = {
    show: function () { K.refreshPlaced(); loadNeeds(); },   // arriving on Home: refresh the waiting card and the needs-you-now box
    reset: function () { needSeq++; $("needBox").hidden = true; $("needBody").textContent = ""; $("homeView").hidden = true; },   // the Console locked
    access: function () {   // hide the tiles this person's role can never open
      Array.prototype.forEach.call(document.querySelectorAll("#stationTiles [data-go]"), function (b) { b.style.display = K.allowed(b.dataset.go) ? "" : "none"; });
    }
  };
})();
