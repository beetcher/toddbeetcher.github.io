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
| `GET`  | `/config` | Read routing table |
| `PUT`  | `/config` | Replace routing table |

## Firestore Collections

- **`routing_table`** — document ID is E.164 phone number, field `webhookUrl` is target app
- **`pending_messages`** — one document per queued outbound message, keyed by MessageSid

Firestore security rules deny all direct client access. Only Cloud Functions (Admin SDK) can read/write.

## MessageSid Idempotency

The Router uses the same `MessageSid` on both the original forward attempt and the single retry (inbound endpoint). Applications that dedupe on `MessageSid` — as Twilio-integrated apps are expected to — will not double-process a message whose first attempt succeeded but whose response was lost in transit.

The mock webhook in `tests/integration/mockWebhook.js` logs a warning if it ever receives the same `MessageSid` twice, so a retry-caused duplicate is caught in testing rather than silently masked.

## Poll Delivery Guarantee

The `/poll` endpoint sends the HTTP response **before** marking messages as `retrieved` in Firestore (at-least-once delivery). If the Firestore commit fails after the response is sent, messages stay in `pending` state and are re-delivered on the next poll — the Emulator's `MessageSid` dedupe in `app.js` absorbs the duplicate without showing a second bubble.

The unavoidable edge case: if the HTTP response reaches the client successfully but the Firestore commit also succeeds after a network timeout on the response, the message is marked retrieved and won't be re-delivered. This is indistinguishable from the "response arrived, commit succeeded" happy path from the server's perspective. For a polling interval of 1 second and a local/cloud-run deployment, this case is negligible in practice.

## Known Security Risk — Config API

The Configuration API has no authentication. Anyone who discovers the `/config` URL can replace the routing table and point it at an arbitrary public webhook URL — effectively turning the Router into an open relay.

This is an accepted, intentional risk for a development-only tool with no real user data or production traffic. The SSRF guard (blocking localhost/private IP targets) does not prevent this against public URLs.

**First thing to lock down if this Router is ever exposed on a persistent or discoverable URL:** add authentication to the Config API (e.g., a pre-shared API key in an `Authorization` header checked at the function boundary).

## SSRF Guard

The Config API validates webhook URLs and rejects targets pointing at localhost or private IP ranges (`127.x.x.x`, `10.x.x.x`, `192.168.x.x`, `172.16–31.x.x`). This guard lives in `src/ssrfGuard.ts` and can be extended there without restructuring callers.

**Integration tests:** Because the SSRF guard blocks localhost URLs, the integration tests in `tests/integration/` seed the routing table directly into the Firestore emulator via the Admin SDK rather than going through `PUT /config`. This is the expected pattern for any test that needs a localhost webhook.

## Local Development

```bash
cd router
npm install
npm run serve        # builds TypeScript + starts Firebase Emulator on ports 5001 (functions) and 8080 (Firestore)
```

Emulator UI: http://localhost:4000

## Running Tests

```bash
npm test             # unit tests only (phone normalizer, SSRF guard, Twilio payload)
npm run test:integration  # endpoint + round-trip tests (requires emulator running)
```

## Deployment

```bash
cd router
npm run deploy
```

After deploying, Firebase outputs the Cloud Run URL for the `router` function. Copy that URL into `testphone/js/routerConfig.js` as `ROUTER_BASE_URL`.

## Update Base URL After Deployment

Edit `testphone/js/routerConfig.js`:

```js
const ROUTER_BASE_URL = 'https://router-<hash>-uc.a.run.app';
```

This is the only file that needs to change when the Router moves to a new URL.
