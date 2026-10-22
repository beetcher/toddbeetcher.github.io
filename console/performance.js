/* Performance station for the Console (P-80): how fast the Console is. Read only. Today one section: Sign-in speed, from the timings every
   sign-in sends (performance_events). Needs the view_performance capability (a super admin has it; the Global Inspector looks too). Loaded by
   index.html after the main script; talks to enjoy_admin through ConsoleKit. More sections (Spend and others) are meant to slot in here. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var mk = K.mk, root = null, MAXN = 500;
  var S = { days: 7, device: "all", records: [], loaded: false, msg: "", seq: 0 };

  function $(id) { return document.getElementById(id); }
  function ok(res) { return res.status === 200 && res.body && res.body.ok; }
  function fmt(ms) { return ms === null || ms === undefined ? "n/a" : ms < 1000 ? Math.round(ms) + " ms" : (ms / 1000).toFixed(1) + " s"; }
  function median(a) { if (!a.length) return null; var s = a.slice().sort(function (x, y) { return x - y; }), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }
  function mean(a) { return a.length ? a.reduce(function (x, y) { return x + y; }, 0) / a.length : null; }
  function num(r, f) { return typeof r[f] === "number" ? r[f] : null; }
  function btn(text, cls, fn) { var b = mk("button", cls || "", text); b.type = "button"; b.addEventListener("click", fn); return b; }

  function inView() {
    var cutoff = Date.now() - S.days * 86400000;
    return S.records.filter(function (r) { return Date.parse(r.created_at) >= cutoff && (S.device === "all" || r.device === S.device); });
  }

  // Where the time goes, on average: the server waking up and the network, the server's own work, loading the lists, and everything else
  // (Google and the page). A record without server numbers counts all of its first call as "waking up and network".
  function parts(rows) {
    var wake = [], work = [], load = [], other = [];
    rows.forEach(function (r) {
      var check = num(r, "check_ms"), ld = num(r, "load_ms"), srv = num(r, "server_ms"), tot = num(r, "total_ms") || 0;
      if (check === null) return;
      var w = srv === null ? check : Math.max(check - srv, 0);
      wake.push(w); if (srv !== null) work.push(srv); load.push(ld || 0); other.push(Math.max(tot - check - (ld || 0), 0));
    });
    return [["Waking up and network", mean(wake), "#c0392b"], ["Server work", mean(work), "#e67e22"], ["Loading the lists", mean(load), "#2e86c1"], ["Everything else (page)", mean(other), "#7f8c8d"]];
  }

  function tile(label, value, note) {
    var t = mk("div", "pfT"); t.appendChild(mk("div", "pfV", value)); t.appendChild(mk("div", "pfL", label)); if (note) t.appendChild(mk("div", "pfN", note)); return t;
  }

  function style() {
    if ($("perfStyle")) return;
    var s = document.createElement("style"); s.id = "perfStyle";
    s.textContent = ".pfv{max-width:1000px;margin:0 auto}.pfv .pfbar{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;margin:10px 0}.pfv .pfseg{display:flex;gap:4px}" +
      ".pfv .pfseg button{min-height:44px}.pfv .pfseg button.on{background:var(--ink,#1a1a2e);color:#fff}.pfv select{font:inherit;padding:8px;min-height:44px}" +
      ".pfv .pftiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:12px 0}.pfv .pfT{border:1px solid #d8d2c4;border-radius:10px;padding:10px 12px;background:#fff}" +
      ".pfv .pfV{font-size:24px;font-weight:800}.pfv .pfL{font-weight:700;font-size:14px}.pfv .pfN,.pfv .pfm{font-size:13px;color:var(--muted)}" +
      ".pfv .pfstack{display:flex;height:34px;border-radius:8px;overflow:hidden;border:1px solid #d8d2c4;margin:8px 0}.pfv .pfstack div{min-width:2px}" +
      ".pfv .pfkey{display:flex;gap:14px;flex-wrap:wrap;font-size:14px;margin:6px 0 14px}.pfv .pfkey i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-1px}" +
      ".pfv .pftab{width:100%;border-collapse:collapse;font-size:14px;background:#fff}.pfv .pftab th,.pfv .pftab td{text-align:left;padding:6px 8px;border-bottom:1px solid #e6e0d2;white-space:nowrap}" +
      ".pfv .pfscroll{overflow-x:auto}.pfv .pfcold{color:#c0392b;font-weight:700}";
    document.head.appendChild(s);
  }

  function draw() {
    if (!root) return;
    root.textContent = "";
    var wrap = mk("div", "pfv");
    var h = mk("div", "pfbar"); h.appendChild(mk("h2", "", "Performance")); h.appendChild(btn("Refresh", "quiet", function () { load(); })); wrap.appendChild(h);
    wrap.appendChild(mk("h3", "", "Sign-in speed"));
    wrap.appendChild(mk("p", "pfm", "How long signing in to the Console takes, measured by each person's own page from the moment Google accepts them until the Console is ready. Nothing here can be changed."));
    var bar = mk("div", "pfbar"), seg = mk("div", "pfseg");
    [[7, "7 days"], [30, "30 days"], [90, "90 days"]].forEach(function (d) {
      var b = btn(d[1], S.days === d[0] ? "on" : "quiet", function () { S.days = d[0]; draw(); }); b.setAttribute("data-days", d[0]); seg.appendChild(b);
    });
    bar.appendChild(seg);
    var f = mk("div", ""), sel = mk("select", ""); sel.id = "pfDevice"; sel.setAttribute("aria-label", "Device");
    [["all", "All devices"], ["phone", "Phones"], ["desktop", "Computers"]].forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; sel.appendChild(op); });
    sel.value = S.device; sel.addEventListener("change", function () { S.device = sel.value; draw(); }); f.appendChild(sel); bar.appendChild(f);
    wrap.appendChild(bar);
    if (S.msg) { wrap.appendChild(mk("p", "msg", S.msg)); root.appendChild(wrap); return; }
    if (!S.loaded) { wrap.appendChild(mk("p", "pfm", "Loading…")); root.appendChild(wrap); return; }
    var rows = inView();
    if (!rows.length) { wrap.appendChild(mk("p", "pfm", "No sign-ins recorded in this time yet. Each sign-in adds one.")); root.appendChild(wrap); return; }
    var tot = rows.map(function (r) { return r.total_ms; }), colds = rows.filter(function (r) { return typeof r.cold === "boolean"; }), nCold = colds.filter(function (r) { return r.cold; }).length;
    var tiles = mk("div", "pftiles");
    tiles.appendChild(tile("Sign-ins", String(rows.length), "in " + S.days + " days"));
    tiles.appendChild(tile("Typical (median)", fmt(median(tot))));
    tiles.appendChild(tile("Slowest", fmt(Math.max.apply(null, tot))));
    tiles.appendChild(tile("Server was asleep", colds.length ? Math.round(100 * nCold / colds.length) + "%" : "n/a", colds.length ? nCold + " of " + colds.length + " sign-ins" : "no data"));
    wrap.appendChild(tiles);
    wrap.appendChild(mk("h3", "", "Where the time goes (average)"));
    var ps = parts(rows), sum = ps.reduce(function (a, p) { return a + (p[1] || 0); }, 0) || 1, stack = mk("div", "pfstack"), key = mk("div", "pfkey");
    stack.setAttribute("role", "img"); stack.setAttribute("aria-label", ps.map(function (p) { return p[0] + " " + fmt(p[1]); }).join(", "));
    ps.forEach(function (p) {
      if (p[1] === null) return;
      var d = mk("div", ""); d.style.width = (100 * p[1] / sum) + "%"; d.style.background = p[2]; d.title = p[0] + ": " + fmt(p[1]); stack.appendChild(d);
      var k = mk("span", ""), sw = mk("i", ""); sw.style.background = p[2]; k.appendChild(sw); k.appendChild(document.createTextNode(p[0] + " " + fmt(p[1]))); key.appendChild(k);
    });
    wrap.appendChild(stack); wrap.appendChild(key);
    wrap.appendChild(mk("h3", "", "Recent sign-ins"));
    var sc = mk("div", "pfscroll"), tb = mk("table", "pftab"), hd = mk("tr", "");
    ["When", "Role", "Device", "How", "Total", "First call", "Server", "Lists", "Asleep"].forEach(function (t) { hd.appendChild(mk("th", "", t)); }); tb.appendChild(hd);
    rows.slice(0, 30).forEach(function (r) {
      var tr = mk("tr", ""), cold = r.cold === true ? "yes" : r.cold === false ? "no" : "n/a";
      [K.when(r.created_at), String(r.role_key || "").replace(/_/g, " "), r.device === "phone" ? "Phone" : "Computer", r.method === "key" ? "Admin key" : "Google",
       fmt(r.total_ms), fmt(num(r, "check_ms")), fmt(num(r, "server_ms")), fmt(num(r, "load_ms")), cold].forEach(function (t, i) {
        var td = mk("td", i === 8 && cold === "yes" ? "pfcold" : "", t); tr.appendChild(td);
      }); tb.appendChild(tr);
    });
    sc.appendChild(tb); wrap.appendChild(sc);
    wrap.appendChild(mk("p", "pfm", "Showing up to " + MAXN + " of the newest sign-ins; the table lists the latest 30. \"Asleep\" means the server had just woken up, which is the usual cause of a slow first sign-in."));
    root.appendChild(wrap);
  }

  function load() {
    var my = ++S.seq; S.msg = ""; S.loaded = false; draw();
    return K.admin("list", { order: "-created_at", limit: MAXN }, "performance_events").then(function (res) {
      if (my !== S.seq) return;
      if (!ok(res)) { S.msg = res.status === 403 ? "You do not have access to Performance." : "Could not load the timings. Try Refresh."; S.records = []; }
      else S.records = (res.body.data && res.body.data.records) || [];
      S.loaded = true; draw();
    });
  }

  function show() { style(); root = $("performanceView"); load(); }
  window.PerformanceStation = {
    show: show,
    reset: function () { S = { days: 7, device: "all", records: [], loaded: false, msg: "", seq: S.seq + 1 }; var v = $("performanceView"); if (v) v.innerHTML = ""; root = null; }
  };
})();
