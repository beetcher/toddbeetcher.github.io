/* Address machinery (window.ConsoleAddresses): the address form, recent city/state/ZIP memory, the place words, the saved-places pick.
   Shared by Places, People's Addresses panel, Venues and the Instructors page, so it loads before the stations. Moved out of console.js without
   changing what it does (PP-2). It reaches the big file only through window.ConsoleKit. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  var mk = K.mk, admin = K.admin, lock = K.lock, adminProblem = K.adminProblem, line = UI.line, str = UI.str;
  var D = window.ConsoleData, COLL_L = D.COLL_L, COLL_LK = D.COLL_LK, REL = D.REL;

  // ---- Places station and the Addresses panel on a person's card: locations and the links to them, through the same admin door.
  // A place is saved once and knows nothing about who is there. A person (or venue) is linked to it with dates.
  var LLABEL = { name: "Name", description: "Description", time_zone: "Time zone", kind: "Kind", addresses: "Address", geometries: "GPS point", status: "Status",
                 location_id: "Place", subject_id: "Person", relationship: "Kind of address", valid_from: "From", valid_to: "Until", id: "Place", address: "Address" };
  var LISSUE = { "addresses:required": "A street address needs a country (two letters, such as US).", "addresses:duplicate": "Only one address can be the main one.",
                 "addresses:out_of_range": "An address ends before it starts.", "geometries:invalid_value": "GPS needs latitude from -90 to 90 and longitude from -180 to 180.",
                 "time_zone:invalid_value": "Use a time zone name such as America/Denver.", "location_id:duplicate": "This person is already linked to that place for those dates.",
                 "status:place_required": "A venue needs a place (an address or a GPS point) to be active.", "address:choose_one": "Give an address or choose a saved place, not both.",
                 "address:required": "Type an address or choose a saved place.", "address:invalid_format": "Check the address.",
                 "location_id:not_found": "That place was not found.", "location_id:retired": "That place is retired.", "subject_id:not_found": "That person was not found.",
                 "valid_to:out_of_range": "The last day is before the first day.", "id:in_use": "People or venues are still linked to this place. End those links first.",
                 "part_of_location_id:invalid_value": "That would make a place part of itself.", "relationship:invalid_value": "That kind of address does not fit.",
                 required: "Required.", invalid_format: "That value is not valid.", invalid_value: "That value is not valid.", out_of_range: "Too long or too short.",
                 invalid_type: "That value is not valid.", not_allowed: "That cannot be set here.", immutable: "That cannot be changed.", not_found: "That was not found." };
  function lProblems(res) {
    var ps = (res.body && res.body.error && res.body.error.problems) || [], out = [];
    ps.forEach(function (p) { out.push((LLABEL[p.field] || p.field) + ": " + (LISSUE[p.field + ":" + p.issue] || LISSUE[p.issue] || "That value is not valid.")); });
    if (!ps.length) out.push(adminProblem(res.status));
    return out.join(" ");
  }
  function locAddr(a) {
    if (!a) return "";
    var parts = [], st = [a.street_number, a.street].filter(Boolean).join(" ");
    if (a.po_box) parts.push("PO Box " + a.po_box);
    if (st) parts.push(a.unit ? st + " " + a.unit : st);
    if (!parts.length && a.lines && a.lines.length) parts.push(a.lines.join(", "));
    var city = [a.locality, [a.region, a.postal_code].filter(Boolean).join(" ")].filter(Boolean).join(", ");
    if (city) parts.push(city);
    return parts.join(", ");
  }
  function locSummary(loc) {
    var pick = null;
    (loc.addresses || []).forEach(function (a) { if (!pick || (a.is_primary && !pick.is_primary)) pick = a; });
    var t = locAddr(pick);
    if (loc.name && t) return loc.name + " · " + t;
    return t || loc.name || "(details removed)";
  }

  // Recently used city / state / ZIP, newest first, kept in this browser only (never the street, never sent anywhere).
  var CSZ_KEY = "launch_console_recent_csz";
  function cszRead() { try { var a = JSON.parse(localStorage.getItem(CSZ_KEY) || "[]"); return Array.isArray(a) ? a.filter(function (x) { return x && (x.c || x.s); }) : []; } catch (e) { return []; } }
  function cszRemember(c, st, z) {
    if (!c && !st) return;
    try {
      var key = function (x) { return [x.c, x.s, x.z].join("|").toLowerCase(); }, cur = { c: c || "", s: st || "", z: z || "" };
      var all = [cur].concat(cszRead().filter(function (x) { return key(x) !== key(cur); })).slice(0, 20);
      localStorage.setItem(CSZ_KEY, JSON.stringify(all));
    } catch (e) {}
  }
  function cszLabel(x) { return [x.c, [x.s, x.z].filter(Boolean).join(" ")].filter(Boolean).join(", "); }

  // A reusable block of address boxes. opts: name, description, tz, gps, usageChoice. block.read() -> {ok, data}.
  function addrForm(opts) {
    var box = mk("div", "afbox"), f = {}, cur = box, sections = !!(opts.name || opts.gps || opts.tz || opts.description);
    function sec(title, grid) {   // a heading (only when the form has more than one part) and, for the address boxes, a two-column grid on wide screens
      if (sections && title) cur = box, cur.appendChild(mk("h3", "fsec", title));
      if (grid) { cur = mk("div", "fgrid"); box.appendChild(cur); } else cur = box;
    }
    function add(key, label, hint, max, ph, wide) {
      var w = mk("div", "fld" + (wide ? " fwide" : "")), l = mk("label", "f", label), el = mk("input"); el.type = "text"; el.maxLength = max || 120; el.autocomplete = "off"; if (ph) el.placeholder = ph;
      el.id = "af" + K.afNext() + "_" + key; l.htmlFor = el.id;
      w.appendChild(l); w.appendChild(el); if (hint) w.appendChild(mk("div", "hint", hint));
      var er = mk("div", "ferr"); w.appendChild(er); cur.appendChild(w); f[key] = { el: el, err: er, wrap: w };
    }
    if (opts.name) { sec("About the place"); if (!opts.optional) box.appendChild(mk("div", "hint", "Give the place at least one of: a name, a street address or a GPS point.")); add("name", "Name of the place (optional)", "For example: Boulder Public Library, or Home.", 200); }
    if (opts.description) { var dl = mk("label", "f", "Description (optional)"), dt = mk("textarea"); dt.maxLength = 2000; dt.id = "af" + K.afNext() + "_desc"; dl.htmlFor = dt.id; box.appendChild(dl); box.appendChild(dt); f.description = { el: dt, err: mk("div", "ferr") }; box.appendChild(mk("div", "hint", "About the place itself, for example: brick building, parking behind. Never who lives there.")); }
    sec(opts.name || opts.gps || opts.tz ? "Address" : "", true);
    if (opts.usageChoice) {
      var uw = mk("div", "fld fwide"), ul = mk("label", "f", "What kind of address"), us = mk("select"); us.id = "af" + K.afNext() + "_usage"; ul.htmlFor = us.id;
      [["civic", "Street address"], ["mailing", "Mailing address"], ["po_box", "PO box"], ["former", "Former address"]].forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; us.appendChild(op); });
      uw.appendChild(ul); uw.appendChild(us); cur.appendChild(uw); f.usage = { el: us, err: mk("div", "ferr") };
    }
    add("street_line", "Street address", "For example: 123 Walnut St. Type it on one line.", 140, "", true); add("unit", "Apartment or suite (optional)", "", 60, "", true);
    if (opts.usageChoice) add("po_box", "PO box number (if it is a PO box)", "", 20, "", true);
    add("locality", "City", "", 120); add("region", "State", "Two letters, for example CO.", 60); add("postal_code", "ZIP code", "", 20);
    add("country", "Country", "Two letters. US for the United States.", 2);
    f.country.el.value = "US";
    // Recent city / state / ZIP: the newest fills the boxes; a list lets you pick another. Every box stays free to overwrite.
    var recent = cszRead(), auto = null;   // auto: the values we filled in, so an untouched fill never counts as an address
    if (recent.length) {
      var rl = mk("label", "f", "Recent city, state and ZIP"), rs = mk("select"); rs.id = "af" + K.afNext() + "_recent"; rl.htmlFor = rs.id;
      recent.forEach(function (x, i) { var o = mk("option", "", cszLabel(x)); o.value = String(i); rs.appendChild(o); });
      var oo = mk("option", "", "Type a different one"); oo.value = ""; rs.appendChild(oo);
      function fillRecent() {
        var x = rs.value === "" ? null : recent[Number(rs.value)];
        if (!x) return;
        f.locality.el.value = x.c || ""; f.region.el.value = x.s || ""; f.postal_code.el.value = x.z || ""; auto = { c: x.c || "", s: x.s || "", z: x.z || "" };
      }
      rs.addEventListener("change", fillRecent);
      var anchor = f.locality.wrap, rw = mk("div", "fld fwide"), grid = anchor.parentNode;
      rw.appendChild(rl); rw.appendChild(rs); rw.appendChild(mk("div", "hint", "From your recent entries. Change any box to overwrite."));
      grid.insertBefore(rw, anchor);
      rs.value = "0"; fillRecent();
    }
    if (opts.gps) { sec("Map point (optional)", true); add("lat", "GPS latitude (optional)", "A number from -90 to 90, for example 40.0150.", 20); add("lon", "GPS longitude (optional)", "A number from -180 to 180, for example -105.2705.", 20); }
    if (opts.tz) {
      sec("Time zone"); var zw = mk("div", "fld"), zl = mk("label", "f", "Time zone (optional)"), zs = mk("select"); zs.id = "af" + K.afNext() + "_time_zone"; zl.htmlFor = zs.id;
      [["", "(none)"]].concat(UI.zoneOptions()).forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; zs.appendChild(op); });
      zw.appendChild(zl); zw.appendChild(zs); zw.appendChild(mk("div", "hint", "Leave it empty to let the ZIP code decide later.")); var ze = mk("div", "ferr"); zw.appendChild(ze); box.appendChild(zw); f.time_zone = { el: zs, err: ze, wrap: zw };
    }
    box.read = function () {
      Object.keys(f).forEach(function (k) { f[k].err.textContent = ""; });
      var v = function (k) { return f[k] ? f[k].el.value.trim() : ""; }, ok = true, data = {}, a = {};
      var usage = f.usage ? f.usage.el.value : "civic";
      ["unit", "po_box", "locality", "region", "postal_code"].forEach(function (k) { if (v(k)) a[k] = v(k); });
      var line = v("street_line");
      if (auto && !line && !v("po_box") && !v("unit") && v("locality") === auto.c && v("region") === auto.s && v("postal_code") === auto.z) { delete a.locality; delete a.region; delete a.postal_code; }
      var sm = /^(\d+[A-Za-z]?(?:-\d+)?)\s+(\S.*)$/.exec(line);
      if (sm) { a.street_number = sm[1]; a.street = sm[2]; } else if (line) a.street = line;
      if (a.street || a.po_box) {
        a.usage = usage; a.country = v("country").toUpperCase();
        if (usage === "civic" && !/^[A-Z]{2}$/.test(a.country)) { f.country.err.textContent = "Two capital letters, such as US."; ok = false; }
        else if (!/^[A-Z]{2}$/.test(a.country)) delete a.country;
        if (opts.primary) a.is_primary = true;
        data.addresses = [a];
      } else if (a.unit || a.locality || a.region || a.postal_code) { f.street_line.err.textContent = "Add the street address (or a PO box) to save an address."; ok = false; }
      if (opts.gps && (v("lat") || v("lon"))) {
        var la = Number(v("lat")), lo = Number(v("lon"));
        if (!v("lat") || isNaN(la) || la < -90 || la > 90) { f.lat.err.textContent = "A number from -90 to 90."; ok = false; }
        if (!v("lon") || isNaN(lo) || lo < -180 || lo > 180) { f.lon.err.textContent = "A number from -180 to 180."; ok = false; }
        if (ok) data.geometries = [{ role: "center", geometry: { type: "Point", coordinates: [lo, la] } }];
      }
      if (ok && (a.street || a.po_box)) cszRemember(a.locality, a.region, a.postal_code);
      if (f.name && v("name")) data.name = v("name");
      if (f.description && v("description")) data.description = v("description");
      if (f.time_zone && v("time_zone")) data.time_zone = v("time_zone");
      if (ok && !opts.optional && !data.name && !data.addresses && !data.geometries) { f.street_line.err.textContent = "Enter a street address, a name or GPS."; ok = false; }
      return { ok: ok, data: data };
    };
    return box;
  }

  // ---- Venues and their places and contacts (the venue stores pointers; these read the records they point at)
  function placeText(pl) {
    if (!pl) return "";
    var t = locAddr(pl.address);
    if (t) return (pl.name && pl.name !== t ? pl.name + " · " : "") + t;
    return (pl.name || "(unnamed place)") + (pl.has_gps ? " (GPS point only)" : "");
  }
  function venuePlaceLine(rec) {
    var pl = rec.place, parts = [];
    if (!pl) parts.push("No place yet");
    else if (pl.address && (pl.address.locality || pl.address.region)) parts.push([pl.address.locality, pl.address.region].filter(Boolean).join(", "));
    else parts.push(pl.name || "Place saved");
    if (pl) parts.push(pl.has_gps ? "GPS: " + (pl.gps_source === "entered" ? "entered" : "looked up") : "No GPS");
    if (rec.main_contact) parts.push("Contact: " + (rec.main_contact.display_name || "(unavailable)"));
    return parts.join(" · ");
  }

  var pickSeq = 0, savedPlaces = null;
  function savedPlacesList() {
    if (savedPlaces) return Promise.resolve(savedPlaces);
    return admin("list", { filters: { status: "active" }, limit: 200 }, COLL_L).then(function (r) {
      if (r.status === 401) { lock("That key did not work."); return []; }
      savedPlaces = (r.status === 200 && r.body.ok) ? (r.body.data.records || []) : [];
      return savedPlaces;
    });
  }
  // An address to type, or a saved place to use. next() -> Promise of {done, args}. args is {address}, {location_id} or {}.
  // If the typed address is already saved it offers that place first and waits for a second click.
  function placeInput(withSaved) {
    var box = mk("div"), block = addrForm({ optional: true }), chooser = mk("div", "confirm"), step = "start", addr = null, savedId = "";
    var seq = ++pickSeq;
    chooser.hidden = true;
    var picked = mk("div", "note"); picked.hidden = true;
    if (withSaved) {
      var sl = mk("label", "f", "Or use a place that is already saved"), si = mk("input"), res = mk("div");
      si.type = "text"; si.id = "pi_" + seq; si.placeholder = "Search by name or address"; si.autocomplete = "off"; sl.htmlFor = si.id;
      box.appendChild(sl); box.appendChild(si); box.appendChild(res);
      var clear = mk("button", "quiet", "Clear"); clear.type = "button";
      clear.addEventListener("click", function () { savedId = ""; picked.hidden = true; });
      picked.appendChild(document.createTextNode("")); picked.appendChild(clear);
      si.addEventListener("input", function () {
        var q = si.value.trim().toLowerCase(); res.textContent = "";
        if (!q) return;
        savedPlacesList().then(function (list) {
          list.filter(function (l) { return locSummary(l).toLowerCase().indexOf(q) >= 0; }).slice(0, 6).forEach(function (l) {
            var b = mk("button", "quiet", locSummary(l)); b.type = "button";
            b.addEventListener("click", function () {
              savedId = l.id; res.textContent = ""; si.value = "";
              picked.textContent = "Using the saved place: " + locSummary(l) + " "; picked.appendChild(clear); picked.hidden = false;
            });
            res.appendChild(b);
          });
          if (!res.firstChild) res.appendChild(mk("div", "hint", "No saved place matches."));
        });
      });
    }
    box.appendChild(block); if (withSaved) box.appendChild(picked); box.appendChild(chooser);
    box.next = function () {
      if (step === "choose") {
        var pick = chooser.querySelector("input[name=pk" + seq + "]:checked");
        return Promise.resolve({ done: true, args: pick && pick.value ? { location_id: pick.value } : { address: addr } });
      }
      if (savedId) return Promise.resolve({ done: true, args: { location_id: savedId } });
      var rd = block.read();
      if (!rd.ok) return Promise.resolve({ done: false });
      if (!rd.data.addresses) return Promise.resolve({ done: true, args: {} });
      addr = rd.data.addresses[0];
      return admin("find_by_address", { address: addr }, COLL_L).then(function (r) {
        if (r.status === 401) { lock("That key did not work."); return { done: false }; }
        var found = (r.status === 200 && r.body.ok) ? (r.body.data.records || []) : [];
        if (!found.length) return { done: true, args: { address: addr } };
        step = "choose"; chooser.hidden = false; chooser.textContent = "";
        chooser.appendChild(mk("div", "", "This address is already saved. Use the saved place, so everything there shares one record? Then press Save again."));
        found.forEach(function (m, i) {
          var lb = mk("label", "f"), rd2 = mk("input"); rd2.type = "radio"; rd2.name = "pk" + seq; rd2.value = m.id; if (i === 0) rd2.checked = true;
          lb.style.display = "flex"; lb.style.gap = "8px"; lb.style.alignItems = "center"; lb.appendChild(rd2); lb.appendChild(document.createTextNode(" Use: " + locSummary(m))); chooser.appendChild(lb);
        });
        var lb2 = mk("label", "f"), rd3 = mk("input"); rd3.type = "radio"; rd3.name = "pk" + seq; rd3.value = "";
        lb2.style.display = "flex"; lb2.style.gap = "8px"; lb2.style.alignItems = "center"; lb2.appendChild(rd3); lb2.appendChild(document.createTextNode(" No, this is a different place")); chooser.appendChild(lb2);
        return { done: false };
      });
    };
    return box;
  }


  window.ConsoleAddresses = {
    addrForm: function () { return addrForm.apply(null, arguments); }, lProblems: function () { return lProblems.apply(null, arguments); },
    locAddr: function () { return locAddr.apply(null, arguments); }, locSummary: function () { return locSummary.apply(null, arguments); },
    placeInput: function () { return placeInput.apply(null, arguments); }, placeText: function () { return placeText.apply(null, arguments); },
    forgetSaved: function () { savedPlaces = null; }
  };
})();
