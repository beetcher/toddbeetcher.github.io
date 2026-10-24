/* Console form engine (step F). Loaded before console.js. One place that builds a labelled form field from a schema property and reads it back.
   window.ConsoleForms.labels            -> the shared { field name: label } object. A page adds its own labels to it (the Classes screen does).
   window.ConsoleForms.humanize(name)    -> the label for a field name.
   window.ConsoleForms.firstSentence(t)  -> the first sentence of a schema description (the small hint under a field).
   window.ConsoleForms.choicesFor(name)  -> a pick list for country, state_region and time_zone, else null.
   window.ConsoleForms.buildField(name, def, rec, ctx) -> a <div> with label, input and hint. ctx is required: { prefix, schema, fields }.
        It records the field in ctx.fields[name] = { el, other, kind, def, sec, summary }. Ids are "ef_" + prefix + name and "ee_" + prefix + name.
   window.ConsoleForms.readValue(f)      -> the value in a recorded field (null when empty, undefined when a number is not a number).
   window.ConsoleForms.openSec(f)        -> opens the section a field sits in (and its "more" group) so an error can be seen. */
(function () {
  "use strict";
  var US_STATES = [["AL","Alabama"],["AK","Alaska"],["AZ","Arizona"],["AR","Arkansas"],["CA","California"],["CO","Colorado"],["CT","Connecticut"],
    ["DE","Delaware"],["DC","District of Columbia"],["FL","Florida"],["GA","Georgia"],["HI","Hawaii"],["ID","Idaho"],["IL","Illinois"],["IN","Indiana"],
    ["IA","Iowa"],["KS","Kansas"],["KY","Kentucky"],["LA","Louisiana"],["ME","Maine"],["MD","Maryland"],["MA","Massachusetts"],["MI","Michigan"],
    ["MN","Minnesota"],["MS","Mississippi"],["MO","Missouri"],["MT","Montana"],["NE","Nebraska"],["NV","Nevada"],["NH","New Hampshire"],["NJ","New Jersey"],
    ["NM","New Mexico"],["NY","New York"],["NC","North Carolina"],["ND","North Dakota"],["OH","Ohio"],["OK","Oklahoma"],["OR","Oregon"],["PA","Pennsylvania"],
    ["RI","Rhode Island"],["SC","South Carolina"],["SD","South Dakota"],["TN","Tennessee"],["TX","Texas"],["UT","Utah"],["VT","Vermont"],["VA","Virginia"],
    ["WA","Washington"],["WV","West Virginia"],["WI","Wisconsin"],["WY","Wyoming"]];

  var LABELS = { is_public_venue: "Public venue", state_region: "State or region", postal_code: "ZIP or postal code", time_zone: "Time zone",
                 has_wifi: "Has Wi-Fi", wifi_notes: "Wi-Fi notes", is_accessible: "Accessible", has_step_free_entry: "Step-free entry",
                 cost_cents: "Cost", deposit_cents: "Deposit", booking_lead_days: "Booking lead time (days)", allows_minors: "Allows minors",
                 allows_animals: "Allows animals", allows_food: "Allows food", allows_alcohol: "Allows alcohol", website_url: "Website" };
  function humanize(n) { if (LABELS[n]) return LABELS[n]; var t = n.replace(/_/g, " "); return t.charAt(0).toUpperCase() + t.slice(1); }
  function firstSentence(t) { if (!t) return ""; var m = t.match(/^.*?[.!?](\s|$)/); return (m ? m[0] : t).trim(); }

  // Pick lists for fields where free text is hard to get right. The saved value is the same kind of string the schema allows.
  function choicesFor(name) {
    if (name === "country") {
      var names = null, out = [];
      try { names = new Intl.DisplayNames(["en"], { type: "region" }); } catch (e) {}
      if (names) {
        for (var a = 65; a <= 90; a++) for (var b = 65; b <= 90; b++) {
          var code = String.fromCharCode(a, b), nm = "";
          try { nm = names.of(code); } catch (e) { continue; }
          if (nm && nm !== code && nm !== "Unknown Region") out.push([code, nm]);
        }
        out.sort(function (x, y) { return x[1] < y[1] ? -1 : 1; });
      }
      out = [["US", "United States"]].concat(out.filter(function (o) { return o[0] !== "US"; }));
      if (out.length < 5) out = [["US", "United States"], ["CA", "Canada"], ["MX", "Mexico"], ["GB", "United Kingdom"]];
      return { groups: [{ label: "", opts: out }], other: false };
    }
    if (name === "state_region") {
      return { groups: [{ label: "", opts: US_STATES }], other: true };
    }
    if (name === "time_zone") {
      var us = [["America/New_York", "Eastern"], ["America/Chicago", "Central"], ["America/Denver", "Mountain"], ["America/Phoenix", "Arizona, no daylight time"],
                ["America/Los_Angeles", "Pacific"], ["America/Anchorage", "Alaska"], ["Pacific/Honolulu", "Hawaii"]]
        .map(function (z) { return [z[0], z[1] + " (" + z[0] + ")"]; });
      var all = [];
      try { all = Intl.supportedValuesOf("timeZone").map(function (z) { return [z, z]; }); } catch (e) {}
      var groups = [{ label: "United States", opts: us }];
      if (all.length) groups.push({ label: "All time zones", opts: all });
      return { groups: groups, other: all.length === 0 };
    }
    return null;
  }

  function buildField(name, def, rec, ctx) {
    var P = ctx.prefix, SCH = ctx.schema, FLD = ctx.fields;
    var wrap = document.createElement("div");
    var label = document.createElement("label"); label.className = "f"; label.htmlFor = "ef_" + P + name;
    label.appendChild(document.createTextNode(humanize(name)));
    var isReq = (SCH.required || []).indexOf(name) >= 0;
    if (isReq) { var star = document.createElement("span"); star.className = "req"; star.setAttribute("aria-hidden", "true"); star.textContent = "*"; label.appendChild(star); }
    var orig = rec[name] === undefined ? null : rec[name];
    var kind, el, other = null;
    var choices = (def.type === "string" && !def["enum"]) ? choicesFor(name) : null;
    function opt(sel, value, text) { var o = document.createElement("option"); o.value = value; o.textContent = text; sel.appendChild(o); }
    if (def.type === "boolean") {
      kind = "bool"; el = document.createElement("select");
      if (!isReq) opt(el, "", "Not answered");
      opt(el, "true", "Yes"); opt(el, "false", "No");
      el.value = orig === null ? "" : String(orig);
    } else if (def["enum"]) {
      kind = "text"; el = document.createElement("select");
      if (!isReq) opt(el, "", "Not set");
      def["enum"].forEach(function (v) { opt(el, String(v), String(v).replace(/_/g, " ")); });
      el.value = orig === null ? "" : String(orig);
    } else if (def.type === "integer" || def.type === "number") {
      kind = /_cents$/.test(name) ? "money" : "num";
      el = document.createElement("input"); el.type = "number"; el.inputMode = "decimal";
      el.step = kind === "money" ? "0.01" : (def.type === "integer" ? "1" : "any");
      var div = kind === "money" ? 100 : 1;
      if (def.minimum != null) el.min = def.minimum / div;
      if (def.maximum != null) el.max = def.maximum / div;
      el.value = orig === null ? "" : (kind === "money" ? (orig / 100).toFixed(2) : String(orig));
    } else if (choices) {
      kind = "text"; el = document.createElement("select");
      opt(el, "", "Not set");
      choices.groups.forEach(function (g) {
        var parent = el;
        if (g.label) { parent = document.createElement("optgroup"); parent.label = g.label; el.appendChild(parent); }
        g.opts.forEach(function (o) { opt(parent, o[0], o[1]); });
      });
      if (choices.other) {
        opt(el, "__other__", "Other (type it)");
        other = document.createElement("input"); other.type = "text"; other.className = "other"; other.id = "ef_" + P + name + "_other";
        other.maxLength = def.maxLength || 100; other.placeholder = "Type it"; other.hidden = true; other.autocomplete = "off";
        el.addEventListener("change", function () { other.hidden = el.value !== "__other__"; if (!other.hidden) other.focus(); });
      }
      var has = orig !== null && Array.prototype.some.call(el.options, function (o) { return o.value === orig; });
      if (orig === null) el.value = "";
      else if (has) el.value = orig;
      else if (other) { el.value = "__other__"; other.value = orig; other.hidden = false; }
      else { opt(el, orig, orig); el.value = orig; }
    } else {
      kind = "text";
      el = (def.maxLength || 0) > 200 ? document.createElement("textarea") : document.createElement("input");
      if (el.tagName === "INPUT") el.type = def.format === "email" ? "email" : def.format === "uri" ? "url" : /_phone$/.test(name) ? "tel" : "text";
      if (def.maxLength) el.maxLength = def.maxLength;
      el.autocomplete = "off"; el.autocapitalize = "off"; el.spellcheck = false;
      el.value = orig === null ? "" : String(orig);
    }
    el.id = "ef_" + P + name; if (isReq) el.setAttribute("aria-required", "true");
    wrap.appendChild(label); wrap.appendChild(el);
    if (other) wrap.appendChild(other);
    if (kind === "money") { var k = document.createElement("div"); k.className = "fhint keep"; k.textContent = "In dollars."; wrap.appendChild(k); }
    var hintText = firstSentence(def.description);
    if (hintText) { var h = document.createElement("div"); h.className = "fhint"; h.textContent = hintText; wrap.appendChild(h); }
    var er = document.createElement("div"); er.className = "ferr"; er.id = "ee_" + P + name; wrap.appendChild(er);
    FLD[name] = { el: el, other: other, kind: kind, def: def, sec: null, summary: null };
    return wrap;
  }

  function openSec(f) {
    f.sec.open = true;
    var m = f.sec.closest("details.more");
    if (m) { m.open = true; m.firstChild.className = "haserr"; }
  }

  function readValue(f) {
    var raw = f.el.value;
    if (f.other && raw === "__other__") raw = f.other.value;
    if (f.kind === "bool") return raw === "" ? null : raw === "true";
    var t = raw.trim();
    if (f.kind === "text") return t === "" ? null : t;
    if (t === "") return null;
    var n = Number(t);
    if (!isFinite(n)) return undefined;
    return f.kind === "money" ? Math.round(n * 100) : n;
  }

  window.ConsoleForms = { labels: LABELS, humanize: humanize, firstSentence: firstSentence, choicesFor: choicesFor, buildField: buildField, readValue: readValue, openSec: openSec };
})();
