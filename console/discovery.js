/* Discovery station for the Console: find things with AI (venues first), run them within a hard spend cap, review the candidates,
   and edit everything the machine uses (models, areas, types, prompt, limits). Loaded by index.html after the main script.
   It talks to two doors: enjoy_admin (the collections, through ConsoleKit.admin) and enjoy_discovery (quote, run, stop, withdraw).
   No key is ever shown here; the page only learns whether a model's key setting exists (yes/no). */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var DISC_URL = "https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_discovery";
  var mk = K.mk, root = null;
  var S = { tab: "run", sub: "models", loaded: false, status: null, models: [], areas: [], types: [], prompts: [], settings: null,
            runs: [], openRun: null, quote: null, quoteKey: "", driving: "", stopAsk: false, seq: 0 };

  var ISSUE = { required: "Required.", duplicate: "That one is already used.", invalid_format: "That value is not valid.", out_of_range: "Too long, too short or out of range.",
    invalid_type: "That value is not valid.", invalid_value: "That value is not valid.", not_allowed: "Not allowed here.", immutable: "That cannot be changed after it is saved.",
    zip_table_missing: "The ZIP table is not loaded yet. Run build_zip_table.py once on your Mac, then deploy.", not_in_state: "A ZIP is not in this state.",
    not_found: "Not found.", conflict: "Someone changed this while you were editing. Reload and try again.", unknown_placeholder: "The text uses a {word} the machine does not supply.",
    cap_above_max: "That is above the maximum in Limits.", default_above_max: "The starting cap cannot be above the maximum.", step_above_run: "Results per step cannot be above results per run.",
    has_regions: "Delete its regions first.", published: "A published version cannot be changed. Start a draft.", draft_exists: "There is already a draft." };
  var CODE = { mode_off: "Discovery is switched off on the server (ICDT_DISCOVERY_MODE), so nothing can run.", unknown_model: "That model is not available.",
    unknown_area: "That area is not available (is it switched on?).", unknown_type: "That type is not available (is it switched on?).", unknown_finder: "That finder is not available.",
    run_not_found: "That run was not found.", run_not_active: "That run is not running any more.", nothing_to_withdraw: "This run has nothing left to take back.",
    key_missing: "That model's key is not set on the server.", too_many_steps: "That needs too many steps. Choose fewer types or a smaller area.",
    cap_too_high: "That cap is above the maximum in Limits.", results_too_high: "That is more results than the maximum in Limits.", not_ready: "Discovery is not ready: check the status line.",
    unauthorized: "That key did not work." };
  var REASON = { no_street_address: "No street address", address_not_matched: "Address not matched", operator_unconfirmed: "Operator is a new organization: confirm it" };

  function $(id) { return document.getElementById(id); }
  function esc(n) { return n == null ? "" : String(n); }
  function usd(c) { c = Number(c) || 0; return "$" + (c / 100).toFixed(2); }
  function el(tag, cls, text) { return mk(tag, cls, text); }
  function btn(text, cls, fn) { var b = el("button", cls || "", text); b.type = "button"; if (fn) b.addEventListener("click", fn); return b; }
  function labelled(text, input, hint) {
    var w = el("div", "dfield"); var l = el("label", "f", text); if (input.id) l.setAttribute("for", input.id); w.appendChild(l); w.appendChild(input);
    if (hint) w.appendChild(el("div", "dhint", hint)); return w;
  }
  function problemsText(res) {
    var e = res && res.body && res.body.error; if (!e) return res && res.status === 0 ? "Could not reach the server." : "Something went wrong. Try again.";
    if (res.status === 401) return CODE.unauthorized;
    var parts = (e.problems || []).map(function (p) { return (p.field ? p.field.replace(/_/g, " ") + ": " : "") + (ISSUE[p.issue] || p.issue); });
    return (CODE[e.code] || e.message || "That did not go through.") + (parts.length ? " " + parts.join(" ") : "");
  }
  function ok(res) { return res && res.status === 200 && res.body && res.body.ok; }
  function recs(res) { return ok(res) ? res.body.data.records || [] : []; }

  // ---- the two doors
  function disc(op, args, quiet) {
    var b = !quiet && K.lastButton();
    if (b) { b.classList.add("working"); b.setAttribute("aria-busy", "true"); }
    if (!quiet) K.toast("", "Working…", 0);
    return fetch(DISC_URL, { method: "POST", cache: "no-store", headers: { "Authorization": "Bearer " + K.key(), "Content-Type": "application/json" },
        body: JSON.stringify({ op: op, args: args || {} }) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { status: r.status, body: j }; }); })
      .catch(function () { return { status: 0, body: {} }; })
      .then(function (res) {
        if (b) { b.classList.remove("working"); b.removeAttribute("aria-busy"); }
        if (!quiet) { if (res.status === 401) K.toast("", "", 1); else K.toast(ok(res) ? "ok" : "bad", ok(res) ? "Done" : "That did not go through. See the message.", ok(res) ? 1800 : 3500); }
        if (res.status === 401) K.lock("That key did not work.");
        return res;
      });
  }
  function adm(op, args, coll) { return K.admin(op, args, coll); }

  // ---- loading
  function loadAll() {
    var my = ++S.seq; setMsg("");
    return Promise.all([disc("status", {}, true), adm("list", { limit: 200 }, "discovery_models"), adm("list", { limit: 200 }, "discovery_areas"),
                        adm("list", { limit: 200 }, "discovery_types"), adm("list", { limit: 200 }, "discovery_prompts"), adm("list", { limit: 5 }, "discovery_settings")]).then(function (r) {
      if (my !== S.seq || !K.key()) return;
      if (!ok(r[0])) { setMsg("Could not reach Discovery. " + problemsText(r[0])); }
      S.status = ok(r[0]) ? r[0].body.data : null;
      S.models = recs(r[1]); S.areas = recs(r[2]); S.types = recs(r[3]); S.prompts = recs(r[4]); S.settings = recs(r[5])[0] || null; S.loaded = true;
      $("dChecked").textContent = "Last checked " + K.clock(new Date());
      drawAll();
    });
  }
  function loadRuns() {
    return disc("list_runs", { limit: 50 }, true).then(function (r) {
      if (ok(r)) { S.runs = r.body.data.records || []; }
      else setMsg("Could not load the runs. " + problemsText(r));
      drawRuns();
    });
  }
  function setMsg(t) { var m = $("dMsg"); if (m) m.textContent = t || ""; }
  function setNote(t) { var m = $("dNotice"); if (m) m.textContent = t || ""; }

  // ---- skeleton
  function build() {
    root = $("discoveryView"); root.innerHTML = "";
    var style = el("style"); style.textContent =
      ".dcard{background:#fff;border:1px solid #d8d2c4;border-radius:10px;padding:12px 14px;margin:10px 0}" +
      ".dcard h3,.dcard h4{margin:0 0 6px}.dtabs{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}" +
      ".dtabs button{min-height:44px;padding:6px 16px;border-radius:999px;border:2px solid var(--muted);background:#fff;color:var(--ink);font:inherit;font-weight:700;cursor:pointer}" +
      ".dtabs button[aria-pressed=true]{background:var(--orange);color:var(--ink);border-color:var(--orange)}" +
      ".dfield{margin:10px 0}.dfield input[type=text],.dfield input[type=number],.dfield select,.dfield textarea{width:100%;max-width:640px;box-sizing:border-box;font:inherit;padding:8px;min-height:44px}" +
      ".dfield textarea{min-height:140px}.dhint{font-size:13px;color:var(--muted);margin-top:2px}.dgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:6px}" +
      ".dchip{display:inline-block;border-radius:999px;padding:2px 10px;font-size:13px;font-weight:700;border:1px solid #bbb;margin:2px 4px 2px 0;background:#f2efe6}" +
      ".dchip.sure{background:#d9f2c4;border-color:#5c9a00;color:#1d4d00}.dchip.verify{background:#ffe9b3;border-color:#c98a00;color:#6a4500}.dchip.unknown{background:#fff;border-style:dashed;color:#666}" +
      ".dchip.bad{background:#fbd5d5;border-color:#b00020;color:#6a0014}.dchip.good{background:#d9f2c4;border-color:#5c9a00;color:#1d4d00}" +
      ".dbanner{padding:10px 14px;border-radius:8px;margin:10px 0;font-weight:600;background:#ffe9b3;border:1px solid #c98a00}.dbanner.live{background:#d9f2c4;border-color:#5c9a00}.dbanner.off{background:#fbd5d5;border-color:#b00020}" +
      ".drow{display:flex;gap:8px;flex-wrap:wrap;align-items:center;justify-content:space-between}.dmini{font-size:14px;color:#555}" +
      ".dprompt{white-space:pre-wrap;font:13px/1.4 ui-monospace,Menlo,Consolas,monospace;background:#f6f3ea;border:1px solid #d8d2c4;border-radius:6px;padding:10px;max-height:340px;overflow:auto}" +
      ".dtable{border-collapse:collapse;width:100%;font-size:14px}.dtable th,.dtable td{border-bottom:1px solid #e4dfd2;text-align:left;padding:4px 6px;vertical-align:top}" +
      ".dprog{height:14px;border-radius:7px;background:#e9e4d8;overflow:hidden;margin:8px 0}.dprog>div{height:100%;background:var(--orange);width:0}" +
      ".dmap{width:100%;height:auto;display:block}.dmap .dst path{fill:#e3ded0;stroke:#fff;stroke-width:1;cursor:pointer}.dmap .dst.on path{fill:#9fd36b}.dmap .dst:hover path{fill:#f3c98a}.dmap .dst.sel path{stroke:var(--orange);stroke-width:3}.dmap .dst:focus{outline:none}.dmap .dst:focus-visible path{stroke:#000;stroke-width:3}" +
      ".dmap .dlab{font:700 11px sans-serif;fill:#1d4d00;pointer-events:none}.dzips{border:1px solid #d8d2c4;border-radius:6px;background:#e4dfd2;touch-action:none;cursor:crosshair;user-select:none}.dzips circle{cursor:pointer}.dbox{fill:rgba(255,138,0,.15);stroke:#ff8a00;stroke-dasharray:4 3}" +
      ".dswatch{display:inline-block;width:14px;height:14px;border-radius:50%;vertical-align:middle;border:1px solid #333}.dkey{padding:4px 0}.btns button[aria-pressed=true]{background:var(--orange);color:var(--ink)}" +
      ".dcard input[type=text],#dStateFind,#dRegName{font:inherit;min-height:44px;padding:6px 12px;border:1px solid var(--muted);border-radius:10px;background:#fff;color:var(--ink);box-sizing:border-box}#dRegName{flex:1 1 220px;min-width:200px}#dStateFind{width:100%;max-width:640px;margin:6px 0}.dstate{fill:#faf8f2;stroke:#4a443b;stroke-width:2;stroke-linejoin:round;vector-effect:non-scaling-stroke;pointer-events:none}#dTip{position:fixed;z-index:60;background:#1c1a17;color:#fff;font:600 13px/1.3 sans-serif;padding:5px 9px;border-radius:6px;pointer-events:none;max-width:260px}#dTip[hidden]{display:none}.dfound{fill:none;stroke:#d6006f;stroke-width:3;vector-effect:non-scaling-stroke;pointer-events:none}#dFind input{max-width:150px}#dSelList{margin:6px 0;padding:8px 10px;max-height:110px;overflow:auto;border:1px solid #d8d2c4;border-radius:6px;background:#faf8f2;font:14px/1.5 ui-monospace,Menlo,Consolas,monospace;word-spacing:2px}#dScroll{overflow:auto;max-height:72vh;max-width:100%;border-radius:6px}" +
      ".dsw{min-height:44px;min-width:84px;border-radius:999px;border:2px solid var(--muted);background:#e9e4d8;color:var(--ink);font:inherit;font-weight:700;cursor:pointer}.dsw[aria-checked=true]{background:var(--new);border-color:#5c9a00;color:#1d4d00}";
    root.appendChild(style);
    var bar = el("div", "bar"); var left = el("div"); var c = el("div", "count", "Discovery"); c.id = "dCount"; var m = el("div", "meta"); m.id = "dChecked"; left.appendChild(c); left.appendChild(m);
    var act = el("div", "actions"); var man = btn("Manual", "quiet manualBtn"); man.dataset.m = "discovery"; act.appendChild(man); act.appendChild(btn("Refresh", "", function () { setNote(""); loadAll(); if (S.tab === "runs") loadRuns(); }));
    act.lastChild.id = "dRefresh"; bar.appendChild(left); bar.appendChild(act); root.appendChild(bar);
    var ban = el("div", "dbanner"); ban.id = "dBanner"; ban.setAttribute("role", "status"); root.appendChild(ban);
    var tabs = el("div", "dtabs"); tabs.id = "dTabs";
    [["run", "Find venues"], ["runs", "Runs"], ["settings", "Settings"]].forEach(function (t) {
      var b = btn(t[1], "", function () { S.tab = t[0]; S.openRun = null; drawTabs(); if (t[0] === "runs") loadRuns(); }); b.dataset.tab = t[0]; tabs.appendChild(b);
    });
    root.appendChild(tabs);
    var n = el("div", "notice"); n.id = "dNotice"; n.setAttribute("role", "status"); var e = el("div", "msg"); e.id = "dMsg"; e.setAttribute("role", "alert"); root.appendChild(n); root.appendChild(e);
    ["dRun", "dRuns", "dSettings"].forEach(function (id) { var d = el("div"); d.id = id; root.appendChild(d); });
  }
  function drawTabs() {
    Array.prototype.forEach.call($("dTabs").children, function (b) { b.setAttribute("aria-pressed", b.dataset.tab === S.tab ? "true" : "false"); });
    $("dRun").hidden = S.tab !== "run"; $("dRuns").hidden = S.tab !== "runs"; $("dSettings").hidden = S.tab !== "settings";
    if (S.tab === "runs") drawRuns();
  }
  function drawAll() { drawBanner(); drawRun(); drawSettings(); drawTabs(); }
  function drawBanner() {
    var b = $("dBanner"), st = S.status; b.className = "dbanner";
    if (!st) { b.textContent = "Discovery status is not known yet."; return; }
    var parts = [];
    if (st.mode === "live") { b.classList.add("live"); parts.push("LIVE: runs call the AI and spend real money, within the cap you set."); }
    else if (st.mode === "dry_run") parts.push("DRY RUN: nothing is sent to the AI and nothing is spent. You can see the plan and the exact prompts.");
    else { b.classList.add("off"); parts.push("OFF: Discovery is switched off on the server, so nothing can run. (Set ICDT_DISCOVERY_MODE to dry_run or live and deploy.)"); }
    if (!st.zip_table || !st.zip_table.loaded) parts.push("The ZIP table is not loaded, so regions cannot be saved yet.");
    else parts.push("ZIP table: " + st.zip_table.zip_count + " ZIPs.");
    b.textContent = parts.join(" ");
  }

  // ---- RUN tab
  function active(list) { return list.filter(function (r) { return r.is_active; }); }
  function byName(a, b) { return String(a.name || a.label).localeCompare(String(b.name || b.label)); }
  function modelNote(m) { return m.key_name && S.status && !S.status.keys[m.key_name] ? " (key not set)" : ""; }
  function areaIds() { return Array.prototype.map.call(document.querySelectorAll("#dRun input[data-area]:checked"), function (c) { return c.value; }); }
  function typeKeys() { return Array.prototype.map.call(document.querySelectorAll("#dRun input[data-type]:checked"), function (c) { return c.value; }); }
  function formReq() {
    return { finder_key: "venue", model_id: $("dModel") ? $("dModel").value : "", area_ids: areaIds(), type_keys: typeKeys(),
             max_results: parseInt($("dMax").value, 10), spend_cap_cents: parseInt($("dCap").value, 10) };
  }
  function drawRun() {
    var host = $("dRun"); host.innerHTML = ""; S.quote = null; S.quoteKey = "";
    var s = S.settings || {};
    var card = el("div", "dcard"); card.appendChild(el("h3", "", "Find venues"));
    card.appendChild(el("p", "dmini", "Pick a model, an area and the kinds of place. Estimate first; nothing is spent until you press Go. Candidates arrive INACTIVE for you to review; nobody is contacted."));
    var ms = el("select"); ms.id = "dModel"; var models = active(S.models);
    models.forEach(function (m) { var o = el("option", "", m.label + modelNote(m)); o.value = m.id; if (m.key_name && S.status && !S.status.keys[m.key_name]) o.disabled = true; ms.appendChild(o); });
    if (s.default_model_id) { try { ms.value = s.default_model_id; } catch (e) {} }
    if (ms.selectedOptions.length && ms.selectedOptions[0].disabled) { for (var i = 0; i < ms.options.length; i++) if (!ms.options[i].disabled) { ms.selectedIndex = i; break; } }
    card.appendChild(labelled("Model", ms, models.length ? "Add or switch off models in Settings." : "No model is switched on. Add one in Settings."));
    // area: state then regions
    var states = active(S.areas).filter(function (a) { return a.kind === "state"; }).sort(byName);
    var ss = el("select"); ss.id = "dState"; states.forEach(function (a) { var o = el("option", "", a.name); o.value = a.id; ss.appendChild(o); });
    card.appendChild(labelled("State", ss, states.length ? "Only states switched on in Settings are listed." : "No state is switched on. Switch one on in Settings > Areas."));
    var ah = el("div", "dfield"); ah.id = "dAreas"; card.appendChild(ah);
    var th = el("fieldset", "fs"); th.appendChild(el("legend", "", "What kinds of place")); th.id = "dTypes";
    var types = active(S.types).filter(function (t) { return t.finder_key === "venue"; }).sort(function (a, b) { return (a.sort_order || 0) - (b.sort_order || 0) || byName(a, b); });
    types.forEach(function (t) {
      var l = el("label", "chk"); var c = el("input"); c.type = "checkbox"; c.value = t.key; c.dataset.type = "1"; l.appendChild(c); l.appendChild(document.createTextNode(" " + t.label + (t.is_chain ? " (a chain)" : ""))); th.appendChild(l);
    });
    if (!types.length) th.appendChild(el("div", "dhint", "No kind of place is switched on. Add one in Settings > Types."));
    card.appendChild(th);
    var mx = el("input"); mx.type = "number"; mx.id = "dMax"; mx.min = 1; mx.max = s.max_results_per_run || 1; mx.value = s.max_results_per_run || 10;
    card.appendChild(labelled("Most results", mx, "At most " + (s.max_results_per_run || "?") + " (set in Settings > Limits)."));
    var cp = el("input"); cp.type = "number"; cp.id = "dCap"; cp.min = 0; cp.max = s.max_spend_cap_cents || 0; cp.value = s.default_spend_cap_cents || 0;
    var capHint = el("span", "", ""); card.appendChild(labelled("Spend cap (cents)", cp, "A hard stop: the run never goes over it. The most allowed is " + usd(s.max_spend_cap_cents) + " (Settings > Limits)."));
    var acts = el("div", "btns"); var est = btn("Estimate", "", doQuote); est.id = "dEstimate"; var go = btn("Go", "", doGo); go.id = "dGo"; go.disabled = true;
    acts.appendChild(est); acts.appendChild(go); card.appendChild(acts);
    host.appendChild(card);
    var qh = el("div"); qh.id = "dQuote"; host.appendChild(qh); var ph = el("div"); ph.id = "dProgress"; host.appendChild(ph);
    if (S.prefill) { var pa = S.areas.filter(function (a) { return a.id === S.prefill; })[0]; var ps_ = pa && stateRec(pa.state_code); if (ps_ && active([ps_]).length) { try { ss.value = ps_.id; } catch (e) {} } }
    ss.addEventListener("change", function () { drawAreaPicks(); invalidate(); });
    host.addEventListener("change", invalidate); host.addEventListener("input", invalidate);
    drawAreaPicks();
  }
  function drawAreaPicks() {
    var host = $("dAreas"); if (!host) return; host.innerHTML = ""; var sid = $("dState").value; if (!sid) return;
    var st = S.areas.filter(function (a) { return a.id === sid; })[0]; if (!st) return;
    var regs = active(S.areas).filter(function (a) { return a.kind === "region" && a.state_code === st.state_code; }).sort(byName);
    var fs = el("fieldset", "fs"); fs.appendChild(el("legend", "", "Where in " + st.name));
    function box(a, text) {
      var l = el("label", "chk"); var c = el("input"); c.type = "checkbox"; c.value = a.id; c.dataset.area = a.kind; l.appendChild(c); l.appendChild(document.createTextNode(" " + text)); fs.appendChild(l); return c;
    }
    var whole = box(st, "The whole state (every ZIP in " + st.name + ")");
    var rbs = regs.map(function (r) { return box(r, r.name + " (" + (r.zip_codes || []).length + " ZIPs)"); });
    if (!regs.length) fs.appendChild(el("div", "dhint", "No regions yet. Add them in Settings > Areas."));
    whole.addEventListener("change", function () { if (whole.checked) rbs.forEach(function (c) { c.checked = false; }); });
    rbs.forEach(function (c) { c.addEventListener("change", function () { if (c.checked) whole.checked = false; }); });
    host.appendChild(fs);
    if (S.prefill) { var pc = fs.querySelector('input[value="' + S.prefill + '"]'); if (pc) { pc.checked = true; whole.checked = false; } S.prefill = ""; }
  }
  function invalidate() { if (S.quote && S.quoteKey !== JSON.stringify(formReq())) { S.quote = null; if ($("dGo")) $("dGo").disabled = true; var q = $("dQuote"); if (q) q.innerHTML = ""; } }
  function reqOk(r) {
    if (!r.model_id) return "Choose a model.";
    if (!r.area_ids.length) return "Choose where to look (the whole state or a region).";
    if (!r.type_keys.length) return "Choose at least one kind of place.";
    if (!(r.max_results >= 1)) return "Give a number of results.";
    if (!(r.spend_cap_cents >= 0)) return "Give a spend cap (0 or more cents).";
    return "";
  }
  function doQuote() {
    var r = formReq(), bad = reqOk(r); setMsg(bad); if (bad) return;
    disc("quote", r).then(function (res) {
      var q = $("dQuote"); q.innerHTML = "";
      if (!ok(res)) { setMsg(problemsText(res)); $("dGo").disabled = true; return; }
      setMsg(""); var d = res.body.data; S.quote = d; S.quoteKey = JSON.stringify(r);
      var c = el("div", "dcard"); c.appendChild(el("h3", "", "Estimate"));
      c.appendChild(el("p", "", d.steps_planned + " AI call" + (d.steps_planned === 1 ? "" : "s") + " with " + d.model_name + " in " + d.area_labels.join(", ") + ". Expected cost " +
        usd(d.estimated_cost_low_cents) + " to " + usd(d.estimated_cost_high_cents) + ". Your cap is " + usd(r.spend_cap_cents) + ". Prompt version " + d.prompt_version + "."));
      if (d.estimated_cost_high_cents > r.spend_cap_cents) c.appendChild(el("p", "dmini", "The top of the estimate is above your cap, so the run may stop early at the cap. That is the cap working."));
      if (d.run_mode === "dry_run") c.appendChild(el("p", "dmini", "This is a dry run: Go will plan the run and send nothing to the AI."));
      var det = el("details", "more"); det.appendChild(el("summary", "", "Show the exact prompts that would be sent (" + d.prompts.length + ")"));
      d.prompts.forEach(function (p) { det.appendChild(el("h4", "", "Call " + p.step + ": " + p.type_key)); det.appendChild(el("div", "dprompt", p.prompt_text)); });
      c.appendChild(det); q.appendChild(c);
      $("dGo").disabled = !(S.status && S.status.mode !== "off");
    });
  }
  function doGo() {
    var r = formReq(); if (!S.quote || S.quoteKey !== JSON.stringify(r)) { setMsg("Estimate first."); return; }
    $("dGo").disabled = true; $("dEstimate").disabled = true;
    disc("plan", r).then(function (res) {
      if (!ok(res)) { setMsg(problemsText(res)); $("dEstimate").disabled = false; return; }
      setMsg(""); drive(res.body.data.run_id, res.body.data.steps_planned);
    });
  }
  // The browser keeps asking for the next step until the run says it is done. The run record holds all progress, so closing the tab loses nothing.
  function drive(runId, planned) {
    if (S.driving) return; S.driving = runId; S.stopAsk = false;
    var host = $("dProgress"); if (S.tab !== "run") { S.tab = "run"; drawTabs(); } host = $("dProgress"); host.innerHTML = "";
    var c = el("div", "dcard"); c.appendChild(el("h3", "", "Running")); var line = el("div", "", "Starting…"); line.id = "dRunLine"; line.setAttribute("role", "status");
    var bar = el("div", "dprog"); var fill = el("div"); bar.appendChild(fill); c.appendChild(bar); c.appendChild(line);
    var stop = btn("Stop", "quiet", function () { S.stopAsk = true; stop.disabled = true; line.textContent = "Stopping after this call…"; }); stop.id = "dStop"; c.appendChild(stop); host.appendChild(c);
    var done = 0;
    function next() {
      if (S.stopAsk) { disc("stop", { run_id: runId }, true).then(function () { finish("Stopped."); }); return; }
      disc("step", { run_id: runId }, true).then(function (res) {
        if (!ok(res)) { setMsg(problemsText(res)); finish("Paused. You can continue it from Runs."); return; }
        var d = res.body.data; done = d.steps_done != null ? d.steps_done : planned;
        fill.style.width = Math.min(100, Math.round(100 * done / Math.max(1, planned))) + "%";
        line.textContent = "Call " + Math.min(done, planned) + " of " + planned + " done.";
        if (d.done) { finish(d.status === "stopped" ? "Stopped (" + (d.stop_reason || "") + ")." : "Finished."); return; }
        next();
      });
    }
    function finish(text) {
      S.driving = ""; fill.style.width = text === "Finished." ? "100%" : fill.style.width; stop.remove();
      disc("get_run", { id: runId }, true).then(function (res) {
        line.textContent = text; if ($("dEstimate")) $("dEstimate").disabled = false;
        if (ok(res)) { c.appendChild(runSummary(res.body.data)); c.appendChild(btn("Review this run", "", function () { S.tab = "runs"; drawTabs(); openRun(runId); })); }
      });
    }
    next();
  }
  function runSummary(r) {
    var d = el("div"); d.appendChild(el("p", "", "Found " + (r.found_count || 0) + ", saved " + (r.created_count || 0) + " for review, " + (r.duplicate_count || 0) + " already known, " + (r.rejected_count || 0) +
      " rejected, " + (r.attention_count || 0) + " need attention. Spent " + usd(r.actual_cost_cents) + " of a " + usd(r.spend_cap_cents) + " cap.")); return d;
  }

  // ---- RUNS tab
  function areaName(id) { var a = S.areas.filter(function (x) { return x.id === id; })[0]; return a ? a.name : "an area"; }
  var STATUS_WORD = { planned: "Planned", running: "Running", finished: "Finished", stopped: "Stopped", failed: "Failed", withdrawn: "Withdrawn" };
  function drawRuns() {
    var host = $("dRuns"); if (!host) return; host.innerHTML = "";
    if (S.openRun) { drawRunDetail(host); return; }
    if (!S.runs.length) { host.appendChild(el("div", "empty", "No runs yet. Use Find venues to start one.")); return; }
    S.runs.forEach(function (r) {
      var c = el("div", "dcard"); var top = el("div", "drow");
      var t = el("div"); t.appendChild(el("b", "", (r.area_labels || []).join(", ") || "Run")); t.appendChild(el("div", "dmini", K.when(r.created_at) + " · " + (r.model_name || "") + " · " + (r.type_keys || []).join(", ")));
      top.appendChild(t); var chip = el("span", "dchip " + (r.status === "finished" ? "good" : r.status === "failed" ? "bad" : ""), STATUS_WORD[r.status] || r.status); top.appendChild(chip); c.appendChild(top);
      c.appendChild(el("div", "dmini", (r.run_mode === "dry_run" ? "Dry run · " : "") + "saved " + (r.created_count || 0) + " · duplicates " + (r.duplicate_count || 0) + " · rejected " + (r.rejected_count || 0) + " · spent " + usd(r.actual_cost_cents) + " of " + usd(r.spend_cap_cents)));
      var b = btn("Open", "", function () { openRun(r.id); }); b.dataset.run = r.id; c.appendChild(b); host.appendChild(c);
    });
  }
  function openRun(id) {
    disc("get_run", { id: id }, true).then(function (res) {
      if (!ok(res)) { setMsg(problemsText(res)); return; }
      S.openRun = res.body.data; S.cands = null; S.candMsg = ""; drawRuns(); loadCandidates(S.openRun);
    });
  }
  function drawRunDetail(host) {
    var r = S.openRun; var back = btn("Back to the list", "quiet", function () { S.openRun = null; loadRuns(); }); host.appendChild(back);
    var c = el("div", "dcard"); c.appendChild(el("h3", "", (r.area_labels || []).join(", ")));
    c.appendChild(el("div", "dmini", K.when(r.created_at) + " · " + r.model_name + " · prompt version " + r.prompt_version + " · " + (STATUS_WORD[r.status] || r.status) + (r.stop_reason ? " (" + r.stop_reason.replace(/_/g, " ") + ")" : "") + (r.run_mode === "dry_run" ? " · dry run" : "")));
    c.appendChild(runSummary(r));
    c.appendChild(el("div", "dmini", "Calls: " + (r.steps_done || 0) + " of " + (r.steps_planned || 0) + ". Estimate " + usd(r.estimated_cost_low_cents) + " to " + usd(r.estimated_cost_high_cents) + ". Tokens in " + (r.input_tokens || 0) + ", out " + (r.output_tokens || 0) + ", searches " + (r.search_count || 0) + "."));
    var acts = el("div", "btns");
    if (r.status === "planned" || r.status === "running") {
      var cont = btn("Continue this run", "", function () { S.tab = "run"; drawTabs(); drive(r.id, r.steps_planned); }); cont.id = "dContinue";
      acts.appendChild(cont);
      acts.appendChild(btn("Stop this run", "quiet", function () { disc("stop", { run_id: r.id }).then(function (x) { if (!ok(x)) setMsg(problemsText(x)); else openRun(r.id); }); }));
    }
    var made = (r.created_venue_ids || []).length;
    if (r.status !== "withdrawn" && made) acts.appendChild(withdrawButton(r));
    c.appendChild(acts); host.appendChild(c);
    if ((r.steps || []).length) {
      var det = el("details", "more"); det.appendChild(el("summary", "", "Each AI call, and the exact prompt that was sent"));
      var tb = el("table", "dtable"); tb.innerHTML = "<tr><th>Call</th><th>Kind</th><th>Where</th><th>Result</th><th>Cost</th></tr>";
      (r.steps || []).forEach(function (s) {
        var tr = el("tr"); [s.step_number, s.type_key, areaName(s.area_id), s.status + (s.error_code ? " (" + s.error_code + ")" : "") + ", " + (s.result_count || 0) + " results", usd(s.cost_cents)].forEach(function (v) { tr.appendChild(el("td", "", String(v))); }); tb.appendChild(tr);
      });
      det.appendChild(tb);
      (r.steps || []).forEach(function (s) { if (s.prompt_text) { det.appendChild(el("h4", "", "Call " + s.step_number + " prompt")); det.appendChild(el("div", "dprompt", s.prompt_text)); } });
      host.appendChild(det);
    }
    if ((r.rejections || []).length) {
      var rj = el("details", "more"); rj.appendChild(el("summary", "", "Rejected (" + r.rejections.length + ") and why"));
      r.rejections.forEach(function (x) { rj.appendChild(el("div", "dmini", (x.name || "(no name)") + ": " + String(x.reason || "").replace(/_/g, " ") + ((x.fields || []).length ? " [" + x.fields.join(", ") + "]" : ""))); }); host.appendChild(rj);
    }
    var ch = el("div"); ch.id = "dCands"; host.appendChild(ch); drawCands();
  }
  function withdrawButton(r) {
    var b = btn("Withdraw this run", "quiet", null), armed = false;
    b.addEventListener("click", function () {
      if (!armed) { armed = true; b.textContent = "Really withdraw? Press again"; setTimeout(function () { armed = false; b.textContent = "Withdraw this run"; }, 5000); return; }
      disc("withdraw", { run_id: r.id }).then(function (x) {
        if (!ok(x)) { setMsg(problemsText(x)); return; }
        var d = x.body.data || {}; setNote("Taken back. Kept because a person has used them: " + ((d.kept || []).length || "none") + "."); openRun(r.id);
      });
    });
    b.id = "dWithdraw"; return b;
  }

  // ---- candidates (review)
  function loadCandidates(r) {
    var ids = (r.created_venue_ids || []).slice(0, 100);
    if (!ids.length) { S.cands = []; drawCands(); return; }
    var my = r.id;
    Promise.all(ids.map(function (id) { return adm("get", { id: id, include_deleted: true, expand: true }, "venues"); })).then(function (rs) {
      if (!S.openRun || S.openRun.id !== my) return;
      S.cands = rs.map(function (x) { return ok(x) ? x.body.data : null; }).filter(Boolean); drawCands();
    });
  }
  var CF = [["description", "About"], ["website_url", "Website"], ["phone", "Phone"], ["email", "Email"], ["has_wifi", "Wifi"], ["is_accessible", "Accessible"], ["allows_minors", "Allows minors"]];
  function yn(v) { return v === true ? "Yes" : v === false ? "No" : v; }
  function placeText(v) {
    var p = v.place || v.location || null; if (!p) return "";
    var a = p.address || p; var parts = [].concat(a.lines || []); var joined = parts.join(", ");
    var cityLine = [a.city || a.locality, a.state || a.region, a.postal_code].filter(Boolean).join(" ");
    if (cityLine && (!a.city || joined.indexOf(a.city) < 0)) parts.push(cityLine);
    return parts.filter(Boolean).join(", ");
  }
  function drawCands() {
    var host = $("dCands"); if (!host) return; host.innerHTML = "";
    var r = S.openRun; host.appendChild(el("h3", "", "Candidates to review"));
    host.appendChild(el("p", "dmini", "Colours are never the only signal: each fact says Sure (a source was cited), Check (the AI could not confirm it) or Unknown. Nothing is live until you activate a venue in Venues."));
    if (S.cands == null) { host.appendChild(el("div", "dmini", "Loading…")); return; }
    if (!S.cands.length) { host.appendChild(el("div", "empty", (r.created_venue_ids || []).length ? "These venues are no longer in the list." : "This run saved no candidates.")); return; }
    S.cands.forEach(function (v) {
      var d = v.discovery || {}, marks = d.marks || {}; var c = el("div", "dcard"); c.dataset.venue = v.id;
      var top = el("div", "drow"); var nm = el("b", "", v.name); top.appendChild(nm);
      var chips = el("span"); chips.appendChild(el("span", "dchip " + (v.deleted_at ? "bad" : v.status === "active" ? "good" : ""), v.deleted_at ? "Removed" : v.status === "active" ? "Active" : "Inactive"));
      if (d.needs_attention) (d.attention_reasons || []).forEach(function (rs) { chips.appendChild(el("span", "dchip verify", REASON[rs] || rs)); });
      top.appendChild(chips); c.appendChild(top);
      var tb = el("table", "dtable"); function row(label, val, mk_) {
        var tr = el("tr"); tr.appendChild(el("td", "", label)); tr.appendChild(el("td", "", val == null || val === "" ? "—" : String(val)));
        var td = el("td"); td.appendChild(el("span", "dchip " + (val == null || val === "" ? "unknown" : mk_ === "sure" ? "sure" : "verify"), val == null || val === "" ? "Unknown" : mk_ === "sure" ? "Sure" : "Check")); tr.appendChild(td); tb.appendChild(tr);
      }
      row("Name", v.name, marks.name);
      if ((d.attention_reasons || []).indexOf("no_street_address") >= 0) { row("Street address", "", ""); row("City", placeText(v), marks.city); }
      else row("Address", placeText(v), marks.street || marks.address || marks.city);
      CF.forEach(function (f) { var val = yn(v[f[0]]); if (val != null && val !== "" || marks[f[0]]) row(f[1], val, marks[f[0]]); });
      c.appendChild(tb);
      var src = (d.source_urls || []).filter(function (u) { return /^https?:\/\//.test(u); }).slice(0, 6);
      if (src.length) { var sd = el("div", "dmini", "Sources: "); src.forEach(function (u, i) { var a = el("a", "", u.replace(/^https?:\/\//, "").slice(0, 60)); a.href = u; a.target = "_blank"; a.rel = "noopener noreferrer"; sd.appendChild(a); if (i < src.length - 1) sd.appendChild(document.createTextNode(" · ")); }); c.appendChild(sd); }
      c.appendChild(btn("Open Venues to check and activate", "quiet", function () { K.go("venues"); }));
      host.appendChild(c);
    });
  }

  // ---- SETTINGS tab
  var SUBS = [["models", "Models"], ["areas", "Areas"], ["types", "Types"], ["prompt", "Prompt"], ["limits", "Limits"]];
  function drawSettings() {
    var host = $("dSettings"); host.innerHTML = ""; var tp = document.getElementById("dTip"); if (tp) tp.hidden = true; var tabs = el("div", "dtabs"); tabs.id = "dSubs";
    SUBS.forEach(function (t) { var b = btn(t[1], "", function () { S.sub = t[0]; drawSettings(); }); b.dataset.sub = t[0]; b.setAttribute("aria-pressed", S.sub === t[0] ? "true" : "false"); tabs.appendChild(b); });
    host.appendChild(tabs); var body = el("div"); body.id = "dSubBody"; host.appendChild(body);
    ({ models: drawModels, areas: drawAreas, types: drawTypes, prompt: drawPrompt, limits: drawLimits })[S.sub](body);
  }
  function refreshAfter(coll, then) {
    return adm("list", { limit: 200 }, coll).then(function (r) {
      var l = recs(r);
      if (coll === "discovery_models") S.models = l; else if (coll === "discovery_areas") S.areas = l; else if (coll === "discovery_types") S.types = l; else if (coll === "discovery_prompts") S.prompts = l; else if (coll === "discovery_settings") S.settings = l[0] || null;
      drawBanner(); drawRun(); drawSettings(); drawTabs(); if (then) then();
    });
  }
  // A generic form. fields: {name,label,kind: text|int|bool|select|textarea|zips, options:[[v,l]], hint, keepOnEdit}
  function crudForm(host, cfg, rec, done) {
    var f = el("form", "dcard"); f.noValidate = true; f.appendChild(el("h3", "", rec ? "Edit " + cfg.one : "Add " + cfg.one));
    var inputs = {};
    cfg.fields.forEach(function (fd) {
      var inp; var locked = rec && fd.immutable;
      if (fd.kind === "bool") { inp = el("input"); inp.type = "checkbox"; inp.checked = rec ? !!rec[fd.name] : !!fd.def; var w = el("label", "chk"); w.appendChild(inp); w.appendChild(document.createTextNode(" " + fd.label)); if (fd.hint) w.appendChild(el("div", "dhint", fd.hint)); f.appendChild(w); inputs[fd.name] = inp; return; }
      if (fd.kind === "select") { inp = el("select"); (fd.options || []).forEach(function (o) { var op = el("option", "", o[1]); op.value = o[0]; inp.appendChild(op); }); inp.value = rec && rec[fd.name] != null ? rec[fd.name] : (fd.def != null ? fd.def : inp.value); }
      else if (fd.kind === "textarea" || fd.kind === "zips") { inp = el("textarea"); inp.value = rec ? (fd.kind === "zips" ? (rec[fd.name] || []).join(", ") : esc(rec[fd.name])) : ""; }
      else { inp = el("input"); inp.type = fd.kind === "int" ? "number" : "text"; inp.value = rec && rec[fd.name] != null ? rec[fd.name] : (fd.def != null ? fd.def : ""); }
      inp.id = "dF_" + cfg.coll + "_" + fd.name; if (locked) inp.disabled = true; inputs[fd.name] = inp; f.appendChild(labelled(fd.label, inp, locked ? "Cannot be changed after it is saved." : fd.hint));
    });
    var err = el("div", "msg"); err.setAttribute("role", "alert"); f.appendChild(err);
    var b = el("div", "btns"); var save = btn(rec ? "Save" : "Add", "", null); save.type = "submit"; b.appendChild(save); b.appendChild(btn("Cancel", "quiet", function () { f.remove(); })); f.appendChild(b);
    f.addEventListener("submit", function (e) {
      e.preventDefault(); err.textContent = ""; var data = {};
      cfg.fields.forEach(function (fd) {
        var inp = inputs[fd.name]; if (rec && fd.immutable) return; var v;
        if (fd.kind === "bool") v = inp.checked; else if (fd.kind === "int") v = inp.value === "" ? undefined : parseInt(inp.value, 10);
        else if (fd.kind === "zips") v = inp.value.split(/[\s,;]+/).filter(Boolean); else v = inp.value.trim();
        if (v === "" || v === undefined) { if (rec && fd.kind !== "int" && rec[fd.name] != null) data[fd.name] = ""; return; }
        data[fd.name] = v;
      });
      if (cfg.fixed && !rec) Object.keys(cfg.fixed).forEach(function (k) { data[k] = cfg.fixed[k]; });
      var call = rec ? adm("update", { id: rec.id, changes: changed(rec, data), expected_updated_at: rec.updated_at }, cfg.coll) : adm("create", { data: data }, cfg.coll);
      call.then(function (res) { if (!ok(res)) { err.textContent = problemsText(res); return; } refreshAfter(cfg.coll, done); });
    });
    host.insertBefore(f, host.firstChild); var first = f.querySelector("input:not([disabled]),select,textarea"); if (first) first.focus();
  }
  function changed(rec, data) {
    var out = {}; Object.keys(data).forEach(function (k) { if (JSON.stringify(rec[k] == null ? "" : rec[k]) !== JSON.stringify(data[k])) out[k] = data[k]; }); return out;
  }
  function switchBtn(on, label, fn) {
    var b = el("button", "dsw", on ? "On" : "Off"); b.type = "button"; b.setAttribute("role", "switch"); b.setAttribute("aria-checked", on ? "true" : "false"); b.setAttribute("aria-label", label + (on ? ": on" : ": off"));
    b.addEventListener("click", fn); return b;
  }
  function toggleActive(coll, rec) { adm("update", { id: rec.id, changes: { is_active: !rec.is_active }, expected_updated_at: rec.updated_at }, coll).then(function (res) { if (!ok(res)) setMsg(problemsText(res)); else setMsg(""); refreshAfter(coll); }); }
  function listSection(host, cfg, list) {
    var top = el("div", "drow"); top.appendChild(el("h3", "", cfg.title)); var add = btn("Add " + cfg.one, "", function () { crudForm(formHost, cfg, null); }); add.id = "dAdd_" + cfg.coll; top.appendChild(add); host.appendChild(top);
    if (cfg.intro) host.appendChild(el("p", "dmini", cfg.intro));
    var formHost = el("div"); host.appendChild(formHost);
    if (!list.length) host.appendChild(el("div", "empty", "None yet."));
    list.forEach(function (rec) {
      var c = el("div", "dcard"); c.dataset.id = rec.id; var row = el("div", "drow"); var t = el("div"); t.appendChild(el("b", "", cfg.name(rec))); t.appendChild(el("div", "dmini", cfg.summary(rec))); row.appendChild(t);
      var r2 = el("div", "btns"); r2.appendChild(switchBtn(!!rec.is_active, cfg.name(rec), function () { toggleActive(cfg.coll, rec); })); r2.appendChild(btn("Edit", "quiet", function () { crudForm(formHost, cfg, rec); }));
      if (cfg.canDelete) r2.appendChild(btn("Delete", "quiet", function () { adm("soft_delete", { id: rec.id }, cfg.coll).then(function (res) { setMsg(ok(res) ? "" : problemsText(res)); refreshAfter(cfg.coll); }); }));
      row.appendChild(r2); c.appendChild(row); host.appendChild(c);
    });
  }
  var MODEL_CFG = { coll: "discovery_models", one: "model", title: "AI models", canDelete: false,
    intro: "Each model is a record: add one to make it selectable on the Find venues tab. A model that needs a key shows whether the key is set on the server (never the key itself). Prices are in whole cents per million tokens.",
    name: function (m) { return m.label; },
    summary: function (m) { var k = m.key_name ? (S.status && S.status.keys[m.key_name] ? " · key " + m.key_name + " is set" : " · key " + m.key_name + " NOT set") : " · uses the Google project"; return m.provider + " · " + m.model_name + " · in " + m.price_input_per_million_cents + "¢ / out " + m.price_output_per_million_cents + "¢ per million" + (m.has_grounding ? " · searches the web" : "") + k; },
    fields: [{ name: "provider", label: "Company", kind: "select", options: [["gemini", "Gemini (Google)"], ["claude", "Claude (Anthropic)"], ["openai", "OpenAI"]], immutable: true },
      { name: "model_name", label: "Model name (exactly as the company writes it)", kind: "text" }, { name: "label", label: "Name shown in the list", kind: "text" },
      { name: "price_input_per_million_cents", label: "Input price (cents per million tokens)", kind: "int", def: 0 }, { name: "price_output_per_million_cents", label: "Output price (cents per million tokens)", kind: "int", def: 0 },
      { name: "search_price_per_1000_cents", label: "Web search price (cents per 1000 searches)", kind: "int" }, { name: "max_output_tokens", label: "Most output tokens per call", kind: "int", def: 8192 },
      { name: "has_grounding", label: "This model can search the web", kind: "bool", def: true }, { name: "key_name", label: "Name of the server setting that holds the key (Claude and OpenAI; leave empty for Gemini)", kind: "text", hint: "Only the NAME, for example ICDT_CLAUDE_KEY. Put the key itself in the server's .env file, never here." },
      { name: "is_active", label: "Switched on", kind: "bool", def: false }, { name: "notes", label: "Notes", kind: "textarea" }] };
  function drawModels(host) { listSection(host, MODEL_CFG, S.models.slice().sort(byName)); }
  var TYPE_CFG = { coll: "discovery_types", one: "kind of place", title: "Kinds of place to look for", canDelete: true, fixed: { finder_key: "venue" },
    intro: "These are the tick boxes on the Find venues tab. The hint steers the AI.",
    name: function (t) { return t.label; }, summary: function (t) { return t.key + (t.is_chain ? " · a chain" : "") + (t.search_hint ? " · " + t.search_hint.slice(0, 90) : ""); },
    fields: [{ name: "label", label: "Name shown in the list", kind: "text" }, { name: "key", label: "Short key (letters, numbers, underscore)", kind: "text", immutable: true }, { name: "search_hint", label: "Hint for the AI", kind: "textarea" },
      { name: "is_chain", label: "This is a chain (many places, one company)", kind: "bool" }, { name: "sort_order", label: "Order in the list (small first)", kind: "int" }, { name: "is_active", label: "Switched on", kind: "bool", def: true }] };
  function drawTypes(host) { listSection(host, TYPE_CFG, S.types.filter(function (t) { return t.finder_key === "venue"; }).sort(function (a, b) { return (a.sort_order || 0) - (b.sort_order || 0); })); }
  function drawAreaList(host) {
    var states = S.areas.filter(function (a) { return a.kind === "state"; }).sort(byName), regions = S.areas.filter(function (a) { return a.kind === "region"; });
    host.appendChild(el("h3", "", "States")); host.appendChild(el("p", "dmini", "Only states switched on can be searched. Switching a state on makes every ZIP in it searchable."));
    var q = el("input"); q.type = "text"; q.id = "dStateFind"; q.placeholder = "Find a state"; q.value = S.stateFind || ""; q.setAttribute("aria-label", "Find a state"); host.appendChild(q);
    var grid = el("div", "dgrid"); host.appendChild(grid);
    function paint() {
      grid.innerHTML = ""; var f = q.value.trim().toLowerCase();
      states.filter(function (s) { return !f || s.name.toLowerCase().indexOf(f) >= 0 || s.state_code.toLowerCase() === f; }).forEach(function (s) {
        var c = el("div", "dcard"); c.dataset.id = s.id; c.appendChild(el("b", "", s.name + " (" + s.state_code + ")"));
        var n = regions.filter(function (r) { return r.state_code === s.state_code; }).length; c.appendChild(el("div", "dmini", n + " region" + (n === 1 ? "" : "s")));
        c.appendChild(switchBtn(!!s.is_active, s.name, function () { toggleActive("discovery_areas", s); })); grid.appendChild(c);
      });
    }
    q.addEventListener("input", function () { S.stateFind = q.value; paint(); }); paint();
    var stateOpts = states.map(function (s) { return [s.state_code, s.name]; });
    var cfg = { coll: "discovery_areas", one: "region", title: "Regions", canDelete: true, fixed: { kind: "region" },
      intro: "A region is a named list of ZIP codes inside one state (for example Boulder). Type the ZIPs separated by commas, spaces or new lines. Edge ZIPs: include them, we lean generous.",
      name: function (r) { return r.name + " (" + r.state_code + ")"; }, summary: function (r) { return (r.zip_codes || []).length + " ZIPs: " + (r.zip_codes || []).slice(0, 12).join(", ") + ((r.zip_codes || []).length > 12 ? "…" : ""); },
      fields: [{ name: "name", label: "Region name", kind: "text" }, { name: "state_code", label: "State", kind: "select", options: stateOpts, immutable: true }, { name: "zip_codes", label: "ZIP codes", kind: "zips" },
        { name: "is_active", label: "Switched on", kind: "bool", def: true }, { name: "notes", label: "Notes", kind: "textarea" }] };
    var rh = el("div"); host.appendChild(rh); listSection(rh, cfg, regions.sort(byName));
  }
  // ---- the map: the whole country (click a state), then a state as ZIP dots (draw a box to make or change a region)
  var NS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs) { var e = document.createElementNS(NS, tag); Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); }); return e; }
  var PALETTE = ["#1f77b4", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#2ca02c"];
  function drawAreas(host) {
    var vw = el("div", "dtabs"); vw.id = "dAreaView";
    [["map", "Map"], ["list", "List"]].forEach(function (t) {
      var b = btn(t[1], "", function () { S.areaView = t[0]; drawSettings(); }); b.id = "dView_" + t[0]; b.setAttribute("aria-pressed", (S.areaView || "map") === t[0] ? "true" : "false"); vw.appendChild(b);
    });
    host.appendChild(vw);
    if ((S.areaView || "map") === "list") { drawAreaList(host); return; }
    if (!window.US_STATES) {
      host.appendChild(el("div", "dmini", "Loading the map…"));
      var sc = document.createElement("script"); sc.src = "assets/us-states.js"; sc.onload = function () { if (S.tab === "settings" && S.sub === "areas") drawSettings(); };
      sc.onerror = function () { S.areaView = "list"; setMsg("Could not load the map outlines. The List view still works."); if (S.tab === "settings" && S.sub === "areas") drawSettings(); };
      document.head.appendChild(sc); return;
    }
    drawNation(host);
    if (S.mapState) drawStatePanel(host);
  }
  function stateRec(code) { return S.areas.filter(function (a) { return a.kind === "state" && a.state_code === code; })[0] || null; }
  function drawNation(host) {
    var U = window.US_STATES; var card = el("div", "dcard"); card.appendChild(el("h3", "", "United States"));
    card.appendChild(el("p", "dmini", "Green states are switched on. Click a state to open it: switch it on or off, see its ZIP codes, and draw regions."));
    var svg = svgEl("svg", { viewBox: U.viewBox, class: "dmap", role: "group", "aria-label": "Map of the United States" }); svg.id = "dNation";
    Object.keys(U.states).forEach(function (code) {
      var st = U.states[code], rec = stateRec(code), on = !!(rec && rec.is_active);
      var g = svgEl("g", { class: "dst" + (on ? " on" : "") + (S.mapState === code ? " sel" : ""), tabindex: "0", role: "button", "data-state": code, "aria-label": st.name + (on ? ", switched on" : ", switched off") });
      g.appendChild(svgEl("title")).textContent = st.name + (on ? " (on)" : " (off)");
      g.appendChild(svgEl("path", { d: st.d }));
      if (on || S.mapState === code) { var t = svgEl("text", { x: st.cx, y: st.cy, "text-anchor": "middle", class: "dlab" }); t.textContent = code; g.appendChild(t); }
      function pick() { S.mapState = S.mapState === code ? "" : code; S.draft = {}; S.editing = ""; S.zoom = 1; S.zoomFocus = null; drawSettings(); }
      g.addEventListener("click", pick);
      g.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
      svg.appendChild(g);
    });
    card.appendChild(svg); host.appendChild(card);
  }
  function drawStatePanel(host) {
    var code = S.mapState, U = window.US_STATES.states[code], rec = stateRec(code); var card = el("div", "dcard"); card.id = "dStatePanel";
    var top = el("div", "drow"); top.appendChild(el("h3", "", U.name + " (" + code + ")"));
    var ctl = el("div", "btns");
    if (rec) ctl.appendChild(switchBtn(!!rec.is_active, U.name, function () { toggleActive("discovery_areas", rec); }));
    ctl.appendChild(btn("Close", "quiet", function () { S.mapState = ""; S.zoom = 1; drawSettings(); })); top.appendChild(ctl); card.appendChild(top);
    host.appendChild(card);
    var cache = S.zipCache = S.zipCache || {};
    if (!cache[code]) {
      card.appendChild(el("div", "dmini", "Loading ZIP codes…"));
      disc("zips", { state_code: code }, true).then(function (r) {
        if (!ok(r)) { cache[code] = { zips: [], loaded: false, failed: true }; } else cache[code] = r.body.data;
        if (S.tab === "settings" && S.sub === "areas" && S.mapState === code) drawSettings();
      });
      return;
    }
    var data = cache[code];
    if (!data.zips.length) {
      card.appendChild(el("p", "dmini", (data.failed ? "Could not load the ZIP codes." : !data.loaded ? "The ZIP table is not loaded on the server yet (run build_zip_table.py once, then deploy)." : "No ZIP data for this state.")));
      return;
    }
    if (!window.US_OUTLINES && !S.outlinesFailed) {
      card.appendChild(el("div", "dmini", "Loading the state border…"));
      var os = document.createElement("script"); os.src = "assets/us-outlines.js";
      os.onload = function () { if (S.tab === "settings" && S.sub === "areas" && S.mapState === code) drawSettings(); };
      os.onerror = function () { S.outlinesFailed = true; if (S.tab === "settings" && S.sub === "areas" && S.mapState === code) drawSettings(); };
      document.head.appendChild(os); return;
    }
    drawDots(card, code, data.zips);
  }
  function drawDots(card, code, zips) {
    var regions = S.areas.filter(function (a) { return a.kind === "region" && a.state_code === code; }).sort(byName);
    var colorOf = {}, regOf = {}; regions.forEach(function (r, i) { (r.zip_codes || []).forEach(function (z) { if (!(z in colorOf)) { colorOf[z] = PALETTE[i % PALETTE.length]; regOf[z] = r; } }); });
    S.draft = S.draft || {};
    var lat0 = Math.min.apply(null, zips.map(function (z) { return z[1]; })), lat1 = Math.max.apply(null, zips.map(function (z) { return z[1]; }));
    var lon0 = Math.min.apply(null, zips.map(function (z) { return z[2]; })), lon1 = Math.max.apply(null, zips.map(function (z) { return z[2]; }));
    var rings = ((window.US_OUTLINES || {})[code] || []).map(function (ring) { return ring.map(function (p) { return [p[0] > 100 ? p[0] - 360 : p[0], p[1]]; }); });   // Alaska crosses the date line: shift the far-west points
    rings.forEach(function (ring) { ring.forEach(function (p) { lon0 = Math.min(lon0, p[0]); lon1 = Math.max(lon1, p[0]); lat0 = Math.min(lat0, p[1]); lat1 = Math.max(lat1, p[1]); }); });
    var k = Math.cos(((lat0 + lat1) / 2) * Math.PI / 180), W = 900, pad = 16; var spanX = Math.max((lon1 - lon0) * k, 0.01), spanY = Math.max(lat1 - lat0, 0.01);
    var sc = Math.min((W - 2 * pad) / spanX, 560 / spanY), Wd = Math.round(spanX * sc + 2 * pad), Ht = Math.round(spanY * sc + 2 * pad);
    var pos = {}; zips.forEach(function (z) { pos[z[0]] = [pad + (z[2] - lon0) * k * sc, pad + (lat1 - z[1]) * sc]; });
    card.appendChild(el("p", "dmini", zips.length + " ZIP codes. Drag a box to select the dots inside it; click a dot to pick or drop one. Selected dots are orange with a black ring. Existing regions have their own colour (see the key)."));
    var mode = el("div", "btns"); var addB = btn("Add to selection", "", null), remB = btn("Take out of selection", "quiet", null);
    function setMode(m) { S.drawMode = m; addB.setAttribute("aria-pressed", m === "add" ? "true" : "false"); remB.setAttribute("aria-pressed", m === "remove" ? "true" : "false"); }
    addB.id = "dModeAdd"; remB.id = "dModeRemove"; addB.addEventListener("click", function () { setMode("add"); }); remB.addEventListener("click", function () { setMode("remove"); }); setMode(S.drawMode || "add");
    mode.appendChild(addB); mode.appendChild(remB); card.appendChild(mode);
    var Z = S.zoom || 1, ZSTEPS = [1, 2, 4, 8];
    function setZoom(z) {
      var sc0 = $("dScroll"), f = sc0 && sc0.scrollWidth ? [(sc0.scrollLeft + sc0.clientWidth / 2) / sc0.scrollWidth, (sc0.scrollTop + sc0.clientHeight / 2) / sc0.scrollHeight] : [0.5, 0.5];
      S.zoom = z; S.zoomFocus = f; drawSettings();
    }
    var zr = el("div", "btns"); zr.id = "dZoom";
    var zIn = btn("Zoom in", "quiet", function () { setZoom(ZSTEPS[Math.min(ZSTEPS.indexOf(Z) + 1, ZSTEPS.length - 1)]); }), zOut = btn("Zoom out", "quiet", function () { setZoom(ZSTEPS[Math.max(ZSTEPS.indexOf(Z) - 1, 0)]); }), zAll = btn("Whole state", "quiet", function () { setZoom(1); });
    zIn.id = "dZoomIn"; zOut.id = "dZoomOut"; zAll.id = "dZoomReset"; zIn.disabled = Z >= 8; zOut.disabled = Z <= 1; zAll.disabled = Z <= 1;
    var zl = el("span", "dmini", " Zoom " + Z + "×" + (Z > 1 ? ". Scroll to move around, then drag a box." : "")); zl.id = "dZoomLabel"; zr.appendChild(zOut); zr.appendChild(zIn); zr.appendChild(zAll); zr.appendChild(zl); card.appendChild(zr);
    var fr = el("div", "btns"); fr.id = "dFind";
    var fz = el("input"); fz.type = "text"; fz.id = "dFindZip"; fz.placeholder = "Find a ZIP"; fz.maxLength = 5; fz.inputMode = "numeric"; fz.setAttribute("aria-label", "Find a ZIP code on the map"); fz.value = S.findText || "";
    var fgo = btn("Find", "quiet", function () { findZip(); }); fgo.id = "dFindGo";
    var fmsg = el("span", "dmini", ""); fmsg.id = "dFindMsg"; fmsg.setAttribute("role", "status");
    fr.appendChild(fz); fr.appendChild(fgo); fr.appendChild(fmsg); card.appendChild(fr);
    fz.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); findZip(); } });
    var svg = svgEl("svg", { viewBox: "0 0 " + Wd + " " + Ht, class: "dmap dzips", role: "group", "aria-label": "ZIP codes in the state" }); svg.id = "dDots"; svg.style.maxWidth = Wd + "px";
    var rBase = 4 / Math.sqrt(Z);
    if (rings.length) {
      var dd = rings.map(function (ring) { return ring.map(function (p, i) { return (i ? "L" : "M") + (pad + (p[0] - lon0) * k * sc).toFixed(1) + " " + (pad + (lat1 - p[1]) * sc).toFixed(1); }).join("") + "Z"; }).join("");
      svg.appendChild(svgEl("path", { d: dd, class: "dstate", "aria-hidden": "true" }));
    }
    var circles = {};
    zips.forEach(function (z) {
      var c = svgEl("circle", { cx: pos[z[0]][0].toFixed(1), cy: pos[z[0]][1].toFixed(1), r: rBase.toFixed(2), "data-zip": z[0] }); var lab = z[0] + (z[3] ? " " + z[3] : "") + (regOf[z[0]] ? " · " + regOf[z[0]].name : ""); c.setAttribute("role", "img"); c.setAttribute("aria-label", lab);
      svg.appendChild(c); circles[z[0]] = c;
    });
    var box = svgEl("rect", { class: "dbox", visibility: "hidden" }); svg.appendChild(box);
    function paint() {
      var n = 0;
      Object.keys(circles).forEach(function (zc) {
        var c = circles[zc], sel = !!S.draft[zc]; if (sel) n++;
        c.setAttribute("fill", sel ? "#ff8a00" : (colorOf[zc] || "#a9a395")); c.setAttribute("stroke", sel ? "#000" : "none"); c.setAttribute("stroke-width", sel ? "1.5" : "0"); c.setAttribute("r", (sel ? rBase * 1.25 : rBase).toFixed(2));
      });
      var chosen = Object.keys(S.draft).filter(function (zc) { return circles[zc]; }).sort();
      selBox.textContent = chosen.length ? chosen.join("  ") : "Nothing selected yet.";
      count.textContent = n + " ZIP" + (n === 1 ? "" : "s") + " selected" + (S.editing ? " (editing " + (S.areas.filter(function (a) { return a.id === S.editing; })[0] || {}).name + ")" : "");
      saveNew.disabled = !n; if (saveEdit) saveEdit.disabled = !n;
    }
    function toSvg(e) { var r = svg.getBoundingClientRect(); return [(e.clientX - r.left) * Wd / r.width, (e.clientY - r.top) * Ht / r.height]; }
    var start = null, moved = false, downZip = "";
    svg.addEventListener("pointerdown", function (e) { if (e.button !== 0) return; start = toSvg(e); moved = false; downZip = (e.target && e.target.getAttribute && e.target.getAttribute("data-zip")) || ""; try { svg.setPointerCapture(e.pointerId); } catch (x) {} });
    svg.addEventListener("pointermove", function (e) {
      if (!start) return; var p = toSvg(e); if (Math.abs(p[0] - start[0]) + Math.abs(p[1] - start[1]) > 6) moved = true; if (!moved) return;
      box.setAttribute("x", Math.min(start[0], p[0])); box.setAttribute("y", Math.min(start[1], p[1])); box.setAttribute("width", Math.abs(p[0] - start[0])); box.setAttribute("height", Math.abs(p[1] - start[1])); box.setAttribute("visibility", "visible");
    });
    svg.addEventListener("pointerup", function (e) {
      if (!start) return; var p = toSvg(e), s0 = start; start = null; box.setAttribute("visibility", "hidden");
      var remove = (S.drawMode === "remove") !== !!e.altKey;
      if (!moved) { var z = downZip; if (z) { if (S.draft[z]) delete S.draft[z]; else S.draft[z] = 1; paint(); } return; }
      var x0 = Math.min(s0[0], p[0]), x1 = Math.max(s0[0], p[0]), y0 = Math.min(s0[1], p[1]), y1 = Math.max(s0[1], p[1]);
      Object.keys(pos).forEach(function (zc) { var q = pos[zc]; if (q[0] >= x0 && q[0] <= x1 && q[1] >= y0 && q[1] <= y1) { if (remove) delete S.draft[zc]; else S.draft[zc] = 1; } });
      paint();
    });
    var ring = svgEl("ellipse", { class: "dfound", rx: (rBase * 3.2).toFixed(2), ry: (rBase * 3.2).toFixed(2), visibility: "hidden", "aria-hidden": "true" }); svg.appendChild(ring);
    function showFound(z, centre) {
      var c = circles[z]; if (!c) { ring.setAttribute("visibility", "hidden"); return; }
      ring.setAttribute("cx", c.getAttribute("cx")); ring.setAttribute("cy", c.getAttribute("cy")); ring.setAttribute("visibility", "visible"); ring.dataset.zip = z;
      if (centre && $("dScroll")) { var sc1 = $("dScroll"), a = sc1.getBoundingClientRect(), b = ring.getBoundingClientRect(); sc1.scrollLeft += (b.x + b.width / 2) - (a.x + a.width / 2); sc1.scrollTop += (b.y + b.height / 2) - (a.y + a.height / 2); }
    }
    function findZip() {
      var t = fz.value.trim(); S.findText = t; S.found = null; ring.setAttribute("visibility", "hidden");
      if (!/^\d{5}$/.test(t)) { fmsg.textContent = "Type all 5 digits of a ZIP code."; return; }
      var row = zips.filter(function (z) { return z[0] === t; })[0];
      if (!row) { fmsg.textContent = t + " is not a ZIP code in " + (window.US_STATES && window.US_STATES.states[code] ? window.US_STATES.states[code].name : code) + "."; return; }
      S.found = { code: code, zip: t }; showFound(t, true);
      fmsg.textContent = t + (row[3] ? " " + row[3] : "") + (regOf[t] ? " · in " + regOf[t].name : " · not in any region") + (S.draft[t] ? " · selected" : "") + ". Click the dot to pick it.";
    }
    var tip = document.getElementById("dTip");
    if (!tip) { tip = el("div"); tip.id = "dTip"; tip.setAttribute("role", "status"); tip.hidden = true; document.body.appendChild(tip); }
    tip.hidden = true;
    svg.addEventListener("pointermove", function (e) {
      var z = e.target && e.target.getAttribute && e.target.getAttribute("data-zip");
      if (!z || (start && moved)) { tip.hidden = true; return; }
      tip.textContent = e.target.getAttribute("aria-label"); tip.hidden = false; tip.style.left = Math.min(e.clientX + 14, window.innerWidth - 260) + "px"; tip.style.top = (e.clientY + 16) + "px";
    });
    svg.addEventListener("pointerleave", function () { tip.hidden = true; });
    var scroller = el("div"); scroller.id = "dScroll"; scroller.appendChild(svg); card.appendChild(scroller);
    if (Z > 1) { var baseW = Math.min(Wd, scroller.clientWidth || Wd); svg.style.width = Math.round(baseW * Z) + "px"; svg.style.maxWidth = "none"; }   // zoom is a multiple of the size you see at 1x
    if (S.zoomFocus) { scroller.scrollLeft = S.zoomFocus[0] * scroller.scrollWidth - scroller.clientWidth / 2; scroller.scrollTop = S.zoomFocus[1] * scroller.scrollHeight - scroller.clientHeight / 2; S.zoomFocus = null; }
    if (S.found && S.found.code === code) showFound(S.found.zip, true);
    var count = el("div", "dmini", ""); count.id = "dDraftCount"; count.setAttribute("role", "status"); card.appendChild(count);
    var nm = el("input"); nm.type = "text"; nm.id = "dRegName"; nm.placeholder = "Name for a new region"; nm.setAttribute("aria-label", "Name for a new region");
    var err = el("div", "msg"); err.setAttribute("role", "alert");
    var row = el("div", "btns"); row.appendChild(nm);
    var saveNew = btn("Make a new region from the selection", "", function () {
      err.textContent = ""; adm("create", { data: { kind: "region", name: nm.value.trim(), state_code: code, zip_codes: Object.keys(S.draft).sort(), is_active: true } }, "discovery_areas").then(function (r) {
        if (!ok(r)) { err.textContent = problemsText(r); return; } S.draft = {}; S.editing = ""; refreshAfter("discovery_areas");
      });
    }); saveNew.id = "dMakeRegion"; row.appendChild(saveNew);
    var saveEdit = null;
    if (S.editing) {
      var cur = S.areas.filter(function (a) { return a.id === S.editing; })[0];
      if (cur) { saveEdit = btn("Save changes to " + cur.name, "", function () {
        err.textContent = ""; adm("update", { id: cur.id, changes: { zip_codes: Object.keys(S.draft).sort() }, expected_updated_at: cur.updated_at }, "discovery_areas").then(function (r) {
          if (!ok(r)) { err.textContent = problemsText(r); return; } S.draft = {}; S.editing = ""; refreshAfter("discovery_areas");
        }); }); saveEdit.id = "dSaveRegion"; row.appendChild(saveEdit); }
    }
    row.appendChild(btn("Clear selection", "quiet", function () { S.draft = {}; S.editing = ""; drawSettings(); }));
    card.appendChild(row); card.appendChild(err);
    var selBox = el("div"); selBox.id = "dSelList"; selBox.tabIndex = 0; selBox.setAttribute("role", "group"); selBox.setAttribute("aria-label", "ZIP codes in the current selection"); card.appendChild(selBox);
    var key = el("div", "dfield"); key.appendChild(el("b", "", "Regions in this state"));
    if (!regions.length) key.appendChild(el("div", "dmini", "None yet. Select some dots and make one."));
    regions.forEach(function (r, i) {
      var li = el("div", "drow dkey"); li.dataset.region = r.id; var sw = el("span", "dswatch"); sw.style.background = PALETTE[i % PALETTE.length]; sw.setAttribute("aria-hidden", "true");
      var lab = el("span", "", " " + r.name + " (" + (r.zip_codes || []).length + " ZIPs)" + (r.is_active ? "" : " · off")); var l = el("span"); l.appendChild(sw); l.appendChild(lab); li.appendChild(l);
      var bs = el("span", "btns");
      bs.appendChild(btn("Change on the map", "quiet", function () { S.draft = {}; (r.zip_codes || []).forEach(function (z) { S.draft[z] = 1; }); S.editing = r.id; drawSettings(); }));
      bs.appendChild(btn("Search here", "quiet", function () { S.prefill = r.id; S.tab = "run"; drawRun(); drawTabs(); }));
      li.appendChild(bs); key.appendChild(li);
    });
    card.appendChild(key); paint();
  }
  // The prompt: the standing published text, an editable draft, and the version history. The exact final text is on the Find venues tab (Estimate).
  function drawPrompt(host) {
    var ps = S.prompts.filter(function (p) { return p.finder_key === "venue"; }); var pub = ps.filter(function (p) { return p.status === "published"; }).sort(function (a, b) { return b.version - a.version; });
    var draft = ps.filter(function (p) { return p.status === "draft"; })[0]; var ph = (S.status && S.status.placeholders) || [];
    host.appendChild(el("h3", "", "The instructions sent to the AI"));
    host.appendChild(el("p", "dmini", "This is the wording of the request. The machine fills in " + ph.map(function (p) { return "{" + p + "}"; }).join(", ") + " for each call. Use those words in curly braces where you want the details to appear, and use curly braces for nothing else. To see the exact final text for a run, press Estimate on the Find venues tab."));
    var msg = el("div", "msg"); msg.setAttribute("role", "alert"); host.appendChild(msg);
    if (draft) {
      var c = el("div", "dcard"); c.appendChild(el("h4", "", "Draft (not in use yet)"));
      var nm = el("input"); nm.type = "text"; nm.id = "dPName"; nm.value = draft.name || ""; c.appendChild(labelled("Name", nm));
      var tx = el("textarea"); tx.id = "dPText"; tx.value = draft.text || ""; tx.style.minHeight = "300px"; c.appendChild(labelled("Text", tx));
      var b = el("div", "btns");
      var save = btn("Save draft", "", function () { adm("update", { id: draft.id, changes: changed(draft, { name: nm.value.trim(), text: tx.value }), expected_updated_at: draft.updated_at }, "discovery_prompts").then(function (r) { if (!ok(r)) msg.textContent = problemsText(r); else refreshAfter("discovery_prompts"); }); }); save.id = "dPSave";
      var pubb = btn("Publish this draft", "", function () {
        adm("update", { id: draft.id, changes: changed(draft, { name: nm.value.trim(), text: tx.value }), expected_updated_at: draft.updated_at }, "discovery_prompts").then(function (r) {
          if (!ok(r)) { msg.textContent = problemsText(r); return; }
          adm("publish", { id: draft.id, expected_updated_at: r.body.data.updated_at }, "discovery_prompts").then(function (r2) { if (!ok(r2)) msg.textContent = problemsText(r2); else refreshAfter("discovery_prompts"); });
        });
      }); pubb.id = "dPPublish";
      var disc_ = btn("Discard draft", "quiet", function () { adm("soft_delete", { id: draft.id }, "discovery_prompts").then(function (r) { if (!ok(r)) msg.textContent = problemsText(r); else refreshAfter("discovery_prompts"); }); });
      b.appendChild(save); b.appendChild(pubb); b.appendChild(disc_); c.appendChild(b); host.appendChild(c);
    }
    var standing = pub[0];
    if (!standing) host.appendChild(el("div", "empty", "No published prompt yet. Run seed_discovery.py, or ask to have one added."));
    else {
      var cs = el("div", "dcard"); cs.appendChild(el("h4", "", "In use: version " + standing.version + (standing.name ? " · " + standing.name : ""))); cs.appendChild(el("div", "dprompt", standing.text));
      if (!draft) { var ed = btn("Edit as a new draft", "", function () { adm("draft_from", { id: standing.id }, "discovery_prompts").then(function (r) { if (!ok(r)) msg.textContent = problemsText(r); else refreshAfter("discovery_prompts"); }); }); ed.id = "dPEdit"; cs.appendChild(ed); }
      host.appendChild(cs);
    }
    if (pub.length > 1) {
      var h = el("details", "more"); h.appendChild(el("summary", "", "Earlier versions (" + (pub.length - 1) + ")"));
      pub.slice(1).forEach(function (p) {
        var d = el("div", "dcard"); d.appendChild(el("b", "", "Version " + p.version + (p.published_at ? " · " + K.when(p.published_at) : ""))); d.appendChild(el("div", "dprompt", p.text));
        if (!draft) d.appendChild(btn("Start a draft from this version", "quiet", function () { adm("draft_from", { id: p.id }, "discovery_prompts").then(function (r) { if (!ok(r)) msg.textContent = problemsText(r); else refreshAfter("discovery_prompts"); }); }));
        h.appendChild(d);
      }); host.appendChild(h);
    }
  }
  function drawLimits(host) {
    var s = S.settings; host.appendChild(el("h3", "", "Limits"));
    if (!s) { host.appendChild(el("div", "empty", "No settings record yet. Run seed_discovery.py.")); return; }
    var cfg = { coll: "discovery_settings", one: "limits", fields: [
      { name: "default_spend_cap_cents", label: "Spend cap a run starts with (cents)", kind: "int" }, { name: "max_spend_cap_cents", label: "Most any run may spend (cents)", kind: "int", hint: "The Find venues tab cannot go above this." },
      { name: "max_results_per_run", label: "Most results in one run", kind: "int" }, { name: "results_per_step", label: "Results asked for in one AI call", kind: "int", hint: "Small calls keep each one quick and let the cap stop a run between calls." },
      { name: "default_model_id", label: "Model chosen first", kind: "select", options: [["", "The first one switched on"]].concat(active(S.models).map(function (m) { return [m.id, m.label]; })) }] };
    var card = el("div", "dcard"); card.appendChild(el("p", "", "Starting cap " + usd(s.default_spend_cap_cents) + ", most allowed " + usd(s.max_spend_cap_cents) + ", up to " + s.max_results_per_run + " results a run, " + s.results_per_step + " a call."));
    var fh = el("div"); card.appendChild(fh); var e = btn("Edit limits", "", function () { crudForm(fh, cfg, s); }); e.id = "dEditLimits"; card.appendChild(e); host.appendChild(card);
  }

  // ---- entry point from the main page
  window.DiscoveryStation = {
    show: function () { if (!root) build(); if (!S.loaded) { loadAll(); } drawTabs(); },
    reset: function () { S = { tab: "run", sub: "models", loaded: false, status: null, models: [], areas: [], types: [], prompts: [], settings: null, runs: [], openRun: null, quote: null, quoteKey: "", driving: "", stopAsk: false, seq: S.seq + 1 }; root = null; var v = $("discoveryView"); if (v) v.innerHTML = ""; }
  };
})();
