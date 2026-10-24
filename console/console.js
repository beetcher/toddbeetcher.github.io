/* Console script (the "legacy" file). Moved out of index.html unchanged (master plan step 0.2). Stations are peeled out of this file one by one in Phase 2. */
(function () {
  "use strict";

  // Settings come from console-config.js. Without them nothing below can run, so say so plainly.
  var CFG = window.CONSOLE_CONFIG;
  if (!CFG || !CFG.appId || !CFG.brandName || !CFG.endpoints || !CFG.endpoints.records || !CFG.endpoints.admin || !CFG.endpoints.discovery) {
    document.body.textContent = "The Console settings file (console-config.js) is missing or incomplete.";
    return;
  }

  var MAX = 100;
  var KEY_STORE = "console_key_" + CFG.appId;

  var $ = function (id) { return document.getElementById(id); };
  var key = "";

  $("appName").textContent = CFG.brandName;

  // Look of this Console (logo, sign-in picture, tab icons) comes from the settings file, so a licensee changes it there and nowhere else.
  (function applyBranding() {
    var hero = CFG.hero || {}, logo = CFG.logo || "assets/launch-tile.webp", small = CFG.logoSmall || logo, icons = CFG.icons || {};
    $("brand").setAttribute("aria-label", CFG.brandName + " Console: go to Home");
    var bi = $("brand").querySelector("img"); if (bi) bi.src = small;
    $("lockLogo").src = logo; $("lockLogo").alt = CFG.brandName;
    $("lockTitle").textContent = CFG.brandName + " Console";
    if (hero.image) {
      $("heroImg").src = hero.image; $("heroImg").alt = hero.alt || "";
      if (hero.caption) { $("heroCap").textContent = hero.caption; $("heroCap").hidden = false; }
      $("lockHero").hidden = false;
    }
    [["icon16", "16"], ["icon32", "32"], ["icon48", "48"], ["iconTouch", "touch"]].forEach(function (p) { if (icons[p[1]]) $(p[0]).href = icons[p[1]]; });
  })();

  // Remember off: the key lives in sessionStorage (gone when the tab closes). On: localStorage (stays until Lock).
  function getKey() {
    try {
      var l = localStorage.getItem(KEY_STORE);
      if (l) return { key: l, remember: true };
      var s = sessionStorage.getItem(KEY_STORE);
      if (s) return { key: s, remember: false };
    } catch (e) {}
    return { key: "", remember: false };
  }
  function setKey(v, remember) {
    try { sessionStorage.removeItem(KEY_STORE); } catch (e) {}
    try { localStorage.removeItem(KEY_STORE); } catch (e) {}
    if (!v) return;
    try { (remember ? localStorage : sessionStorage).setItem(KEY_STORE, v); } catch (e) {}
  }

  // ---- Who is signed in. method "key" = the admin key (the back door); "google" = a Google sign-in (Firebase). While signed in with
  // Google, `key` holds the current Google ID token and every call sends it as the Bearer value, exactly like the key. ME is what the
  // server's `me` op said (or, for the key, a super admin). Hiding stations here is a courtesy: the server decides what is allowed.
  var method = "key", ME = null, auth = null, unlockSeq = 0, timing = null;
  function tnow() { return window.performance && performance.now ? performance.now() : Date.now(); }
  var SDK = "https://www.gstatic.com/firebasejs/10.14.1/";
  var STATION_CAPS = { requests: ["manage_requests", "manage_classes"], venues: ["view_console"], classes: ["view_console"], people: ["edit_people"],
    places: ["edit_places", "edit_venues"], instructors: ["manage_instructors", "manage_classes"], students: ["manage_classes", "manage_requests"],
    curriculums: ["view_console"], attendance: ["manage_classes", "manage_requests"], organizations: ["edit_people"], messages: ["view_messages"],
    discovery: ["run_discovery", "view_spend", "edit_discovery_settings"], access: ["manage_access", "invite_people"], performance: ["view_performance"] };
  function can(c) { return !!ME && (ME.is_super_admin === true || ME.inspector === true || (ME.capabilities || []).indexOf(c) >= 0); }   // an inspector may LOOK at everything; the server refuses every write
  function canAny(list) { for (var i = 0; i < list.length; i++) if (can(list[i])) return true; return false; }
  function stationAllowed(id) { var l = STATION_CAPS[id]; return l ? canAny(l) : !!(ME && (ME.is_super_admin || ME.inspector)); }
  function canPlaced() { return canAny(["manage_requests", "manage_classes"]); }
  function keyMe() { return { name: "Admin key", role_key: "super_admin", method: "key", is_super_admin: true, capabilities: [], email: "", scope_region_id: "" }; }

  var fmtTime = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" });   // the viewer's own zone, named (a class shows its own zone: classWhen)
  var fmtClock = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" });
  function when(iso) { var d = new Date(iso); return isNaN(d) ? String(iso || "") : fmtTime.format(d); }


  // ---- Stations and manuals. To add a station: one SURFACES entry (name, blurb, manual), one view section, one line in route().
  var SURFACES = [
    { id: "requests", name: "Registration requests", short: "Requests", blurb: "Sign-ups arriving from the website, newest first.",
      manual:
        '<div class="kicker">Station 1</div><h2>Registration requests</h2>' +
        '<h3>Mission</h3><p>Every time someone registers on the website, a request lands here. This is where you watch them arrive and put them in a class.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>Tap a card</b> to open it and see every answer they gave.</li>' +
        '<li><b>Put in a class…</b> places the requester in a class, and <b>everyone else named on the request</b> with them (each as a student, all together or none; the requester is left out if they said they are not attending). It says who will be added to the student roster. Each person with an email is sent the confirmation; anyone without one is placed and not told. Choose the class, then <b>Add to class</b>. If we already have someone with the same email or name, you are asked whether to use them, so nobody is added twice. Use <b>Change the name or contact details</b> to fix a typo first. The request is remembered, so the card then lists where it was placed. Choose <b>+ A new class (build it now)</b> (shown in green) in the class list to build one on the spot: pick the curriculum, venue and room, date and time, and a lead instructor. With a venue, date and time it is saved as scheduled; otherwise as an idea to finish in Classes. A multi-session curriculum starts a series at session 1; add the other sessions in Classes. <b>Delete</b> (two presses: the second says Really delete?) hides a request from this list; the record is kept for now. A request with someone still in a class is not deleted: cancel or remove them in the class Attendance first.</li>' +
        '<li><b>New requests glow lime</b> and appear on their own: the list checks for news every 20 seconds while this station is open.</li>' +
        '<li><b>Refresh</b> checks right now.</li>' +
        '<li><b>No active trainer</b> (a red chip): the request came from a ZIP that no active region holds. The requester was told we are securing the best trainer, and the staff were emailed. A red bar at the top counts them (a super admin or admin also sees <b>Send reminders now</b>, which sends the daily 8:00 reminder email to everyone who should get it, right away); the <b>Show</b> list has a <b>No active trainer</b> choice. <b>Mark handled…</b> asks what was done (required) and closes it; it also closes itself once an active region holds that ZIP. A view-only account sees these and cannot mark them.</li>' +
        '<li><b>The chip under each card</b> says <b>Placed</b> (with how many people are in classes from it) or <b>Not placed yet</b>. A request counts as placed while anyone is in a class from it. If that class is cancelled it goes back to Waiting to be placed.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>Nothing is placed by itself. You choose the class, so a full class never turns anyone away: a student simply starts on the waiting list unless you pick another status.</li>' +
        '<li>Home lists every request that is <b>Waiting to be placed</b>.</li>' +
        '</ul>' +
        '<h3>Try this</h3><ul><li>Register on the website in another window, watch the card appear, tap Put in a class…, build a class for it, and watch the chip turn to Placed.</li></ul>' },
    { id: "venues", name: "Venues", short: "Venues", blurb: "Places where classes happen: where, rooms, hours, rules.",
      manual:
        '<div class="kicker">Station 2</div><h2>Venues</h2>' +
        '<h3>Mission</h3><p>A venue is a place where a class can happen: a library, a cafe, a community room or a private home. Its rooms and opening hours live inside it.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>Status menu</b> filters the list to Active or Inactive.</li>' +
        '<li><b>Add venue</b> needs only a name, a short name and the kind of place. It starts <b>inactive</b>. Type an address too and the place is saved with it; if that address is already saved you are offered the saved place.</li>' +
        '<li><b>Tap a card</b> to read the details. <b>Edit</b> opens the form: Basics, Place and Contact first, everything else under More details. <b>Change place</b> saves right away; the old place is kept.</li>' +
        '<li>The venue\'s <b>email and phone</b> are the venue\'s own. The <b>main and backup contacts</b> are contacts you choose by name; the venue keeps only a pointer, so their details stay in one place.</li>' +
        '<li><b>Rooms: N</b> and <b>Open days: N</b> on a card open a window where you can add, change or remove them without opening the whole form.</li>' +
        '<li><b>What is needed to make this active?</b> is a checklist in the edit form. It updates as you fill in fields.</li>' +
        '<li><b>Delete</b> asks first. The venue disappears from the list but the record is kept.</li>' +
        '<li>Venues found by <b>Discovery</b> (AI) arrive here <b>inactive</b>, with a note saying what still needs a look. Check the facts, then activate. See the Discovery station.</li>' +
        '<li>Changing a venue name, or moving it to another place, emails everyone placed in an upcoming class here, with the old and the new.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>To make a venue <b>active</b> it needs one thing: a place with an address or a GPS point. Everything else is optional (a park has no one to call and no rooms).</li>' +
        '<li>The short name cannot be changed once saved.</li>' +
        '<li>A venue that has live classes <b>cannot be deleted</b>. Set it inactive instead.</li>' +
        '<li>A room a live class uses cannot be removed, renamed, or made smaller than that class\'s biggest size.</li>' +
        '<li>If someone else changed the venue while you were editing, you are asked to reload. Nothing is overwritten.</li>' +
        '</ul>' +
        '<div class="tip"><b>Captain\'s tip:</b> a class that is scheduled or enrolling needs an <b>active</b> venue, so fill a venue in and activate it before scheduling.</div>' +
        '<h3>Try this</h3><ul><li>Add a venue, edit it, add a room, then open Rooms: 1 and change the room size.</li></ul>' },
    { id: "classes", name: "Classes", short: "Classes", blurb: "Scheduled sessions: when, where, how many seats.",
      manual:
        '<div class="kicker">Station 3</div><h2>Classes</h2>' +
        '<h3>Mission</h3><p>A class is one scheduled session: a workshop, a group, or a one on one. It points at a venue and a room.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>Filters</b> are tick boxes for status and kind. Everything is ticked at first, so you see every class. Untick to narrow, or tap Show all.</li>' +
        '<li><b>Add class</b> needs a title, a short name, the kind, whether it shows in the public list, and the people numbers. It starts as an <b>idea</b> with no date.</li>' +
        '<li><b>Edit</b> adds the venue, room, date and time, price and notes. Pick the venue first; the room list then shows that venue\'s rooms.</li>' +
        '<li><b>Start time</b> is typed in the class\'s own time zone and saved correctly for everyone else.</li>' +
        '<li><b>Attendance</b> on a card opens the real list: the instructors and students of that class, each with a status you can change. Open <b>Add a student or instructor</b> to pick someone we already know or add someone new. A new student or instructor is added to the student or instructor list in the same step. A student joins as <b>assigned</b>, or on the <b>waiting list</b> if the class is full; you can pick any status yourself (assigned, waiting list, confirmed, attended, late, did not show, declined, withdrawn, cancelled), and a full class never refuses anyone. <b>Journal</b> on the card shows who was placed, changed or removed, and when. <b>Setting a class to cancelled</b> cancels everyone in it, students and instructors, and puts each request back to Waiting to be placed. <b>Remove</b> takes a mistaken entry out; their record is kept. <b>People are emailed when a placement ends</b>: everyone in a cancelled or deleted class gets a cancel notice (with a calendar file that removes the event); a person set to declined, withdrawn or cancelled, or removed, is told, and when a student who held a seat leaves, every instructor of the class is told. Choosing a status that ends a person’s place (declined, withdrawn, cancelled) asks you to confirm first, because they are emailed. Every save shows a spinner on the button and a Working, then Done, message at the bottom of the screen. Messages shows every one of these emails, including any that could not be sent.</li>' +
        '<li><b>Curriculum, series and session number</b> are in Edit, under Basics. The curriculum says what is taught. A curriculum with several sessions is taught as several classes, one per session: give them all the same <b>series</b> (choose "A new series" on the first, then pick that series on the rest) and a session number each. Two classes in one series cannot share a number.</li>' +
        '<li><b>Cancel class</b> is for a real class that does not happen. It stays in the list marked cancelled, and everyone in it is cancelled and emailed (students and instructors).</li>' +
        '<li><b>Delete</b> is for a class built by mistake, such as a duplicate. It asks first, then disappears from the list. The record is kept.</li>' +
        '<li><b>Saving a change</b> to the date, start time, length, time zone, venue, room or venue notes of a class that has not started emails everyone placed in it (students, the waiting list and instructors) what changed and what it is now. Students and instructors get a calendar update that replaces the old entry; the waiting list gets no calendar file. It is one message per person per save. Changing the lead instructor does the same. A class that is given its first date emails the people already placed in it the usual placement emails. Titles, sizes and prices send nothing.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>Fewest people, target and biggest size must go in order: fewest, then target, then biggest.</li>' +
        '<li>The biggest size cannot be more than the chosen room holds.</li>' +
        '<li>A <b>scheduled</b> or <b>enrolling</b> class needs a venue that exists and is <b>active</b>.</li>' +
        '<li>A cancelled reason is only for cancelled classes.</li>' +
        '<li>The short name cannot be changed once saved. The counts (registered, waiting, attended, reviews) belong to the ship and cannot be typed in.</li>' +
        '<li>A class that holds registrations <b>cannot be deleted</b> (cancel the registrations first), and its biggest size cannot drop below the seats already taken.</li>' +
        '</ul>' +
        '<div class="tip"><b>Captain\'s tip:</b> if a class seems missing, open Filters and tap Show all, then Refresh.</div>' +
        '<h3>Try this</h3><ul><li>Add a one on one class, then edit it and give it a venue, a room and a start time.</li></ul>' },
    { id: "people", admin: true, name: "People", short: "People", blurb: "The people behind the sign-ups: names, birth dates, merging duplicates.",
      manual:
        '<div class="kicker">Station 4</div><h2>People</h2>' +
        '<h3>Mission</h3><p>A person is one human, recorded once, whatever they do with LAUNCH: a student, a payer, a leader, a guest. Roles and details that change over time are kept elsewhere and point back here.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>Status menu</b> shows Active, Inactive, or all. <b>Find by name</b> narrows the list as you type.</li>' +
        '<li><b>Add person</b> needs only a given name.</li>' +
        '<li><b>History</b> on a card lists every class the person is in, as a student or an instructor, and how it went.</li>' +
        '<li><b>Tap a card</b> to read everything on file. <b>Edit</b> changes names, birth date, language, status and notes. Clear a box to remove that value.</li>' +
        '<li><b>Merge into another person</b> is for duplicates. Pick who to keep and say why. Gaps on the kept person are filled from the duplicate, records pointing at the duplicate move over, and the duplicate is marked merged.</li>' +
        '<li><b>Addresses</b> opens the person\'s addresses: where they live, mail goes, and so on, each with dates. <b>Add an address</b> finds the place if it is already saved, or saves it, and links the person. <b>End</b> records a move; <b>Remove</b> is only for a mistake.</li>' +
        '<li>To link a person to an organization (a superintendent, a teacher, a volunteer), open the organization in <b>Organizations</b> and tap <b>Add link</b>. The person\'s card does not show it yet.</li>' +
        '<li><b>Merge history</b> lists every merge. <b>Undo this merge</b> puts the records back. Values changed since the merge are left alone.</li>' +
        '<li><b>Delete</b> asks first. The person is hidden from the lists but the record is kept.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>The ship never merges two people on its own, and never because an email or phone matches. A person decides.</li>' +
        '<li>Dates are typed month first: 04-17-1961, 04-1961, or just 1961 when that is all you know. Whether someone is under 18 is worked out by the ship, never typed.</li>' +
        '<li>Protected details (health and similar) have no screen here on purpose. They need a recorded purpose and consent first.</li>' +
        '<li>Erasing a person for good is not available here. It waits for sign-in roles.</li>' +
        '<li>If someone else changed the person while you were editing, you are asked to refresh. Nothing is overwritten.</li>' +
        '</ul>' +
        '<div class="tip"><b>Captain\'s tip:</b> a name like "Bob Smith" twice is not proof of one person. Check a birth date or ask before merging.</div>' +
        '<h3>Try this</h3><ul><li>Add two people with nearly the same name, merge one into the other, then undo it from Merge history.</li></ul>' },
    { id: "places", admin: true, name: "Places", short: "Places", blurb: "Locations on Earth: addresses, GPS points, and who is linked.",
      manual:
        '<div class="kicker">Station 5</div><h2>Places</h2>' +
        '<h3>Mission</h3><p>A place is somewhere on Earth, big or small: a doorway, a street address, a whole property with several GPS points. It never says who lives, owns or works there. People and venues are <b>linked</b> to a place, with dates, so a move ends one link and starts another while the places stay as they are.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>Add place</b> saves a place by itself. To give a person an address, open their card in <b>People</b> and tap <b>Addresses</b>: that finds the place if it is already saved, or saves it, and links the person with a start date.</li>' +
        '<li><b>Tap a card</b> to see every address and GPS point. <b>Add address</b> and <b>Add GPS point</b> put more on the same place. <b>Show who is linked here</b> lists the people, venues and organizations. An organization is linked to a place from its own card in <b>Organizations</b> (<b>Add place</b>).</li>' +
        '<li>Changing a place address emails everyone placed in an upcoming class at a venue there, with the old and the new address.</li>' +
        '<li><b>Retire</b> hides a place that is no longer used. <b>Delete</b> hides a mistake. Neither works while anyone is still linked: end those links first.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>Two places with the same address are reported, never merged by the ship.</li>' +
        '<li>Living at the same place does not make two people related. The ship never guesses family from an address.</li>' +
        '<li>Homes of people marked confidential or sealed are not shown here.</li>' +
        '<li>Structures (how many bedrooms) and neighborhoods or cities are not part of a place.</li>' +
        '</ul>' +
        '<div class="tip"><b>Captain\'s tip:</b> use End, not Remove, when someone moves. Remove is for a mistake.</div>' +
        '<h3>Try this</h3><ul><li>Add an address to a person, then add a second person at the same address and see the ship offer the saved place.</li></ul>' },
    { id: "instructors", name: "Instructors", short: "Instructors", blurb: "The people who teach: bio, what they teach, where and when.",
      manual:
        '<div class="kicker">Station 6</div><h2>Instructors</h2>' +
        '<h3>Mission</h3><p>The instructor roster is the list of who can teach a LAUNCH class. A name or phone number is kept in one place only, and each entry adds what LAUNCH needs to know about them as an instructor.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>Add instructor</b> is one window. Type a name and pick them from the list, or choose <b>Someone new</b> and fill in their name, email and phone. If anything is refused, nothing is saved.</li>' +
        '<li><b>Tap a card</b> to read it. <b>Edit</b> changes the instructor details and their name, email and phone together. The weekly hours are one row per day: leave a day empty if they cannot teach.</li>' +
        '<li><b>Remove from instructors</b> takes them off the roster. Their history is kept, and you can add them again later.</li>' +
        '<li>The status menu shows Active, Inactive or all. Inactive instructors are kept but will not be offered when assigning.</li>' +
        '<li>An instructor needs an address. When you add one, enter where they live (saved privately; only the state is shown afterwards). A card that says <b>No address on file</b> has an <b>Add address</b> button, and an instructor without an address cannot be made active again until you add one.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>Someone is an instructor once. If you pick someone who already is, the window says so and opens their card.</li>' +
        '<li>The ship never matches a typed name on its own. You pick, or you say it is someone new.</li>' +
        '<li>The weekly hours, bio and tags are optional. The roster is expected to grow more fields.</li>' +
        '<li>If two records for the same person are merged, their roster entries move to the one kept. Erasing someone removes their entries.</li>' +
        '</ul>' +
        '<div class="tip"><b>Captain\'s tip:</b> someone can be both an instructor and a student. They have one entry on each roster.</div>' +
        '<h3>Try this</h3><ul><li>Add a new instructor, then open their card and add a bio and Tuesday hours.</li></ul>' },
    { id: "students", name: "Students", short: "Students", blurb: "Who takes classes: a simple roster with a status and a note.",
      manual:
        '<div class="kicker">Station 7</div><h2>Students</h2>' +
        '<h3>Mission</h3><p>The student roster is the list of who takes LAUNCH classes. Each entry holds a status and a note. It is deliberately thin and will grow.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>Add student</b> works like adding an instructor: type a name, pick them, or choose <b>Someone new</b>.</li>' +
        '<li><b>Edit</b> changes the status, the note, and their name, email and phone together.</li>' +
        '<li><b>Remove from students</b> takes them off the roster but keeps the history. They can be added again later.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>Someone is a student once. Nothing is matched for you.</li>' +
        '<li>Merging and erasing carry over to this roster.</li>' +
        '</ul>' +
        '<div class="tip"><b>Captain\'s tip:</b> People and Places show in red in the station menu. They are the super-admin stations that will be hidden from other operators once sign-in exists.</div>' +
        '<h3>Try this</h3><ul><li>Add two friends as students, then remove one and add them back.</li></ul>' },
    { id: "curriculums", name: "Curriculum", short: "Curriculum", blurb: "What is taught: the portfolio of curricula a class points at.",
      manual:
        '<div class="kicker">Station 8</div><h2>Curriculum</h2>' +
        '<h3>Mission</h3><p>A curriculum is what is taught, such as Introduction to AI Use. A class is a place at a time with one curriculum. LAUNCH keeps a small portfolio of them; which instructors can teach which is set on each instructor\'s card.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>Add curriculum</b> needs a title and a short identifier (it fills itself in from the title; lowercase letters, digits and underscores). Sessions and minutes per session are optional.</li>' +
        '<li><b>Edit</b> changes everything except the identifier. Setting a curriculum to <b>inactive</b> keeps it but stops offering it when a class is built.</li>' +
        '<li><b>Delete</b> asks first. The curriculum disappears from the list but the record is kept.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>The short identifier is unique and cannot be changed once saved.</li>' +
        '<li>Each session of a multi-session curriculum is its own class. The curriculum only says how many sessions there are and how long each lasts.</li>' +
        '</ul>' +
        '<div class="tip"><b>Captain\'s tip:</b> start with one or two curricula. You can add more any time.</div>' +
        '<h3>Try this</h3><ul><li>Add Introduction to AI Use as one session of 60 minutes.</li></ul>' },
    { id: "attendance", name: "Attendance", short: "Attendance", blurb: "Everyone in every class: find, filter and change their status.",
      manual:
        '<div class="kicker">Station 9</div><h2>Attendance</h2>' +
        '<h3>Mission</h3><p>One list of every student and instructor in every class. Use it to answer questions like who is waiting, who has not confirmed, or where a reference number went.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>Filter chips</b> sit under the search box: <b>Status</b>, <b>Role</b> and <b>Came from</b>. Tap one and tick what you want to see. A dark chip means that filter is narrowing the list, and <b>Clear all</b> puts every chip back. They apply as you tick them, and the line at the bottom of each list says how many records are showing. <b>Refresh</b> loads the records again from the server.</li>' +
        '<li><b>Search</b> looks at the name, the class title, and the reference or request number. It narrows the list as you type, together with the chips.</li>' +
        '<li>Each row shows the class (tap it to open that class\'s attendance), the person, their reference and request numbers, and a status menu you can change right there.</li>' +
        '<li><b>Remove</b> asks twice. The record is kept.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>A reference (ICDT-A-…) belongs to one person in one class. A request number (ICDT-…) is the sign-up it came from.</li>' +
        '<li>The list shows the newest 200 records. If you see a note about that, narrow it with the filters or search.</li>' +
        '</ul>' },
    { id: "organizations", name: "Organizations", short: "Organizations", blurb: "Companies, schools, districts and other organized groups.",
      manual:
        '<div class="kicker">Station 10</div><h2>Organizations</h2>' +
        '<h3>Mission</h3><p>An organization is a company, nonprofit, school, school district, board, club or other organized group, such as Ozo Coffee or Boulder Valley School District. It is not a place and not a venue: a place is on Earth, a venue is somewhere a class happens. An organization may <b>sponsor</b> a class, but a shop it runs is a venue. Only the name is needed.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>Add organization</b> needs a name. Tick every kind that fits (one organization can be a nonprofit and a school). Short name, web address, email and phone are optional.</li>' +
        '<li><b>Search</b> looks at the name, short name, legal name and other names. The status menu narrows the list; choose All to see everything.</li>' +
        '<li><b>Tap a card</b> for the details. <b>Edit</b> shows the main fields, with <b>More details</b> for the legal name, other names, description, outside identifiers, dates and notes.</li>' +
        '<li><b>Outside identifiers</b> go one per line as <i>type: value</i>, for example <i>ein: 00-0000000</i>.</li>' +
        '<li>The <b>switch</b> on a card sets it active or inactive. In Edit you can also choose <b>Closed</b> for an organization that no longer exists.</li>' +
        '<li><b>Delete</b> asks first. The organization disappears from the list but the record is kept.</li>' +
        '<li><b>Show links</b> lists what is linked to the organization (people, venues, other organizations) and what the organization is itself linked to, such as a school that is <i>part of</i> a district. <b>Add link</b> picks a person, venue or organization, then how they are linked, with an optional title (Superintendent) and dates. <b>End</b> sets the last day to today; <b>Delete</b> (tap twice) is for a mistake.</li>' +
        '<li><b>Show places</b> and <b>Add place</b> link the organization to a place, for example <i>Operates here</i> for a factory, with the main-place tick for headquarters.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>Two organizations can share a name; nothing warns you. One organization can have many other names.</li>' +
        '<li>No date check: the closing date is not compared with the founding date.</li>' +
        '<li>Addresses, people and the schools that belong to a district are not typed on the organization. They are <b>links</b>, added from its card.</li>' +
        '<li>A link is never an access right. Linking a person to an organization gives them no permission to anything.</li>' +
        '</ul>' +
        '<div class="tip"><b>Captain\'s tip:</b> start with the few organizations LAUNCH deals with. More can be added any time.</div>' +
        '<h3>Try this</h3><ul><li>Add Ozo Coffee as a business, then search for it.</li></ul>' },
    { id: "messages", name: "Messages", short: "Messages", blurb: "Every message the system sent or tried to send, with notes.",
      manual:
        '<div class="kicker">Station 11</div><h2>Messages</h2>' +
        '<h3>Mission</h3><p>One list of every message the system tried to send: receipts, placement confirmations and whatever comes next. Use it to check that a message went out, to see why one did not, and to leave a note so the next person does not repeat your investigation.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li>The newest message is first. The coloured edge shows trouble: red means it needs attention, grey is skipped or already handled, green is sent.</li>' +
        '<li><b>Filter chips</b> sit under the search box. <b>Needs attention</b> is the first chip: it is a switch, not a menu. Press it to see only failed and unknown messages and anything not sent that nobody has handled yet; the number beside it is how many there are. The others, <b>Status</b>, <b>Message</b>, <b>How it was sent</b> and <b>Only show</b>, open a short list: tick what you want to see. A dark chip means that filter is narrowing the list, and <b>Clear all</b> puts every chip back. They apply as you tick them, and the line at the bottom of each list says how many messages are showing.</li>' +
        '<li><b>Search</b> looks at the address, subject, reason, notes and ids, across the whole log. The filter chips are ignored while you are searching.</li>' +
        '<li><b>Tap a message</b> for everything we recorded about it. The text of the message itself is never kept.</li>' +
        '<li><b>Add a note</b> saves a comment on that message. Notes can be added but never edited or removed; to correct one, add another.</li>' +
        '<li><b>Mark handled</b> appears on a message that was not sent: say what you did, for example phoned her.</li>' +
        '<li><b>Copy entry</b> and <b>Copy as JSON</b> put the whole message, notes included, on your clipboard.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>Messages cannot be edited or deleted here. This is the record of what happened.</li>' +
        '<li>The list shows the newest 200. If you see a note about that, narrow it with the filters or search.</li>' +
        '<li>A message with a test-address mark went to our own test inbox, not to the person.</li>' +
        '</ul>' },
    { id: "discovery", admin: true, name: "Discovery", short: "Discovery", blurb: "Find venues with AI: pick a model and an area, set a spend cap, review what comes back.",
      manual:
        '<div class="kicker">Station 12</div><h2>Discovery</h2>' +
        '<h3>Mission</h3><p>Discovery asks an AI model to find places in an area you choose (venues first) and saves what it finds as <b>inactive candidates</b> for you to check. Nobody is contacted. Nothing goes live until you activate a venue in Venues.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>The banner</b> at the top says whether Discovery is off, a dry run (plans and prompts only, nothing sent, nothing spent) or live.</li>' +
        '<li><b>Find venues</b>: choose the model, the state, then the whole state or a region, the kinds of place, the most results and a spend cap in cents. <b>Estimate</b> shows how many AI calls, the expected cost range and the exact prompts that would be sent. <b>Go</b> is only enabled after an estimate, and the run never spends past the cap. <b>Stop</b> ends it after the current call.</li>' +
        '<li><b>Runs</b>: every run ever made. Open one to see each call and its exact prompt, what was rejected and why, and the candidates. <b>Continue</b> restarts a run that paused. <b>Withdraw</b> (two presses) takes back what the run created, except venues a person has already activated, edited or used.</li>' +
        '<li><b>Candidates</b>: each fact is labelled <b>Sure</b> (a source was cited), <b>Check</b> (the AI could not confirm it) or <b>Unknown</b> (blank). A venue flagged <b>No street address</b> or <b>Operator is a new organization</b> needs a look before you activate it. Open Venues to finish and activate it.</li>' +
        '<li><b>Settings</b>: <b>Models</b> (add one, switch one on or off; only the NAME of a key setting is stored), <b>Areas</b> (a US map: click a state to switch it on or off and see its ZIP codes as dots; drag a box over dots to build a region, click a dot to pick or drop one, or change an existing region; <b>List</b> does the same with typed ZIP codes), <b>Types</b> (the tick boxes), <b>Prompt</b> (read the wording sent to the AI, edit it as a draft, publish it, or start a new draft from an older version), <b>Limits</b> (starting and maximum spend cap, results per run and per call).</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>The mode (off, dry run, live) is set on the server, never here, so a slip in the Console cannot start spending.</li>' +
        '<li>A new state starts switched off. Only states and regions switched on can be searched.</li>' +
        '<li>A fact marked Sure means a source was cited, not that it is certainly true. Always look before activating.</li>' +
        '<li>Run records are history: they are never deleted. A published prompt is never edited; edit a draft and publish it as the next version.</li>' +
        '<li>The money fields are whole cents. The Find venues tab cannot go above the maximum in Limits.</li>' +
        '</ul>' +
        '<h3>Try this</h3><ul><li>Estimate a small run for one library type in a region, open the prompts, read them, then press Go.</li></ul>' },
    { id: "access", admin: true, name: "Access", short: "Access", blurb: "Who may sign in with Google, and what each role may do.",
      manual:
        '<div class="kicker">Station 13</div><h2>Access</h2>' +
        '<h3>Mission</h3><p>Decide who may sign in to the Console with their Google account and what they may do there. Only a super admin sees this station.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>Invite someone</b>: type the Google email they sign in with, pick a role (and a territory if you like) and press Send invitation. They can sign in at once, and an email goes to that address with the Console link, who invited them, their role and the exact Google account to use. If the email did not go, the message says why.</li>' +
        '<li><b>Resend invite email</b> (on each person who is switched on) sends that email again, for example when it was missed or the address was only just corrected. Every send is in the Messages station.</li>' +
        '<li><b>Edit</b> changes a person\'s name, role or region. Once someone has signed in, their email cannot change.</li>' +
        '<li><b>Switch off / Switch on</b> stops or restores a person\'s access at their very next request. Nothing is deleted.</li>' +
        '<li><b>Roles</b> are bundles of capabilities. Tick what a role may do; the table at the bottom says what each capability allows. A super admin role does everything.</li>' +
        '<li><b>Global Inspector</b> is a view-only role for demos. A person with it sees every station (Activity, Access, Spend and Messages too) and can change nothing: the server refuses every save, delete, invitation and email, even if one is typed by hand, and the buttons that would change something are switched off. Private details are hidden (notes, birth details, home addresses, restricted details) or show as (hidden) (email, phone, ZIP); names show, and staff emails here show in full. An inspector may start a Discovery run, capped at 25 cents. Give it by choosing the Global Inspector role when you invite someone.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>The last active super admin cannot be switched off or demoted, and you cannot change your own role, region, email or on/off switch.</li>' +
        '<li>A role that people still hold cannot be deleted. Switch it off instead.</li>' +
        '<li>Only a super admin may manage access; that capability cannot be given to an ordinary role yet.</li>' +
        '<li>The admin key still opens the Console as a super admin, whatever is set here.</li>' +
        '<li>The <b>Review access code</b> (Sign-in box, super admin only) is a temporary way in for a reviewer: one code, 24 hours, view only. Type a new one and it replaces the old one and starts the 24 hours again. The reviewer types it into the Key box on the sign-in screen. The code is shown once when you set it.</li>' +
        '<li>Region limits are saved but not enforced yet.</li>' +
        '</ul>' +
        '<h3>Try this</h3><ul><li>Invite a second Google account as Region head, sign in with it in another browser, and see which stations it gets.</li></ul>' },
    { id: "activity", admin: true, name: "Activity", short: "Activity", blurb: "Who changed what, and when. Read only.",
      manual:
        '<div class="kicker">Station 14</div><h2>Activity</h2>' +
        '<h3>Mission</h3><p>A record of every change made through the Console: who did it, when, and which fields went from what to what. Only a super admin sees this station, and nothing in it can be edited or removed.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>Newest first.</b> Each card says what happened (Created, Edited, Deleted or Restored), to which record, by whom, and when.</li>' +
        '<li><b>Show</b> narrows the list to one kind of record, one kind of change, or one person or source. The server takes one of these at a time.</li>' +
        '<li><b>Search</b> narrows what is already on the screen: a name, a field, a value, a person.</li>' +
        '<li><b>Change history</b> on any card here, or on a class, venue, place, person, request or instructor card, shows everything that ever happened to that one record and the records that point at it.</li>' +
        '<li><b>Refresh</b> reads the log again. The newest 200 entries are loaded; use Show or Change history to reach older ones.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>An entry is written at the same moment as the change. A change cannot happen without its entry.</li>' +
        '<li><b>Personal details are never copied here.</b> A change to a name, email, phone, address or birth date shows that the field changed, and says its values are not recorded. So erasing a person leaves nothing to scrub.</li>' +
        '<li>A save that changed nothing writes nothing. A person\'s last sign in time is not recorded.</li>' +
        '<li>Not yet recorded: the public sign-up form and the completion link, and records created by tests.</li>' +
        '</ul>' +
        '<h3>Try this</h3><ul><li>Edit a venue, then open Activity and find the edit. Tap Change history on the venue card to see only that venue.</li></ul>' },
    { id: "performance", admin: true, name: "Performance", short: "Performance", blurb: "How fast the Console is. Read only.",
      manual:
        '<div class="kicker">Station 15</div><h2>Performance</h2>' +
        '<h3>Mission</h3><p>How fast the Console is, so slow spots can be found and fixed. Today it shows sign-in speed: every sign-in sends the time each step took, measured by that person\'s own page. More measures (Spend and others) will be added here.</p>' +
        '<h3>Controls</h3><ul>' +
        '<li><b>7, 30 or 90 days</b> and <b>device</b> narrow what the numbers cover.</li>' +
        '<li><b>The bar</b> shows where the time goes, on average: the server waking up and the network, the server\'s own work, loading the lists, and everything else.</li>' +
        '<li><b>Asleep</b> means the server had just woken up (a cold start), the usual cause of a slow first sign-in.</li>' +
        '<li><b>Refresh</b> reads the timings again.</li>' +
        '</ul>' +
        '<h3>Ship\'s rules</h3><ul>' +
        '<li>Needs the View performance capability (a super admin has it; give it to Admin in Access). Read only, nothing can be changed here.</li>' +
        '<li>No names, emails or keys are stored: only the role, the device and the times.</li>' +
        '</ul>' +
        '<h3>Try this</h3><ul><li>Sign out, sign in again, then Refresh here and look at the newest row.</li></ul>' },
  ];
  var COMING = [
    { name: "More stations", blurb: "New collections dock here as they are built." }
  ];

  var mOpen = null, mScroll = {}, mOpener = null, mPages = {};
  function surfaceById(id) { for (var i = 0; i < SURFACES.length; i++) if (SURFACES[i].id === id) return SURFACES[i]; return null; }
  function buildHome() {
    var pick = $("collPick"); pick.innerHTML = "";
    var o = document.createElement("option"); o.value = "home"; o.textContent = "Home"; pick.appendChild(o);
    var tiles = $("stationTiles");
    SURFACES.forEach(function (sf, i) {
      var op = document.createElement("option"); op.value = sf.id; op.textContent = sf.name + (sf.admin ? " (admin)" : ""); if (sf.admin) { op.style.color = "var(--err)"; op.className = "adminstn"; } pick.appendChild(op);
      var t = document.createElement("button"); t.type = "button"; t.className = "tile" + (sf.admin ? " adm" : ""); t.dataset.go = sf.id;
      t.innerHTML = '<span class="tno">Station ' + (i + 1) + '</span><span class="tname"></span><span class="tdesc"></span>';
      t.querySelector(".tname").textContent = sf.name; if (sf.admin) t.querySelector(".tno").textContent += " · admin"; t.querySelector(".tdesc").textContent = sf.blurb;
      tiles.appendChild(t);
    });
    COMING.forEach(function (c) {
      var d = document.createElement("div"); d.className = "tile soon";
      d.innerHTML = '<span class="tno">Coming soon</span><span class="tname"></span><span class="tdesc"></span>';
      d.querySelector(".tname").textContent = c.name; d.querySelector(".tdesc").textContent = c.blurb;
      tiles.appendChild(d);
    });
    ["overlayBtns"].forEach(function (host) {
      SURFACES.forEach(function (sf) {
        var b = document.createElement("button"); b.type = "button"; b.dataset.m = sf.id; b.setAttribute("aria-pressed", "false"); b.textContent = sf.short || sf.name;
        $(host).appendChild(b);
      });
    });
    var sc = $("manualScroll");
    SURFACES.forEach(function (sf) {
      var pg = document.createElement("div"); pg.className = "mpage"; pg.hidden = true; pg.innerHTML = sf.manual; sc.appendChild(pg); mPages[sf.id] = pg;
    });
    buildNav();
  }

  // ---- Sidebar (1.2a): the same stations as the drop-down, in five groups. A station not listed in a group lands under "More".
  var NAV_GROUPS = [
    { name: "Today", ids: ["requests", "messages"] },
    { name: "Classes", ids: ["classes", "attendance", "venues", "curriculums", "instructors"] },
    { name: "People", ids: ["people", "students", "organizations", "places"] },
    { name: "Growth and admin", ids: ["discovery", "access", "activity", "performance"] }
  ];
  function navLink(id, label, adm) {
    var li = document.createElement("li"), a = document.createElement("a");
    a.href = "#/" + id; a.dataset.nav = id; a.textContent = label;
    if (adm) { var t = document.createElement("span"); t.className = "nadm"; t.textContent = "admin"; a.appendChild(t); }
    li.appendChild(a); return li;
  }
  function buildNav() {
    var nav = $("sideNav"); nav.innerHTML = "";
    var home = document.createElement("ul"); home.className = "nlist"; home.appendChild(navLink("home", "Home", false)); nav.appendChild(home);
    var used = {}, groups = NAV_GROUPS.map(function (g) { g.ids.forEach(function (i) { used[i] = true; }); return { name: g.name, ids: g.ids }; });
    var rest = SURFACES.filter(function (s) { return !used[s.id]; }).map(function (s) { return s.id; });
    if (rest.length) groups.push({ name: "More", ids: rest });
    groups.forEach(function (g, gi) {
      var sec = document.createElement("div"); sec.className = "ngroup";
      var h = document.createElement("div"); h.className = "nhead"; h.id = "navg" + gi; h.textContent = g.name; sec.appendChild(h);
      var ul = document.createElement("ul"); ul.className = "nlist"; ul.setAttribute("aria-labelledby", h.id);
      g.ids.forEach(function (id) { var sf = surfaceById(id); if (sf) ul.appendChild(navLink(id, sf.short || sf.name, !!sf.admin)); });
      sec.appendChild(ul); nav.appendChild(sec);
    });
  }
  function navAccess() {   // hide what this person's role can never open, and any group left empty
    Array.prototype.forEach.call(document.querySelectorAll("#sideNav a[data-nav]"), function (a) { a.parentNode.style.display = (a.dataset.nav === "home" || stationAllowed(a.dataset.nav)) ? "" : "none"; });
    Array.prototype.forEach.call(document.querySelectorAll("#sideNav .ngroup"), function (g) {
      var any = false; Array.prototype.forEach.call(g.querySelectorAll("li"), function (li) { if (li.style.display !== "none") any = true; });
      g.style.display = any ? "" : "none";
    });
  }
  function markNav(r) {
    Array.prototype.forEach.call(document.querySelectorAll("#sideNav a[data-nav]"), function (a) { if (a.dataset.nav === r) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  }
  function setTopH() { document.documentElement.style.setProperty("--topbar-h", $("topbar").offsetHeight + "px"); }
  var ALL_OPTS = null;
  function applyAccess() {
    var pick = $("collPick");
    if (!ALL_OPTS) ALL_OPTS = Array.prototype.slice.call(pick.options);
    var cur = pick.value;
    pick.innerHTML = "";
    ALL_OPTS.forEach(function (o) { if (o.value === "home" || stationAllowed(o.value)) pick.appendChild(o); });
    pick.value = cur;
    Array.prototype.forEach.call(document.querySelectorAll("#stationTiles [data-go]"), function (b) { b.style.display = stationAllowed(b.dataset.go) ? "" : "none"; });
    Array.prototype.forEach.call(document.querySelectorAll(".mbtns button[data-m]"), function (b) { b.style.display = stationAllowed(b.dataset.m) ? "" : "none"; });
    navAccess();
    $("attnBox").hidden = !canPlaced();
    var who = $("who");
    who.textContent = ""; who.title = "";
    if (ME) { who.appendChild(document.createTextNode(ME.name + " · ")); var rl = document.createElement("span"); rl.className = "role"; rl.textContent = (ME.role_key || "").replace(/_/g, " "); who.appendChild(rl); who.title = who.textContent; }
    who.hidden = !ME || ME.method === "key";     // the admin key is no person: nothing to name
    viewOnlyMode(!!(ME && ME.inspector));
    capPass();
    if (!capObs && window.MutationObserver) { capObs = new MutationObserver(function () { capPass(); }); capObs.observe(document.body, { childList: true, subtree: true }); }
  }
  // View only (P-78): a courtesy on top of the server, which refuses every write for an inspector. The banner shows, and the buttons that would
  // change something are switched off as they appear (the words below). A button a screen needs for looking carries data-viewok.
  var VIEW_WRITE = /^(edit|save|delete|remove|add|change|switch|cancel class|merge|undo|publish|resend|invite|put in|create|retire|withdraw|mark|send|assign|activate|deactivate|find gps|restore|rename|new |draft|end$)/i;
  // data-needs="cap1 cap2" on a control that changes data (any one capability is enough). A role that can never use it does not see it;
  // a view-only account sees it switched off with the reason. Stations being ported use this instead of the label list above, which stays
  // only for controls that have not been marked yet (it goes when the last station is ported).
  function canWrite(list) { if (!ME || ME.inspector) return false; if (ME.is_super_admin === true) return true; for (var i = 0; i < list.length; i++) if ((ME.capabilities || []).indexOf(list[i]) >= 0) return true; return false; }
  function capEl(el) {
    var list = (el.getAttribute("data-needs") || "").split(/\s+/).filter(Boolean);
    if (ME && ME.inspector) { el.hidden = false; el.disabled = true; el.setAttribute("data-viewonly", "1"); el.title = "View only: this account cannot change anything."; return; }
    var ok = canWrite(list);
    el.hidden = !ok;
    if (ok && el.getAttribute("data-viewonly")) { el.disabled = false; el.removeAttribute("data-viewonly"); el.removeAttribute("title"); }
  }
  function capPass(root) { Array.prototype.forEach.call((root || document).querySelectorAll("[data-needs]"), capEl); }
  function needs(el, caps) { el.setAttribute("data-needs", caps); capEl(el); return el; }
  var capObs = null;
  var viewObs = null;
  function viewOnlyPass(root) {
    Array.prototype.forEach.call((root || document).querySelectorAll("main button, #manual button"), function (b) {
      if (b.getAttribute("data-viewok") || b.getAttribute("data-viewonly")) return;
      var t = (b.textContent || "").trim();
      if (b.classList.contains("stoggle") || VIEW_WRITE.test(t)) { b.disabled = true; b.setAttribute("data-viewonly", "1"); b.title = "View only: this account cannot change anything."; }
    });
  }
  function viewOnlyMode(on) {
    $("viewOnly").hidden = !on; document.body.classList.toggle("viewonly", on);
    $("viewOnly").innerHTML = (on && ME && ME.method === "code")      // a review code never starts a Discovery run (REVIEW_CODE_GUIDE.md)
      ? "<b>View only.</b> You can look at everything and change nothing. Private details are hidden. This temporary review access ends on its own."
      : "<b>View only.</b> You can look at everything and change nothing. Private details are hidden. You can start a Discovery run (25 cents at most).";
    if (viewObs) { viewObs.disconnect(); viewObs = null; }
    if (!on || !window.MutationObserver) return;
    viewObs = new MutationObserver(function () { viewOnlyPass(); });
    viewObs.observe(document.body, { childList: true, subtree: true });
    viewOnlyPass();
  }
  var WF_TAB = "_workflows";   // mOpen holds the open manual's id, or this when the drawer shows the workflows
  function markManual() {
    Array.prototype.forEach.call(document.querySelectorAll(".mbtns button[data-m]"), function (b) { b.setAttribute("aria-pressed", b.dataset.m === mOpen ? "true" : "false"); });
    var wf = mOpen === WF_TAB;
    $("hTabM").setAttribute("aria-selected", wf ? "false" : "true"); $("hTabM").tabIndex = wf ? -1 : 0;
    $("hTabW").setAttribute("aria-selected", wf ? "true" : "false"); $("hTabW").tabIndex = wf ? 0 : -1;
    $("paneM").hidden = wf; $("paneW").hidden = !wf;
    $("helpOpen").setAttribute("aria-expanded", mOpen ? "true" : "false");
  }
  function closeManual() {
    if (!mOpen) return;
    mScroll[mOpen] = (mOpen === WF_TAB ? $("wfBody") : $("manualScroll")).scrollTop;
    mOpen = null; $("manual").hidden = true; document.body.classList.remove("mopen"); markManual();
    if (mOpener && document.body.contains(mOpener) && mOpener.offsetParent) { try { mOpener.focus(); } catch (e) {} }
    mOpener = null;
  }
  function openHelp(tab, opener, keepScroll) {   // the drawer, on the Manuals tab (first manual, or the last one used) or the Workflows tab
    if (tab === "workflows") {
      if (mOpen === WF_TAB) return;
      if (mOpen) mScroll[mOpen] = $("manualScroll").scrollTop; else mOpener = opener || null;
      $("manual").style.setProperty("--hh", $("topbar").offsetHeight + "px");
      mOpen = WF_TAB; $("manual").hidden = false; document.body.classList.add("mopen");
      markManual(); if (!keepScroll) $("wfBody").scrollTop = mScroll[WF_TAB] || 0;
      return;
    }
    openManual(lastManual || (SURFACES[0] && SURFACES[0].id), opener, true);
  }
  var lastManual = null;
  function openManual(id, opener, noToggle) {
    if (!surfaceById(id)) return;
    if (mOpen === id) { if (!noToggle) closeManual(); return; }
    lastManual = id;
    var sc = $("manualScroll");
    if (mOpen) mScroll[mOpen] = (mOpen === WF_TAB ? $("wfBody") : sc).scrollTop; else mOpener = opener || null;
    $("manual").style.setProperty("--hh", $("topbar").offsetHeight + "px");
    mOpen = id;
    Object.keys(mPages).forEach(function (k) { mPages[k].hidden = k !== id; });
    $("manual").hidden = false; document.body.classList.add("mopen");
    sc.scrollTop = mScroll[id] || 0;
    markManual();
  }
  var DISCARD = { title: "Discard your changes?", message: "You have edits that are not saved.", yes: "Discard", no: "Keep editing", danger: true };
  function askDiscard(dirty, go, stay) {   // runs go() at once when nothing is unsaved; otherwise asks first
    if (!dirty) { go(); return; }
    UI.confirm(DISCARD).then(function (ok) { if (ok) go(); else if (stay) stay(); });
  }
  function goTo(id) {
    askDiscard((window.VenuesStation && window.VenuesStation.dirty()) || (window.ClassesStation && window.ClassesStation.dirty()), function () {
      closeManual();
      if (location.hash === "#/" + id) route(); else location.hash = "#/" + id;
    }, function () { $("collPick").value = currentRoute(); });
  }

  function show(locked) {
    $("lockView").hidden = !locked;
    $("lockBtn").hidden = locked;
    $("collPick").hidden = locked;
    $("helpOpen").hidden = locked;
    document.body.classList.toggle("withnav", !locked); setTopH(); if (locked) { lastRoute = null; document.title = "Console"; UI.dismiss(); netOk(); }
    if (locked) { closeManual(); $("homeView").hidden = true; $("listView").hidden = true; $("venuesView").hidden = true; $("classesView").hidden = true; $("peopleView").hidden = true; $("placesView").hidden = true; $("instructorsView").hidden = true; $("studentsView").hidden = true; $("curriculumsView").hidden = true; $("organizationsView").hidden = true; $("attendanceView").hidden = true; $("messagesView").hidden = true; $("discoveryView").hidden = true; $("accessView").hidden = true; $("activityView").hidden = true; $("performanceView").hidden = true; }
  }

  // Addresses: #/requests (default) and #/venues. A new collection is one more option and one more view.
  function currentRoute() { var h = (location.hash || "").replace(/^#\/?/, "").replace(/^station\//, ""); return h === "venues" ? "venues" : h === "classes" ? "classes" : h === "requests" ? "requests" : h === "people" ? "people" : h === "places" ? "places" : h === "instructors" ? "instructors" : h === "students" ? "students" : h === "curriculums" ? "curriculums" : h === "organizations" ? "organizations" : h === "attendance" ? "attendance" : h === "messages" ? "messages" : h === "discovery" ? "discovery" : h === "access" ? "access" : h === "activity" ? "activity" : h === "performance" ? "performance" : "home"; }
  var SELF_TITLED = { requests: 1, messages: 1, attendance: 1, access: 1, activity: 1, performance: 1 };   // these draw their own visible h2
  function stationHead(r) {
    var v = $((r === "requests" ? "list" : r) + "View"), sf = surfaceById(r);
    if (!v || !sf || SELF_TITLED[r] || v.querySelector(":scope > .stnh")) return;
    var h = document.createElement("h2"); h.className = "sr stnh"; h.textContent = sf.name; v.insertBefore(h, v.firstChild);
  }
  var lastRoute = null;
  function route() {
    if (!key) return;
    var r = currentRoute();
    if (r !== "home" && !stationAllowed(r)) { location.hash = "#/home"; return; }
    closeManual();
    $("homeView").hidden = r !== "home";
    if (r !== "venues" && window.VenuesStation) window.VenuesStation.stop();
    if (r !== "classes" && window.ClassesStation) window.ClassesStation.stop();
    $("collPick").value = r;
    markPick(); markNav(r); setTopH();
    var sfr = surfaceById(r);
    document.title = (r === "home" ? "Home" : sfr ? (sfr.short || sfr.name) : r) + " \u00b7 " + CFG.brandName + " Console";
    if (lastRoute !== null && lastRoute !== r) $("main").focus({ preventScroll: true });
    lastRoute = r;
    $("listView").hidden = r !== "requests";
    $("venuesView").hidden = r !== "venues";
    $("classesView").hidden = r !== "classes";
    $("peopleView").hidden = r !== "people";
    $("placesView").hidden = r !== "places";
    $("instructorsView").hidden = r !== "instructors";
    $("studentsView").hidden = r !== "students";
    $("curriculumsView").hidden = r !== "curriculums";
    $("organizationsView").hidden = r !== "organizations";
    $("attendanceView").hidden = r !== "attendance";
    $("messagesView").hidden = r !== "messages";
    $("discoveryView").hidden = r !== "discovery";
    if (r === "discovery" && window.DiscoveryStation) window.DiscoveryStation.show();
    $("accessView").hidden = r !== "access";
    if (r === "access" && window.AccessStation) window.AccessStation.show();
    $("activityView").hidden = r !== "activity";
    if (r === "activity" && window.ActivityStation) window.ActivityStation.show();
    $("performanceView").hidden = r !== "performance";
    if (r === "performance" && window.PerformanceStation) window.PerformanceStation.show();
    if (r === "messages" && window.MessagesStation) window.MessagesStation.show();
    if (r === "attendance" && window.AttendanceStation) window.AttendanceStation.show();
    if (r === "home" && window.RequestsStation) window.RequestsStation.loadPlaced();
    if (r === "requests" && window.RequestsStation) window.RequestsStation.show();
    if (r !== "requests") { if (window.RequestsStation) window.RequestsStation.stop(); if (r === "venues" && window.VenuesStation) window.VenuesStation.show(); if (r === "classes" && window.ClassesStation) window.ClassesStation.show(); if (r === "people" && !pLoaded) loadPeople(); if (r === "places" && !lLoaded) loadPlaces(); if (r === "curriculums" && window.CurriculumStation) window.CurriculumStation.show(); if (r === "instructors" && window.InstructorsStation) window.InstructorsStation.show(); if (r === "students" && window.StudentsStation) window.StudentsStation.show(); if (ROSTER[r] && !ROSTER[r].loaded) ROSTER[r].load(); }
    stationHead(r);   // after the stations that redraw their own page (Discovery) have drawn it
  }

  // Returns {status, records} ; status: ok | unauthorized | limited | network | error
  function fetchRecords(since, opt) {
    var url = CFG.endpoints.records + "?limit=" + MAX + (since ? "&since=" + encodeURIComponent(since) : "") + (opt && opt.q ? "&q=" + encodeURIComponent(opt.q) : "") + (opt && opt.region ? "&region=" + encodeURIComponent(opt.region) : "");
    return fetchT(url, { method: "GET", headers: { "Authorization": "Bearer " + key }, cache: "no-store" }, READ_MS)
      .then(function (r) {
        if (r.ok) netOk();
        if (r.status === 401) return { status: "unauthorized" };
        if (r.status === 429) return { status: "limited" };
        if (!r.ok) return { status: "error" };
        return r.json().then(function (j) {
          return { status: "ok", records: (j && j.data && j.data.records) || [], total: j && j.data && j.data.total };
        });
      })
      .catch(function (e) { netShow(!!(e && e.timedOut)); return { status: "network" }; });
  }

  function line(label, value) {
    var d = document.createElement("div");
    var b = document.createElement("b");
    b.textContent = label + ": ";
    d.appendChild(b);
    d.appendChild(document.createTextNode(value));
    return d;
  }
  function str(v) { return (v !== null && typeof v === "object") ? JSON.stringify(v) : String(v); }
  function problem(status) {
    if (status === "unauthorized") return method === "google" ? "Google sign-in did not work. Try again." : "That key did not work.";
    if (status === "forbidden") return "This Google account has not been invited. Ask the owner.";
    if (status === "limited") return "Too many tries. Wait a few minutes.";
    if (status === "network") return "Could not reach the server.";
    return "Something went wrong. Try again.";
  }

  function lock(message) {
    launchStop();
    if (method === "google") {
      if (message === "That key did not work.") message = "Your Google sign-in ended. Sign in again.";
      method = "key"; try { if (auth) auth.signOut(); } catch (e) {}
    }
    ME = null; $("who").hidden = true; viewOnlyMode(false); idleEnd();
    setKey("", false); key = ""; if (window.RequestsStation) window.RequestsStation.reset(); if (window.VenuesStation) window.VenuesStation.reset(); if (window.ClassesStation) window.ClassesStation.reset(); if (window.CurriculumStation) window.CurriculumStation.reset(); if (window.InstructorsStation) window.InstructorsStation.reset(); if (window.StudentsStation) window.StudentsStation.reset(); resetPlaced(); resetPeople(); resetPlaces(); resetRosters(); if (window.ConsoleNames) window.ConsoleNames.reset(); if (window.AttendanceStation) window.AttendanceStation.reset(); if (window.DiscoveryStation) window.DiscoveryStation.reset(); if (window.AccessStation) window.AccessStation.reset(); if (window.ActivityStation) window.ActivityStation.reset(); if (window.PerformanceStation) window.PerformanceStation.reset(); if (window.MessagesStation) window.MessagesStation.reset();
    $("keyInput").value = ""; $("keyInput").type = "password"; $("keyShow").textContent = "Show"; $("keyShow").setAttribute("aria-pressed", "false");
    $("lockMsg").textContent = message || "";
    show(true);
  }

  // The first call after a key or sign-in: who is this, and may they in? The key proves itself by reading the registration records
  // (as it always did). A Google sign-in asks the server's `me` op; the records are read only if the role may see requests.
  function accessProbe() {
    if (method !== "google") return fetchRecords("").then(function (r) {
      if (r.status !== "ok") return r;
      ME = keyMe();
      // A temporary review code is typed into the same Key box but is view only: ask the server who this really is (anything else stays the admin key).
      return adminCall("me", {}, "access_persons").then(function (m) {
        if (m && m.status === 200 && m.body && m.body.ok && m.body.data && m.body.data.method === "code") ME = m.body.data;
        return r;
      }, function () { return r; });
    });
    return adminCall("me", {}, "access_persons").then(function (r) {
      if (r.status !== 200 || !r.body || !r.body.ok) return { status: r.status === 401 ? "unauthorized" : r.status === 403 ? "forbidden" : r.status === 429 ? "limited" : r.status === 0 ? "network" : "error" };
      ME = r.body.data; launchStage(3); if (timing) timing.tMe = tnow();
      return canPlaced() ? fetchRecords("") : { status: "ok", records: [] };
    });
  }

  // ---- The launch screen: instant feedback while a sign-in is in progress (a spinning tile, a line that follows the real stages, a spinning tab icon).
  // It hides the sign-in buttons so nobody presses twice; a failure or a lock brings the form back.
  var launching = false, launchN = 0, launchTimers = [], launchSaved = null, spinTimer = null, iconKeep = null;
  var LAUNCH_LINES = ["Boarding pass accepted…", "Mission control is checking your clearance…", "Fueling the stations…"];
  var LAUNCH_SLOW = "Still on the launch pad. Slow link or cold engines. Hang tight.";
  function launchStage(n) { if (!launching || n <= launchN) return; launchN = n; $("launchLine").textContent = LAUNCH_LINES[n - 1]; }
  function spinIcons(on) {
    if (!on) {
      if (spinTimer) { clearInterval(spinTimer); spinTimer = null; }
      if (iconKeep) { iconKeep.forEach(function (k) { k.el.setAttribute("href", k.href); }); iconKeep = null; }
      return;
    }
    if (spinTimer || iconKeep) return;
    try { if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return; } catch (e) {}
    var links = document.querySelectorAll('link[rel="icon"]'); if (!links.length) return;
    var img = new Image();
    img.onload = function () {
      if (!launching || spinTimer || iconKeep) return;
      iconKeep = [].map.call(links, function (el) { return { el: el, href: el.getAttribute("href") }; });
      var c = document.createElement("canvas"); c.width = 32; c.height = 32; var x = c.getContext("2d"), a = 0;
      spinTimer = setInterval(function () {
        a += Math.PI / 6; x.clearRect(0, 0, 32, 32); x.save(); x.translate(16, 16); x.rotate(a); x.drawImage(img, -11, -11, 22, 22); x.restore();
        try { var u = c.toDataURL("image/png"); iconKeep.forEach(function (k) { k.el.setAttribute("href", u); }); } catch (e) { spinIcons(false); }
      }, 100);
    };
    img.src = "assets/console-favicon-32.png";
  }
  function launchStart() {
    if (launching) return;
    launching = true; launchN = 0;
    launchSaved = { g: $("googleBox").hidden, k: $("keyBox").hidden, s: $("swapLink").hidden };
    $("googleBox").hidden = true; $("keyBox").hidden = true; $("swapLink").hidden = true; $("lockMsg").textContent = "";
    $("launching").hidden = false; launchStage(1); spinIcons(true);
    launchTimers.push(setTimeout(function () { launchStage(2); }, 700));
    launchTimers.push(setTimeout(function () { if (launching) { launchN = 9; $("launchLine").textContent = LAUNCH_SLOW; } }, 8000));
  }
  function launchStop() {
    launchTimers.forEach(clearTimeout); launchTimers = []; spinIcons(false);
    if (!launching) return;
    launching = false; $("launching").hidden = true;
    if (launchSaved) { $("googleBox").hidden = launchSaved.g; $("keyBox").hidden = launchSaved.k; $("swapLink").hidden = launchSaved.s; launchSaved = null; }
  }
  function launchDone() {   // a short "Liftoff!" before the Console opens, only when the launch screen was showing
    return new Promise(function (ok) {
      if (!launching) { ok(); return; }
      launchTimers.forEach(clearTimeout); launchTimers = []; $("launchLine").textContent = "Liftoff!";
      setTimeout(function () { launchStop(); ok(); }, 350);
    });
  }

  // The Performance log: after a sign-in, send how long each step took (numbers only; the server stamps who). Never for a view-only account; a failure is ignored.
  function sendTiming(tm) {
    if (!tm || !tm.tReady || !ME || ME.inspector) return;
    var ms = function (n) { return Math.max(0, Math.min(600000, Math.round(n))); }, a = { kind: "sign_in", device: window.innerWidth < 700 ? "phone" : "desktop", method: tm.method,
      total_ms: ms(tm.tReady - tm.t0), check_ms: ms(tm.tMe - tm.t0), load_ms: ms(tm.tRecords - tm.tMe) };
    if (tm.method === "google" && typeof ME.server_ms === "number") a.server_ms = ms(ME.server_ms);
    if (tm.method === "google" && typeof ME.cold === "boolean") a.cold = ME.cold;
    try { adminCall("record_timing", a, "performance_events").catch(function () {}); } catch (e) {}
  }

  function unlock(k, remember) {
    var mine = ++unlockSeq;
    timing = { t0: tnow(), method: method === "google" ? "google" : "key" };
    launchStart();
    idleTouch();                                       // a sign-in starts a fresh clock: after a timeout the old "last active" time must not sign this person straight out again
    key = k; if (window.RequestsStation) window.RequestsStation.clearList();
    $("lockMsg").textContent = "";
    $("unlockBtn").disabled = true;
    return accessProbe().then(function (res) {
      $("unlockBtn").disabled = false;
      if (mine !== unlockSeq || !key) return;          // the page was locked, or signed in again, while this was in flight: this answer is out of date
      if (timing) { timing.tRecords = tnow(); if (!timing.tMe) timing.tMe = timing.tRecords; }
      if (res.status !== "ok") {
        key = ""; launchStop();
        $("lockMsg").textContent = "Launch aborted: " + problem(res.status);
        if (method === "google") { method = "key"; try { if (auth) auth.signOut(); } catch (e) {} }
        ME = null;
        show(true);
        return;
      }
      if (method !== "google") setKey(k, remember);
      idleStaleAtLoad = false; idleStart();
      var tm = timing; timing = null; if (tm) tm.tReady = tnow();
      return launchDone().then(function () {
        if (mine !== unlockSeq || !key) return;
        show(false);
        applyAccess();
        if (window.RequestsStation) window.RequestsStation.adopt(res.records);
        route();
        sendTiming(tm);
      });
    });
  }

  // ---- Venues view: list and add, through the admin endpoint (the CRUD handler file does the checking).
  var ADMIN_URL = CFG.endpoints.admin;
  var CF = window.ConsoleForms, LABELS = CF.labels, humanize = CF.humanize, readValue = CF.readValue, buildField = CF.buildField;
  var ISSUE = window.ConsoleForms.issue, wholeNum = window.ConsoleForms.wholeNum, slugify = window.ConsoleForms.slugify, skelOn = UI.skelOn, skelOff = UI.skelOff;   // shared pieces (forms.js, ui.js)

  // Anything that changes data shows a working indicator on the button that was pressed (which then cannot be pressed twice) and a
  // toast at the bottom: "Working…", then "Done" or "Did not go through". Reading (list, get, lookups) stays silent.
  var READ_OPS = { list: 1, get: 1, find_gps: 1 }, lastBtn = null, lastBtnAt = 0, workN = 0, toastTimer = null;
  document.addEventListener("click", function (e) { var b = e.target && e.target.closest && e.target.closest("button"); if (b) { lastBtn = b; lastBtnAt = Date.now(); } }, true);
  function toast(kind, text, ms) {
    var el = document.getElementById("workToast"); if (!el) return;
    clearTimeout(toastTimer); el.className = (kind ? kind + " " : "") + "on"; document.getElementById("workText").textContent = text;
    if (ms) toastTimer = setTimeout(function () { el.className = el.className.replace(/\bon\b/, "").trim(); }, ms);
  }
  var VIEW_READS = { list: 1, get: 1, find_by_address: 1, get_for_individual: 1, suggest: 1, queue: 1 };
  function viewOnlyRefusal() { return { status: 403, body: { ok: false, error: { code: "view_only", message: "View only: this account can look at everything and change nothing." } } }; }
  function admin(op, args, coll) {
    if (ME && ME.inspector && !VIEW_READS[op]) { toast("bad", "View only: nothing was changed.", 3500); return Promise.resolve(viewOnlyRefusal()); }   // the server would refuse it too
    if (READ_OPS[op]) return adminCall(op, args, coll);
    var btn = lastBtn && Date.now() - lastBtnAt < 4000 ? lastBtn : null;
    if (btn) { btn.classList.add("working"); btn.setAttribute("aria-busy", "true"); }
    workN++; toast("", "Working… this can take a few seconds when emails are sent.", 0);
    return adminCall(op, args, coll).then(function (res) {
      workN--; if (btn) { btn.classList.remove("working"); btn.removeAttribute("aria-busy"); }
      if (!workN) { var ok = res.status === 200 && res.body && res.body.ok; if (ok) toast("ok", "Done", 1800); else if (res.status === 401) toast("", "", 1); else toast("bad", "That did not go through. See the message above.", 3500); }
      return res;
    });
  }
  // ---- Time limits and the connection banner (1.3b). A read that gets no answer shows a banner with Try again; a write that gets no answer says it may have gone through.
  var TMO = CFG.timeouts || {}, READ_MS = (TMO.readSeconds || 20) * 1000, WRITE_MS = (TMO.writeSeconds || 60) * 1000, netWhy = "";
  function fetchT(url, opts, ms) {
    var ctl = typeof AbortController === "function" ? new AbortController() : null, t = null;
    if (ctl) { opts.signal = ctl.signal; t = setTimeout(function () { ctl.abort(); }, ms); }
    return fetch(url, opts).then(function (r) { clearTimeout(t); return r; }, function (e) { clearTimeout(t); e.timedOut = !!(ctl && ctl.signal.aborted); throw e; });
  }
  function netShow(timedOut) {
    $("netText").textContent = (timedOut ? "The server did not answer in time." : "Could not reach the server.") + " What is on screen may be out of date.";
    $("netBanner").hidden = false;
  }
  function netOk() { $("netBanner").hidden = true; }
  function netRetry() {   // load the current station again, from scratch
    netOk(); if (window.VenuesStation) window.VenuesStation.forget(); if (window.ClassesStation) window.ClassesStation.forget(); if (window.CurriculumStation) window.CurriculumStation.forget(); if (window.InstructorsStation) window.InstructorsStation.forget(); if (window.StudentsStation) window.StudentsStation.forget(); pLoaded = false; lLoaded = false;
    Object.keys(ROSTER).forEach(function (k) { ROSTER[k].loaded = false; });
    route();
  }
  function adminCall(op, args, coll) {
    var isRead = !!VIEW_READS[op];
    return fetchT(ADMIN_URL, { method: "POST", cache: "no-store",
        headers: { "Authorization": "Bearer " + key, "Content-Type": "application/json" },
        body: JSON.stringify({ collection: coll || "venues", op: op, args: args }) }, isRead ? READ_MS : WRITE_MS)
      .then(function (r) {
        if (isRead && r.ok) netOk();
        return r.json().catch(function () { return {}; }).then(function (j) { return { status: r.status, body: j }; });
      })
      .catch(function (e) {
        var to = !!(e && e.timedOut);
        netWhy = to ? (isRead ? "read-timeout" : "write-timeout") : "down";
        if (isRead) netShow(to);
        return { status: 0, body: {}, timedOut: to };
      });
  }
  function adminProblem(status) {
    if (status === 429) return "Too many tries. Wait a few minutes.";
    if (status === 0) return netWhy === "write-timeout" ? "No answer after " + (WRITE_MS / 1000) + " seconds. It may still have gone through: check the list before trying again." : netWhy === "read-timeout" ? "The server did not answer in time." : "Could not reach the server.";
    return "Something went wrong. Try again.";
  }

  // A one-tap status switch on a card. Taps are collected: 1.5 seconds after the LAST tap the server is asked once, and only if the
  // final choice differs from what is saved (two taps cancel out). opts: coll (admin collection or undefined), on, off (status words), problem(res).
  var TOGGLE_WAIT = 1500;
  function statusToggle(rec, li, opts) {
    var b = mk("button", "stoggle"); b.type = "button"; b.setAttribute("role", "switch");
    var knob = mk("span", "knob"), word = mk("span", "");
    b.appendChild(knob); b.appendChild(word);
    var want = rec.status === opts.on, timer = null, busy = false;
    var msg = mk("div", "stmsg"); msg.setAttribute("role", "alert");
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
      (opts.coll ? admin("update", args, opts.coll) : admin("update", args)).then(function (res) {
        busy = false; b.disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          rec.status = want ? opts.on : opts.off;
          var u = res.body.data && res.body.data.updated_at; if (u) rec.updated_at = u;
          draw(); return;
        }
        want = rec.status === opts.on; draw();
        msg.textContent = res.status === 409 ? "This changed somewhere else. Tap Refresh, then try again." : res.status === 400 ? opts.problem(res) : adminProblem(res.status);
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

  function mk(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  // The History button on a card: opens the Activity station on this one record. Only a super admin gets it (the server decides; this is courtesy).
  function historyBtn(id, label) {
    if (!id || !ME || (ME.is_super_admin !== true && ME.inspector !== true)) return null;
    var b = mk("button", "quiet", "Change history"); b.type = "button"; b.setAttribute("data-history", id); b.setAttribute("data-viewok", "1");
    b.addEventListener("click", function (ev) { ev.stopPropagation(); if (window.ActivityStation) window.ActivityStation.openFor(id, label || ""); });
    return b;
  }
  // What a station that lives in its own file (console/discovery.js) may use from this page. Nothing here exposes the key except to that file's own calls.
  window.ConsoleKit = { mk: mk, admin: admin, toast: toast, lock: lock, key: function () { return key; }, can: can, me: function () { return ME; }, when: when, clock: function (d) { return fmtClock.format(d); },
                        go: function (id) { goTo(id); }, sessionMinutes: function (n) { if (n === undefined) return idleMinutes; idleMinutes = idleClamp(n); idleSet(IDLE_MIN, idleMinutes); return idleMinutes; }, lastButton: function () { return lastBtn && Date.now() - lastBtnAt < 4000 ? lastBtn : null; },
                        // Added for station files (M-1, the Messages extraction). Functions, not values, because the things they read are filled in later or replaced.
                        adminProblem: function (status) { return adminProblem(status); },
                        time: function (d) { return fmtTime.format(d); },
                        attName: function (r) { return attName(r); },
                        classChoices: function () { return window.ClassesStation.choices(); },
                        classById: function (id) { return window.ClassesStation ? window.ClassesStation.byId(id) : undefined; },
                        openAttendance: function (cls, host) { openAttendance(cls, host); },
                        requests: function () { var have = window.RequestsStation ? window.RequestsStation.records() : []; return have.length ? Promise.resolve(have) : fetchRecords("").then(function (r) { return r.status === "ok" ? r.records : []; }); },
                        words: function () { return { corrKind: CORR_KIND, reasonWord: REASON_WORD, attWord: ATT_WORD, roleWord: ROLE_WORD }; }, historyBtn: function (id, label) { return historyBtn(id, label); }, fetchT: function (url, opts, ms) { return fetchT(url, opts, ms); }, netShow: function (t) { netShow(t); }, canPlaced: function () { return canPlaced(); }, fetchRecords: function (since, opt) { return fetchRecords(since, opt); }, putInClass: function (rec, host, said) { window.ClassesStation.putInClass(rec, host, said); }, line: function (l, v) { return line(l, v); }, str: function (v) { return str(v); }, problem: function (st) { return problem(st); }, consts: function () { return { MAX: MAX, READ_MS: READ_MS, ATT_RANK: ATT_RANK, ATT_GONE: ATT_GONE, RECORDS_URL: CFG.endpoints.records }; }, attConsts: function () { return { ATT: ATT, ATT_STATUSES: ATT_STATUSES, ATT_WORD: ATT_WORD, ROLE_WORD: ROLE_WORD, ATT_TONE: ATT_TONE, ATT_OPEN: ATT_OPEN, ATT_OFF: ATT_OFF, CORR_KIND: CORR_KIND, REASON_WORD: REASON_WORD, leftOpen: leftOpen }; }, attFail: function (res) { return attFail(res); }, classWhen: function (c) { return window.ClassesStation.classWhen(c); }, refreshPlaced: function () { return refreshPlaced(); }, assignForm: function (opts) { return window.ClassesStation.assignForm(opts); },
                        // Added for the Classes station (C-2): openWorkflows, attLine (straight to the Attendance station), afNext (the shared id counter), forgetPeople.
                        openWorkflows: function () { return openWorkflows.apply(null, arguments); }, attLine: function (r, withClass) { return window.AttendanceStation.attLine(r, withClass); }, afNext: function () { return ++afSeq; }, forgetPeople: function () { peopleForPick = null; },
                        // Added for the Venues station (V-4). Functions that point at the places, people and shared helpers still in this file.
                        lProblems: function () { return lProblems.apply(null, arguments); }, placeInput: function () { return placeInput.apply(null, arguments); }, placeText: function () { return placeText.apply(null, arguments); },
                        forgetSavedPlaces: function () { savedPlaces = null; }, peopleList: function () { return peopleList.apply(null, arguments); }, peopleMatches: function () { return peopleMatches.apply(null, arguments); },
                        pFull: function () { return pFull.apply(null, arguments); }, statusToggle: function () { return statusToggle.apply(null, arguments); }, askDiscard: function () { return askDiscard.apply(null, arguments); },
                        // Added for the Instructors and Students stations (RO-2): the address form, the People problem words, the Places refresh, the collection names, and People's stale flags.
                        addrForm: function () { return addrForm.apply(null, arguments); }, pProblems: function () { return pProblems.apply(null, arguments); }, refreshPlaces: function () { refreshPlaces(); },
                        colls: function () { return { P: COLL_P, L: COLL_L, LK: COLL_LK }; }, peopleStale: function () { pLoaded = false; peopleForPick = null; } };   // R-2 (Journal): attWord, roleWord, historyBtn. R-3 (Requests): fetchT to consts. consts holds constants only. A-1 (Attendance): attConsts to assignForm.
  $("lockForm").addEventListener("submit", function (e) {
    e.preventDefault(); if (launching) return;
    var k = $("keyInput").value.trim();
    if (!k) { $("lockMsg").textContent = "That key did not work."; return; }
    unlock(k, $("rememberBox").checked);
  });
  $("keyShow").addEventListener("click", function () {      // see what you typed or pasted; starts hidden again after every lock
    var i = $("keyInput"), reveal = i.type === "password";
    i.type = reveal ? "text" : "password"; this.textContent = reveal ? "Hide" : "Show"; this.setAttribute("aria-pressed", reveal ? "true" : "false"); i.focus();
  });
  $("lockBtn").addEventListener("click", function () { lock(""); });
  $("refreshBtn").addEventListener("click", function () { if (window.RequestsStation) { window.RequestsStation.check(true); window.RequestsStation.loadPlaced(); } });
  document.addEventListener("visibilitychange", function () { if (!document.hidden && key && currentRoute() === "requests" && window.RequestsStation) window.RequestsStation.check(false); });
  window.addEventListener("hashchange", route);
  $("netRetry").addEventListener("click", netRetry);
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a.skip"); if (!a) return;
    e.preventDefault(); $("main").focus();
  });
  function markPick() { var o = $("collPick").selectedOptions[0]; $("collPick").classList.toggle("adm", !!(o && o.className === "adminstn")); }
  $("collPick").addEventListener("change", function () { markPick(); goTo($("collPick").value); });
  $("brand").addEventListener("click", function (e) { e.preventDefault(); goTo("home"); });
  $("sideNav").addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("a[data-nav]") : null;
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;   // modified clicks keep their normal meaning (new tab)
    e.preventDefault(); goTo(a.dataset.nav);
  });
  window.addEventListener("resize", setTopH);
  document.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target.closest("[data-go],[data-m]") : null;
    if (!t) return;
    if (t.dataset.go) { goTo(t.dataset.go); return; }
    if (t.dataset.m) openManual(t.dataset.m, t);
  });
  $("manualClose").addEventListener("click", closeManual);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && mOpen && !document.querySelector("dialog[open]")) closeManual(); });
  window.addEventListener("resize", function () { if (mOpen) $("manual").style.setProperty("--hh", $("topbar").offsetHeight + "px"); });
  buildHome();


  function refreshPlaced() { return window.RequestsStation ? window.RequestsStation.loadPlaced() : Promise.resolve(); }   // Classes and Attendance call this after they place or remove someone


  // ================= Attendance: who is in which class =================
  var ATT = "attendances";
  var ROLE_WORD = { student: "Student", primary_instructor: "Lead instructor", instructor: "Instructor" };
  var ATT_STATUSES = ["assigned", "waitlisted", "confirmed", "attended", "late", "no_show", "declined", "withdrawn", "cancelled"];
  var ATT_WORD = { assigned: "Assigned", confirmed: "Confirmed", waitlisted: "On the waiting list", declined: "Declined", withdrawn: "Withdrawn", cancelled: "Cancelled", attended: "Attended", late: "Late", no_show: "Did not show" };
  var ATT_RANK = { assigned: 1, waitlisted: 1, confirmed: 2, attended: 3, late: 3, no_show: 3 };   // how far a placement has come: placed, confirmed, then the class happened
  var ATT_GONE = { declined: 1, withdrawn: 1, cancelled: 1 };   // a request with only these is back to waiting
  var ATT_OPEN = { assigned: 1, waitlisted: 1, confirmed: 1 };   // a placement still open: ending it sends emails
  function leftOpen(from, to) { return !!ATT_OPEN[from] && !!ATT_GONE[to]; }
  var ATT_OFF = { waitlisted: 1, declined: 1, withdrawn: 1, cancelled: 1 };   // statuses that do not hold a seat
  var afSeq = 0;

  function attFail(res) {
    var ps = (res.body && res.body.error && res.body.error.problems) || [];
    if (res.status === 409 && !ps.length) return "Someone changed this a moment ago. Close this window and open it again.";
    if (!ps.length) return adminProblem(res.status);
    return ps.map(function (p) {
      if (p.issue === "duplicate") return "They are already in this class in that role.";
      if (p.issue === "choose_one") return "Choose someone we know or add someone new, not both.";
      if (/^person\./.test(p.field)) return (PLABEL[p.field.slice(7)] || p.field) + ": " + (p.issue === "invalid_format" && /email$/.test(p.field) ? "That email address does not look right." : (PISSUE[p.issue] || "That value is not valid."));
      if (p.field === "scheduled_class_id") return "Choose a class.";
      if (p.field === "role") return "Choose a role.";
      if (p.field === "individual_id" && p.issue === "address_required") return "An instructor needs an address first. Add the person in the Instructors station with their address, then add them here.";
      if (p.field === "individual_id") return p.issue === "required" ? "Choose someone." : "We could not find them.";
      if (p.field === "order") return "Place has to be a whole number from 1 to 50.";
      return p.field + ": " + (PISSUE[p.issue] || p.issue);
    }).join(" ");
  }
  // The card's tone, chip words and "Next" line, by status (the cue rules in console/DESIGN-RULES.md)
  var ATT_TONE = {
    assigned: { tone: "wait", next: "Next: wait for them to confirm." },
    waitlisted: { tone: "wait", next: "Next: they stay waiting until a seat opens." },
    confirmed: { tone: "ok", next: "Next: take attendance on class day." },
    attended: { tone: "ok", next: "Done: they came to class." },
    late: { tone: "ok", next: "Done: they came late." },
    no_show: { tone: "done", next: "Closed: they did not show." },
    declined: { tone: "done", next: "Closed: they declined." },
    withdrawn: { tone: "done", next: "Closed: they withdrew." },
    cancelled: { tone: "done", next: "Closed: this was cancelled." }
  };
  function attName(r) { return (r.person && r.person.display_name) || "(person not found)"; }

  // People that fit what was typed. Every word must appear somewhere in the name, email or phone (any order), so "Todd Beecher" finds a Todd Beecher.
  // If nobody fits every word, people who fit ANY word are offered as "close" matches, so a record with only a first name is not missed and then duplicated.
  function peopleMatches(list, q) {
    var words = q.toLowerCase().split(/\s+/).filter(Boolean), live = list.filter(function (p) { return p.status !== "erased"; });
    var text = function (p) { return [pName(p), p.given_name, p.name_to_use, p.family_name, p.email, p.phone].join(" ").toLowerCase(); };
    var all = live.filter(function (p) { var t = text(p); return words.every(function (w) { return t.indexOf(w) >= 0; }); });
    if (all.length || words.length < 2) return { exact: all, near: [] };
    var any = live.filter(function (p) { var t = text(p); return words.some(function (w) { return w.length >= 2 && t.indexOf(w) >= 0; }); });
    return { exact: [], near: any };
  }


  // Attendance lives in attendance.js. These forwarders keep the callers that are still here (Classes, People, Put in a class) unchanged; they go when the placing machinery moves (DT-18).
  function openAttendance(cls, host) { if (window.AttendanceStation) window.AttendanceStation.openAttendance(cls, host); }
  function personHistory(rec, host) { if (window.AttendanceStation) window.AttendanceStation.personHistory(rec, host); }
  var CORR_KIND = { placement_confirmation: "Placement confirmation", request_received: "Request received" };
  var REASON_WORD = { no_contact: "no email or phone on file", channel_unavailable: "they prefer a text, so contact them by hand", no_template: "no message is set up for this",
                      incomplete: "a detail the message needs is missing", invalid_context: "the details were not valid", unknown_kind: "unknown kind of message",
                      time_budget: "ran out of time", internal_error: "a problem on our side", cms_off: "messaging is off", log_only: "test mode, nothing is really sent",
                      duplicate: "already sent", excluded: "left out on purpose", muted: "they asked not to be contacted" };


  // ---- Workflows: step cards with a jump button to the right station
  var WORKFLOWS = [
    { id: "setup", title: "Set up before your first request", steps: [
      { t: "Add a venue and make it active (a place with an address).", go: "venues", b: "Open Venues" },
      { t: "Add a curriculum: what will be taught.", go: "curriculums", b: "Open Curriculum" },
      { t: "Add the instructor to the Instructors list.", go: "instructors", b: "Open Instructors" },
      { t: "Then wait for a request, or register on the website yourself.", go: "requests", b: "Open Requests" } ] },
    { id: "place_existing", title: "Place a request in an existing class", steps: [
      { t: "Open the request and tap Put in a class…", go: "requests", b: "Open Requests" },
      { t: "Choose the class and the role, then Add to class. The request leaves Waiting to be placed.", go: "requests", b: "Open Requests" },
      { t: "Check the result: Attendance on the class card shows the person and their status.", go: "classes", b: "Open Classes" } ] },
    { id: "build_class", title: "Build a class for a request", steps: [
      { t: "Make sure the venue (active) and curriculum exist, and the instructor is on the Instructors list.", go: "venues", b: "Open Venues" },
      { t: "On the request, tap Put in a class… and choose + A new class (build it now).", go: "requests", b: "Open Requests" },
      { t: "Pick the curriculum, venue, date and time, and the lead instructor, then build. The requester is placed in it.", go: "requests", b: "Open Requests" },
      { t: "Open the class to confirm the details; change the status to confirmed when the person agrees.", go: "classes", b: "Open Classes" } ] },
    { id: "class_cancelled", title: "When a class is cancelled", steps: [
      { t: "Open the class, Edit, set its status to cancelled and add the reason.", go: "classes", b: "Open Classes" },
      { t: "Everyone in it, students and instructors, is cancelled automatically and each request returns to Waiting to be placed.", go: "requests", b: "Open Requests" },
      { t: "Read the Journal on the class or the request to see exactly what changed, then place the request again.", go: "requests", b: "Open Requests" } ] }
  ];
  function wfCard(wf, host, open) {
    var det = mk("details", "wfcard"); det.dataset.wf = wf.id; if (open) det.open = true;
    det.appendChild(mk("summary", "", wf.title));
    var ol = mk("ol");
    wf.steps.forEach(function (st) {
      var li = mk("li", "", st.t);
      var b = mk("button", "quiet wfgo", st.b); b.type = "button";
      b.addEventListener("click", function () { goTo(st.go); });
      li.appendChild(b); ol.appendChild(li);
    });
    det.appendChild(ol); host.appendChild(det);
  }
  function openWorkflows(ids) {   // ids[0] (if given) opens expanded; every workflow is listed
    var body = $("wfBody"); body.textContent = "";
    var hint = mk("p", "mhint", "Step by step, with a button that jumps to the right station."); body.appendChild(hint);
    WORKFLOWS.forEach(function (wf) { wfCard(wf, body, !!(ids && ids[0] === wf.id)); });
    mScroll[WF_TAB] = 0; var was = mOpen === WF_TAB; if (was) body.scrollTop = 0;
    openHelp("workflows", document.activeElement, false);
    var first = body.querySelector("details[open] summary") || body.querySelector("summary"); if (first) { try { first.focus(); } catch (e) {} }
  }
  $("helpOpen").addEventListener("click", function () { if (mOpen) closeManual(); else openHelp("manuals", $("helpOpen")); });
  $("hTabM").addEventListener("click", function () { openHelp("manuals", null, true); });
  $("hTabW").addEventListener("click", function () { if (mOpen !== WF_TAB) openWorkflows(null); });
  $("helpHomeM").addEventListener("click", function () { openHelp("manuals", $("helpHomeM")); });
  $("helpHomeW").addEventListener("click", function () { openWorkflows(null); });
  $("hTabM").parentNode.addEventListener("keydown", function (e) {   // arrow keys move between the two tabs
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault(); var toW = mOpen !== WF_TAB; if (toW) { openWorkflows(null); $("hTabW").focus(); } else { openHelp("manuals", null, true); $("hTabM").focus(); }
  });
  $("reqInfo").addEventListener("click", function () { openWorkflows(["place_existing", "build_class", "class_cancelled", "setup"]); });

  function resetPlaced() {
    try { $("atDlg").close(); } catch (e) {} try { $("jrDlg").close(); $("wfDlg").close(); } catch (e) {}
    $("attnBody").textContent = "Checking the requests…"; $("attnBadge").hidden = true; $("attnBox").className = "attn";
  }
  $("atClose").addEventListener("click", function () { $("atDlg").close(); });

  // ---- People station: the individuals, through the same admin door. Restricted details are not reachable from here (the server refuses them).
  var COLL_P = "individuals", COLL_MERGE = "merge_events";
  var pAll = [], pLoaded = false, pSeq = 0, pNewId = "";
  var PLABEL = { given_name: "Given name", middle_names: "Middle names", family_name: "Family name", name_to_use: "Name to use", pronouns: "Pronouns",
                 birth_date: "Birth date", birth_date_certainty: "Birth date certainty", preferred_language: "Preferred language", time_zone: "Time zone",
                 requires_interpreter: "Interpreter", email: "Email", phone: "Phone", backup_email: "Backup email", backup_phone: "Backup phone", prefers_email: "Preferred way to reach", status: "Status", notes: "Notes", survivor_id: "Person to keep", duplicate_id: "This person", reason: "Reason", id: "Person" };
  var PISSUE = { required: "Required.", invalid_format: "That value is not valid.", out_of_range: "Too long or too short.", invalid_value: "That value is not valid.",
                 invalid_type: "That value is not valid.", not_found: "That person was not found.", same_as_survivor: "Pick a different person.",
                 conflict_restricted_detail: "Both people hold protected details. That needs a person to sort out first.",
                 too_many_links: "Too many records point at this person to merge in one go.", snapshots_erased: "One of the people has been erased, so this cannot be undone.",
                 not_merged: "This merge was already undone.", already_erased: "Already erased.", in_use: "Protected details exist for this person.", immutable: "That cannot be changed.",
                 inconsistent: "That does not fit with the other answers." };
  var PADD_ERR = { given_name: "epaGiven", family_name: "epaFamily", name_to_use: "epaUse", birth_date: "epaBirth", email: "epaEmail", phone: "epaPhone" };
  var P_FIELDS = [
    { k: "given_name", label: "Given name", t: "text" }, { k: "middle_names", label: "Middle names", t: "text" },
    { k: "family_name", label: "Family name", t: "text" }, { k: "name_to_use", label: "Name to use", t: "text", hint: "What the person asks to be called. It shows instead of the given name." },
    { k: "pronouns", label: "Pronouns", t: "text", hint: "As the person says them, for example she/her." },
    { k: "birth_date", label: "Birth date", t: "text", hint: "Month first: 04-17-1961, 04-1961 or just 1961. A year alone is fine." },
    { k: "birth_date_certainty", label: "How sure is the birth date?", t: "select", opts: [["", "Not stated (treated as exact)"], ["exact", "Exact"], ["approximate", "Approximate"], ["estimated", "Estimated"]] },
    { k: "preferred_language", label: "Preferred language", t: "text", hint: "A language tag such as en or es-MX." },
    { k: "time_zone", label: "Time zone", t: "text", hint: "For example America/Denver." },
    { k: "requires_interpreter", label: "Needs an interpreter?", t: "bool" },
    { k: "email", label: "Email", t: "text", hint: "The email address they asked us to use. Couples may share one." },
    { k: "phone", label: "Phone (text messages)", t: "text", hint: "We send text messages only and never call." },
    { k: "backup_email", label: "Backup email", t: "text", hint: "Used when the first one is missing or fails." },
    { k: "backup_phone", label: "Backup phone", t: "text", hint: "Used when the first one is missing or fails." },
    { k: "prefers_email", label: "How do they want to hear from us?", t: "prefer", opts: [["", "Not said (the one they gave, or email if both)"], ["email", "Email"], ["text", "Text message"]] },
    { k: "status", label: "Status", t: "select", opts: [["active", "Active"], ["inactive", "Inactive (kept, not offered in pickers)"]] },
    { k: "notes", label: "Notes", t: "area", hint: "Visible to operators only." }
  ];
  // Dates: people type and read them the American way, month first (04-17-1961, 04-1961 or just 1961). The record stores YYYY, YYYY-MM or YYYY-MM-DD.
  var MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var DATE_HELP = "Use 1961, 04-1961 or 04-17-1961 (month first).";
  function pDateIn(s) {   // text typed by a person -> {iso} or {bad:true}; blank -> {iso:""}
    var t = String(s || "").trim().replace(/[\/.\s]+/g, "-"), m;
    if (t === "") return { iso: "" };
    if (/^\d{4}$/.test(t)) return { iso: t };
    if ((m = /^(\d{4})-(\d{2})(?:-(\d{2}))?$/.exec(t))) return pDateParts(m[1], m[2], m[3]);   // already stored style
    if ((m = /^(\d{1,2})-(\d{4})$/.exec(t))) return pDateParts(m[2], m[1]);
    if ((m = /^(\d{1,2})-(\d{1,2})-(\d{4})$/.exec(t))) return pDateParts(m[3], m[1], m[2]);
    return { bad: true };
  }
  function pDateParts(y, mo, d) {
    var M = parseInt(mo, 10), D = d === undefined ? 0 : parseInt(d, 10), Y = parseInt(y, 10);
    if (M < 1 || M > 12 || Y < 1) return { bad: true };
    if (D) { var dt = new Date(Date.UTC(Y, M - 1, D)); if (dt.getUTCFullYear() !== Y || dt.getUTCMonth() !== M - 1 || dt.getUTCDate() !== D) return { bad: true }; }
    var z = function (n) { return (n < 10 ? "0" : "") + n; };
    return { iso: y + "-" + z(M) + (D ? "-" + z(D) : "") };
  }
  function pDateOut(iso) {   // stored value -> "Apr 17, 1961", "Apr 1961" or "1961"
    var m = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$/.exec(String(iso || ""));
    if (!m) return String(iso || "");
    return (m[2] ? MON[parseInt(m[2], 10) - 1] + " " : "") + (m[3] ? parseInt(m[3], 10) + ", " : "") + m[1];
  }
  function pDateField(iso) {   // stored value -> what the box shows: 04-17-1961, 04-1961 or 1961
    var m = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$/.exec(String(iso || ""));
    if (!m) return String(iso || "");
    return m[3] ? m[2] + "-" + m[3] + "-" + m[1] : m[2] ? m[2] + "-" + m[1] : m[1];
  }
  function pName(rec) { return rec.display_name || rec.given_name || "(no name)"; }
  // The whole name for pickers: the display name, plus the family name when the display name leaves it out.
  function pFull(rec) {
    var d = pName(rec), fam = rec.family_name;
    if (fam && d.toLowerCase().indexOf(fam.toLowerCase()) < 0) return (rec.name_to_use || rec.given_name || d) + " " + fam;
    return d;
  }
  function pById(id) { for (var i = 0; i < pAll.length; i++) if (pAll[i].id === id) return pAll[i]; return null; }
  function pProblems(res, map) {
    var ps = (res.body && res.body.error && res.body.error.problems) || [], out = [], mine = {};
    ps.forEach(function (p) {
      var text = (p.field === "birth_date" && p.issue === "invalid_format") ? DATE_HELP + " It has to be a real date."
               : (/email$/.test(p.field) && p.issue === "invalid_format") ? "That email address does not look right."
               : (/phone$/.test(p.field) && p.issue === "invalid_format") ? "That phone number does not look right. Use digits, for example 303-555-0142."
               : (PISSUE[p.issue] || "That value is not valid.");
      if (map && map[p.field]) mine[p.field] = text; else out.push((PLABEL[p.field] || p.field) + ": " + text);
    });
    if (!ps.length) out.push(adminProblem(res.status));
    return { fields: mine, other: out };
  }

  function loadPeople() {
    var my = ++pSeq;
    $("pMsg").textContent = ""; $("pRetry").hidden = true;
    if (!pLoaded) skelOn($("pList"));
    var f = $("pFilter").value;
    return admin("list", { filters: f ? { status: f } : {}, limit: 200 }, COLL_P).then(function (res) {
      if (my !== pSeq) return;
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body.ok) { skelOff($("pList")); $("pMsg").textContent = "Could not load the people. " + adminProblem(res.status); $("pRetry").hidden = false; return; }
      pAll = res.body.data.records || []; pLoaded = true;
      UI.limitNote($("pList"), pAll.length, 200);
      renderPeople();
      $("pChecked").textContent = "Last checked " + fmtClock.format(new Date());
      if ($("pHist").open) loadMerges();
    });
  }
  function renderPeople() {
    var q = $("pSearch").value.trim().toLowerCase(), list = $("pList");
    var shown = pAll.filter(function (r) { return !q || [r.display_name, r.given_name, r.family_name, r.name_to_use].join(" ").toLowerCase().indexOf(q) >= 0; });
    list.textContent = "";
    shown.forEach(function (r) { list.appendChild(personRow(r, r.id === pNewId)); });
    pNewId = "";
    $("pCount").textContent = pAll.length + (pAll.length === 1 ? " person" : " people");
    $("pEmpty").hidden = pAll.length > 0;
    $("pNoMatch").hidden = !(pAll.length > 0 && shown.length === 0);
  }

  function personRow(rec, isNew) {
    var li = mk("li", isNew ? "isnew" : "");
    var head = mk("button", "head"); head.type = "button"; head.setAttribute("aria-expanded", "false");
    var top = mk("div", "top");
    top.appendChild(mk("span", "vname", pName(rec)));
    var tgl = (rec.status === "active" || rec.status === "inactive") ? statusToggle(rec, li, { coll: COLL_P, on: "active", off: "inactive", label: "Person", problem: function (res) { return pProblems(res).other.join(" "); } }) : null;
    if (!tgl) top.appendChild(mk("span", "type", rec.status || ""));
    head.appendChild(top);
    var bits = [];
    if (rec.birth_date) bits.push("Born " + pDateOut(rec.birth_date));
    if (rec.is_minor) bits.push("Under 18");
    if (rec.life_status && rec.life_status !== "alive") bits.push(rec.life_status.replace(/_/g, " "));
    if (rec.record_privacy && rec.record_privacy !== "normal") bits.push(rec.record_privacy);
    if (bits.length) head.appendChild(mk("div", "sub", bits.join(" · ")));
    var detail = mk("div", "detail");
    detail.appendChild(personActions(rec));
    var done = {};
    ["display_name", "given_name", "family_name", "status", "birth_date", "id"].forEach(function (f) { if (rec[f] !== undefined) { detail.appendChild(line(f, str(rec[f]))); done[f] = 1; } });
    Object.keys(rec).sort().forEach(function (f) { if (!done[f]) detail.appendChild(line(f, str(rec[f]))); });
    head.addEventListener("click", function () { var open = li.classList.toggle("open"); head.setAttribute("aria-expanded", open ? "true" : "false"); });
    li.appendChild(head); if (tgl) { li.appendChild(tgl.btn); li.appendChild(tgl.msg); } li.appendChild(detail);
    if (isNew) setTimeout(function () { li.classList.remove("isnew"); }, 6000);
    return li;
  }

  function personActions(rec) {
    var wrap = mk("div"), row = mk("div", "actions-row");
    var ed = mk("button", "", "Edit"); ed.type = "button";
    var ad = mk("button", "quiet", "Addresses"); ad.type = "button";
    var mg = mk("button", "quiet", "Merge into another person"); mg.type = "button";
    var del = mk("button", "danger", "Delete"); del.type = "button";
    row.appendChild(ed); var hp = historyBtn(rec.id, "this person"); if (hp) row.appendChild(hp); row.appendChild(ad); row.appendChild(mg); row.appendChild(del);
    var hi = mk("button", "quiet", "History"); hi.type = "button"; row.appendChild(hi);
    var histHost = mk("div");
    hi.addEventListener("click", function () { if (histHost.firstChild) histHost.textContent = ""; else personHistory(rec, histHost); });
    var editHost = mk("div"), mergeHost = mk("div"), addrHost = mk("div");
    var box = mk("div", "confirm"); box.hidden = true;
    box.appendChild(mk("div", "", "Delete " + pName(rec) + "? They are hidden from the lists but the record is kept."));
    var btns = mk("div", "btns"), yes = mk("button", "danger", "Delete person"), no = mk("button", "quiet", "Cancel");
    yes.type = "button"; no.type = "button";
    var err = mk("div", "msg"); err.setAttribute("role", "alert");
    btns.appendChild(yes); btns.appendChild(no); box.appendChild(btns); box.appendChild(err);
    ed.addEventListener("click", function () { mergeHost.textContent = ""; addrHost.textContent = ""; box.hidden = true; if (editHost.firstChild) editHost.textContent = ""; else editHost.appendChild(personEditForm(rec, editHost)); });
    mg.addEventListener("click", function () { editHost.textContent = ""; addrHost.textContent = ""; box.hidden = true; if (mergeHost.firstChild) mergeHost.textContent = ""; else mergeHost.appendChild(mergeForm(rec, mergeHost)); });
    del.addEventListener("click", function () { editHost.textContent = ""; mergeHost.textContent = ""; addrHost.textContent = ""; box.hidden = !box.hidden; err.textContent = ""; });
    ad.addEventListener("click", function () { editHost.textContent = ""; mergeHost.textContent = ""; box.hidden = true; if (addrHost.firstChild) addrHost.textContent = ""; else addrHost.appendChild(personAddresses(rec, addrHost)); });
    no.addEventListener("click", function () { box.hidden = true; });
    yes.addEventListener("click", function () {
      yes.disabled = true; err.textContent = "";
      admin("soft_delete", { id: rec.id }, COLL_P).then(function (res) {
        yes.disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) { $("pNotice").textContent = "Deleted " + pName(rec) + "."; loadPeople(); }
        else if (res.status === 404) { $("pNotice").textContent = "That person was already gone."; loadPeople(); }
        else if (res.status === 409) err.textContent = "This person has protected details on file. Those have to be dealt with first.";
        else err.textContent = pProblems(res).other.join(" ");
      });
    });
    wrap.appendChild(row); wrap.appendChild(histHost); wrap.appendChild(editHost); wrap.appendChild(mergeHost); wrap.appendChild(addrHost); wrap.appendChild(box);
    return wrap;
  }

  function personEditForm(rec, host) {
    var form = mk("form", "eform"); form.noValidate = true; form.autocomplete = "off";
    var els = {};
    P_FIELDS.forEach(function (f) {
      var id = "pe_" + rec.id + "_" + f.k, cur = rec[f.k];
      var l = mk("label", "f", f.label); l.htmlFor = id; form.appendChild(l);
      var el;
      if (f.t === "select" || f.t === "bool" || f.t === "prefer") {
        el = mk("select");
        var opts = f.t === "bool" ? [["", "Not stated"], ["yes", "Yes"], ["no", "No"]] : f.opts;
        opts.forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; el.appendChild(op); });
        el.value = f.t === "prefer" ? (cur === true ? "email" : cur === false ? "text" : "") : f.t === "bool" ? (cur === true ? "yes" : cur === false ? "no" : "") : (cur === undefined ? (f.k === "status" ? "active" : "") : cur);
      } else if (f.t === "area") { el = mk("textarea"); el.maxLength = 2000; el.value = cur === undefined ? "" : cur; }
      else { el = mk("input"); el.type = "text"; el.maxLength = 200; el.value = cur === undefined ? "" : (f.k === "birth_date" ? pDateField(cur) : cur); }
      el.id = id; form.appendChild(el);
      if (f.hint) form.appendChild(mk("div", "hint", f.hint));
      var er = mk("div", "ferr"); form.appendChild(er);
      els[f.k] = { el: el, err: er, t: f.t };
    });
    var btns = mk("div", "btns"), save = mk("button", "", "Save changes"), cancel = mk("button", "quiet", "Cancel");
    save.type = "submit"; cancel.type = "button"; btns.appendChild(save); btns.appendChild(cancel); form.appendChild(btns);
    var msg = mk("div", "msg"); msg.setAttribute("role", "alert"); form.appendChild(msg);
    cancel.addEventListener("click", function () { host.textContent = ""; });
    form.addEventListener("submit", function (e) {
      e.preventDefault(); msg.textContent = "";
      Object.keys(els).forEach(function (k) { els[k].err.textContent = ""; });
      var changes = {}, badDate = false;
      P_FIELDS.forEach(function (f) {
        var x = els[f.k], v = x.el.value.trim(), cur = rec[f.k];
        if (f.k === "birth_date" && v !== "") { var pd = pDateIn(v); if (pd.bad) { x.err.textContent = DATE_HELP + " It has to be a real date."; badDate = true; return; } v = pd.iso; }
        var val = f.t === "prefer" ? (v === "email" ? true : v === "text" ? false : null) : f.t === "bool" ? (v === "yes" ? true : v === "no" ? false : null) : (v === "" ? null : v);
        if (f.k === "status" && val === null) val = "active";
        if (val === null) { if (cur !== undefined) changes[f.k] = null; }
        else if (val !== cur) changes[f.k] = val;
      });
      if (badDate) return;
      if (!Object.keys(changes).length) { host.textContent = ""; $("pNotice").textContent = "Nothing changed."; return; }
      save.disabled = true;
      admin("update", { id: rec.id, changes: changes, expected_updated_at: rec.updated_at }, COLL_P).then(function (res) {
        save.disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) { pNewId = rec.id; $("pNotice").textContent = "Saved changes to " + pName(rec) + "."; loadPeople(); return; }
        if (res.status === 409) { msg.textContent = "Someone changed this person while you were editing. Close this, tap Refresh, and try again. Nothing was overwritten."; return; }
        if (res.status === 404) { msg.textContent = "That person is gone or merged. Tap Refresh."; return; }
        var pr = pProblems(res, els);
        Object.keys(pr.fields).forEach(function (k) { els[k].err.textContent = pr.fields[k]; });
        if (pr.other.length) msg.textContent = "Could not save: " + pr.other.join(" ");
      });
    });
    return form;
  }

  function mergeForm(rec, host) {
    var box = mk("div", "mergebox");
    box.appendChild(mk("div", "", pName(rec) + " is the same person as someone already listed. Pick who to keep. Anything missing on that person is filled in from this record, links to this person move over, and this record is marked merged. It can be undone in Merge history."));
    var l1 = mk("label", "f", "Person to keep"); var sel = mk("select"); sel.id = "pm_" + rec.id; l1.htmlFor = sel.id;
    var o0 = mk("option", "", "Choose one"); o0.value = ""; sel.appendChild(o0);
    pAll.filter(function (p) { return p.id !== rec.id && p.status === "active"; }).forEach(function (p) {
      var o = mk("option", "", pName(p) + (p.birth_date ? " (born " + pDateOut(p.birth_date) + ")" : "")); o.value = p.id; sel.appendChild(o);
    });
    var e1 = mk("div", "ferr");
    var l2 = mk("label", "f", "Reason"); var why = mk("input"); why.type = "text"; why.maxLength = 500; why.id = "pr_" + rec.id; l2.htmlFor = why.id; why.placeholder = "For example: same phone and birth date, confirmed by phone";
    var e2 = mk("div", "ferr");
    var btns = mk("div", "btns"), go = mk("button", "", "Merge"), no = mk("button", "quiet", "Cancel"); go.type = "button"; no.type = "button";
    btns.appendChild(go); btns.appendChild(no);
    var msg = mk("div", "msg"); msg.setAttribute("role", "alert");
    [l1, sel, e1, l2, why, e2, btns, msg].forEach(function (n) { box.appendChild(n); });
    no.addEventListener("click", function () { host.textContent = ""; });
    go.addEventListener("click", function () {
      e1.textContent = ""; e2.textContent = ""; msg.textContent = "";
      var bad = false;
      if (!sel.value) { e1.textContent = "Choose one."; bad = true; }
      if (!why.value.trim()) { e2.textContent = "Say why they are the same person."; bad = true; }
      if (bad) return;
      go.disabled = true;
      admin("merge", { survivor_id: sel.value, duplicate_id: rec.id, reason: why.value.trim() }, COLL_P).then(function (res) {
        go.disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          var d = res.body.data, keep = pById(sel.value);
          $("pNotice").textContent = "Merged " + pName(rec) + " into " + (keep ? pName(keep) : "the other person") + ": " + d.changed_fields.length + " values filled in, " + d.moved_links + " records moved. Undo it in Merge history.";
          if ($("pHist").open) loadMerges();
          loadPeople(); return;
        }
        if (res.status === 409) { msg.textContent = "Someone changed one of them while you were working. Tap Refresh and try again."; return; }
        msg.textContent = "Could not merge: " + pProblems(res).other.join(" ");
      });
    });
    return box;
  }

  function loadMerges() {
    $("pHMsg").textContent = "";
    return admin("list", { limit: 50 }, COLL_MERGE).then(function (res) {
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body.ok) { $("pHMsg").textContent = "Could not load the merge history. " + adminProblem(res.status); return; }
      var evs = res.body.data.records || [], ul = $("pHList");
      ul.textContent = "";
      evs.forEach(function (ev) {
        var li = mk("li"), body = mk("div", "detail"); body.style.display = "block";
        var a = pById(ev.duplicate_id) || ev.duplicate_before, b = pById(ev.survivor_id) || ev.survivor_before;
        body.appendChild(mk("div", "", when(ev.created_at) + ": " + (a && (a.display_name || a.given_name) ? pName(a) : "a person") + " merged into " + (b && (b.display_name || b.given_name) ? pName(b) : "another person") + " (" + ev.status + ")"));
        body.appendChild(line("reason", ev.reason || ""));
        if (ev.status === "unmerged" && ev.unmerge_skipped && ev.unmerge_skipped.length) body.appendChild(line("left as they were after the undo", String(ev.unmerge_skipped.length) + " values changed since the merge"));
        if (ev.status === "merged") {
          var row = mk("div", "actions-row"), undo = mk("button", "quiet", "Undo this merge"); undo.type = "button"; row.appendChild(undo);
          var err = mk("div", "msg"); err.setAttribute("role", "alert");
          undo.addEventListener("click", function () {
            undo.disabled = true; err.textContent = "";
            admin("unmerge", { id: ev.id }, COLL_P).then(function (r2) {
              undo.disabled = false;
              if (r2.status === 401) { lock("That key did not work."); return; }
              if (r2.status === 200 && r2.body && r2.body.ok) {
                var sk = (r2.body.data.skipped || []).length;
                $("pNotice").textContent = "Undone: " + r2.body.data.restored_links + " records pointed back." + (sk ? " " + sk + " values were left alone because they changed after the merge." : "");
                loadPeople(); return;
              }
              err.textContent = "Could not undo: " + pProblems(r2).other.join(" ");
            });
          });
          body.appendChild(row); body.appendChild(err);
        }
        li.appendChild(body); ul.appendChild(li);
      });
      $("pHEmpty").hidden = evs.length > 0;
    });
  }

  function resetPeople() {
    pLoaded = false; pAll = []; pNewId = "";
    $("pList").textContent = ""; $("pCount").textContent = ""; $("pChecked").textContent = ""; $("pMsg").textContent = ""; $("pNotice").textContent = "";
    $("pEmpty").hidden = true; $("pNoMatch").hidden = true; $("pSearch").value = ""; $("pFilter").value = "active";
    $("pAddForm").hidden = true; $("pAddBtn").hidden = false; $("pHist").open = false; $("pHList").textContent = "";
  }
  function pClearErrs() { Object.keys(PADD_ERR).forEach(function (k) { $(PADD_ERR[k]).textContent = ""; }); $("pFMsg").textContent = ""; }
  $("pAddBtn").addEventListener("click", function () { $("pAddForm").reset(); pClearErrs(); $("pNotice").textContent = ""; $("pAddForm").hidden = false; $("pAddBtn").hidden = true; $("paGiven").focus(); });
  $("pCancelBtn").addEventListener("click", function () { $("pAddForm").hidden = true; $("pAddBtn").hidden = false; });
  $("pAddForm").addEventListener("submit", function (e) {
    e.preventDefault(); pClearErrs();
    var data = {}, map = { given_name: "paGiven", family_name: "paFamily", name_to_use: "paUse", birth_date: "paBirth", email: "paEmail", phone: "paPhone" };
    Object.keys(map).forEach(function (k) { var v = $(map[k]).value.trim(); if (v) data[k] = v; });
    if (!data.given_name) { $("epaGiven").textContent = "Required."; return; }
    if (data.birth_date) { var pd = pDateIn(data.birth_date); if (pd.bad) { $("epaBirth").textContent = DATE_HELP + " It has to be a real date."; return; } data.birth_date = pd.iso; }
    $("pSaveBtn").disabled = true;
    admin("create", { data: data }, COLL_P).then(function (res) {
      $("pSaveBtn").disabled = false;
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status === 200 && res.body && res.body.ok) {
        pNewId = res.body.data.id; $("pNotice").textContent = "Added " + pName(res.body.data) + ".";
        $("pAddForm").hidden = true; $("pAddBtn").hidden = false;
        if ($("pFilter").value === "inactive") $("pFilter").value = "active";
        loadPeople(); return;
      }
      var pr = pProblems(res, PADD_ERR);
      Object.keys(pr.fields).forEach(function (k) { $(PADD_ERR[k]).textContent = pr.fields[k]; });
      if (pr.other.length) $("pFMsg").textContent = "Could not save: " + pr.other.join(" ");
    });
  });
  $("pFilter").addEventListener("change", function () { $("pNotice").textContent = ""; loadPeople(); });
  $("pRefresh").addEventListener("click", function () { $("pNotice").textContent = ""; loadPeople(); });
  $("pRetry").addEventListener("click", loadPeople);
  $("pSearch").addEventListener("input", renderPeople);
  $("pHist").addEventListener("toggle", function () { if ($("pHist").open) loadMerges(); });

  // ---- Places station and the Addresses panel on a person's card: locations and the links to them, through the same admin door.
  // A place is saved once and knows nothing about who is there. A person (or venue) is linked to it with dates.
  var COLL_L = "locations", COLL_LK = "location_links";
  var lAll = [], lLoaded = false, lSeq = 0, lNewId = "", afSeq = 0;
  var REL = { resides_at: "Lives here", mailing_address_for: "Mailing address", billing_address_for: "Billing address", works_at: "Works here",
              owns: "Owns", manages: "Manages", operates_at: "Operates here", delivers_to: "Delivers here", other: "Other" };
  var PERSON_RELS = ["resides_at", "mailing_address_for", "billing_address_for", "works_at", "owns", "other"];
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
    var box = mk("div"), f = {};
    function add(key, label, hint, max, ph) {
      var l = mk("label", "f", label), el = mk("input"); el.type = "text"; el.maxLength = max || 120; el.autocomplete = "off"; if (ph) el.placeholder = ph;
      el.id = "af" + (++afSeq) + "_" + key; l.htmlFor = el.id;
      box.appendChild(l); box.appendChild(el); if (hint) box.appendChild(mk("div", "hint", hint));
      var er = mk("div", "ferr"); box.appendChild(er); f[key] = { el: el, err: er };
    }
    if (opts.name) add("name", "Name of the place (optional)", "For example: Boulder Public Library, or Home.", 200);
    if (opts.usageChoice) {
      var ul = mk("label", "f", "What kind of address"), us = mk("select"); us.id = "af" + (++afSeq) + "_usage"; ul.htmlFor = us.id;
      [["civic", "Street address"], ["mailing", "Mailing address"], ["po_box", "PO box"], ["former", "Former address"]].forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; us.appendChild(op); });
      box.appendChild(ul); box.appendChild(us); f.usage = { el: us, err: mk("div", "ferr") };
    }
    add("street_line", "Street address", "For example: 123 Walnut St. Type it on one line.", 140); add("unit", "Apartment or suite (optional)", "", 60);
    if (opts.usageChoice) add("po_box", "PO box number (if it is a PO box)", "", 20);
    add("locality", "City", "", 120); add("region", "State", "Two letters, for example CO.", 60); add("postal_code", "ZIP code", "", 20);
    add("country", "Country", "Two letters. US for the United States.", 2);
    f.country.el.value = "US";
    // Recent city / state / ZIP: the newest fills the boxes; a list lets you pick another. Every box stays free to overwrite.
    var recent = cszRead(), auto = null;   // auto: the values we filled in, so an untouched fill never counts as an address
    if (recent.length) {
      var rl = mk("label", "f", "Recent city, state and ZIP"), rs = mk("select"); rs.id = "af" + (++afSeq) + "_recent"; rl.htmlFor = rs.id;
      recent.forEach(function (x, i) { var o = mk("option", "", cszLabel(x)); o.value = String(i); rs.appendChild(o); });
      var oo = mk("option", "", "Type a different one"); oo.value = ""; rs.appendChild(oo);
      function fillRecent() {
        var x = rs.value === "" ? null : recent[Number(rs.value)];
        if (!x) return;
        f.locality.el.value = x.c || ""; f.region.el.value = x.s || ""; f.postal_code.el.value = x.z || ""; auto = { c: x.c || "", s: x.s || "", z: x.z || "" };
      }
      rs.addEventListener("change", fillRecent);
      var anchor = f.locality.el.previousSibling;
      box.insertBefore(rl, anchor); box.insertBefore(rs, anchor);
      box.insertBefore(mk("div", "hint", "From your recent entries. Change any box to overwrite."), anchor);
      rs.value = "0"; fillRecent();
    }
    if (opts.gps) { add("lat", "GPS latitude (optional)", "A number from -90 to 90, for example 40.0150.", 20); add("lon", "GPS longitude (optional)", "A number from -180 to 180, for example -105.2705.", 20); }
    if (opts.description) { var dl = mk("label", "f", "Description (optional)"), dt = mk("textarea"); dt.maxLength = 2000; dt.id = "af" + (++afSeq) + "_desc"; dl.htmlFor = dt.id; box.appendChild(dl); box.appendChild(dt); f.description = { el: dt, err: mk("div", "ferr") }; box.appendChild(mk("div", "hint", "About the place itself, for example: brick building, parking behind. Never who lives there.")); }
    if (opts.tz) add("time_zone", "Time zone (optional)", "For example America/Denver.", 64);
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


  // A person pointer on the venue form. The venue stores only the person's id; the name is read from their record.
  var peopleForPick = null;
  function peopleList() {
    if (peopleForPick) return Promise.resolve(peopleForPick);
    return admin("list", { order: "display_name", limit: 200 }, "individuals").then(function (r) {
      if (r.status === 401) { lock("That key did not work."); return []; }
      peopleForPick = (r.status === 200 && r.body.ok) ? (r.body.data.records || []) : [];
      return peopleForPick;
    });
  }

  function refreshPlaces() { lLoaded = false; if (currentRoute() === "places") loadPlaces(); }

  // ---- Addresses on a person's card
  function personAddresses(rec, host) {
    var wrap = mk("div", "eform"), listHost = mk("div"), formHost = mk("div"), btnRow = mk("div", "actions-row");
    var msg = mk("div", "msg"); msg.setAttribute("role", "alert");
    wrap.appendChild(mk("div", "", "Addresses for " + pName(rec) + ". A place is saved once; the person is linked to it with dates. When someone moves, end the old address and add the new one."));
    var addBtn = mk("button", "", "Add an address"); addBtn.type = "button"; btnRow.appendChild(addBtn);
    var closeBtn = mk("button", "quiet", "Close"); closeBtn.type = "button"; btnRow.appendChild(closeBtn);
    wrap.appendChild(listHost); wrap.appendChild(btnRow); wrap.appendChild(formHost); wrap.appendChild(msg);
    closeBtn.addEventListener("click", function () { host.textContent = ""; });
    addBtn.addEventListener("click", function () { msg.textContent = ""; if (formHost.firstChild) formHost.textContent = ""; else formHost.appendChild(addressForm()); });

    function refresh() {
      listHost.textContent = ""; listHost.appendChild(mk("div", "hint", "Loading addresses..."));
      admin("list", { filters: { subject_id: rec.id }, limit: 50 }, COLL_LK).then(function (res) {
        if (res.status === 401) { lock("That key did not work."); return; }
        listHost.textContent = "";
        if (res.status !== 200 || !res.body.ok) { listHost.appendChild(mk("div", "msg", "Could not load addresses. " + adminProblem(res.status))); return; }
        var links = res.body.data.records || [];
        if (!links.length) { listHost.appendChild(mk("div", "hint", "No addresses yet.")); return; }
        Promise.all(links.map(function (l) { return admin("get", { id: l.location_id }, COLL_L); })).then(function (locs) {
          links.forEach(function (l, i) { listHost.appendChild(linkRow(l, locs[i].status === 200 && locs[i].body.ok ? locs[i].body.data : null)); });
        });
      });
    }
    function linkRow(l, loc) {
      var row = mk("div", "mergebox"), ended = l.status === "ended";
      var h = mk("div", "", (REL[l.relationship] || l.relationship) + (l.is_primary ? " (main)" : "") + (ended ? " (ended)" : "")); h.style.fontWeight = "700"; row.appendChild(h);
      row.appendChild(mk("div", "", loc ? locSummary(loc) : "(place not available)"));
      var span = (l.valid_from ? "From " + pDateOut(l.valid_from) : "") + (l.valid_to ? (l.valid_from ? " " : "") + "until " + pDateOut(l.valid_to) : "");
      if (span) row.appendChild(mk("div", "hint", span));
      var acts = mk("div", "actions-row"), box = mk("div"), err = mk("div", "msg"); err.setAttribute("role", "alert");
      if (!ended) {
        var en = mk("button", "quiet", "End"); en.type = "button"; acts.appendChild(en);
        en.addEventListener("click", function () { box.textContent = ""; err.textContent = ""; box.appendChild(endBox(l, err)); });
        if (!l.is_primary) {
          var mm = mk("button", "quiet", "Make main"); mm.type = "button"; acts.appendChild(mm);
          mm.addEventListener("click", function () {
            mm.disabled = true; err.textContent = "";
            admin("update", { id: l.id, changes: { is_primary: true }, expected_updated_at: l.updated_at }, COLL_LK).then(function (r) {
              mm.disabled = false; if (r.status === 401) { lock("That key did not work."); return; }
              if (r.status === 200 && r.body.ok) { refresh(); return; }
              err.textContent = r.status === 409 ? "This changed while you were looking. Close and reopen." : lProblems(r);
            });
          });
        }
      }
      var rm = mk("button", "danger", "Remove"); rm.type = "button"; acts.appendChild(rm);
      rm.addEventListener("click", function () {
        box.textContent = ""; err.textContent = "";
        var c = mk("div", "confirm"); c.appendChild(mk("div", "", "Remove this address? Use this for a mistake. To record a move, use End instead."));
        var b = mk("div", "btns"), y = mk("button", "danger", "Remove"), n = mk("button", "quiet", "Cancel"); y.type = "button"; n.type = "button";
        b.appendChild(y); b.appendChild(n); c.appendChild(b); box.appendChild(c);
        n.addEventListener("click", function () { box.textContent = ""; });
        y.addEventListener("click", function () {
          y.disabled = true;
          admin("soft_delete", { id: l.id }, COLL_LK).then(function (r) {
            y.disabled = false; if (r.status === 401) { lock("That key did not work."); return; }
            if (r.status === 200 || r.status === 404) { refreshPlaces(); refresh(); return; }
            err.textContent = lProblems(r);
          });
        });
      });
      row.appendChild(acts); row.appendChild(box); row.appendChild(err);
      return row;
    }
    function endBox(l, err) {
      var b = mk("div", "confirm"), lab = mk("label", "f", "Last day at this address (blank means today)"), inp = mk("input");
      inp.type = "text"; inp.maxLength = 10; inp.id = "ed_" + l.id; lab.htmlFor = inp.id; inp.placeholder = "MM-DD-YYYY";
      var btns = mk("div", "btns"), go = mk("button", "", "End this address"), no = mk("button", "quiet", "Cancel"); go.type = "button"; no.type = "button";
      btns.appendChild(go); btns.appendChild(no);
      [lab, inp, mk("div", "hint", DATE_HELP), btns].forEach(function (n) { b.appendChild(n); });
      no.addEventListener("click", function () { b.remove(); });
      go.addEventListener("click", function () {
        err.textContent = ""; var args = { id: l.id, expected_updated_at: l.updated_at };
        if (inp.value.trim()) { var pd = pDateIn(inp.value); if (pd.bad) { err.textContent = DATE_HELP + " It has to be a real date."; return; } args.valid_to = pd.iso; }
        go.disabled = true;
        admin("end", args, COLL_LK).then(function (r) {
          go.disabled = false; if (r.status === 401) { lock("That key did not work."); return; }
          if (r.status === 200 && r.body.ok) { refreshPlaces(); refresh(); return; }
          err.textContent = r.status === 409 ? "That address already ended, or it changed while you were looking. Close and reopen." : lProblems(r);
        });
      });
      return b;
    }
    function addressForm() {
      var form = mk("form", "eform"); form.noValidate = true; form.autocomplete = "off";
      var rl = mk("label", "f", "What is this address?"), rs = mk("select"); rs.id = "ar_" + rec.id; rl.htmlFor = rs.id;
      PERSON_RELS.forEach(function (k) { var o = mk("option", "", REL[k]); o.value = k; rs.appendChild(o); });
      form.appendChild(rl); form.appendChild(rs);
      var block = addrForm({ name: true }); form.appendChild(block);
      var sl = mk("label", "f", "Since (optional)"), si = mk("input"); si.type = "text"; si.maxLength = 10; si.id = "as_" + rec.id; sl.htmlFor = si.id; si.placeholder = "MM-DD-YYYY, MM-YYYY or YYYY";
      var se = mk("div", "ferr"); form.appendChild(sl); form.appendChild(si); form.appendChild(mk("div", "hint", DATE_HELP)); form.appendChild(se);
      var pl = mk("label", "f"), pc = mk("input"); pc.type = "checkbox"; pc.id = "ap_" + rec.id; pl.htmlFor = pc.id; pl.appendChild(pc); pl.appendChild(document.createTextNode(" This is the main one"));
      pl.style.display = "flex"; pl.style.gap = "8px"; pl.style.alignItems = "center"; form.appendChild(pl);
      var chooser = mk("div", "confirm"); chooser.hidden = true; form.appendChild(chooser);
      var btns = mk("div", "btns"), save = mk("button", "", "Save address"), cancel = mk("button", "quiet", "Cancel"); save.type = "submit"; cancel.type = "button";
      btns.appendChild(save); btns.appendChild(cancel); form.appendChild(btns);
      var fm = mk("div", "msg"); fm.setAttribute("role", "alert"); form.appendChild(fm);
      var step = "start", locData = null, linkBase = null;
      cancel.addEventListener("click", function () { formHost.textContent = ""; });
      function link(locationId) {
        var data = {}; Object.keys(linkBase).forEach(function (k) { data[k] = linkBase[k]; }); data.location_id = locationId;
        return admin("create", { data: data }, COLL_LK).then(function (r) {
          save.disabled = false;
          if (r.status === 401) { lock("That key did not work."); return; }
          if (r.status === 200 && r.body.ok) { formHost.textContent = ""; msg.textContent = ""; refreshPlaces(); refresh(); return; }
          fm.textContent = "The place was saved but the link was not: " + lProblems(r);
        });
      }
      form.addEventListener("submit", function (e) {
        e.preventDefault(); fm.textContent = ""; se.textContent = "";
        if (step === "choose") {
          var pick = form.querySelector("input[name=usep]:checked"); save.disabled = true;
          if (pick && pick.value) return link(pick.value);
          return admin("create", { data: locData }, COLL_L).then(function (r) {
            if (r.status === 401) { lock("That key did not work."); return; }
            if (r.status === 200 && r.body.ok) return link(r.body.data.id);
            save.disabled = false; fm.textContent = "Could not save the place: " + lProblems(r);
          });
        }
        var rd = block.read(), ok = rd.ok, since = "";
        if (ok && !(rd.data.addresses)) { ok = false; fm.textContent = "A person's address needs a street or a PO box."; }
        if (si.value.trim()) { var pd = pDateIn(si.value); if (pd.bad) { se.textContent = DATE_HELP + " It has to be a real date."; ok = false; } else since = pd.iso; }
        if (!ok) return;
        locData = rd.data; linkBase = { subject_type: "individual", subject_id: rec.id, relationship: rs.value };
        if (since) linkBase.valid_from = since;
        if (pc.checked) linkBase.is_primary = true;
        save.disabled = true;
        admin("find_by_address", { address: locData.addresses[0] }, COLL_L).then(function (r) {
          if (r.status === 401) { lock("That key did not work."); return; }
          var found = (r.status === 200 && r.body.ok) ? (r.body.data.records || []) : [];
          if (!found.length) {
            admin("create", { data: locData }, COLL_L).then(function (c) {
              if (c.status === 401) { lock("That key did not work."); return; }
              if (c.status === 200 && c.body.ok) return link(c.body.data.id);
              save.disabled = false; fm.textContent = "Could not save the place: " + lProblems(c);
            });
            return;
          }
          step = "choose"; save.disabled = false; save.textContent = "Continue"; chooser.hidden = false; chooser.textContent = "";
          chooser.appendChild(mk("div", "", "This address is already saved. Use the saved place, so everyone at it shares one record?"));
          found.forEach(function (m, i) {
            var lb = mk("label", "f"), rd2 = mk("input"); rd2.type = "radio"; rd2.name = "usep"; rd2.value = m.id; if (i === 0) rd2.checked = true;
            lb.style.display = "flex"; lb.style.gap = "8px"; lb.style.alignItems = "center"; lb.appendChild(rd2); lb.appendChild(document.createTextNode(" Use: " + locSummary(m))); chooser.appendChild(lb);
          });
          var lb2 = mk("label", "f"), rd3 = mk("input"); rd3.type = "radio"; rd3.name = "usep"; rd3.value = "";
          lb2.style.display = "flex"; lb2.style.gap = "8px"; lb2.style.alignItems = "center"; lb2.appendChild(rd3); lb2.appendChild(document.createTextNode(" No, this is a different place")); chooser.appendChild(lb2);
        });
      });
      return form;
    }
    refresh();
    return wrap;
  }

  // ---- Places station
  function loadPlaces() {
    var my = ++lSeq;
    $("lMsg").textContent = ""; $("lRetry").hidden = true;
    if (!lLoaded) skelOn($("lList"));
    var f = $("lFilter").value;
    return admin("list", { filters: f ? { status: f } : {}, limit: 200 }, COLL_L).then(function (res) {
      if (my !== lSeq) return;
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status !== 200 || !res.body.ok) { skelOff($("lList")); $("lMsg").textContent = "Could not load the places. " + adminProblem(res.status); $("lRetry").hidden = false; return; }
      lAll = res.body.data.records || []; lLoaded = true;
      UI.limitNote($("lList"), lAll.length, 200);
      renderPlaces();
      $("lChecked").textContent = "Last checked " + fmtClock.format(new Date());
    });
  }
  function renderPlaces() {
    var q = $("lSearch").value.trim().toLowerCase(), list = $("lList");
    var shown = lAll.filter(function (r) { return !q || (locSummary(r) + " " + (r.aliases || []).join(" ")).toLowerCase().indexOf(q) >= 0; });
    list.textContent = "";
    shown.forEach(function (r) { list.appendChild(placeRow(r, r.id === lNewId)); });
    lNewId = "";
    $("lCount").textContent = lAll.length + (lAll.length === 1 ? " place" : " places");
    $("lEmpty").hidden = lAll.length > 0;
    $("lNoMatch").hidden = !(lAll.length > 0 && shown.length === 0);
  }
  function placeRow(rec, isNew) {
    var li = mk("li", isNew ? "isnew" : "");
    var head = mk("button", "head"); head.type = "button"; head.setAttribute("aria-expanded", "false");
    var top = mk("div", "top");
    top.appendChild(mk("span", "vname", locSummary(rec)));
    var tgl = (rec.status === "active" || rec.status === "retired") ? statusToggle(rec, li, { coll: COLL_L, on: "active", off: "retired", offWord: "Retired", label: "Place", problem: function (res) { return lProblems(res); } }) : null;
    if (!tgl) top.appendChild(mk("span", "type", rec.status || ""));
    head.appendChild(top);
    var bits = [];
    if (rec.kind) bits.push(rec.kind);
    if ((rec.geometries || []).length) bits.push(rec.geometries.length + (rec.geometries.length === 1 ? " GPS point" : " GPS shapes"));
    if ((rec.addresses || []).length > 1) bits.push(rec.addresses.length + " addresses");
    if (rec.is_residential) bits.push("someone lives here");
    if (bits.length) head.appendChild(mk("div", "sub", bits.join(" · ")));
    var detail = mk("div", "detail");
    detail.appendChild(placeActions(rec));
    (rec.addresses || []).forEach(function (a, i) { detail.appendChild(line("Address " + (i + 1) + " (" + a.usage + (a.is_primary ? ", main" : "") + ")", locAddr(a) || "(no text)")); });
    (rec.geometries || []).forEach(function (g, i) {
      var c = g.geometry.coordinates, t = g.geometry.type === "Point" ? c[1] + ", " + c[0] : g.geometry.type;
      detail.appendChild(line("GPS " + (i + 1) + " (" + g.role + (g.label ? ", " + g.label : "") + ")", t));
    });
    ["name", "aliases", "description", "time_zone", "kind", "part_of_location_id", "id"].forEach(function (k) { if (rec[k] !== undefined) detail.appendChild(line(k, str(rec[k]))); });
    var who = mk("div"), wb = mk("button", "quiet", "Show who is linked here"); wb.type = "button"; who.appendChild(wb);
    wb.addEventListener("click", function () { wb.disabled = true; showLinked(rec, who, wb); });
    detail.appendChild(who);
    head.addEventListener("click", function () { var open = li.classList.toggle("open"); head.setAttribute("aria-expanded", open ? "true" : "false"); });
    li.appendChild(head); if (tgl) { li.appendChild(tgl.btn); li.appendChild(tgl.msg); } li.appendChild(detail);
    if (isNew) setTimeout(function () { li.classList.remove("isnew"); }, 6000);
    return li;
  }
  function showLinked(rec, host, btn) {
    admin("list", { filters: { location_id: rec.id }, limit: 100 }, COLL_LK).then(function (res) {
      if (res.status === 401) { lock("That key did not work."); return; }
      btn.remove();
      if (res.status !== 200 || !res.body.ok) { host.appendChild(mk("div", "msg", "Could not load. " + adminProblem(res.status))); return; }
      var links = res.body.data.records || [];
      if (!links.length) { host.appendChild(mk("div", "hint", "Nobody is linked to this place.")); return; }
      links.forEach(function (l) {
        var coll = l.subject_type === "venue" ? "venues" : l.subject_type === "organization" ? "organizations" : COLL_P, d = mk("div");
        d.textContent = "Loading...";
        host.appendChild(d);
        admin("get", { id: l.subject_id }, coll).then(function (r) {
          var nm = r.status === 200 && r.body.ok ? (r.body.data.display_name || r.body.data.name || r.body.data.given_name) : "(not available)";
          d.textContent = nm + " · " + (REL[l.relationship] || l.relationship) + (l.valid_from ? " from " + pDateOut(l.valid_from) : "") + (l.valid_to ? " until " + pDateOut(l.valid_to) : "") + (l.status === "ended" ? " (ended)" : "");
        });
      });
    });
  }
  function placeActions(rec) {
    var wrap = mk("div"), row = mk("div", "actions-row"), host = mk("div"), box = mk("div", "confirm"); box.hidden = true;
    var err = mk("div", "msg"); err.setAttribute("role", "alert");
    function btn(label, cls) { var b = mk("button", cls || "", label); b.type = "button"; row.appendChild(b); return b; }
    var ed = btn("Edit"), aa = btn("Add address", "quiet"), ag = btn("Add GPS point", "quiet"), ra = btn("Remove an address or GPS point", "quiet");
    var hl = historyBtn(rec.id, rec.name || rec.label || "this place"); if (hl) row.insertBefore(hl, aa);
    var rt = btn(rec.status === "retired" ? "Restore" : "Retire", "quiet"), del = btn("Delete", "danger");
    function open(builder) { box.hidden = true; err.textContent = ""; if (host.firstChild) { host.textContent = ""; return; } host.appendChild(builder()); }
    function save(changes, done) {
      admin("update", { id: rec.id, changes: changes, expected_updated_at: rec.updated_at }, COLL_L).then(function (r) {
        if (r.status === 401) { lock("That key did not work."); return; }
        if (r.status === 200 && r.body.ok) { lNewId = rec.id; $("lNotice").textContent = "Saved changes. If an address changed, people in upcoming classes at venues here are emailed the new address. Messages shows the result."; loadPlaces(); return; }
        if (r.status === 409 && r.body.error && r.body.error.code === "conflict" && lProblems(r).indexOf("still linked") >= 0) { err.textContent = lProblems(r); return; }
        err.textContent = r.status === 409 ? "Someone changed this place while you were editing. Tap Refresh and try again." : lProblems(r);
        if (done) done();
      });
    }
    ed.addEventListener("click", function () { open(function () {
      var form = mk("form", "eform"); form.noValidate = true;
      var defs = [["name", "Name", "text"], ["description", "Description", "area"], ["time_zone", "Time zone", "text"], ["kind", "Kind", "kind"]], els = {};
      defs.forEach(function (d) {
        var id = "pl_" + rec.id + "_" + d[0], l = mk("label", "f", d[1]); l.htmlFor = id; form.appendChild(l); var el;
        if (d[2] === "kind") { el = mk("select"); [["point", "Point (a doorway or a spot)"], ["site", "Site (a building, campus or property)"], ["parcel", "Parcel (a legal lot)"], ["route", "Route (a street or trail)"]].forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; el.appendChild(op); }); el.value = rec.kind || "site"; }
        else if (d[2] === "area") { el = mk("textarea"); el.maxLength = 2000; el.value = rec[d[0]] || ""; }
        else { el = mk("input"); el.type = "text"; el.maxLength = 200; el.value = rec[d[0]] || ""; }
        el.id = id; form.appendChild(el); els[d[0]] = el;
      });
      var btns = mk("div", "btns"), s = mk("button", "", "Save changes"), c = mk("button", "quiet", "Cancel"); s.type = "submit"; c.type = "button"; btns.appendChild(s); btns.appendChild(c); form.appendChild(btns);
      c.addEventListener("click", function () { host.textContent = ""; });
      form.addEventListener("submit", function (e) {
        e.preventDefault(); err.textContent = ""; var ch = {};
        defs.forEach(function (d) { var v = els[d[0]].value.trim(), cur = rec[d[0]]; if (v === "") { if (cur !== undefined && d[0] !== "kind") ch[d[0]] = null; } else if (v !== cur) ch[d[0]] = v; });
        if (!Object.keys(ch).length) { host.textContent = ""; $("lNotice").textContent = "Nothing changed."; return; }
        save(ch);
      });
      return form;
    }); });
    aa.addEventListener("click", function () { open(function () {
      var form = mk("form", "eform"); form.noValidate = true; var block = addrForm({ usageChoice: true }); form.appendChild(block);
      var pl = mk("label", "f"), pc = mk("input"); pc.type = "checkbox"; pc.id = "pa_" + rec.id; pl.htmlFor = pc.id; pl.appendChild(pc); pl.appendChild(document.createTextNode(" This is the main address")); pl.style.display = "flex"; pl.style.gap = "8px"; pl.style.alignItems = "center"; form.appendChild(pl);
      var btns = mk("div", "btns"), s = mk("button", "", "Add address"), c = mk("button", "quiet", "Cancel"); s.type = "submit"; c.type = "button"; btns.appendChild(s); btns.appendChild(c); form.appendChild(btns);
      c.addEventListener("click", function () { host.textContent = ""; });
      form.addEventListener("submit", function (e) {
        e.preventDefault(); err.textContent = ""; var rd = block.read();
        if (rd.ok && !rd.data.addresses) { err.textContent = "Enter a street or a PO box."; return; }
        if (!rd.ok) return;
        var a = rd.data.addresses[0], cur = (rec.addresses || []).map(function (x) { var y = JSON.parse(JSON.stringify(x)); if (pc.checked) delete y.is_primary; return y; });
        if (pc.checked) a.is_primary = true; else delete a.is_primary;
        save({ addresses: cur.concat([a]) });
      });
      return form;
    }); });
    ag.addEventListener("click", function () { open(function () {
      var form = mk("form", "eform"); form.noValidate = true;
      var rl = mk("label", "f", "What does this point mark?"), rs = mk("select"); rs.id = "gr_" + rec.id; rl.htmlFor = rs.id;
      [["center", "Center of the place"], ["entrance", "An entrance"], ["other", "Something else"]].forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; rs.appendChild(op); });
      var ll = mk("label", "f", "Label (optional)"), li2 = mk("input"); li2.type = "text"; li2.maxLength = 100; li2.id = "gl_" + rec.id; ll.htmlFor = li2.id; li2.placeholder = "for example: north gate";
      var a1 = mk("label", "f", "Latitude"), i1 = mk("input"); i1.type = "text"; i1.id = "ga_" + rec.id; a1.htmlFor = i1.id;
      var a2 = mk("label", "f", "Longitude"), i2 = mk("input"); i2.type = "text"; i2.id = "go_" + rec.id; a2.htmlFor = i2.id;
      [rl, rs, ll, li2, a1, i1, a2, i2].forEach(function (n) { form.appendChild(n); });
      var btns = mk("div", "btns"), s = mk("button", "", "Add GPS point"), c = mk("button", "quiet", "Cancel"); s.type = "submit"; c.type = "button"; btns.appendChild(s); btns.appendChild(c); form.appendChild(btns);
      c.addEventListener("click", function () { host.textContent = ""; });
      form.addEventListener("submit", function (e) {
        e.preventDefault(); err.textContent = "";
        var la = Number(i1.value.trim()), lo = Number(i2.value.trim());
        if (!i1.value.trim() || !i2.value.trim() || isNaN(la) || isNaN(lo) || la < -90 || la > 90 || lo < -180 || lo > 180) { err.textContent = "Latitude is -90 to 90 and longitude is -180 to 180."; return; }
        var g = { role: rs.value, geometry: { type: "Point", coordinates: [lo, la] } }; if (li2.value.trim()) g.label = li2.value.trim();
        save({ geometries: (rec.geometries || []).concat([g]) });
      });
      return form;
    }); });
    ra.addEventListener("click", function () { open(function () {
      var f = mk("div", "eform"), items = [];
      (rec.addresses || []).forEach(function (a, i) { items.push({ label: "Address: " + (locAddr(a) || a.usage), key: "addresses", idx: i }); });
      (rec.geometries || []).forEach(function (g, i) { items.push({ label: "GPS " + g.role + (g.label ? " (" + g.label + ")" : "") + ": " + (g.geometry.type === "Point" ? g.geometry.coordinates[1] + ", " + g.geometry.coordinates[0] : g.geometry.type), key: "geometries", idx: i }); });
      if (!items.length) f.appendChild(mk("div", "hint", "Nothing to remove."));
      items.forEach(function (it) {
        var r = mk("div", "actions-row"); r.appendChild(mk("span", "", it.label));
        var b = mk("button", "danger", "Remove"); b.type = "button"; r.appendChild(b); f.appendChild(r);
        b.addEventListener("click", function () {
          if (b.dataset.sure !== "1") { b.dataset.sure = "1"; b.textContent = "Tap again to remove"; setTimeout(function () { b.dataset.sure = ""; b.textContent = "Remove"; }, 4000); return; }
          var list = (rec[it.key] || []).slice(); list.splice(it.idx, 1);
          var ch = {}; ch[it.key] = list.length ? list : null; save(ch);
        });
      });
      var c = mk("button", "quiet", "Close"); c.type = "button"; c.addEventListener("click", function () { host.textContent = ""; }); f.appendChild(c);
      return f;
    }); });
    rt.addEventListener("click", function () { host.textContent = ""; box.hidden = true; err.textContent = ""; save({ status: rec.status === "retired" ? "active" : "retired" }); });
    box.appendChild(mk("div", "", "Delete this place? It is hidden from the lists but the record is kept. A place with a live link cannot be deleted."));
    var bb = mk("div", "btns"), yes = mk("button", "danger", "Delete place"), no = mk("button", "quiet", "Cancel"); yes.type = "button"; no.type = "button"; bb.appendChild(yes); bb.appendChild(no); box.appendChild(bb);
    del.addEventListener("click", function () { host.textContent = ""; err.textContent = ""; box.hidden = !box.hidden; });
    no.addEventListener("click", function () { box.hidden = true; });
    yes.addEventListener("click", function () {
      yes.disabled = true;
      admin("soft_delete", { id: rec.id }, COLL_L).then(function (r) {
        yes.disabled = false; if (r.status === 401) { lock("That key did not work."); return; }
        if (r.status === 200 || r.status === 404) { $("lNotice").textContent = "Deleted the place."; loadPlaces(); return; }
        err.textContent = r.status === 409 ? "People or venues are still linked to this place. End those links first." : lProblems(r);
      });
    });
    wrap.appendChild(row); wrap.appendChild(host); wrap.appendChild(box); wrap.appendChild(err);
    return wrap;
  }
  function resetPlaces() {
    lLoaded = false; lAll = []; lNewId = "";
    $("lList").textContent = ""; $("lCount").textContent = ""; $("lChecked").textContent = ""; $("lMsg").textContent = ""; $("lNotice").textContent = "";
    $("lEmpty").hidden = true; $("lNoMatch").hidden = true; $("lSearch").value = ""; $("lFilter").value = "active";
    $("lAddForm").hidden = true; $("lAddBtn").hidden = false; $("lAddFields").textContent = "";
  }
  var lBlock = null;
  $("lAddBtn").addEventListener("click", function () {
    $("lAddFields").textContent = ""; lBlock = addrForm({ name: true, description: true, tz: true, gps: true, usageChoice: false }); $("lAddFields").appendChild(lBlock);
    $("lFMsg").textContent = ""; $("lNotice").textContent = ""; $("lAddForm").hidden = false; $("lAddBtn").hidden = true;
  });
  $("lCancelBtn").addEventListener("click", function () { $("lAddForm").hidden = true; $("lAddBtn").hidden = false; });
  $("lAddForm").addEventListener("submit", function (e) {
    e.preventDefault(); $("lFMsg").textContent = "";
    var rd = lBlock.read(); if (!rd.ok) return;
    $("lSaveBtn").disabled = true;
    admin("create", { data: rd.data }, COLL_L).then(function (res) {
      $("lSaveBtn").disabled = false;
      if (res.status === 401) { lock("That key did not work."); return; }
      if (res.status === 200 && res.body.ok) {
        var d = res.body.data, same = d.address_matches || [];
        lNewId = d.id; $("lNotice").textContent = "Saved " + locSummary(d) + "." + (same.length ? " Heads up: " + same.length + " other saved " + (same.length === 1 ? "place has" : "places have") + " this same address. Nothing was merged." : "");
        $("lAddForm").hidden = true; $("lAddBtn").hidden = false;
        if ($("lFilter").value === "retired") $("lFilter").value = "active";
        loadPlaces(); return;
      }
      $("lFMsg").textContent = "Could not save: " + lProblems(res);
    });
  });
  $("lFilter").addEventListener("change", function () { $("lNotice").textContent = ""; loadPlaces(); });
  $("lRefresh").addEventListener("click", function () { $("lNotice").textContent = ""; loadPlaces(); });
  $("lRetry").addEventListener("click", loadPlaces);
  $("lSearch").addEventListener("input", renderPlaces);

  var ROSTER = {};   // the Organizations station still registers here; Instructors and Students are their own files (instructors.js, students.js, roster-engine.js)

  var OISSUE = { required: "Required.", invalid_format: "Check the format.", out_of_range: "That is too long, too short or out of range.", invalid_type: "That value is not valid.",
                 invalid_value: "That value is not valid.", not_allowed: "Not allowed.", immutable: "That cannot be changed.", duplicate: "Already used." };
  var OKINDS = [["business", "Business"], ["nonprofit", "Nonprofit"], ["school", "School"], ["school_district", "School district"], ["college_university", "College or university"],
                ["government", "Government"], ["governing_body", "Governing body (a board)"], ["association", "Association"], ["club", "Club"],
                ["training_provider", "Training provider"], ["community_group", "Community group"], ["other", "Other"]];
  var OKIND_LABEL = {}; OKINDS.forEach(function (k) { OKIND_LABEL[k[0]] = k[1]; });
  function buildOrganization() {
    var P = "ro", S = { all: [], loaded: false, seq: 0, newId: "" }, g = function (s) { return $(P + s); };
    ROSTER.organizations = S;
    var root = $("organizationsView");
    root.innerHTML =
      '<div class="bar"><div><div class="count" id="roCount"></div><div class="meta" id="roChecked"></div></div>' +
      '<div class="actions"><select id="roFilter" aria-label="Filter by status"><option value="active">Active</option><option value="inactive">Inactive</option><option value="closed">Closed</option><option value="">All</option></select>' +
      '<input type="search" id="roSearch" placeholder="Search by name" aria-label="Search by name" autocomplete="off">' +
      '<button type="button" class="quiet manualBtn" data-m="organizations">Manual</button><button id="roRefresh" class="quiet" type="button">Refresh</button>' +
      '<button id="roAddBtn" type="button">Add organization</button></div></div>' +
      '<form class="panel" id="roAddForm" hidden autocomplete="off" novalidate><h2>Add an organization</h2>' +
      '<div class="hint">Only the name is needed. Everything else can be added later.</div>' +
      '<div id="roAddFields"></div>' +
      '<div class="btns"><button type="submit" id="roSaveBtn">Save organization</button><button type="button" class="quiet" id="roCancelBtn">Cancel</button></div>' +
      '<div class="msg" id="roFMsg" role="alert"></div></form>' +
      '<div class="notice" id="roNotice" role="status"></div><div class="msg" id="roMsg" role="alert"></div>' +
      '<button type="button" class="quiet" id="roRetry" hidden>Retry</button><ul id="roList"></ul><div class="empty" id="roEmpty" hidden>No organizations yet.</div>';
    // t: text | area | kinds | lines (one per line) | ids (type: value per line) | date
    var FIELDS = [
      { k: "name", label: "Name", t: "text", add: true, max: 200, hint: "What people call it, for example Ozo Coffee." },
      { k: "kinds", label: "Kind (tick all that fit)", t: "kinds", add: true },
      { k: "short_name", label: "Short name (optional)", t: "text", add: true, max: 60, hint: "For example BVSD." },
      { k: "website_url", label: "Web address (optional)", t: "text", add: true, max: 300, hint: "Starts with http:// or https://" },
      { k: "email", label: "Email (optional)", t: "text", add: true, max: 200 },
      { k: "phone", label: "Phone (optional)", t: "text", add: true, max: 40 },
      { k: "legal_name", label: "Legal name (optional)", t: "text", add: false, max: 200, more: true },
      { k: "aliases", label: "Other names (optional)", t: "lines", add: false, more: true, hint: "One per line: former names, trade names, abbreviations." },
      { k: "description", label: "Description (optional)", t: "area", add: false, more: true, max: 2000 },
      { k: "identifiers", label: "Outside identifiers (optional)", t: "ids", add: false, more: true, hint: "One per line as type: value, for example ein: 00-0000000." },
      { k: "founded_date", label: "Founded (optional)", t: "date", add: false, more: true, hint: "YYYY, YYYY-MM or YYYY-MM-DD." },
      { k: "closed_date", label: "Closed (optional)", t: "date", add: false, more: true, hint: "YYYY, YYYY-MM or YYYY-MM-DD." },
      { k: "notes", label: "Notes (optional)", t: "area", add: false, more: true, max: 2000, hint: "Visible to operators only." }
    ];
    var LAB = { name: "Name", kinds: "Kind", short_name: "Short name", website_url: "Web address", email: "Email", phone: "Phone", legal_name: "Legal name", aliases: "Other names",
                description: "Description", identifiers: "Identifiers", founded_date: "Founded", closed_date: "Closed", notes: "Notes", status: "Status" };
    function idsText(list) { return (list || []).map(function (i) { return i.type + ": " + i.value; }).join("\n"); }
    function mkF(f, idp, cur) {
      var wrap = mk("div"), l = mk("label", "f", f.label), el;
      if (f.t === "kinds") {
        el = mk("div"); el.id = idp + f.k; el.setAttribute("role", "group"); el.setAttribute("aria-label", f.label); l.removeAttribute("for");
        OKINDS.forEach(function (kk) {
          var lab = mk("label"), cb = mk("input"); cb.type = "checkbox"; cb.value = kk[0]; cb.checked = (cur || []).indexOf(kk[0]) >= 0;
          lab.style.display = "flex"; lab.style.gap = "8px"; lab.style.alignItems = "center"; lab.style.padding = "2px 0";
          lab.appendChild(cb); lab.appendChild(document.createTextNode(kk[1])); el.appendChild(lab);
        });
      } else if (f.t === "area" || f.t === "lines" || f.t === "ids") {
        el = mk("textarea"); el.maxLength = f.max || 2000; el.value = f.t === "lines" ? (cur || []).join("\n") : f.t === "ids" ? idsText(cur) : (cur == null ? "" : cur);
        if (f.t !== "area") el.rows = 3;
      } else {
        el = mk("input"); el.type = "text"; el.maxLength = f.t === "date" ? 10 : (f.max || 200); el.value = cur == null ? "" : String(cur);
        if (f.k === "email") el.inputMode = "email"; if (f.k === "website_url") el.inputMode = "url";
      }
      el.id = idp + f.k; if (f.t !== "kinds") l.htmlFor = el.id; wrap.appendChild(l); wrap.appendChild(el);
      if (f.hint) wrap.appendChild(mk("div", "hint", f.hint));
      var er = mk("div", "ferr"); wrap.appendChild(er);
      return { wrap: wrap, el: el, err: er, f: f };
    }
    function val(x, rec) {   // -> {v} (v = "" means empty) or {bad}
      var f = x.f, el = x.el;
      if (f.t === "kinds") { var ks = []; Array.prototype.forEach.call(el.querySelectorAll("input"), function (cb) { if (cb.checked) ks.push(cb.value); }); return ks.length ? { v: ks } : { v: "" }; }
      if (f.t === "lines") { var ls = el.value.split("\n").map(function (s) { return s.trim(); }).filter(Boolean); return ls.length ? { v: ls } : { v: "" }; }
      if (f.t === "ids") {
        var out = [], bad = false;
        el.value.split("\n").map(function (s) { return s.trim(); }).filter(Boolean).forEach(function (s) {
          var m = /^([A-Za-z][A-Za-z0-9_ ]*?)\s*:\s*(.+)$/.exec(s);
          if (!m) { bad = true; return; }
          var type = m[1].trim().toLowerCase().replace(/\s+/g, "_"), value = m[2].trim(), o = { type: type, value: value };
          ((rec && rec.identifiers) || []).forEach(function (old) { if (old.type === type && old.value === value && old.description) o.description = old.description; });
          out.push(o);
        });
        if (bad) return { bad: "Use type: value on each line, for example ein: 00-0000000." };
        return out.length ? { v: out } : { v: "" };
      }
      return { v: el.value.trim() };
    }
    function problems(res, els) {
      var ps = (res.body && res.body.error && res.body.error.problems) || [], out = [], mine = {};
      ps.forEach(function (p) { var t = OISSUE[p.issue] || "That value is not valid."; if (els[p.field]) mine[p.field] = t; else out.push((LAB[p.field] || p.field) + ": " + t); });
      if (!ps.length) out.push(adminProblem(res.status));
      return { fields: mine, other: out };
    }
    var addEls = {};
    FIELDS.forEach(function (f) { if (!f.add) return; var x = mkF(f, "roA_", null); g("AddFields").appendChild(x.wrap); addEls[f.k] = x; });

    function load() {
      var my = ++S.seq; g("Msg").textContent = ""; g("Retry").hidden = true;
      return admin("list", { limit: 200 }, "organizations").then(function (res) {
        if (my !== S.seq) return;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status !== 200 || !res.body.ok) { g("Msg").textContent = "Could not load the organizations. " + adminProblem(res.status); g("Retry").hidden = false; return; }
        S.all = res.body.data.records || []; S.loaded = true; render(); g("Checked").textContent = "Last checked " + fmtClock.format(new Date());
      });
    }
    S.load = load;
    function matches(r, q) {
      if (!q) return true;
      var hay = [r.name, r.short_name, r.legal_name].concat(r.aliases || []).join(" ").toLowerCase();
      return hay.indexOf(q) >= 0;
    }
    function render() {
      var f = g("Filter").value, q = g("Search").value.trim().toLowerCase(), list = g("List"), n = 0; list.textContent = "";
      S.all.filter(function (r) { return (!f || r.status === f) && matches(r, q); }).forEach(function (r) { list.appendChild(row(r)); n++; });
      S.newId = "";
      g("Count").textContent = n + (n === 1 ? " organization" : " organizations") + (n !== S.all.length ? " shown of " + S.all.length : "");
      g("Empty").hidden = S.all.length > 0;
    }
    function kindsLine(rec) { return (rec.kinds || []).map(function (k) { return OKIND_LABEL[k] || k; }).join(", "); }
    function row(rec) {
      var li = mk("li", rec.id === S.newId ? "isnew" : ""), head = mk("button", "head"); head.type = "button"; head.setAttribute("aria-expanded", "false");
      var top = mk("div", "top"); top.appendChild(mk("span", "vname", rec.name || "(no name)"));
      var tgl = (rec.status === "active" || rec.status === "inactive") ? statusToggle(rec, li, { coll: "organizations", on: "active", off: "inactive", label: "Organization", problem: function (res) { return problems(res, {}).other.join(" "); } }) : null;
      if (!tgl) top.appendChild(mk("span", "type", rec.status || ""));
      head.appendChild(top);
      var sub = [kindsLine(rec), rec.short_name].filter(Boolean).join(" · ");
      if (sub) head.appendChild(mk("div", "sub", sub));
      var detail = mk("div", "detail"), wrap = mk("div"), r = mk("div", "actions-row"), host = mk("div"), box = mk("div", "confirm"); box.hidden = true;
      var ed = mk("button", "", "Edit"), del = mk("button", "danger", "Delete"); ed.type = "button"; del.type = "button"; r.appendChild(ed); r.appendChild(del);
      box.appendChild(mk("div", "", "Delete " + (rec.name || "this organization") + "? It disappears from the list but the record is kept. To stop using it without deleting, set it to inactive or closed."));
      var b = mk("div", "btns"), yes = mk("button", "danger", "Delete organization"), no = mk("button", "quiet", "Cancel"), err = mk("div", "msg"); yes.type = "button"; no.type = "button"; err.setAttribute("role", "alert");
      b.appendChild(yes); b.appendChild(no); box.appendChild(b); box.appendChild(err);
      ed.addEventListener("click", function () { box.hidden = true; if (host.firstChild) host.textContent = ""; else host.appendChild(editForm(rec, host)); });
      del.addEventListener("click", function () { host.textContent = ""; box.hidden = !box.hidden; err.textContent = ""; });
      no.addEventListener("click", function () { box.hidden = true; });
      yes.addEventListener("click", function () {
        yes.disabled = true;
        admin("soft_delete", { id: rec.id }, "organizations").then(function (res) {
          yes.disabled = false;
          if (res.status === 401) { lock("That key did not work."); return; }
          if (res.status === 200 && res.body && res.body.ok) { g("Notice").textContent = "Deleted " + rec.name + "."; load(); }
          else if (res.status === 404) { g("Notice").textContent = "That organization was already gone."; load(); }
          else err.textContent = problems(res, {}).other.join(" ");
        });
      });
      wrap.appendChild(r); wrap.appendChild(host); wrap.appendChild(box); detail.appendChild(wrap);
      if (rec.legal_name) detail.appendChild(line("Legal name", rec.legal_name));
      if (rec.aliases && rec.aliases.length) detail.appendChild(line("Also known as", rec.aliases.join(", ")));
      if (rec.description) detail.appendChild(line("Description", rec.description));
      if (rec.website_url) detail.appendChild(line("Web", rec.website_url));
      if (rec.email) detail.appendChild(line("Email", rec.email));
      if (rec.phone) detail.appendChild(line("Phone", rec.phone));
      (rec.identifiers || []).forEach(function (i) { detail.appendChild(line(i.type, i.value)); });
      if (rec.founded_date) detail.appendChild(line("Founded", rec.founded_date));
      if (rec.closed_date) detail.appendChild(line("Closed", rec.closed_date));
      if (rec.status === "active" || rec.status === "inactive") { /* shown by the switch */ }
      if (rec.notes) detail.appendChild(line("Notes", rec.notes));
      detail.appendChild(line("Added", when(rec.created_at)));
      detail.appendChild(linksPanel(rec));
      head.addEventListener("click", function () { var open = li.classList.toggle("open"); head.setAttribute("aria-expanded", open ? "true" : "false"); });
      li.appendChild(head); if (tgl) { li.appendChild(tgl.btn); li.appendChild(tgl.msg); } li.appendChild(detail);
      if (rec.id === S.newId) setTimeout(function () { li.classList.remove("isnew"); }, 6000);
      return li;
    }
    // ---- Links on the card: people, venues and other organizations (organization_links), and places (location_links) ----
    var COLL_OL = "organization_links";
    var OREL = [["leads", "Leads"], ["works_for", "Works for"], ["member_of", "Member of"], ["volunteers_for", "Volunteers for"], ["teaches_for", "Teaches for"],
                ["contact_for", "Contact for"], ["part_of", "Part of"], ["affiliated_with", "Affiliated with"], ["sponsored_by", "Sponsored by"],
                ["operated_by", "Operated by"], ["succeeded_by", "Succeeded by"], ["other", "Other"]];
    var OREL_LABEL = {}; OREL.forEach(function (r) { OREL_LABEL[r[0]] = r[1]; });
    var OSUBJ = { individual: ["Person", "individuals"], venue: ["Venue", "venues"], organization: ["Organization", "organizations"] };
    var PLACE_RELS = ["operates_at", "owns", "manages", "works_at", "mailing_address_for", "billing_address_for", "delivers_to", "other"];
    var LINK_ISSUE = { required: "Required.", not_found: "That one was not found.", invalid_format: "Check the format (YYYY, YYYY-MM or YYYY-MM-DD).", invalid_value: "That value is not allowed.",
                       out_of_range: "That is too long or out of order.", duplicate: "That link already exists for these dates.", retired: "That place is retired.", not_allowed: "Not allowed.", immutable: "That cannot be changed." };
    var nameCache = {};
    function subjName(type, id) {
      var key = type + ":" + id;
      if (nameCache[key]) return Promise.resolve(nameCache[key]);
      return admin("get", { id: id }, type === "location" ? "locations" : OSUBJ[type][1]).then(function (r) {
        var d = r.status === 200 && r.body && r.body.ok ? r.body.data : null;
        var nm = d ? (d.display_name || d.name || d.given_name || (type === "location" && d.addresses && d.addresses[0] ? locAddr(d.addresses[0]) : "") || "(no name)") : "(not available)";
        if (d) nameCache[key] = nm;
        return nm;
      });
    }
    function todayStr() { var d = new Date(); return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }
    function span(l) { return (l.valid_from ? " from " + pDateOut(l.valid_from) : "") + (l.valid_to ? " until " + pDateOut(l.valid_to) : ""); }
    function linkProblems(res) {
      var ps = (res.body && res.body.error && res.body.error.problems) || [];
      if (!ps.length) return adminProblem(res.status);
      return ps.map(function (p) { return ((LAB[p.field] || { subject_id: "Who", organization_id: "Organization", relationship: "Kind of link", valid_from: "From", valid_to: "Until", title: "Title", location_id: "Place" }[p.field] || p.field)) + ": " + (LINK_ISSUE[p.issue] || "not valid."); }).join(" ");
    }
    function labeled(parent, text, el, idv) { var l = mk("label", "f", text); if (idv) { el.id = idv; l.htmlFor = idv; } parent.appendChild(l); parent.appendChild(el); return el; }
    function selectOf(opts) { var s = mk("select"); opts.forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; s.appendChild(op); }); return s; }
    function textIn(max, ph) { var i = mk("input"); i.type = "text"; i.maxLength = max; if (ph) i.placeholder = ph; i.autocomplete = "off"; return i; }

    function linksPanel(rec) {
      var wrap = mk("div", "olinks"), row2 = mk("div", "actions-row"), host = mk("div"), msg = mk("div", "msg"); msg.setAttribute("role", "alert");
      function btn(label, cls) { var b = mk("button", cls || "quiet", label); b.type = "button"; row2.appendChild(b); return b; }
      var bShow = btn("Show links"), bAdd = btn("Add link"), bPl = btn("Show places"), bAddPl = btn("Add place");
      wrap.appendChild(mk("div", "hint", "Links: who and what belongs to this organization, and where it is.")); wrap.appendChild(row2); wrap.appendChild(host); wrap.appendChild(msg);
      function open(builder) { msg.textContent = ""; if (host.firstChild && host.dataset.k === builder.k) { host.textContent = ""; host.dataset.k = ""; return; } host.textContent = ""; host.dataset.k = builder.k; builder(); }
      function actions(l, coll, li, reload) {
        var r = mk("span", "olact");
        if (!l.valid_to) {
          var e = mk("button", "quiet", "End"); e.type = "button"; r.appendChild(e);
          e.addEventListener("click", function () {
            e.disabled = true;
            var p = coll === COLL_LK ? admin("end", { id: l.id }, coll) : admin("update", { id: l.id, changes: { valid_to: todayStr() }, expected_updated_at: l.updated_at }, coll);
            p.then(function (res) { if (res.status === 401) { lock("That key did not work."); return; } if (res.status === 200 && res.body.ok) { reload(); } else { e.disabled = false; msg.textContent = res.status === 409 ? "This changed somewhere else. Show the list again." : linkProblems(res); } });
          });
        }
        var d = mk("button", "danger", "Delete"); d.type = "button"; r.appendChild(d);
        d.addEventListener("click", function () {
          if (d.dataset.sure !== "1") { d.dataset.sure = "1"; d.textContent = "Tap again to delete"; setTimeout(function () { d.dataset.sure = ""; d.textContent = "Delete"; }, 4000); return; }
          d.disabled = true;
          admin("soft_delete", { id: l.id }, coll).then(function (res) { if (res.status === 401) { lock("That key did not work."); return; } if (res.status === 200 || res.status === 404) reload(); else { d.disabled = false; msg.textContent = linkProblems(res); } });
        });
        li.appendChild(r);
      }
      function showLinks() {
        host.textContent = ""; host.dataset.k = "show"; host.appendChild(mk("div", "hint", "Loading..."));
        Promise.all([admin("list", { filters: { organization_id: rec.id }, limit: 100 }, COLL_OL), admin("list", { filters: { subject_id: rec.id }, limit: 100 }, COLL_OL)]).then(function (rs) {
          if (rs[0].status === 401 || rs[1].status === 401) { lock("That key did not work."); return; }
          host.textContent = ""; host.dataset.k = "show";
          if (rs.some(function (r) { return r.status !== 200 || !r.body.ok; })) { host.appendChild(mk("div", "msg", "Could not load. " + adminProblem(rs[0].status !== 200 ? rs[0].status : rs[1].status))); return; }
          var into = (rs[0].body.data.records || []).filter(function (l) { return !(l.subject_type === "organization" && l.subject_id === rec.id); }), outof = rs[1].body.data.records || [];
          host.appendChild(mk("div", "hint", "Linked to " + rec.name + ":"));
          if (!into.length) host.appendChild(mk("div", "empty2", "Nobody and nothing yet."));
          into.forEach(function (l) {
            var li = mk("div", "olrow"), t = mk("span", "", "Loading..."); li.appendChild(t); host.appendChild(li);
            subjName(l.subject_type, l.subject_id).then(function (nm) { t.textContent = nm + " (" + OSUBJ[l.subject_type][0].toLowerCase() + ") · " + (OREL_LABEL[l.relationship] || l.relationship) + (l.title ? " · " + l.title : "") + span(l); });
            actions(l, COLL_OL, li, showLinks);
          });
          host.appendChild(mk("div", "hint", rec.name + " is linked to:"));
          if (!outof.length) host.appendChild(mk("div", "empty2", "No other organization yet."));
          outof.forEach(function (l) {
            var li = mk("div", "olrow"), t = mk("span", "", "Loading..."); li.appendChild(t); host.appendChild(li);
            subjName("organization", l.organization_id).then(function (nm) { t.textContent = (OREL_LABEL[l.relationship] || l.relationship) + ": " + nm + (l.title ? " · " + l.title : "") + span(l); });
            actions(l, COLL_OL, li, showLinks);
          });
        });
      }
      showLinks.k = "show";
      function showPlaces() {
        host.textContent = ""; host.dataset.k = "places"; host.appendChild(mk("div", "hint", "Loading..."));
        admin("list", { filters: { subject_id: rec.id }, limit: 100 }, COLL_LK).then(function (res) {
          if (res.status === 401) { lock("That key did not work."); return; }
          host.textContent = ""; host.dataset.k = "places";
          if (res.status !== 200 || !res.body.ok) { host.appendChild(mk("div", "msg", "Could not load. " + adminProblem(res.status))); return; }
          var links = res.body.data.records || [];
          if (!links.length) { host.appendChild(mk("div", "empty2", "No place is linked to " + rec.name + ".")); return; }
          links.forEach(function (l) {
            var li = mk("div", "olrow"), t = mk("span", "", "Loading..."); li.appendChild(t); host.appendChild(li);
            subjName("location", l.location_id).then(function (nm) { t.textContent = nm + " · " + (REL[l.relationship] || l.relationship) + (l.is_primary ? " (main)" : "") + (l.description ? " · " + l.description : "") + span(l); });
            actions(l, COLL_LK, li, showPlaces);
          });
        });
      }
      showPlaces.k = "places";
      function addLink() {
        var form = mk("form", "eform"), pid = rec.id + "_al_"; form.noValidate = true; form.autocomplete = "off";
        var type = labeled(form, "What is being linked to " + rec.name + "?", selectOf([["individual", "A person"], ["venue", "A venue"], ["organization", "Another organization"]]), pid + "t");
        var q = labeled(form, "Find it by name", textIn(100, "type to search"), pid + "q"), opts = mk("div"), chosen = mk("div", "note", "Nothing chosen."), cid = "";
        form.appendChild(opts); form.appendChild(chosen);
        var rel = labeled(form, "How is it linked?", selectOf(OREL), pid + "r");
        var title = labeled(form, "Role or title (optional)", textIn(100, "for example Superintendent"), pid + "ti");
        var from = labeled(form, "From (optional)", textIn(10, "YYYY, YYYY-MM or YYYY-MM-DD"), pid + "f");
        var to = labeled(form, "Until (optional, leave empty if it still applies)", textIn(10, "YYYY, YYYY-MM or YYYY-MM-DD"), pid + "u");
        var btns = mk("div", "btns"), s = mk("button", "", "Save link"), c = mk("button", "quiet", "Cancel"); s.type = "submit"; c.type = "button"; btns.appendChild(s); btns.appendChild(c); form.appendChild(btns);
        var fm = mk("div", "msg"); fm.setAttribute("role", "alert"); form.appendChild(fm);
        function source() {
          if (type.value === "individual") return peopleList().then(function (l) { return l.map(function (p) { return { id: p.id, name: p.display_name || p.given_name || "(no name)" }; }); });
          if (type.value === "venue") return admin("list", { limit: 200 }, "venues").then(function (r) { return (r.status === 200 && r.body.ok ? r.body.data.records : []).map(function (v) { return { id: v.id, name: v.name }; }); });
          return Promise.resolve(S.all.filter(function (o) { return o.id !== rec.id; }).map(function (o) { return { id: o.id, name: o.name }; }));
        }
        function find() {
          var term = q.value.trim().toLowerCase(), kind = type.value; opts.textContent = "";
          source().then(function (list) {
            if (type.value !== kind || q.value.trim().toLowerCase() !== term) return;
            var m = list.filter(function (x) { return !term || (x.name || "").toLowerCase().indexOf(term) >= 0; }).slice(0, 8);
            if (!m.length) opts.appendChild(mk("div", "hint", "Nothing found."));
            m.forEach(function (x) { var b = mk("button", "quiet", x.name); b.type = "button"; b.addEventListener("click", function () { cid = x.id; chosen.textContent = "Chosen: " + x.name; opts.textContent = ""; }); opts.appendChild(b); });
          });
        }
        q.addEventListener("input", find); type.addEventListener("change", function () { cid = ""; chosen.textContent = "Nothing chosen."; q.value = ""; opts.textContent = ""; find(); });
        c.addEventListener("click", function () { host.textContent = ""; host.dataset.k = ""; });
        form.addEventListener("submit", function (e) {
          e.preventDefault(); fm.textContent = "";
          if (!cid) { fm.textContent = "Choose who or what to link first."; return; }
          var data = { subject_type: type.value, subject_id: cid, organization_id: rec.id, relationship: rel.value };
          if (title.value.trim()) data.title = title.value.trim(); if (from.value.trim()) data.valid_from = from.value.trim(); if (to.value.trim()) data.valid_to = to.value.trim();
          s.disabled = true;
          admin("create", { data: data }, COLL_OL).then(function (res) {
            s.disabled = false;
            if (res.status === 401) { lock("That key did not work."); return; }
            if (res.status === 200 && res.body.ok) { g("Notice").textContent = "Link saved."; showLinks(); return; }
            fm.textContent = "Could not save: " + linkProblems(res);
          });
        });
        host.appendChild(form); find();
      }
      addLink.k = "add";
      function addPlace() {
        var form = mk("form", "eform"), pid = rec.id + "_ap_"; form.noValidate = true; form.autocomplete = "off";
        var sel = labeled(form, "Which place?", selectOf([["", "Loading places..."]]), pid + "p"), places = [];
        admin("list", { limit: 200 }, "locations").then(function (r) {
          places = (r.status === 200 && r.body.ok ? r.body.data.records : []).filter(function (p) { return p.status !== "retired"; });
          sel.textContent = "";
          var first = mk("option", "", places.length ? "Choose a place" : "No places yet. Add one in Places."); first.value = ""; sel.appendChild(first);
          places.forEach(function (p) { var op = mk("option", "", p.name || (p.addresses && p.addresses[0] ? locAddr(p.addresses[0]) : "(no name)")); op.value = p.id; sel.appendChild(op); });
        });
        var rel = labeled(form, "How is it linked?", selectOf(PLACE_RELS.map(function (k) { return [k, REL[k] || k]; })), pid + "r");
        var prim = mk("input"); prim.type = "checkbox"; var pl = mk("label", "f"); pl.style.display = "flex"; pl.style.gap = "8px"; pl.style.alignItems = "center"; pl.appendChild(prim); pl.appendChild(document.createTextNode("This is the main place (for example headquarters)")); form.appendChild(pl);
        var desc = labeled(form, "A few words (optional)", textIn(300, "for example headquarters, factory"), pid + "d");
        var from = labeled(form, "From (optional)", textIn(10, "YYYY, YYYY-MM or YYYY-MM-DD"), pid + "f");
        var to = labeled(form, "Until (optional)", textIn(10, "YYYY, YYYY-MM or YYYY-MM-DD"), pid + "u");
        var btns = mk("div", "btns"), s = mk("button", "", "Save place link"), c = mk("button", "quiet", "Cancel"); s.type = "submit"; c.type = "button"; btns.appendChild(s); btns.appendChild(c); form.appendChild(btns);
        var fm = mk("div", "msg"); fm.setAttribute("role", "alert"); form.appendChild(fm);
        c.addEventListener("click", function () { host.textContent = ""; host.dataset.k = ""; });
        form.addEventListener("submit", function (e) {
          e.preventDefault(); fm.textContent = "";
          if (!sel.value) { fm.textContent = "Choose a place first."; return; }
          var data = { subject_type: "organization", subject_id: rec.id, location_id: sel.value, relationship: rel.value };
          if (prim.checked) data.is_primary = true; if (desc.value.trim()) data.description = desc.value.trim(); if (from.value.trim()) data.valid_from = from.value.trim(); if (to.value.trim()) data.valid_to = to.value.trim();
          s.disabled = true;
          admin("create", { data: data }, COLL_LK).then(function (res) {
            s.disabled = false;
            if (res.status === 401) { lock("That key did not work."); return; }
            if (res.status === 200 && res.body.ok) { g("Notice").textContent = "Place linked."; refreshPlaces(); showPlaces(); return; }
            fm.textContent = "Could not save: " + linkProblems(res);
          });
        });
        host.appendChild(form);
      }
      addPlace.k = "addplace";
      bShow.addEventListener("click", function () { open(showLinks); });
      bAdd.addEventListener("click", function () { open(addLink); });
      bPl.addEventListener("click", function () { open(showPlaces); });
      bAddPl.addEventListener("click", function () { open(addPlace); });
      return wrap;
    }
    function editForm(rec, host) {
      var form = mk("form", "eform"), els = {}; form.noValidate = true; form.autocomplete = "off";
      var more = mk("details"); more.appendChild(mk("summary", "", "More details"));
      FIELDS.forEach(function (f) { var x = mkF(f, "roe_" + rec.id + "_", rec[f.k]); (f.more ? more : form).appendChild(x.wrap); els[f.k] = x; });
      var sl = mk("label", "f", "Status"), ss = mk("select"); ss.id = "rost_" + rec.id; sl.htmlFor = ss.id;
      [["active", "Active"], ["inactive", "Inactive (kept, not used)"], ["closed", "Closed (no longer exists)"]].forEach(function (o) { var op = mk("option", "", o[1]); op.value = o[0]; ss.appendChild(op); });
      ss.value = rec.status === "merged" ? "active" : (rec.status || "active");
      var sw = mk("div"); sw.appendChild(sl); sw.appendChild(ss); form.appendChild(sw);
      form.appendChild(more);
      var btns = mk("div", "btns"), save = mk("button", "", "Save changes"), cancel = mk("button", "quiet", "Cancel"); save.type = "submit"; cancel.type = "button"; btns.appendChild(save); btns.appendChild(cancel); form.appendChild(btns);
      var msg = mk("div", "msg"); msg.setAttribute("role", "alert"); form.appendChild(msg);
      cancel.addEventListener("click", function () { host.textContent = ""; });
      form.addEventListener("submit", function (e) {
        e.preventDefault(); msg.textContent = ""; var changes = {}, bad = false;
        Object.keys(els).forEach(function (k) { els[k].err.textContent = ""; });
        Object.keys(els).forEach(function (k) {
          var x = els[k], v = val(x, rec), cur = rec[k];
          if (v.bad) { x.err.textContent = v.bad; bad = true; more.open = true; return; }
          if (v.v === "") { if (cur !== undefined) { if (k === "name") { x.err.textContent = "Required."; bad = true; } else changes[k] = null; } }
          else if (JSON.stringify(v.v) !== JSON.stringify(cur)) changes[k] = v.v;
        });
        if (ss.value !== (rec.status === "merged" ? "merged" : (rec.status || "active"))) changes.status = ss.value;
        if (bad) return;
        if (!Object.keys(changes).length) { host.textContent = ""; g("Notice").textContent = "Nothing changed."; return; }
        save.disabled = true;
        admin("update", { id: rec.id, changes: changes, expected_updated_at: rec.updated_at }, "organizations").then(function (res) {
          save.disabled = false;
          if (res.status === 401) { lock("That key did not work."); return; }
          if (res.status === 200 && res.body && res.body.ok) { S.newId = rec.id; g("Notice").textContent = "Saved changes to " + (changes.name || rec.name) + "."; load(); return; }
          if (res.status === 409) { msg.textContent = "Someone changed this organization while you were editing. Close this, tap Refresh, and try again. Nothing was overwritten."; return; }
          if (res.status === 404) { msg.textContent = "That organization is gone. Tap Refresh."; return; }
          var pr = problems(res, els); Object.keys(pr.fields).forEach(function (k) { els[k].err.textContent = pr.fields[k]; if (FIELDS.filter(function (f) { return f.k === k && f.more; }).length) more.open = true; });
          if (pr.other.length) msg.textContent = "Could not save: " + pr.other.join(" ");
        });
      });
      return form;
    }
    g("AddBtn").addEventListener("click", function () {
      g("AddForm").reset(); Object.keys(addEls).forEach(function (k) { addEls[k].err.textContent = ""; }); g("FMsg").textContent = ""; g("Notice").textContent = "";
      g("AddForm").hidden = false; g("AddBtn").hidden = true; addEls.name.el.focus();
    });
    g("CancelBtn").addEventListener("click", function () { g("AddForm").hidden = true; g("AddBtn").hidden = false; });
    g("AddForm").addEventListener("submit", function (e) {
      e.preventDefault(); g("FMsg").textContent = ""; var data = {}, bad = false;
      Object.keys(addEls).forEach(function (k) { addEls[k].err.textContent = ""; });
      Object.keys(addEls).forEach(function (k) {
        var v = val(addEls[k], null);
        if (v.bad) { addEls[k].err.textContent = v.bad; bad = true; return; }
        if (v.v !== "") data[k] = v.v;
      });
      if (!data.name) { addEls.name.err.textContent = "Required."; bad = true; }
      if (bad) return;
      g("SaveBtn").disabled = true;
      admin("create", { data: data }, "organizations").then(function (res) {
        g("SaveBtn").disabled = false;
        if (res.status === 401) { lock("That key did not work."); return; }
        if (res.status === 200 && res.body && res.body.ok) {
          S.newId = res.body.data.id; g("Notice").textContent = "Added " + res.body.data.name + "."; g("AddForm").hidden = true; g("AddBtn").hidden = false;
          g("Filter").value = "active"; g("Search").value = ""; load(); return;
        }
        var pr = problems(res, addEls); Object.keys(pr.fields).forEach(function (k) { addEls[k].err.textContent = pr.fields[k]; });
        if (pr.other.length) g("FMsg").textContent = "Could not save: " + pr.other.join(" ");
      });
    });
    g("Filter").addEventListener("change", function () { g("Notice").textContent = ""; render(); });
    g("Search").addEventListener("input", render);
    g("Refresh").addEventListener("click", function () { g("Notice").textContent = ""; load(); });
    g("Retry").addEventListener("click", load);
    S.reset = function () { S.loaded = false; S.all = []; S.newId = ""; g("List").textContent = ""; g("Count").textContent = ""; g("Checked").textContent = ""; g("Msg").textContent = ""; g("Notice").textContent = ""; g("Empty").hidden = true; g("Filter").value = "active"; g("Search").value = ""; g("AddForm").hidden = true; g("AddBtn").hidden = false; };
  }
  buildOrganization();

  function resetRosters() { Object.keys(ROSTER).forEach(function (k) { ROSTER[k].reset(); }); }

  // ---- Google sign-in. Only switched on when console/firebase-config.js holds the project's public web key; until then the page is key-only.
  function loadScript(src) { return new Promise(function (ok, no) { var s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = no; document.head.appendChild(s); }); }
  function onToken(user) {
    if (!user) { if (method === "google" && key) lock("You have been signed out."); return; }
    user.getIdToken().then(function (t) {
      if (method === "google" && key) { key = t; return; }   // a refreshed token for the session already open
      if (key) return;                                       // already in with the admin key
      if (idleStaleAtLoad) { idleStaleAtLoad = false; idleDrop(IDLE_AT); try { auth.signOut(); } catch (e) {} $("lockMsg").textContent = idleStaleMessage(); show(true); return; }   // a restored session that sat idle too long
      method = "google"; unlock(t, false);
    }).catch(function () {});
  }
  function refreshToken() {
    if (method === "google" && auth && auth.currentUser) auth.currentUser.getIdToken().then(function (t) { if (method === "google") key = t; }).catch(function () {});
  }
  function showGoogle(on) {
    $("googleBox").hidden = !on; $("keyBox").hidden = on; $("swapLink").textContent = on ? "Use admin key" : "Use Google sign-in"; $("swapLink").hidden = false;
  }
  function initGoogle() {
    var cfg = window.CONSOLE_FIREBASE;
    if (!cfg || !cfg.apiKey) return;
    var ready = window.firebase ? Promise.resolve() : loadScript(SDK + "firebase-app-compat.js").then(function () { return loadScript(SDK + "firebase-auth-compat.js"); });
    ready.then(function () {
      var fb = window.firebase;
      if (!fb.apps || !fb.apps.length) fb.initializeApp(cfg);
      auth = fb.auth();
      showGoogle(true);
      auth.onIdTokenChanged(onToken);
    }).catch(function () { /* stays key-only */ });
  }
  $("googleBtn").addEventListener("click", function () {
    if (!auth || launching) return;
    $("lockMsg").textContent = ""; idleStaleAtLoad = false;       // a deliberate sign-in is never dropped as stale
    var p = new window.firebase.auth.GoogleAuthProvider();
    p.setCustomParameters({ prompt: "select_account" });
    auth.signInWithPopup(p).catch(function (e) {
      $("lockMsg").textContent = e && e.code === "auth/popup-closed-by-user" ? "" : "Google sign-in did not complete. Try again.";
    });
  });
  $("swapLink").addEventListener("click", function (e) { e.preventDefault(); showGoogle($("googleBox").hidden); });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) refreshToken(); });
  setInterval(refreshToken, 20 * 60 * 1000);
  initGoogle();

  // ---- Automatic sign-out after inactivity (console_setting.session_timeout_minutes, set by a super admin in Access > Sign-in).
  // This locks the page in this browser; it is not a server session (the admin key itself stays valid until it is changed). The clock
  // is shared by every Console tab in this browser (localStorage); a Discovery run in progress counts as activity (it is driven from this
  // page); a remembered key or Google session that has sat idle past the limit is dropped when the page loads instead of signing in.
  // If the number cannot be read, the last known one is used, and 10 minutes if none was ever known: it fails closed, never open.
  var IDLE_AT = "console_last_active", IDLE_MIN = "console_timeout_minutes", IDLE_DEFAULT = 10, IDLE_WARN_MS = 60000;
  var idleMinutes = IDLE_DEFAULT, idleLast = Date.now(), idleWrote = 0, idleTimer = null, idleShown = false, idleStaleAtLoad = false;
  function idleGet(k) { try { return parseInt(localStorage.getItem(k) || "", 10) || 0; } catch (e) { return 0; } }
  function idleSet(k, v) { try { localStorage.setItem(k, String(v)); } catch (e) {} }
  function idleDrop(k) { try { localStorage.removeItem(k); } catch (e) {} }
  function idleClamp(n) { n = Math.round(Number(n)); return n >= 1 && n <= 480 ? n : IDLE_DEFAULT; }
  idleMinutes = idleClamp(idleGet(IDLE_MIN) || IDLE_DEFAULT);
  function idleTouch() { var t = Date.now(); idleLast = t; if (t - idleWrote > 5000) { idleWrote = t; idleSet(IDLE_AT, t); } }
  function idleLastActive() { return Math.max(idleLast, idleGet(IDLE_AT)); }
  function idleBusy() { return !!(window.DiscoveryStation && window.DiscoveryStation.busy && window.DiscoveryStation.busy()); }
  function idleWarn(ms) {
    var w = $("idleWarn"); if (!w) return;
    if (!ms) { if (idleShown) { w.hidden = true; idleShown = false; } return; }
    var sec = Math.max(1, Math.ceil(ms / 1000)); $("idleCount").textContent = (sec >= 60 ? Math.floor(sec / 60) + ":" + ("0" + (sec % 60)).slice(-2) : sec + " second" + (sec === 1 ? "" : "s"));
    if (!idleShown) { w.hidden = false; idleShown = true; }
  }
  function idleTick() {
    if (!key) { idleWarn(0); return; }
    if (idleBusy()) idleTouch();
    var left = idleMinutes * 60000 - (Date.now() - idleLastActive());
    if (left <= 0) { idleWarn(0); lock("You were signed out after " + idleMinutes + " minute" + (idleMinutes === 1 ? "" : "s") + " without activity. Sign in again."); return; }
    idleWarn(left <= IDLE_WARN_MS ? left : 0);
  }
  function idleStart() {   // a person is signed in: start the clock and read the super admin's number
    idleTouch();
    if (!idleTimer) idleTimer = setInterval(idleTick, 1000);
    if (!can("view_console")) return;                                  // this person may not read the setting: keep the last known number (no refused call)
    adminCall("list", { limit: 1 }, "console_settings").then(function (r) {
      var recs = r.status === 200 && r.body && r.body.ok && r.body.data && r.body.data.records;
      if (!recs) return;                                              // could not read: keep the last known number
      idleMinutes = idleClamp(recs.length ? recs[0].session_timeout_minutes : IDLE_DEFAULT); idleSet(IDLE_MIN, idleMinutes);
    });
  }
  function idleEnd() { idleWarn(0); idleDrop(IDLE_AT); idleLast = Date.now(); }   // locked: forget the old activity time too (a later sign-in must not inherit it)
  ["pointerdown", "keydown", "wheel", "touchstart", "scroll"].forEach(function (ev) {
    document.addEventListener(ev, function () { if (!key) return; idleTouch(); if (idleShown) idleWarn(0); }, { capture: true, passive: true });
  });
  $("idleStay").addEventListener("click", function () { idleTouch(); idleWarn(0); });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) idleTick(); });
  idleStaleAtLoad = idleGet(IDLE_AT) > 0 && Date.now() - idleGet(IDLE_AT) > idleMinutes * 60000;   // a saved session that sat idle past the limit
  function idleStaleMessage() { return "You were signed out after " + idleMinutes + " minute" + (idleMinutes === 1 ? "" : "s") + " without activity. Sign in again."; }

  var saved = getKey();
  if (saved.key && idleStaleAtLoad) { idleStaleAtLoad = false; setKey('', false); idleDrop(IDLE_AT); $("lockMsg").textContent = idleStaleMessage(); show(true); }
  else if (saved.key) { $("rememberBox").checked = saved.remember; unlock(saved.key, saved.remember); } else show(true);
})();
