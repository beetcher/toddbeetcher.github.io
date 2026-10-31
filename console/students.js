/* Students station: who attends, with notes. The engine is console/roster-engine.js, which reaches the big file through window.ConsoleKit; this file is only its settings and the hooks console.js calls. */
(function () {
  "use strict";
  var CFG =
  { id: "students", coll: "student_rosters", pre: "rs", one: "student", Many: "Students", hours: false, placement: true,
      fields: [ { k: "notes", label: "Notes", t: "area", hint: "Visible to operators only." } ] };
  var S = window.ConsoleRoster.build(CFG);
  window.StudentsStation = { show: function () { if (!S.loaded) S.load(); }, reset: function () { S.reset(); }, forget: function () { S.loaded = false; } };
})();
