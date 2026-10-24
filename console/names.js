/* Shared names for the Console: the venue and curriculum lists that several pages read (the request cards say which venue and curriculum a person
   asked for; Classes and the Put in a class form offer them in drop-downs). One owner, so no station has to reach into another to get them.
   Moved out of console.js (the Requests run, R-1): the code is the same; the three kinds of change are listed in claude/requests-extraction-run-log.md.
   Not a station: no show. It empties its data on sign-out (reset). Loaded by index.html after console.js and before the stations. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var admin = K.admin, lock = K.lock;

  var cVenues = [], cVenueById = {}, cCurricula = [];
  var venueChipFetch = null, curChipFetch = null;

  function loadVenueChoices() {
    return admin("list", { limit: 200, expand: true }, "venues").then(function (res) {
      if (res.status === 401) { lock("That key did not work."); return false; }
      if (res.status !== 200 || !res.body.ok) return false;
      cVenues = (res.body.data.records || []).slice().sort(function (a, b) { return (a.name || "").toLowerCase() < (b.name || "").toLowerCase() ? -1 : 1; });
      cVenueById = {}; cVenues.forEach(function (v) { cVenueById[v.id] = v; });
      return true;
    });
  }
  function loadCurriculumChoices() {
    return admin("list", { filters: { status: "active" }, limit: 200 }, "curriculums").then(function (res) {
      if (res.status === 401) { lock("That key did not work."); return false; }
      if (res.status !== 200 || !res.body.ok) return false;
      cCurricula = (res.body.data.records || []).slice().sort(function (a, b) { return (a.title || "").toLowerCase() < (b.title || "").toLowerCase() ? -1 : 1; });
      return true;
    });
  }
  function refreshCurriculumChips() {   // the curriculum titles arrive after the request cards are drawn
    Array.prototype.forEach.call(document.querySelectorAll(".curchip[data-cid]"), function (c) {
      var n = curriculumAsked(c.getAttribute("data-cid")); if (n) c.textContent = "Interested in: " + n;
    });
  }
  function curriculumAsked(id) {
    var r = "";
    cCurricula.forEach(function (c) { if (c.id === id) r = c.title || "(no title)"; });
    return r;
  }
  function refreshVenueChips() {   // the venue names arrive after the request cards are drawn
    Array.prototype.forEach.call(document.querySelectorAll(".venuechip[data-vid]"), function (c) {
      var n = venueAsked(c.getAttribute("data-vid")); if (n) c.textContent = "Venue asked for: " + n;
    });
  }
  // "Name, Town" for a venue the requester picked on the form. Empty until the venues are loaded or when it is gone.
  function venueAsked(id) {
    var v = id ? cVenueById[id] : null;
    if (!v) return "";
    var town = v.place && v.place.address && v.place.address.locality;
    return (v.name || "(no name)") + (town ? ", " + town : "");
  }

  window.ConsoleNames = {
    loadVenueChoices: loadVenueChoices, loadCurriculumChoices: loadCurriculumChoices,
    venues: function () { return cVenues; }, venueById: function (id) { return cVenueById[id]; }, curricula: function () { return cCurricula; },
    venueAsked: venueAsked, curriculumAsked: curriculumAsked,
    // A request card was drawn before the names were here: fetch them once and fill the chips in (was inline in the card code).
    ensureVenueChips: function () { if (!cVenues.length && !venueChipFetch) venueChipFetch = loadVenueChoices().then(refreshVenueChips); },
    ensureCurriculumChips: function () { if (!cCurricula.length && !curChipFetch) curChipFetch = loadCurriculumChoices().then(refreshCurriculumChips); },
    // Sign-out: the names leave the page (a deliberate change: they used to stay in memory after the Console locked).
    reset: function () { cVenues = []; cVenueById = {}; cCurricula = []; venueChipFetch = null; curChipFetch = null; }
  };
})();
