/* Services for the Console: how one station asks another for something without naming it (DT-29, DT-3, DT-4). A station that others need registers itself once,
   at the end of its own file: ConsoleServices.provide("people", <its own station object>). A station that needs something reads it from the registry:
   ConsoleServices.fn("people", "list") gives a function that looks the owner up when it is CALLED (the owner usually loads after the reader), and
   ConsoleServices.call("people", "stale") calls straight away. The owners and what they offer are listed in console/ARCHITECTURE.md ("Services"); the
   architecture test checks that every service asked for is provided once and that the owner file defines the member. Plain code, no state but the table.
   Loaded by index.html before console.js. */
(function () {
  "use strict";
  var owners = {}, asked = [];
  function look(name, member) {
    var o = owners[name];
    if (!o || typeof o[member] !== "function") throw new Error("Console service " + name + "." + member + " is not provided");
    return o[member];
  }
  window.ConsoleServices = {
    provide: function (name, obj) { owners[name] = obj; },
    fn: function (name, member) { asked.push([name, member]); return function () { return look(name, member).apply(null, arguments); }; },
    call: function (name, member) { return look(name, member).apply(null, Array.prototype.slice.call(arguments, 2)); },
    missing: function () { return asked.filter(function (p) { var o = owners[p[0]]; return !o || typeof o[p[1]] !== "function"; }).map(function (p) { return p[0] + "." + p[1]; }); }   // for the tests: what was asked for at load and is not provided
  };
})();
