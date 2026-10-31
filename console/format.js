/* Date and name formatters for the Console: a stored time as words in the viewer's own zone, the clock for "Last checked", and a person's display name from
   an attendance row. Pure functions, no state. One owner (DT-9): before this they sat in console.js and reached every station through the kit doors when,
   time, clock and attName. Loaded by index.html before console.js. */
(function () {
  "use strict";
  var fmtTime = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" });   // the viewer's own zone, named (a class shows its own zone: classWhen)
  var fmtClock = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" });
  function when(iso) { var d = new Date(iso); return isNaN(d) ? String(iso || "") : fmtTime.format(d); }
  function attName(r) { return (r.person && r.person.display_name) || "(person not found)"; }
  window.ConsoleFormat = {
    when: when,
    time: function (d) { return fmtTime.format(d); },
    clock: function (d) { return fmtClock.format(d); },
    attName: attName
  };
})();
