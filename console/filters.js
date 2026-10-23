/* Chip filters: the Console's shared filter control. Loads after ui.js and before any station file. Not part of console.js, on purpose:
   every station that comes out of the big file uses this one component (design rule: console/DESIGN-RULES.md, "Chip filters").

   var cf = UI.chipFilters({
     mount: element,                 // an empty element the row is drawn into
     label: "Message filters",       // spoken name of the whole row
     filters: [ { id, label, kind, start, options: [ { value, label, count } ] } ],
     onChange: function (selection, cf) {}   // fires when the PERSON changes something (never for calls you make)
   });

   kind "multi"         tick boxes. start "all" (default): every entry ticked, the filter is off until something is unticked. start "none": nothing ticked, off until something is ticked ("Only show").
   kind "one"           pick one (radio). The first option is the "any" choice and is the default.
   kind "search-multi"  like multi, with a search box inside the popover (long lists, for example regions).
   kind "toggle"        a switch chip: no popover, no caret, pressed or not (for a quick filter such as "Needs attention"). Optional: noun ("messages", used in its spoken name) and a number beside the words (setBadge).
   Any filter may carry a title (a hover hint).

   cf.getSelection()            -> { filterId: [values ticked] }   (for "one": a one-item array)
   cf.setSelection(sel)         -> set choices from code; does not fire onChange
   cf.setOptions(id, options)   -> replace a filter's entries; choices the person made are kept, new entries start ticked (start "all") or unticked (start "none")
   cf.setCounts({ id: { value: n } }) -> the small number beside each entry; {} blanks them
   cf.setNote(text), cf.setCount(text) -> a plain line after the chips ("" hides it)
   cf.setBadge(id, n)           -> the number beside a switch chip's words ("" hides it)
   cf.setResult(text)           -> a live line inside every popover, above Clear and Done ("4 of 74 messages"), so the effect of a tick is visible even though the popover covers part of the list; "" hides it
   cf.isNarrowed(), cf.clearAll() (fires onChange once), cf.refresh(), cf.destroy()

   A chip says its own state: "Status" when off, "Status: Not sent, Failed" or "Status: 3 of 5" when narrowed (filled dark, like the Needs attention pill).
   Spoken name of a chip: "Status filter, 3 of 5 selected" (a switch: "Needs attention filter, on, 6 messages"). Keyboard: Tab to a chip, Enter / Space / Down opens, Up and Down move between ticks, Space ticks, Escape closes and returns to the chip.
   Focus on open: by keyboard it lands on the first entry; by mouse or touch it stays on the popover itself, so no entry shows a focus ring it was never given. A search list always focuses its search box.
   On a phone (520 px and under) the popover is a bottom sheet with a dimmed backdrop. */
