/* Shared data tables for the Console: the three collection names the People, Places and address code read and write, the two word tables for how a
   place relates to a person or an organization, and the two person word tables (field names, problem words; DT-34). One owner (DT-33); before this they sat in console.js and reached the stations through the kit doors
   colls, rel and personRels. Plain data, no behaviour, nothing to empty on sign-out. Loaded by index.html before console.js, so everything below can read it. */
(function () {
  "use strict";
  window.ConsoleData = {
    COLL_P: "individuals",   // the People collection
    COLL_L: "locations", COLL_LK: "location_links",   // Places, and the links from a place to a person or an organization
    REL: { resides_at: "Lives here", mailing_address_for: "Mailing address", billing_address_for: "Billing address", works_at: "Works here",
      owns: "Owns", manages: "Manages", operates_at: "Operates here", delivers_to: "Delivers here", other: "Other" },
    PERSON_RELS: ["resides_at", "mailing_address_for", "billing_address_for", "works_at", "owns", "other"],   // the relations offered on a person's address
    PLABEL: { given_name: "Given name", middle_names: "Middle names", family_name: "Family name", name_to_use: "Name to use", pronouns: "Pronouns",
      birth_date: "Birth date", birth_date_certainty: "Birth date certainty", preferred_language: "Preferred language", time_zone: "Time zone",
      requires_interpreter: "Interpreter", email: "Email", phone: "Phone", backup_email: "Backup email", backup_phone: "Backup phone", prefers_email: "Preferred way to reach", status: "Status", notes: "Notes", survivor_id: "Person to keep", duplicate_id: "This person", reason: "Reason", id: "Person" },   // person field names in plain words (People, and the failed-attendance sentence)
    PISSUE: { required: "Required.", invalid_format: "That value is not valid.", out_of_range: "Too long or too short.", invalid_value: "That value is not valid.",
      invalid_type: "That value is not valid.", not_found: "That person was not found.", same_as_survivor: "Pick a different person.",
      conflict_restricted_detail: "Both people hold protected details. That needs a person to sort out first.",
      too_many_links: "Too many records point at this person to merge in one go.", snapshots_erased: "One of the people has been erased, so this cannot be undone.",
      not_merged: "This merge was already undone.", already_erased: "Already erased.", in_use: "Protected details exist for this person.", immutable: "That cannot be changed.",
      inconsistent: "That does not fit with the other answers." }   // person problem words
  };
})();
