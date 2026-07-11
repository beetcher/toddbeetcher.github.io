# Test Phone Router

Firebase Cloud Functions (2nd gen) service that acts as the messaging boundary between a Twilio-compatible application, a Test Phone emulator, and Firestore.

## Firebase Project

- **Project ID:** `test-phone-router`
- **Region:** `us-central1`
- **Console:** https://console.firebase.google.com/project/test-phone-router/overview

## Endpoints

All endpoints are exposed under a single Cloud Run URL after deployment.
During local development they're at: `http://127.0.0.1:5001/test-phone-router/us-central1/router`

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/incoming` | Simulated SMS from Test Phone → forward to app webhook |
| `POST` | `/messages` | Application → queue message for a Test Phone |
| `GET`  | `/poll?phoneNumber=+1...` | Test Phone polls for pending messages |
| `GET`  | `/config` | Read routing table (triggers seed initialization on first call) |
| `PUT`  | `/config` | Replace routing table |

## Firestore Collections

- **`routing_table`** — document ID is E.164 phone number, field `webhookUrl` is target app
- **`pending_messages`** — one document per queued outbound message, keyed by MessageSid
- **`seed_meta`** — single document `init` with field `seeded: boolean` (initialization marker)

Firestore security rules deny all direct client access. Only Cloud Functions (Admin SDK) can read/write.

---

## Reference Applications

Three small webhook endpoints that provide known-good targets for end-to-end Test Phone testing.
They live in the same Firebase project as the Router, deployed as separate Cloud Functions.

Each reference app:
1. Receives a Twilio-compatible inbound webhook from the Router.
2. Generates a response specific to its behavior.
3. Sends that response back through the Router's `/messages` endpoint.
4. Does not communicate directly with Test Phone or write to Firestore.

### Reference App 1 — Echo

| | |
|---|---|
| **Fake number** | `+15550000001` |
| **Webhook URL** | `https://echo-112367027974.us-central1.run.app` |
| **Behavior** | Returns the inbound Body unchanged |

Use to verify the complete message path with the least possible application logic.

### Reference App 2 — Random Response

| | |
|---|---|
| **Fake number** | `+15550000002` |
| **Webhook URL** | `https://randomresponse-112367027974.us-central1.run.app` |
| **Behavior** | Returns one of 10 hard-coded neutral responses at random |

Use to verify that application-side logic executes before a response is returned.

### Reference App 3 — Random Joke

| | |
|---|---|
| **Fake number** | `+15550000003` |
| **Webhook URL** | `https://randomjoke-112367027974.us-central1.run.app` |
| **Behavior** | Returns one of 10 hard-coded jokes at random |

### Round-Trip Flow

```
Test Phone
  → POST /incoming (From=myNumber, To=+1555000000X, Body=text)
Router
  → POST https://<reference-app>.run.app (Twilio form payload)
Reference App
  → POST /messages (From=+1555000000X, To=myNumber, Body=response)
Router
  → queues message in pending_messages
Test Phone
  ← GET /poll → receives response
```

### Verifying Reference Endpoints Independently

```bash
# Echo
curl -X POST https://echo-112367027974.us-central1.run.app \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=+15551234567&To=+15550000001&Body=hello"

# Random Response
curl -X POST https://randomresponse-112367027974.us-central1.run.app \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=+15551234567&To=+15550000002&Body=test"

# Random Joke
curl -X POST https://randomjoke-112367027974.us-central1.run.app \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=+15551234567&To=+15550000003&Body=test"
```

---

## Seed Configuration

### File Location

`src/config/seed.config.json` (version-controlled; compiled into `lib/config/seed.config.json` for deployment)

### Contents

```json
[
  { "phoneNumber": "+15550000001", "webhookUrl": "https://echo-112367027974.us-central1.run.app" },
  { "phoneNumber": "+15550000002", "webhookUrl": "https://randomresponse-112367027974.us-central1.run.app" },
  { "phoneNumber": "+15550000003", "webhookUrl": "https://randomjoke-112367027974.us-central1.run.app" }
]
```

### Phone Number Range Used

`+15550000001` through `+15550000003`. Area code 555 has no real geographic assignment in the NANP; these numbers pass the Router's normalizer (`+1` + 10 digits) and are safe fictional test numbers.

### Empty Configuration

An empty routing configuration is defined as **zero documents in the `routing_table` collection**. This is the condition tested by `GET /config` before returning the current table.

### Seed Initialization Rules

The Router distinguishes three cases using a durable Firestore marker (`seed_meta/init`, field `seeded: boolean`):

| State | `seed_meta/init` | `routing_table` | Result |
|---|---|---|---|
| Never initialized, empty | does not exist | empty | Seed records written; marker set |
| Never initialized, non-empty | does not exist | has entries | Leave table unchanged; marker set |
| Already initialized | `{ seeded: true }` | any | Return immediately, never modify |

**Critical:** Once `seeded: true` is written, the routing table is never modified by the seed process — even if the developer later deletes every entry. The developer's intentional empty table stays empty on every subsequent request.

### Initialization Timing

Seed initialization runs lazily on the first call to `GET /config` and `POST /incoming`. Both handlers call `ensureSeeded(db)` before any routing table read, ensuring the browser's Config Editor and message routing see consistent state.

