/* The Help drawer for the Console: the manuals (one page per station), the step-by-step Workflows, and the drawer that shows them. Moved out of
   console.js (H-1) with the code unchanged. The station list (ids, names, blurbs) stays in console.js and comes through ConsoleKit.surfaces();
   the manual text for each station is MANUALS below. Not a station: no show, nothing to empty (closing the drawer is close(), called by console.js
   when the Console locks or the page changes). Loaded by index.html after console.js and before the stations. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var $ = function (id) { return document.getElementById(id); };
  var mk = K.mk, goTo = K.go, SURFACES = K.surfaces();
  function surfaceById(id) { for (var i = 0; i < SURFACES.length; i++) if (SURFACES[i].id === id) return SURFACES[i]; return null; }

  // ---- The manuals, one per station (the station list itself is SURFACES in console.js)
  var MANUALS = {
    requests:
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
        '<h3>Try this</h3><ul><li>Register on the website in another window, watch the card appear, tap Put in a class…, build a class for it, and watch the chip turn to Placed.</li></ul>',
    venues:
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
        '<h3>Try this</h3><ul><li>Add a venue, edit it, add a room, then open Rooms: 1 and change the room size.</li></ul>',
    classes:
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
        '<h3>Try this</h3><ul><li>Add a one on one class, then edit it and give it a venue, a room and a start time.</li></ul>',
    people:
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
        '<h3>Try this</h3><ul><li>Add two people with nearly the same name, merge one into the other, then undo it from Merge history.</li></ul>',
    places:
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
        '<h3>Try this</h3><ul><li>Add an address to a person, then add a second person at the same address and see the ship offer the saved place.</li></ul>',
    instructors:
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
        '<h3>Try this</h3><ul><li>Add a new instructor, then open their card and add a bio and Tuesday hours.</li></ul>',
    students:
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
        '<h3>Try this</h3><ul><li>Add two friends as students, then remove one and add them back.</li></ul>',
    curriculums:
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
        '<h3>Try this</h3><ul><li>Add Introduction to AI Use as one session of 60 minutes.</li></ul>',
    attendance:
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
        '</ul>',
    organizations:
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
        '<h3>Try this</h3><ul><li>Add Ozo Coffee as a business, then search for it.</li></ul>',
    messages:
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
        '</ul>',
    discovery:
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
        '<h3>Try this</h3><ul><li>Estimate a small run for one library type in a region, open the prompts, read them, then press Go.</li></ul>',
    access:
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
        '<h3>Try this</h3><ul><li>Invite a second Google account as Region head, sign in with it in another browser, and see which stations it gets.</li></ul>',
    activity:
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
        '<h3>Try this</h3><ul><li>Edit a venue, then open Activity and find the edit. Tap Change history on the venue card to see only that venue.</li></ul>',
    performance:
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
        '<h3>Try this</h3><ul><li>Sign out, sign in again, then Refresh here and look at the newest row.</li></ul>'
  };

    var mOpen = null, mScroll = {}, mOpener = null, mPages = {};

  // ---- The manual pages and the buttons that open them (built once, at load)
  (function () {
    ["overlayBtns"].forEach(function (host) {
      SURFACES.forEach(function (sf) {
        var b = document.createElement("button"); b.type = "button"; b.dataset.m = sf.id; b.setAttribute("aria-pressed", "false"); b.textContent = sf.short || sf.name;
        $(host).appendChild(b);
      });
    });
    var sc = $("manualScroll");
    SURFACES.forEach(function (sf) {
      var pg = document.createElement("div"); pg.className = "mpage"; pg.hidden = true; pg.innerHTML = MANUALS[sf.id]; sc.appendChild(pg); mPages[sf.id] = pg;
    });
  })();

  // ---- The drawer
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


  // ---- Buttons, keys and sizes
  $("manualClose").addEventListener("click", closeManual);
  document.addEventListener("click", function (e) {   // a manual button (data-m) opens that manual; data-go stays console.js's
    var t = e.target.closest ? e.target.closest("[data-go],[data-m]") : null;
    if (!t || t.dataset.go || !t.dataset.m) return;
    openManual(t.dataset.m, t);
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && mOpen && !document.querySelector("dialog[open]")) closeManual(); });
  window.addEventListener("resize", function () { if (mOpen) $("manual").style.setProperty("--hh", $("topbar").offsetHeight + "px"); });

  window.ConsoleHelp = { close: closeManual, openWorkflows: openWorkflows };
})();
