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

  window.HomeStation = {
    show: function () { K.refreshPlaced(); },   // arriving on Home: refresh the waiting card
    reset: function () { $("homeView").hidden = true; },   // the Console locked
    access: function () {   // hide the tiles this person's role can never open
      Array.prototype.forEach.call(document.querySelectorAll("#stationTiles [data-go]"), function (b) { b.style.display = K.allowed(b.dataset.go) ? "" : "none"; });
    }
  };
})();
