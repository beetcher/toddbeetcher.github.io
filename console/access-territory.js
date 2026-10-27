/* Access: the Territory tab (P-60): who works where, as two views of the same grants. Loaded before access.js; access.js hands in what it owns. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var mk = K.mk, S = null, redraw = null, btn = null, TERR = window.ConsoleAccessRoles.TERR, areaByKind = null, sortBy = null, regionsOf = null, roleOf = null, grantsOf = null, grantCaps = null, areaName = null, stateName = null, regionNames = null;
  function bind(c) { redraw = c.draw; S = c.S; btn = c.btn; areaByKind = c.areaByKind; sortBy = c.sortBy; regionsOf = c.regionsOf; roleOf = c.roleOf; grantsOf = c.grantsOf; grantCaps = c.grantCaps; areaName = c.areaName; stateName = c.stateName; regionNames = c.regionNames; }

  function whoName(p) { return p.display_name || p.email; }
  function territoryView(wrap) {
    var h = mk("div", "ac1"); h.appendChild(mk("h2", "", "Who works where"));
    var tabs = mk("div", "acbtns");
    [["region", "By region"], ["capability", "By capability"]].forEach(function (t) { tabs.appendChild(btn(t[1], S.view === t[0] ? "" : "quiet", function () { S.view = t[0]; redraw(); })); });
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
  function drawTerritory(wrap, c) { bind(c); territoryView(wrap); }
  window.ConsoleAccessTerritory = { draw: drawTerritory };
})();
