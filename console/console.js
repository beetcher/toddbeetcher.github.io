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
    if (r !== "requests") { if (window.RequestsStation) window.RequestsStation.stop(); if (r === "venues" && window.VenuesStation) window.VenuesStation.show(); if (r === "classes" && window.ClassesStation) window.ClassesStation.show(); if (r === "people" && window.PeopleStation) window.PeopleStation.show(); if (r === "places" && window.PlacesStation) window.PlacesStation.show(); if (r === "curriculums" && window.CurriculumStation) window.CurriculumStation.show(); if (r === "instructors" && window.InstructorsStation) window.InstructorsStation.show(); if (r === "students" && window.StudentsStation) window.StudentsStation.show(); if (r === "organizations" && window.OrganizationsStation) window.OrganizationsStation.show(); }
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
    setKey("", false); key = ""; if (window.RequestsStation) window.RequestsStation.reset(); if (window.VenuesStation) window.VenuesStation.reset(); if (window.ClassesStation) window.ClassesStation.reset(); if (window.CurriculumStation) window.CurriculumStation.reset(); if (window.InstructorsStation) window.InstructorsStation.reset(); if (window.StudentsStation) window.StudentsStation.reset(); resetPlaced(); if (window.PeopleStation) window.PeopleStation.reset(); if (window.PlacesStation) window.PlacesStation.reset(); if (window.OrganizationsStation) window.OrganizationsStation.reset(); if (window.ConsoleNames) window.ConsoleNames.reset(); if (window.AttendanceStation) window.AttendanceStation.reset(); if (window.DiscoveryStation) window.DiscoveryStation.reset(); if (window.AccessStation) window.AccessStation.reset(); if (window.ActivityStation) window.ActivityStation.reset(); if (window.PerformanceStation) window.PerformanceStation.reset(); if (window.MessagesStation) window.MessagesStation.reset();
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
    netOk(); if (window.VenuesStation) window.VenuesStation.forget(); if (window.ClassesStation) window.ClassesStation.forget(); if (window.CurriculumStation) window.CurriculumStation.forget(); if (window.InstructorsStation) window.InstructorsStation.forget(); if (window.StudentsStation) window.StudentsStation.forget(); if (window.PeopleStation) window.PeopleStation.forget(); if (window.PlacesStation) window.PlacesStation.forget();
    if (window.OrganizationsStation) window.OrganizationsStation.forget();
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
                        openWorkflows: function () { return openWorkflows.apply(null, arguments); }, attLine: function (r, withClass) { return window.AttendanceStation.attLine(r, withClass); }, afNext: function () { return ++afSeq; }, forgetPeople: function () { window.PeopleStation.forgetPick(); },
                        // Added for the Venues station (V-4). Functions that point at the places, people and shared helpers still in this file.
                        lProblems: function () { return lProblems.apply(null, arguments); }, placeInput: function () { return placeInput.apply(null, arguments); }, placeText: function () { return placeText.apply(null, arguments); },
                        forgetSavedPlaces: function () { window.ConsoleAddresses.forgetSaved(); }, peopleList: function () { return window.PeopleStation.list.apply(null, arguments); }, peopleMatches: function () { return window.PeopleStation.matches.apply(null, arguments); },
                        pFull: function () { return window.PeopleStation.full.apply(null, arguments); }, statusToggle: function () { return statusToggle.apply(null, arguments); }, askDiscard: function () { return askDiscard.apply(null, arguments); },
                        // Added for the Instructors and Students stations (RO-2): the address form, the People problem words, the Places refresh, the collection names, and People's stale flags.
                        addrForm: function () { return addrForm.apply(null, arguments); }, pProblems: function () { return window.PeopleStation.problems.apply(null, arguments); }, refreshPlaces: function () { refreshPlaces(); },
                        colls: function () { return { P: COLL_P, L: COLL_L, LK: COLL_LK }; }, peopleStale: function () { window.PeopleStation.stale(); },
                        // Added for the Organizations station (OR-2): People's date words, Places' one-line address, the Places relation words (a function: defined later in this file).
                        pDateOut: function () { return window.PeopleStation.dateOut.apply(null, arguments); }, locAddr: function () { return locAddr.apply(null, arguments); }, rel: function () { return REL; },
                        // Added for the Places station (PP-2): the skeleton helpers and the current page, which it needs and cannot own.
                        skelOn: function () { return skelOn.apply(null, arguments); }, skelOff: function () { return skelOff.apply(null, arguments); }, currentRoute: function () { return currentRoute(); },
                        // Added for the People station (PP-5): the person history forwarder, and the person relation list (data, stays here).
                        personHistory: function () { return personHistory.apply(null, arguments); }, personRels: function () { return PERSON_RELS; } };   // R-2 (Journal): attWord, roleWord, historyBtn. R-3 (Requests): fetchT to consts. consts holds constants only. A-1 (Attendance): attConsts to assignForm.
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
      if (/^person\./.test(p.field)) return (window.PeopleStation.words().label[p.field.slice(7)] || p.field) + ": " + (p.issue === "invalid_format" && /email$/.test(p.field) ? "That email address does not look right." : (window.PeopleStation.words().issue[p.issue] || "That value is not valid."));
      if (p.field === "scheduled_class_id") return "Choose a class.";
      if (p.field === "role") return "Choose a role.";
      if (p.field === "individual_id" && p.issue === "address_required") return "An instructor needs an address first. Add the person in the Instructors station with their address, then add them here.";
      if (p.field === "individual_id") return p.issue === "required" ? "Choose someone." : "We could not find them.";
      if (p.field === "order") return "Place has to be a whole number from 1 to 50.";
      return p.field + ": " + (window.PeopleStation.words().issue[p.issue] || p.issue);
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

  var COLL_P = "individuals";   // the People collection name stays here as data (the kit hands it to the rosters and Places); the People station is people.js (PP-5)

  // Places moved to places.js and addresses.js (PP-2). The data tables stay here (the rosters and Organizations read them at load); the helpers below forward so the code that stays reads as before.
  var COLL_L = "locations", COLL_LK = "location_links";
  var REL = { resides_at: "Lives here", mailing_address_for: "Mailing address", billing_address_for: "Billing address", works_at: "Works here",
              owns: "Owns", manages: "Manages", operates_at: "Operates here", delivers_to: "Delivers here", other: "Other" };
  var PERSON_RELS = ["resides_at", "mailing_address_for", "billing_address_for", "works_at", "owns", "other"];
  function addrForm() { return window.ConsoleAddresses.addrForm.apply(null, arguments); }
  function lProblems() { return window.ConsoleAddresses.lProblems.apply(null, arguments); }
  function locAddr() { return window.ConsoleAddresses.locAddr.apply(null, arguments); }
  function locSummary() { return window.ConsoleAddresses.locSummary.apply(null, arguments); }
  function placeInput() { return window.ConsoleAddresses.placeInput.apply(null, arguments); }
  function placeText() { return window.ConsoleAddresses.placeText.apply(null, arguments); }
  function refreshPlaces() { window.PlacesStation.refresh(); }



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