Atomicity is provided by a Firestore transaction: the initialization marker and all seed records are written in a single transaction. Concurrent Cloud Functions instances race to write the marker; only one wins, and the others abort their transaction cleanly.

---

## Verify Current Cloud Routing Table

```bash
curl https://router-in7qh2jyoq-uc.a.run.app/config
```

Expected output on a freshly-initialized, never-seeded installation:
```json
[
  {"phoneNumber":"+15550000001","webhookUrl":"https://echo-112367027974.us-central1.run.app"},
  {"phoneNumber":"+15550000002","webhookUrl":"https://randomresponse-112367027974.us-central1.run.app"},
  {"phoneNumber":"+15550000003","webhookUrl":"https://randomjoke-112367027974.us-central1.run.app"}
]
```

---

## Security — Reference Applications

The three reference webhooks are publicly invocable with no authentication — the same posture as the Router's Configuration API, which is documented below.

**First thing to lock down if any of these URLs are ever exposed on a persistent or discoverable production URL:** add authentication (e.g., a shared secret in an `X-Webhook-Token` header checked at the function boundary). This applies to the reference apps before the Config API since the reference apps are the webhook targets that an attacker could invoke directly.

## Known Security Risk — Config API

The Configuration API has no authentication. Anyone who discovers the `/config` URL can replace the routing table and point it at an arbitrary public webhook URL — effectively turning the Router into an open relay.

This is an accepted, intentional risk for a development-only tool with no real user data or production traffic. The SSRF guard (blocking localhost/private IP targets) does not prevent this against public URLs.

**First thing to lock down if this Router is ever exposed on a persistent or discoverable URL:** add authentication to the Config API (e.g., a pre-shared API key in an `Authorization` header checked at the function boundary).

## SSRF Guard

The Config API validates webhook URLs and rejects targets pointing at localhost or private IP ranges (`127.x.x.x`, `10.x.x.x`, `192.168.x.x`, `172.16–31.x.x`). This guard lives in `src/ssrfGuard.ts` and can be extended there without restructuring callers.

**Integration tests:** Because the SSRF guard blocks localhost URLs, the integration tests in `tests/integration/` seed the routing table directly into the Firestore emulator via the Admin SDK rather than going through `PUT /config`. This is the expected pattern for any test that needs a localhost webhook.

## MessageSid Idempotency

The Router uses the same `MessageSid` on both the original forward attempt and the single retry (inbound endpoint). Applications that dedupe on `MessageSid` — as Twilio-integrated apps are expected to — will not double-process a message whose first attempt succeeded but whose response was lost in transit.

The mock webhook in `tests/integration/mockWebhook.js` logs a warning if it ever receives the same `MessageSid` twice, so a retry-caused duplicate is caught in testing rather than silently masked.

## Poll Delivery Guarantee

The `/poll` endpoint sends the HTTP response **before** marking messages as `retrieved` in Firestore (at-least-once delivery). If the Firestore commit fails after the response is sent, messages stay in `pending` state and are re-delivered on the next poll — the Emulator's `MessageSid` dedupe in `app.js` absorbs the duplicate without showing a second bubble.

The unavoidable edge case: if the HTTP response reaches the client successfully but the Firestore commit also succeeds after a network timeout on the response, the message is marked retrieved and won't be re-delivered. This is indistinguishable from the "response arrived, commit succeeded" happy path from the server's perspective. For a polling interval of 1 second and a local/cloud-run deployment, this case is negligible in practice.

## Local Development

```bash
cd router
npm install
npm run serve        # builds TypeScript + starts Firebase Emulator on ports 5001 (functions) and 8080 (Firestore)
```

Emulator UI: http://localhost:4000

## Running Tests

```bash
npm test             # unit tests only (phone normalizer, SSRF guard, Twilio payload, reference apps, seed config)
npm run test:integration  # endpoint + round-trip tests (requires emulator running)
```

## Deployment

```bash
cd router
npm run deploy
```

After deploying, Firebase outputs the Cloud Run URL for the `router` function. Copy that URL into `testphone/js/routerConfig.js` as `ROUTER_BASE_URL`.

## Manual Browser Verification (End-to-End)

After deployment, to verify the complete Test Phone → Router → Reference App → Router → Test Phone round trip:

1. Open Test Phone in a browser (e.g., `testphone/index.html` served locally or via GitHub Pages).
2. Enter **My Phone Number** (e.g., `5551234567`).
3. Enter **Destination** `5550000001` (Echo).
4. Type any message body and click **Send**.
5. Confirm the same text returns as an incoming message within a few seconds.
6. Change destination to `5550000002` (Random Response) and send any message.
7. Confirm one of the 10 neutral responses arrives.
8. Change destination to `5550000003` (Random Joke) and send any message.
9. Confirm one of the 10 jokes arrives.
10. Open Config Editor (Ctrl+Shift+C) and edit or delete a reference mapping.
11. Confirm the change persists after closing and reopening the editor.
12. If desired, delete all entries and save — reopening the editor must show an empty table (no reseeding).

## Update Base URL After Deployment

Edit `testphone/js/routerConfig.js`:

```js
const ROUTER_BASE_URL = 'https://router-<hash>-uc.a.run.app';
```

This is the only file that needs to change when the Router moves to a new URL.
