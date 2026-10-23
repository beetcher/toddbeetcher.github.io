/* Console settings: the one place that says WHICH organization's Console this is and WHERE its server doors are.
   Read before anything else (before sign-in). To point the Console somewhere else, change this file only.
   These values are NOT secrets: every visitor's browser receives them. (The Google sign-in web settings stay in firebase-config.js.)
   Colours, logo, hero image and wording join this file when the new shell is built (master plan, Phase 1). */
window.CONSOLE_CONFIG = {
  appId: "launch",        // names the browser's saved-key slot; do not change for a live Console
  brandName: "LAUNCH",    // shown in the top bar and on the sign-in screen
  // Look of this Console. To rebrand it, change these lines (put the files in assets/). A settings page for a super admin replaces this later (parking lot CP-9).
  logo: "assets/console-touch-180.png",         // sign-in screen (square, 180 px or larger); the same mark as the tab icon
  logoSmall: "assets/launch-tile-mobile.webp",  // top bar (square, shown at 40 px)
  hero: {                                       // the picture beside the sign-in form; remove "image" to show no picture
    image: "assets/bridge.webp",                // 3:2 works best (1200 x 800)
    alt: "Two crew members in starship uniforms grin over a glowing warp engine, then high-five inside the starship BFN-1 as it flies into a galaxy.",
    caption: ""                                 // optional line under the picture
  },
  icons: { "16": "assets/console-favicon-16.png", "32": "assets/console-favicon-32.png", "48": "assets/console-favicon-48.png", touch: "assets/console-touch-180.png" },   // browser tab icon and phone home-screen icon
  timeouts: { readSeconds: 20, writeSeconds: 60 },   // how long to wait for the server before saying so (writes wait longer: emails are slow)
  endpoints: {
    records: "https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_console_records",
    admin: "https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_admin",
    discovery: "https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_discovery"
  }
};
