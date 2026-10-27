/* Access: the Territory tab (P-60): who works where, as two views of the same grants. Loaded before access.js; access.js hands in what it owns. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var mk = K.mk, S = null, redraw = null, btn = null, TERR = window.ConsoleAccessRoles.TERR, areaByKind = null, sortBy = null, regionsOf = null, roleOf = null, grantsOf = null, grantCaps = null, areaName = null, stateName = null, regionNames = null, capNames = window.ConsoleAccessRoles.capNames, capName = window.ConsoleAccessRoles.capName;
  function bind(c) { redraw = c.draw; S = c.S; btn = c.btn; areaByKind = c.areaByKind; sortBy = c.sortBy; regionsOf = c.regionsOf; roleOf = c.roleOf; grantsOf = c.grantsOf; grantCaps = c.grantCaps; areaName = c.areaName; stateName = c.stateName; regionNames = c.regionNames; }

  function whoName(p) { return p.display_name || p.email; }
  function territoryView(wrap) {
    var h = mk("div", "ac1"); h.appendChild(mk("h2", "", "Who works where"));
    var tabs = mk("div", "acbtns");
    [["region", "By region"], ["capability", "By permission"]].forEach(function (t) { var vb = btn(t[1], "btn-secondary", function () { S.view = t[0]; redraw(); }); vb.setAttribute("aria-pressed", S.view === t[0] ? "true" : "false"); tabs.appendChild(vb); });
    h.appendChild(tabs); wrap.appendChild(h);
    var live = S.persons.filter(function (p) { return p.is_active; });
    var holders = function (test) { var out = []; live.forEach(function (p) { var r = roleOf(p); if (r && r.is_super_admin) { out.push({ p: p, caps: TERR, why: "super admin" }); return; }
      grantsOf(p).forEach(function (g) { var res = test(g); if (res) out.push({ p: p, caps: grantCaps(g), why: res }); }); }); return out; };
    var box = mk("div", "acterr"); box.id = "acTerr";
    var anyAll = holders(function (g) { return g.kind === "all" ? "x" : null; }).some(function (h) { return h.why !== "super admin"; });
    var stateCover = function (code) { return anyAll || holders(function (g) { return g.kind === "state" && g.state_code === code ? "x" : null; }).some(function (h) { return h.why !== "super admin"; }); };
    var regionCover = function (rg, code) { return stateCover(code) || holders(function (g) { return g.kind === "regions" && (g.region_ids || []).indexOf(rg.id) >= 0 ? "x" : null; }).some(function (h) { return h.why !== "super admin"; }); };
    var gaps = {}, gapTotal = 0;
    areaByKind("state").forEach(function (stA) { var miss = regionsOf(stA.state_code).filter(function (rg) { return !regionCover(rg, stA.state_code); }); gaps[stA.state_code] = miss; gapTotal += miss.length; });
    var nc = mk("div", "acnc"); nc.id = "acNotCovered"; nc.appendChild(mk("h3", "", "Not covered"));
    if (!gapTotal) nc.appendChild(mk("div", "acm", "Every region has someone working it (super admins not counted)."));
    else {
      nc.appendChild(mk("div", "acm", gapTotal + (gapTotal === 1 ? " region has" : " regions have") + " no one but a super admin. Requests there are seen only by super admins."));
      areaByKind("state").sort(sortBy("name")).forEach(function (stA) { var miss = gaps[stA.state_code]; if (!miss.length) return; nc.appendChild(mk("div", "acm", stA.name + ": " + miss.map(function (r) { return r.name; }).join(", "))); });
    }
    box.appendChild(nc);
    if (S.view === "region") {
      var allU = holders(function (g) { return g.kind === "all" ? "whole US" : null; });
      box.appendChild(mk("div", "acm", "Whole US: " + (allU.length ? allU.map(function (h) { return whoName(h.p); }).join(", ") : "nobody")));
      areaByKind("state").sort(sortBy("name")).forEach(function (stA) {
        var d = mk("details"); d.open = false; var gn = (gaps[stA.state_code] || []).length, nreg = regionsOf(stA.state_code).length; var sm = mk("summary", "", stA.name + " \u2014 " + nreg + (nreg === 1 ? " region" : " regions") + (gn ? ", " + gn + " not covered" : "")); d.appendChild(sm);
        var admins = holders(function (g) { return g.kind === "state" && g.state_code === stA.state_code ? "state" : null; }).filter(function (h) { return h.why !== "super admin"; });
        d.appendChild(mk("div", "acm", "State administrators (every region and every ZIP, including ZIPs in no region): " + (admins.length ? admins.map(function (h) { return whoName(h.p); }).join(", ") : "nobody")));
        regionsOf(stA.state_code).forEach(function (rg) {
          var row = mk("div", "acrow"); row.appendChild(mk("div", "acn", rg.name + "  (" + ((rg.zip_codes || []).length) + " ZIPs)"));
          var hs = holders(function (g) { return g.kind === "regions" && (g.region_ids || []).indexOf(rg.id) >= 0 ? "region" : null; }).filter(function (h) { return h.why !== "super admin"; });
          if (!hs.length) row.appendChild(mk("div", "acm", "No one is given this region by name."));
          hs.forEach(function (h) { row.appendChild(mk("div", "acm", whoName(h.p) + ": " + capNames(h.caps).join(", "))); });
          d.appendChild(row);
        });
        if (!regionsOf(stA.state_code).length) d.appendChild(mk("div", "acm", "No regions in this state yet."));
        box.appendChild(d);
      });
    } else {
      TERR.forEach(function (c) {
        var d = mk("details"); d.appendChild(mk("summary", "", capName(c)));
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
