/* Console settings: the one place that says WHICH organization's Console this is and WHERE its server doors are.
   Read before anything else (before sign-in). To point the Console somewhere else, change this file only.
   These values are NOT secrets: every visitor's browser receives them. (The Google sign-in web settings stay in firebase-config.js.)
   Colours, logo, hero image and wording join this file when the new shell is built (master plan, Phase 1). */
window.CONSOLE_CONFIG = {
  appId: "launch",        // names the browser's saved-key slot; do not change for a live Console
  brandName: "LAUNCH",    // shown in the top bar
  timeouts: { readSeconds: 20, writeSeconds: 60 },   // how long to wait for the server before saying so (writes wait longer: emails are slow)
  endpoints: {
    records: "https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_console_records",
    admin: "https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_admin",
    discovery: "https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_discovery"
  }
};
