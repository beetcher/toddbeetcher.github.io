/* Word tables for the Console: plain-language words for things the server stores as codes. The message kinds and the reasons a message was not sent,
   the roles and statuses of a person in a class (and `att`, the attendance status tables), and the person field names and problem words used in failed-save sentences. One owner (DT-8): before this
   they sat in console.js (and, for the person words, in people.js and data.js) and reached the stations through the kit doors words and attConsts.
   Plain data, no behaviour, nothing to empty on sign-out. Loaded by index.html before console.js. */
(function () {
  "use strict";
  var ATT = "attendances";
  var ATT_STATUSES = ["assigned", "waitlisted", "confirmed", "attended", "late", "no_show", "declined", "withdrawn", "cancelled"];
  var ATT_RANK = { assigned: 1, waitlisted: 1, confirmed: 2, attended: 3, late: 3, no_show: 3 };   // how far a placement has come: placed, confirmed, then the class happened
  var ATT_GONE = { declined: 1, withdrawn: 1, cancelled: 1 };   // a request with only these is back to waiting
  var ATT_OPEN = { assigned: 1, waitlisted: 1, confirmed: 1 };   // a placement still open: ending it sends emails
  function leftOpen(from, to) { return !!ATT_OPEN[from] && !!ATT_GONE[to]; }
  var ATT_OFF = { waitlisted: 1, declined: 1, withdrawn: 1, cancelled: 1 };   // statuses that do not hold a seat
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
  window.ConsoleWords = {
    corrKind: { placement_confirmation: "Placement confirmation", request_received: "Request received" },
    reasonWord: { no_contact: "no email or phone on file", channel_unavailable: "they prefer a text, so contact them by hand", no_template: "no message is set up for this",
                    incomplete: "a detail the message needs is missing", invalid_context: "the details were not valid", unknown_kind: "unknown kind of message",
                    time_budget: "ran out of time", internal_error: "a problem on our side", cms_off: "messaging is off", log_only: "test mode, nothing is really sent",
                    duplicate: "already sent", excluded: "left out on purpose", muted: "they asked not to be contacted" },
    roleWord: { student: "Student", primary_instructor: "Lead instructor", instructor: "Instructor" },
    attWord: { assigned: "Assigned", confirmed: "Confirmed", waitlisted: "On the waiting list", declined: "Declined", withdrawn: "Withdrawn", cancelled: "Cancelled", attended: "Attended", late: "Late", no_show: "Did not show" },
    personLabel: { given_name: "Given name", middle_names: "Middle names", family_name: "Family name", name_to_use: "Name to use", pronouns: "Pronouns",
    birth_date: "Birth date", birth_date_certainty: "Birth date certainty", preferred_language: "Preferred language", time_zone: "Time zone",
    requires_interpreter: "Interpreter", email: "Email", phone: "Phone", backup_email: "Backup email", backup_phone: "Backup phone", prefers_email: "Preferred way to reach", status: "Status", notes: "Notes", survivor_id: "Person to keep", duplicate_id: "This person", reason: "Reason", id: "Person" },   // person field names, in plain words
    att: { ATT: ATT, ATT_STATUSES: ATT_STATUSES, ATT_RANK: ATT_RANK, ATT_GONE: ATT_GONE, ATT_OPEN: ATT_OPEN, ATT_OFF: ATT_OFF, ATT_TONE: ATT_TONE, leftOpen: leftOpen },   // the attendance statuses and tones
    personIssue: { required: "Required.", invalid_format: "That value is not valid.", out_of_range: "Too long or too short.", invalid_value: "That value is not valid.",
    invalid_type: "That value is not valid.", not_found: "That person was not found.", same_as_survivor: "Pick a different person.",
    conflict_restricted_detail: "Both people hold protected details. That needs a person to sort out first.",
    too_many_links: "Too many records point at this person to merge in one go.", snapshots_erased: "One of the people has been erased, so this cannot be undone.",
    not_merged: "This merge was already undone.", already_erased: "Already erased.", in_use: "Protected details exist for this person.", immutable: "That cannot be changed.",
    inconsistent: "That does not fit with the other answers." }   // person problem words
  };
})();
