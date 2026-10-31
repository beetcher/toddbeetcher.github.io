/* Console shared parts (step 1.3a). Loaded before console.js. Stations use these instead of building their own.
   window.UI.confirm(opts)  -> Promise<boolean>. A real dialog: the page behind it is inert, Escape or Cancel answers no, focus returns to where it was.
        opts: { title, message, yes, no, danger } . The safe button (Cancel) has focus first when danger is true.
   window.UI.dismiss() -> closes an open dialog as 'no' (used when the Console locks).
   window.UI.chip(kind, text) -> a status chip. kind: ok | warn | err | info | quiet. The words always carry the meaning; colour only helps.
   window.UI.banner(kind, text) -> a message strip. kind: ok | warn | err | info. Errors are announced at once (role=alert).
   window.UI.empty(title, hint, actionNode) -> an empty-state block.
   window.UI.skeleton(rows) -> grey placeholder rows for a list that is loading (announced once as "Loading").
   window.UI.filterBar(opts) -> { refresh } . Takes the page's existing filter <select>s and tucks them behind one "Filters" button, closed by default.
        What is switched on shows as removable chips ("Status: Active"), with "Clear all" from two up. The button carries the count: "Filters (2)".
        opts: { id, toggleBefore: element the button goes before, after: element the chips and panel go after, fields: [{ el: select, label }] }.
        The first option of each select is its "off" value. Call refresh() after changing a select's options or value from code.
   window.UI.limitNote(listEl, shown, limit, text) -> after a list, a note that appears only when the list hit its cap (the server returns no total). */
