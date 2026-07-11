// Full round-trip integration test — requires:
//   1. Firebase Emulator Suite running: npm run serve (from router/)
//   2. Mock webhook will be started by this test
//
// Round-trip: seed routing table → POST /incoming → mock webhook receives it
//   → mock webhook POSTs /messages → GET /poll → assert reply received.

import axios from 'axios';
import * as http from 'http';
import * as admin from 'firebase-admin';
import { URLSearchParams } from 'url';

const BASE_URL = 'http://127.0.0.1:5001/test-phone-router/us-central1/router';
const FIRESTORE_HOST = '127.0.0.1:8080';
const MOCK_PORT = 3098;
const MOCK_URL = `http://127.0.0.1:${MOCK_PORT}/webhook`;

let mockServer: http.Server;
let db: admin.firestore.Firestore;

// The mock webhook sends an outbound reply when it receives a message.
function startMockWebhook(): Promise<void> {
  return new Promise(resolve => {
    mockServer = http.createServer(async (req, res) => {
      let body = '';
      req.on('data', chunk => { body += chunk; });
      req.on('end', async () => {
        const params = Object.fromEntries(new URLSearchParams(body));
        console.log(`[mock-webhook] Received: From=${params.From} Body=${params.Body}`);

        // Send outbound reply via /messages
        await axios.post(
          `${BASE_URL}/messages`,
          new URLSearchParams({
            From: params.To,
            To: params.From,
            Body: `[mock-reply] Got: ${params.Body}`,
          }).toString(),
          { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
        ).catch(err => console.error('[mock-webhook] Failed to send reply:', err.message));

        res.writeHead(200, { 'Content-Type': 'text/xml' });
        res.end('<Response></Response>');
      });
    });
    mockServer.listen(MOCK_PORT, resolve);
  });
}

beforeAll(async () => {
  process.env.FIRESTORE_EMULATOR_HOST = FIRESTORE_HOST;
  if (!admin.apps.length) {
    admin.initializeApp({ projectId: 'test-phone-router' });
  }
  db = admin.firestore();
  await startMockWebhook();
});

afterAll(done => {
  mockServer.close(done);
});

afterEach(async () => {
  const collections = ['routing_table', 'pending_messages'];
  for (const col of collections) {
    const snap = await db.collection(col).get();
    const batch = db.batch();
    snap.forEach(doc => batch.delete(doc.ref));
    if (!snap.empty) await batch.commit();
  }
});

test('full round-trip: seed route → inbound → app replies → poll receives reply', async () => {
  const testPhoneNumber = '+13035550101';

  // Seed routing table directly (bypasses SSRF guard — localhost is required for testing)
  await db.collection('routing_table').doc(testPhoneNumber).set({ webhookUrl: MOCK_URL });

  // Test Phone sends inbound message
  const inboundRes = await axios.post(
    `${BASE_URL}/incoming`,
    new URLSearchParams({ From: testPhoneNumber, To: testPhoneNumber, Body: 'Hello app' }).toString(),
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  );
  expect(inboundRes.data.status).toBe('forwarded');

  // Give the mock webhook time to process and call /messages
  await new Promise(resolve => setTimeout(resolve, 1000));

  // Test Phone polls for reply
  const pollRes = await axios.get(
    `${BASE_URL}/poll?phoneNumber=${encodeURIComponent(testPhoneNumber)}`
  );

  expect(pollRes.data.messages.length).toBeGreaterThan(0);
  const reply = pollRes.data.messages[0];
  expect(reply.body).toContain('[mock-reply] Got: Hello app');
  expect(reply.messageSid).toMatch(/^SM[0-9A-F]{32}$/);

  // Poll responds before committing retrieved status (at-least-once guarantee).
  // Give the async Firestore commit a moment to land before the second poll.
  await new Promise(resolve => setTimeout(resolve, 1500));

  // Second poll should return nothing (messages marked retrieved)
  const pollRes2 = await axios.get(
    `${BASE_URL}/poll?phoneNumber=${encodeURIComponent(testPhoneNumber)}`
  );
  expect(pollRes2.data.messages).toHaveLength(0);
});

test('outbound queues for phone that has never polled', async () => {
  const neverSeenPhone = '+13035559999';

  const res = await axios.post(
    `${BASE_URL}/messages`,
    new URLSearchParams({ From: '+15005550001', To: neverSeenPhone, Body: 'Waiting for you' }).toString(),
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  );
  expect(res.status).toBe(201);
  expect(res.data.status).toBe('queued');

  // Later when the phone opens and polls
  const pollRes = await axios.get(
    `${BASE_URL}/poll?phoneNumber=${encodeURIComponent(neverSeenPhone)}`
  );
  expect(pollRes.data.messages).toHaveLength(1);
  expect(pollRes.data.messages[0].body).toBe('Waiting for you');
});
