/* Shared data tables for the Console: the three collection names the People, Places and address code read and write, and the two word tables for how a
   place relates to a person or an organization. One owner (DT-33); before this they sat in console.js and reached the stations through the kit doors
   colls, rel and personRels. Plain data, no behaviour, nothing to empty on sign-out. Loaded by index.html before console.js, so everything below can read it. */
(function () {
  "use strict";
  window.ConsoleData = {
    COLL_P: "individuals",   // the People collection
    COLL_L: "locations", COLL_LK: "location_links",   // Places, and the links from a place to a person or an organization
    REL: { resides_at: "Lives here", mailing_address_for: "Mailing address", billing_address_for: "Billing address", works_at: "Works here",
      owns: "Owns", manages: "Manages", operates_at: "Operates here", delivers_to: "Delivers here", other: "Other" },
    PERSON_RELS: ["resides_at", "mailing_address_for", "billing_address_for", "works_at", "owns", "other"]   // the relations offered on a person's address
  };
})();