(function () {
  "use strict";
  var dlg = null, pending = null, opener = null;

  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }

  function ensure() {
    if (dlg) return dlg;
    dlg = el("dialog", "uidlg"); dlg.id = "uiDialog";
    dlg.setAttribute("aria-labelledby", "uiTitle"); dlg.setAttribute("aria-describedby", "uiMsg");
    var t = el("h2", "uititle"); t.id = "uiTitle";
    var m = el("p", "uimsg"); m.id = "uiMsg";
    var row = el("div", "uibtns");
    var no = el("button", "quiet", "Cancel"); no.type = "button"; no.id = "uiNo";
    var yes = el("button", "", "Yes"); yes.type = "button"; yes.id = "uiYes";
    row.appendChild(no); row.appendChild(yes);
    dlg.appendChild(t); dlg.appendChild(m); dlg.appendChild(row);
    document.body.appendChild(dlg);
    yes.addEventListener("click", function () { finish(true); });
    no.addEventListener("click", function () { finish(false); });
    dlg.addEventListener("cancel", function (e) { e.preventDefault(); finish(false); });   // Escape
    dlg.addEventListener("click", function (e) { if (e.target === dlg) finish(false); });   // the dimmed area around the box
    return dlg;
  }

  function finish(answer) {
    if (!pending) return;
    var done = pending; pending = null;
    if (dlg.open) dlg.close();
    if (opener && opener.focus && document.contains(opener)) { try { opener.focus(); } catch (e) {} }
    opener = null;
    done(answer);
  }

  function confirmDialog(opts) {
    opts = opts || {};
    if (!ensure().showModal) return Promise.resolve(window.confirm(opts.message || opts.title || "Are you sure?"));
    if (pending) finish(false);
    opener = document.activeElement;
    $t("uiTitle").textContent = opts.title || "Are you sure?";
    $t("uiMsg").textContent = opts.message || "";
    $t("uiMsg").hidden = !opts.message;
    $t("uiYes").textContent = opts.yes || "Yes";
    $t("uiNo").textContent = opts.no || "Cancel";
    dlg.classList.toggle("danger", !!opts.danger);
    return new Promise(function (resolve) {
      pending = resolve;
      dlg.showModal();
      $t(opts.danger ? "uiNo" : "uiYes").focus();
    });
  }
  function $t(id) { return document.getElementById(id); }

  function chip(kind, text) { return el("span", "chip chip-" + (kind || "quiet"), text); }

  function banner(kind, text) {
    var b = el("div", "banner banner-" + (kind || "info"), text);
    b.setAttribute("role", kind === "err" ? "alert" : "status");
    return b;
  }

  function empty(title, hint, action) {
    var d = el("div", "empty"); d.appendChild(el("p", "empty-title", title));
    if (hint) d.appendChild(el("p", "empty-hint", hint));
    if (action) d.appendChild(action);
    return d;
  }

  function skeleton(rows) {
    var d = el("div", "skel"); d.setAttribute("role", "status");
    d.appendChild(el("span", "sr", "Loading"));
    for (var i = 0; i < (rows || 4); i++) { var r = el("div", "skel-row"); r.setAttribute("aria-hidden", "true"); d.appendChild(r); }
    return d;
  }
  function limitNote(listEl, shown, limit, text) {
    if (!listEl || !listEl.parentNode) return null;
    var id = listEl.id + "Limit", n = document.getElementById(id);
    if (!n) { n = el("div", "limitnote"); n.id = id; listEl.parentNode.insertBefore(n, listEl.nextSibling); }
    n.textContent = text || ("Showing the first " + limit + ". There may be more: use the filters to narrow the list.");
    n.hidden = !(shown >= limit);
    return n;
  }

  function filterBar(o) {
    var fields = o.fields, id = o.id || "fb";
    var toggle = el("button", "quiet fbtn"); toggle.type = "button"; toggle.id = id + "FilterBtn";
    toggle.setAttribute("aria-expanded", "false"); toggle.setAttribute("aria-controls", id + "FilterPanel");
    var wrap = el("div", "fwrap"), chips = el("div", "fchips"), panel = el("div", "fpanel");
    chips.setAttribute("role", "group"); chips.setAttribute("aria-label", "Filters in use");
    panel.id = id + "FilterPanel"; panel.hidden = true;
    o.toggleBefore.parentNode.insertBefore(toggle, o.toggleBefore);   // place the button and the chips first: the selects are about to move into the panel
    o.after.parentNode.insertBefore(wrap, o.after.nextSibling);
    fields.forEach(function (f) {
      var lab = el("label", "flab"); lab.appendChild(el("span", "", f.label)); lab.appendChild(f.el); panel.appendChild(lab);
      f.el.addEventListener("change", refresh);
    });
    wrap.appendChild(chips); wrap.appendChild(panel);
    function off(f) { return f.el.options.length ? f.el.options[0].value : ""; }
    function active() { return fields.filter(function (f) { return f.el.value !== off(f); }); }
    function clear(f) { f.el.value = off(f); f.el.dispatchEvent(new Event("change", { bubbles: true })); }
    function setOpen(on) { panel.hidden = !on; toggle.setAttribute("aria-expanded", on ? "true" : "false"); }
    function refresh() {
      var on = active();
      toggle.textContent = on.length ? "Filters (" + on.length + ")" : "Filters";
      chips.textContent = "";
      on.forEach(function (f) {
        var text = f.label + ": " + f.el.options[f.el.selectedIndex].text;
        var c = chip("info", text), x = el("button", "fx", "\u00d7"); x.type = "button"; x.setAttribute("aria-label", "Remove filter " + text);
        x.addEventListener("click", function () { clear(f); toggle.focus(); });
        c.appendChild(x); chips.appendChild(c);
      });
      if (on.length > 1) {
        var all = el("button", "quiet fclear", "Clear all"); all.type = "button";
        all.addEventListener("click", function () { on.forEach(function (f) { f.el.value = off(f); }); fields.forEach(function (f) { f.el.dispatchEvent(new Event("change", { bubbles: true })); }); toggle.focus(); });
        chips.appendChild(all);
      }
    }
    toggle.addEventListener("click", function () { setOpen(panel.hidden); });
    refresh();
    return { refresh: refresh, open: function () { setOpen(true); }, close: function () { setOpen(false); } };
  }

  function skelOn(host) { if (host && !host.querySelector(".skel")) { host.textContent = ""; host.appendChild(UI.skeleton(4)); } }
  function skelOff(host) { var s = host && host.querySelector(".skel"); if (s) s.parentNode.removeChild(s); }
  // ---- Look helpers shared by Places, Organizations and People (combo look build, S-1)
  // Plain names for the U.S. time zones the Console uses (the raw IANA name is never shown on its own).
  var ZONE_NAMES = { "America/New_York": "Eastern", "America/Chicago": "Central", "America/Denver": "Mountain", "America/Phoenix": "Arizona (no daylight saving)",
                     "America/Los_Angeles": "Pacific", "America/Anchorage": "Alaska", "America/Adak": "Aleutian (Alaska islands)", "Pacific/Honolulu": "Hawaii" };
  function zoneOptions() { return Object.keys(ZONE_NAMES).map(function (k) { return [k, ZONE_NAMES[k]]; }); }
  function zoneName(tz) { return tz ? (ZONE_NAMES[tz] || String(tz).replace(/_/g, " ")) : ""; }
  // A label with a red "required" star (hidden from screen readers; the field itself carries aria-required).
  function requiredLabel(text, forId) {
    var l = el("label", "f", text); if (forId) l.htmlFor = forId;
    var st = el("span", "req", " *"); st.setAttribute("aria-hidden", "true"); l.appendChild(st); return l;
  }
  // "Showing 50 of 83" and a "Load 50 more" button. onMore() is called when it is pressed. Returns the element (empty when everything is shown).
  function moreBar(host, shown, total, step, onMore, noun) {
    var old = host.querySelector(".morebar"); if (old) old.parentNode.removeChild(old);
    if (shown >= total) return null;
    var d = el("div", "morebar"), t = el("span", "", "Showing " + shown + " of " + total + (noun ? " " + noun : "") + "."), b = el("button", "btn-secondary", "Load " + Math.min(step, total - shown) + " more");
    b.type = "button"; b.addEventListener("click", onMore); d.appendChild(t); d.appendChild(b); host.appendChild(d); return d;
  }


  // ---- Small shared helpers moved from console.js (DT-19). line and str build detail rows; askDiscard asks before leaving unsaved edits; statusToggle is the
  // Active/Inactive switch that collects taps into one save (it reaches the server and the lock through ConsoleKit when it is used, not when this file loads).
  function kit() { return window.ConsoleKit; }
  function line(label, value) {
    var d = document.createElement("div");
    var b = document.createElement("b");
    b.textContent = label + ": ";
    d.appendChild(b);
    d.appendChild(document.createTextNode(value));
    return d;
  }
  function str(v) { return (v !== null && typeof v === "object") ? JSON.stringify(v) : String(v); }
  var DISCARD = { title: "Discard your changes?", message: "You have edits that are not saved.", yes: "Discard", no: "Keep editing", danger: true };
  function askDiscard(dirty, go, stay) {   // runs go() at once when nothing is unsaved; otherwise asks first
    if (!dirty) { go(); return; }
    UI.confirm(DISCARD).then(function (ok) { if (ok) go(); else if (stay) stay(); });
  }
  var TOGGLE_WAIT = 1500;
  function statusToggle(rec, li, opts) {
    var b = el("button", "stoggle"); b.type = "button"; b.setAttribute("role", "switch");
    var knob = el("span", "knob"), word = el("span", "");
    b.appendChild(knob); b.appendChild(word);
    var want = rec.status === opts.on, timer = null, busy = false;
    var msg = el("div", "stmsg"); msg.setAttribute("role", "alert");
    function draw() {
      var saved = rec.status === opts.on;
      b.classList.toggle("on", want); b.classList.toggle("pending", want !== saved || !!timer);
      b.setAttribute("aria-checked", want ? "true" : "false");
      word.textContent = want ? (opts.onWord || "Active") : (opts.offWord || "Inactive");
      b.setAttribute("aria-label", (opts.label || "Status") + ": " + (want ? (opts.onWord || "Active") : (opts.offWord || "Inactive")).toLowerCase() + (timer ? ", saving soon" : "") + ". Tap to change.");
    }
    function send() {
      timer = null;
      if (want === (rec.status === opts.on)) { draw(); return; }
      busy = true; b.disabled = true; msg.textContent = "";
      var args = { id: rec.id, changes: { status: want ? opts.on : opts.off }, expected_updated_at: rec.updated_at };
      (opts.coll ? kit().admin("update", args, opts.coll) : kit().admin("update", args)).then(function (res) {
        busy = false; b.disabled = false;
        if (res.status === 401) { kit().lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          rec.status = want ? opts.on : opts.off;
          var u = res.body.data && res.body.data.updated_at; if (u) rec.updated_at = u;
          draw(); return;
        }
        want = rec.status === opts.on; draw();
        msg.textContent = res.status === 409 ? "This changed somewhere else. Tap Refresh, then try again." : res.status === 400 ? opts.problem(res) : kit().adminProblem(res.status);
      });
    }
    b.addEventListener("click", function () {
      if (busy) return;
      want = !want; if (timer) clearTimeout(timer);
      timer = setTimeout(send, TOGGLE_WAIT); draw();
    });
    li.classList.add("hasToggle"); draw();
    return { btn: b, msg: msg };
  }

  window.UI = { line: line, str: str, askDiscard: askDiscard, statusToggle: statusToggle, zoneName: zoneName, zoneOptions: zoneOptions, requiredLabel: requiredLabel, moreBar: moreBar, skelOn: skelOn, skelOff: skelOff, filterBar: filterBar, skeleton: skeleton, limitNote: limitNote, dismiss: function () { finish(false); }, confirm: confirmDialog, chip: chip, banner: banner, empty: empty };
})();
