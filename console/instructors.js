/* Instructors station: who teaches, their hours, curricula, regions and private address. The engine is console/roster-engine.js, which reaches the big file through window.ConsoleKit; this file is only its settings and the hooks console.js calls. */
(function () {
  "use strict";
  var CFG =
  { id: "instructors", coll: "instructor_rosters", pre: "ri", one: "instructor", Many: "Instructors", hours: true, curricula: true,
      fields: [
        { k: "bio", label: "Bio", t: "area", hint: "A short paragraph written for people choosing a class." },
        { k: "capabilities", label: "What they can teach or do", t: "tags", hint: "Separate tags with commas or put each on its own line. Each tag is a few words (up to 60 characters); up to 30 tags. For example: prompting basics, large rooms, voice and images." },
        { k: "service_area", label: "Where they will travel", t: "text", hint: "For example Denver metro, or online only." },
        { k: "notes", label: "Notes", t: "area", hint: "Visible to operators only." } ] };
  var S = window.ConsoleRoster.build(CFG);
  window.InstructorsStation = { show: function () { if (!S.loaded) S.load(); }, reset: function () { S.reset(); }, forget: function () { S.loaded = false; } };
})();