(function () {
  "use strict";
  window.UI = window.UI || {};
  var counter = 0;

  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function phone() { return !!(window.matchMedia && window.matchMedia("(max-width: 520px)").matches); }

  function chipFilters(o) {
    var uid = "cf" + (++counter), filters = [], byId = {}, openF = null, resultText = "";
    var row = el("div", "cf-row"); row.setAttribute("role", "group"); row.setAttribute("aria-label", o.label || "Filters");
    var clearAllBtn = el("button", "btn-link cf-clearall", "Clear all"); clearAllBtn.type = "button"; clearAllBtn.hidden = true;
    var noteEl = el("span", "cf-note"); noteEl.setAttribute("role", "status");
    var countEl = el("span", "cf-count"); countEl.setAttribute("role", "status");

    function copyOption(x) { return { value: String(x.value), label: x.label != null ? String(x.label) : String(x.value), count: x.count }; }
    function resetSel(f) {
      f.sel = {};
      if (f.kind === "toggle") { f.on = false; return; }
      if (f.kind === "one") f.one = f.options.length ? f.options[0].value : "";
      else if (f.start === "all") f.options.forEach(function (x) { f.sel[x.value] = true; });
    }
    function pickedOptions(f) { return f.options.filter(function (x) { return f.sel[x.value]; }); }
    function narrowed(f) {
      if (f.kind === "toggle") return !!f.on;
      if (f.kind === "one") return f.options.length > 0 && f.one !== f.options[0].value;
      var n = pickedOptions(f).length;
      return f.start === "all" ? n < f.options.length : n > 0;
    }
    function oneLabel(f) { var m = f.options.filter(function (x) { return x.value === f.one; })[0]; return m ? m.label : ""; }
    function summary(f) {
      if (f.kind === "one") return oneLabel(f);
      var picked = pickedOptions(f), names = picked.map(function (x) { return x.label; }).join(", ");
      if (f.start === "all") {
        if (!picked.length) return "None";
        return picked.length <= 2 && names.length <= 28 ? names : picked.length + " of " + f.options.length;
      }
      return picked.length <= 2 && names.length <= 28 ? names : picked.length + " selected";
    }
    function spoken(f) {
      if (f.kind === "toggle") return (f.on ? "on" : "off") + (f.badge !== "" ? ", " + f.badge + (f.noun ? " " + f.noun : "") : "");
      if (f.kind === "one") return "showing " + oneLabel(f);
      var n = pickedOptions(f).length;
      if (f.start === "all") return narrowed(f) ? n + " of " + f.options.length + " selected" : "all selected";
      return n ? n + " selected" : "none selected";
    }
    function countText(f, v) { return f.n[v] != null && f.n[v] !== "" ? String(f.n[v]) : ""; }

    function refreshChip(f) {
      var on = narrowed(f);
      if (f.kind === "toggle") { f.lab.textContent = f.label; f.badgeEl.textContent = f.badge; f.chip.setAttribute("aria-pressed", on ? "true" : "false"); }
      else f.lab.textContent = on ? f.label + ": " + summary(f) : f.label;
      f.chip.setAttribute("data-on", on ? "true" : "false");
      f.chip.setAttribute("aria-label", f.label + " filter, " + spoken(f));
    }
    function refreshAll() {
      var any = false;
      filters.forEach(function (f) { refreshChip(f); if (narrowed(f)) any = true; });
      clearAllBtn.hidden = !any;
    }
    function syncInputs(f) {
      f.options.forEach(function (x) {
        var r = f.inputs[x.value]; if (!r) return;
        r.input.checked = f.kind === "one" ? f.one === x.value : !!f.sel[x.value];
      });
    }
    function applySearch(f) {
      if (!f.search) return;
      var q = f.search.value.trim().toLowerCase(), shown = 0;
      f.options.forEach(function (x) {
        var r = f.inputs[x.value]; if (!r) return;
        var hit = !q || x.label.toLowerCase().indexOf(q) >= 0; r.label.hidden = !hit; if (hit) shown++;
      });
      f.none.hidden = shown > 0;
    }
    function renderList(f) {
      f.list.textContent = ""; f.inputs = {};
      var type = f.kind === "one" ? "radio" : "checkbox";
      f.options.forEach(function (x) {
        var l = el("label", "cf-opt"), i = document.createElement("input");
        i.type = type; i.value = x.value; if (type === "radio") i.name = uid + "-" + f.id;
        var t = el("span", "cf-t", x.label), n = el("span", "cf-n", countText(f, x.value));
        l.appendChild(i); l.appendChild(t); l.appendChild(n); f.list.appendChild(l);
        f.inputs[x.value] = { input: i, label: l, count: n };
      });
      f.none = el("div", "cf-none", "Nothing matches."); f.none.hidden = true; f.list.appendChild(f.none);
      syncInputs(f); applySearch(f);
    }
    function emit() { if (o.onChange) o.onChange(getSelection(), api); }

    function place(f) {
      f.pop.style.left = ""; f.pop.style.right = "";
      if (phone()) return;
      var r = f.pop.getBoundingClientRect(), vw = document.documentElement.clientWidth;
      if (r.right > vw - 8) { f.pop.style.left = "auto"; f.pop.style.right = "0"; }   // near the right edge: open towards the left
    }
    function open(f, byKeyboard) {
      if (openF && openF !== f) close(openF, false);
      if (f.search) { f.search.value = ""; applySearch(f); }   // a list that opens still filtered by old text would look like entries had vanished
      f.pointer = false; f.pop.hidden = false; f.wrap.classList.add("cf-open"); f.chip.setAttribute("aria-expanded", "true"); openF = f; place(f);
      // by keyboard: the first entry; by mouse or touch: the popover itself (no ring on an entry nobody chose); a search list: the search box
      var first = f.search || (byKeyboard ? (f.list.querySelector("input:checked") || f.list.querySelector("input")) : null);
      if (first) first.focus(); else f.pop.focus();
    }
    function close(f, restore) {
      if (f.pop.hidden) return;
      f.pop.hidden = true; f.wrap.classList.remove("cf-open"); f.chip.setAttribute("aria-expanded", "false");
      if (openF === f) openF = null;
      if (restore) f.chip.focus();
    }

    function add(def) {
      var kind = def.kind === "one" || def.kind === "search-multi" || def.kind === "toggle" ? def.kind : "multi";
      var f = { id: def.id, label: def.label, kind: kind, start: kind === "one" ? "first" : (def.start === "none" ? "none" : "all"), options: [], sel: {}, one: "", n: {}, inputs: {} };
      f.options = (def.options || []).map(function (x) { var c = copyOption(x); if (x.count != null) f.n[c.value] = x.count; return c; });
      resetSel(f);
      if (kind === "toggle") {   // a switch chip: no popover at all
        f.badge = ""; f.noun = def.noun || "";
        f.wrap = el("div", "cf-chipwrap");
        f.chip = el("button", "cf-chip cf-switch"); f.chip.type = "button"; if (def.title) f.chip.title = def.title;
        f.lab = el("span", "cf-lab"); f.badgeEl = el("span", "cf-badge"); f.chip.appendChild(f.lab); f.chip.appendChild(f.badgeEl);
        f.chip.addEventListener("click", function () { f.on = !f.on; refreshAll(); emit(); });
        f.wrap.appendChild(f.chip); refreshChip(f);
        filters.push(f); byId[f.id] = f; row.appendChild(f.wrap);
        return;
      }
      var pid = uid + "-" + f.id + "-pop";
      f.wrap = el("div", "cf-chipwrap");
      f.chip = el("button", "cf-chip"); f.chip.type = "button"; if (def.title) f.chip.title = def.title; f.chip.setAttribute("aria-haspopup", "dialog"); f.chip.setAttribute("aria-expanded", "false"); f.chip.setAttribute("aria-controls", pid);
      f.lab = el("span", "cf-lab"); var caret = el("span", "cf-caret", "▾"); caret.setAttribute("aria-hidden", "true");
      f.chip.appendChild(f.lab); f.chip.appendChild(caret);
      f.back = el("div", "cf-back"); f.back.setAttribute("aria-hidden", "true");
      f.pop = el("div", "cf-pop"); f.pop.id = pid; f.pop.hidden = true; f.pop.tabIndex = -1;
      f.pop.setAttribute("role", "dialog"); f.pop.setAttribute("aria-label", f.label + " filter");
      var title = el("div", "cf-title", f.label); title.setAttribute("aria-hidden", "true");   // shown on a phone only, where the sheet covers the chip it belongs to
      f.pop.appendChild(title);
      if (kind === "search-multi") {
        f.search = el("input", "cf-search"); f.search.type = "search"; f.search.placeholder = "Search " + f.label.toLowerCase(); f.search.setAttribute("aria-label", "Search " + f.label); f.search.autocomplete = "off";
        f.search.addEventListener("input", function () { applySearch(f); });
        f.pop.appendChild(f.search);
      }
      f.list = el("div", "cf-list"); f.list.setAttribute("role", "group"); f.list.setAttribute("aria-label", f.label);
      f.pop.appendChild(f.list);
      f.result = el("div", "cf-result", resultText); f.result.setAttribute("role", "status"); f.result.setAttribute("aria-live", "polite");
      f.pop.appendChild(f.result);
      var foot = el("div", "cf-foot");
      var clear = el("button", "btn-link cf-clear", "Clear"); clear.type = "button"; clear.setAttribute("aria-label", "Clear " + f.label + " filter");
      var done = el("button", "btn-secondary cf-done", "Done"); done.type = "button"; done.setAttribute("aria-label", "Done with " + f.label + " filter");
      foot.appendChild(clear); foot.appendChild(done); f.pop.appendChild(foot);
      f.wrap.appendChild(f.chip); f.wrap.appendChild(f.back); f.wrap.appendChild(f.pop);

      f.chip.addEventListener("click", function (e) { if (f.pop.hidden) open(f, e.detail === 0); else close(f, false); });   // a click with no mouse behind it (detail 0) is Enter or Space
      f.chip.addEventListener("keydown", function (e) { if (e.key === "ArrowDown" && f.pop.hidden) { e.preventDefault(); open(f, true); } });
      f.back.addEventListener("click", function () { close(f, true); });
      done.addEventListener("click", function () { close(f, true); });
      clear.addEventListener("click", function () { resetSel(f); syncInputs(f); refreshAll(); emit(); });
      f.pop.addEventListener("pointerdown", function () { f.pointer = true; });
      f.pop.addEventListener("change", function (e) {
        var t = e.target; if (!t || t.tagName !== "INPUT" || t === f.search) return;
        if (f.kind === "one") f.one = t.value; else if (t.checked) f.sel[t.value] = true; else delete f.sel[t.value];
        refreshAll(); emit();
        if (f.kind === "one" && f.pointer) close(f, true);   // a mouse or touch pick on a pick-one list closes it; the keyboard keeps it open so Up and Down can keep choosing
      });
      f.pop.addEventListener("keydown", function (e) {
        f.pointer = false;
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(f, true); return; }
        if ((e.key === "ArrowDown" || e.key === "ArrowUp") && f.kind !== "one") {
          var items = f.options.map(function (x) { return f.inputs[x.value]; }).filter(function (r) { return r && !r.label.hidden; }).map(function (r) { return r.input; });
          if (!items.length) return;
          var i = items.indexOf(document.activeElement), next;
          if (i < 0) next = e.key === "ArrowDown" ? items[0] : items[items.length - 1];
          else next = items[Math.max(0, Math.min(items.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))];
          e.preventDefault(); next.focus();
        } else if (e.key === "ArrowDown" && f.search && document.activeElement === f.search) {
          var firstBox = f.list.querySelector("label:not([hidden]) input"); if (firstBox) { e.preventDefault(); firstBox.focus(); }
        }
      });
      f.wrap.addEventListener("focusout", function (e) { if (!f.pop.hidden && e.relatedTarget && !f.wrap.contains(e.relatedTarget)) close(f, false); });

      renderList(f); refreshChip(f);
      filters.push(f); byId[f.id] = f; row.appendChild(f.wrap);
    }

    function onDocDown(e) { if (openF && !openF.wrap.contains(e.target)) close(openF, false); }
    document.addEventListener("mousedown", onDocDown);

    function getSelection() {
      var out = {};
      filters.forEach(function (f) { out[f.id] = f.kind === "toggle" ? (f.on ? ["on"] : []) : f.kind === "one" ? [f.one] : pickedOptions(f).map(function (x) { return x.value; }); });
      return out;
    }
    function setSelection(sel) {
      Object.keys(sel || {}).forEach(function (id) {
        var f = byId[id], vals = sel[id]; if (!f || !vals) return;
        if (f.kind === "toggle") f.on = vals.length > 0;
        else if (f.kind === "one") { var has = f.options.some(function (x) { return x.value === String(vals[0]); }); if (has) f.one = String(vals[0]); }
        else { f.sel = {}; vals.forEach(function (v) { f.sel[String(v)] = true; }); }
        syncInputs(f);
      });
      refreshAll();
    }
    function setOptions(id, options) {
      var f = byId[id]; if (!f || f.kind === "toggle") return;
      var known = {}; f.options.forEach(function (x) { known[x.value] = true; });
      f.options = (options || []).map(function (x) { var c = copyOption(x); if (x.count != null) f.n[c.value] = x.count; return c; });
      if (f.kind === "one") { if (!f.options.some(function (x) { return x.value === f.one; })) f.one = f.options.length ? f.options[0].value : ""; }
      else {
        var keep = {};
        f.options.forEach(function (x) { if (known[x.value]) { if (f.sel[x.value]) keep[x.value] = true; } else if (f.start === "all") keep[x.value] = true; });
        f.sel = keep;
      }
      renderList(f); refreshAll();
    }
    function setCounts(map) {
      map = map || {};
      var blank = Object.keys(map).length === 0;
      filters.forEach(function (f) {
        if (blank) f.n = {}; else if (map[f.id]) f.n = map[f.id]; else return;
        f.options.forEach(function (x) { var r = f.inputs[x.value]; if (r) r.count.textContent = countText(f, x.value); });
      });
    }
    function doClearAll() {
      filters.forEach(function (f) { resetSel(f); syncInputs(f); });
      refreshAll(); emit();
      if (filters.length && document.activeElement === document.body) filters[0].chip.focus();
    }
    clearAllBtn.addEventListener("click", function () { doClearAll(); if (filters.length) filters[0].chip.focus(); });

    (o.filters || []).forEach(add);
    row.appendChild(clearAllBtn); row.appendChild(noteEl); row.appendChild(countEl);
    refreshAll();
    o.mount.textContent = ""; o.mount.appendChild(row);

    var api = {
      getSelection: getSelection, setSelection: setSelection, setOptions: setOptions, setCounts: setCounts,
      setNote: function (t) { noteEl.textContent = t || ""; }, setCount: function (t) { countEl.textContent = t || ""; },
      setBadge: function (id, n) { var f = byId[id]; if (!f || f.kind !== "toggle") return; f.badge = n == null ? "" : String(n); refreshChip(f); },
      setResult: function (t) { resultText = t || ""; filters.forEach(function (f) { if (f.result) f.result.textContent = resultText; }); },
      isNarrowed: function () { return filters.some(narrowed); }, clearAll: doClearAll, refresh: refreshAll,
      destroy: function () { document.removeEventListener("mousedown", onDocDown); o.mount.textContent = ""; }
    };
    return api;
  }

  window.UI.chipFilters = chipFilters;
})();
