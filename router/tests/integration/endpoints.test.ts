// Endpoint tests — require Firebase Emulator Suite running.
// From router/: npm run serve
//
// Note: the Config API's SSRF guard rejects localhost webhook URLs, so routing
// table entries are seeded directly into Firestore via the Admin SDK pointed at
// the emulator rather than going through PUT /config.

import axios from 'axios';
import * as admin from 'firebase-admin';
import * as http from 'http';
import * as net from 'net';

const BASE_URL = 'http://127.0.0.1:5001/test-phone-router/us-central1/router';
const FIRESTORE_HOST = '127.0.0.1:8080';

let db: admin.firestore.Firestore;

beforeAll(() => {
  process.env.FIRESTORE_EMULATOR_HOST = FIRESTORE_HOST;
  if (!admin.apps.length) {
    admin.initializeApp({ projectId: 'test-phone-router' });
  }
  db = admin.firestore();
});

afterEach(async () => {
  // Clear Firestore collections between tests
  const collections = ['routing_table', 'pending_messages'];
  for (const col of collections) {
    const snap = await db.collection(col).get();
    const batch = db.batch();
    snap.forEach(doc => batch.delete(doc.ref));
    if (!snap.empty) await batch.commit();
  }
});

// ── /incoming ──────────────────────────────────────────────────────────────────

describe('POST /incoming', () => {
  test('returns ROUTING_NOT_FOUND for unconfigured destination', async () => {
    const res = await axios.post(
      `${BASE_URL}/incoming`,
      new URLSearchParams({ From: '+13035551111', To: '+13035559999', Body: 'Hi' }).toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, validateStatus: () => true }
    );
    expect(res.status).toBe(404);
    expect(res.data.error).toBe('ROUTING_NOT_FOUND');
    expect(res.data.phoneNumber).toBe('+13035559999');
  });

  test('returns 400 for missing fields', async () => {
    const res = await axios.post(
      `${BASE_URL}/incoming`,
      new URLSearchParams({ From: '+13035551111', To: '+13035552222' }).toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, validateStatus: () => true }
    );
    expect(res.status).toBe(400);
    expect(res.data.error).toBe('MISSING_FIELDS');
  });

  test('returns 400 for unnormalizable phone number', async () => {
    const res = await axios.post(
      `${BASE_URL}/incoming`,
      new URLSearchParams({ From: 'notaphone', To: '+13035552222', Body: 'Hi' }).toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, validateStatus: () => true }
    );
    expect(res.status).toBe(400);
    expect(res.data.error).toBe('INVALID_PHONE');
  });

  test('normalizes common US phone formats before lookup', async () => {
    // Use a local webhook server — same fix applied to emulator.spec.js.
    // The SSRF guard only applies to PUT /config; direct Firestore seeds allow localhost.
    const webhookServer = await new Promise<http.Server>(resolve => {
      const s = http.createServer((_req, res) => {
        res.writeHead(200, { 'Content-Type': 'text/xml' });
        res.end('<Response></Response>');
      });
      s.listen(0, '127.0.0.1', () => resolve(s));
    });
    const { port } = webhookServer.address() as net.AddressInfo;

    await db.collection('routing_table').doc('+13035552222').set({
      webhookUrl: `http://127.0.0.1:${port}/webhook`,
    });

    const res = await axios.post(
      `${BASE_URL}/incoming`,
      new URLSearchParams({ From: '(303) 555-1111', To: '303-555-2222', Body: 'Hi' }).toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, validateStatus: () => true }
    );

    await new Promise<void>(resolve => webhookServer.close(() => resolve()));

    expect(res.status).toBe(200);
  });

  test('returns FORWARD_FAILED after one retry when webhook returns non-OK response', async () => {
    // A local server that always returns 500 — simulates a broken app webhook.
    // The Router should attempt delivery twice (original + 1 retry) then return 502.
    let callCount = 0;
    const failingServer = await new Promise<http.Server>(resolve => {
      const s = http.createServer((_req, res) => {
        callCount++;
        res.writeHead(500);
        res.end();
      });
      s.listen(0, '127.0.0.1', () => resolve(s));
    });
    const { port } = failingServer.address() as net.AddressInfo;
    const webhookUrl = `http://127.0.0.1:${port}/webhook`;

    // Seed routing directly — SSRF guard blocks localhost in PUT /config, but not in the routing table itself
    await db.collection('routing_table').doc('+13035554444').set({ webhookUrl });

    const res = await axios.post(
      `${BASE_URL}/incoming`,
      new URLSearchParams({ From: '+13035551111', To: '+13035554444', Body: 'Test retry' }).toString(),
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        validateStatus: () => true,
        timeout: 15000,
      }
    );

    await new Promise<void>(resolve => failingServer.close(() => resolve()));

    expect(res.status).toBe(502);
    expect(res.data.error).toBe('FORWARD_FAILED');
    // Router attempts original + 1 retry = 2 total delivery attempts
    expect(callCount).toBe(2);
  }, 30000);

  test('preserves MessageSid across original attempt and retry', async () => {
    // Verify same MessageSid is used on both attempts — critical for app-side idempotency.
    const receivedSids: string[] = [];
    const trackingServer = await new Promise<http.Server>(resolve => {
      const s = http.createServer((req, res) => {
        let body = '';
        req.on('data', chunk => { body += chunk.toString(); });
        req.on('end', () => {
          const match = body.match(/MessageSid=([^&\s]+)/);
          if (match) receivedSids.push(decodeURIComponent(match[1]));
          res.writeHead(500);
          res.end();
        });
      });
      s.listen(0, '127.0.0.1', () => resolve(s));
    });
    const { port } = trackingServer.address() as net.AddressInfo;

    await db.collection('routing_table').doc('+13035555555').set({
      webhookUrl: `http://127.0.0.1:${port}/webhook`,
    });

    await axios.post(
      `${BASE_URL}/incoming`,
      new URLSearchParams({ From: '+13035551111', To: '+13035555555', Body: 'SID test' }).toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, validateStatus: () => true, timeout: 15000 }
    );

    await new Promise<void>(resolve => trackingServer.close(() => resolve()));

    expect(receivedSids).toHaveLength(2);
    expect(receivedSids[0]).toMatch(/^SM[0-9A-F]{32}$/);
    // Both attempts must carry the same MessageSid
    expect(receivedSids[0]).toBe(receivedSids[1]);
  }, 30000);
});

// ── /messages ──────────────────────────────────────────────────────────────────

describe('POST /messages', () => {
  test('queues message for unregistered Test Phone number', async () => {
    const res = await axios.post(
      `${BASE_URL}/messages`,
      new URLSearchParams({ From: '+15005550001', To: '+13035557777', Body: 'Reply here' }).toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, validateStatus: () => true }
    );
    expect(res.status).toBe(201);
    expect(res.data.status).toBe('queued');
    expect(res.data.sid).toMatch(/^SM[0-9A-F]{32}$/);
    expect(res.data.to).toBe('+13035557777');
  });

  test('returns Twilio-compatible acceptance response', async () => {
    const res = await axios.post(
      `${BASE_URL}/messages`,
      new URLSearchParams({ From: '+15005550001', To: '+13035558888', Body: 'Hello' }).toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    );
    expect(res.data).toMatchObject({
      status: 'queued',
      direction: 'outbound-api',
      num_media: '0',
    });
    expect(res.data.date_created).toBeDefined();
  });

  test('returns 400 for missing fields', async () => {
    const res = await axios.post(
      `${BASE_URL}/messages`,
      new URLSearchParams({ From: '+15005550001', To: '+13035558888' }).toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, validateStatus: () => true }
    );
    expect(res.status).toBe(400);
  });
});

// ── /poll ──────────────────────────────────────────────────────────────────────

describe('GET /poll', () => {
  test('returns empty array when no pending messages', async () => {
    const res = await axios.get(`${BASE_URL}/poll?phoneNumber=+13035550001`);
    expect(res.data).toEqual({ messages: [] });
  });

  test('returns and marks pending messages for phone number', async () => {
    const sid = 'SM' + 'A'.repeat(32);
    await db.collection('pending_messages').doc(sid).set({
      messageSid: sid,
      from: '+15005550001',
      to: '+13035551234',
      body: 'Test message',
      createdAt: new Date().toISOString(),
      retrievalStatus: 'pending',
      retrievedAt: null,
    });

    const res = await axios.get(`${BASE_URL}/poll?phoneNumber=%2B13035551234`);
    expect(res.status).toBe(200);
    expect(res.data.messages).toHaveLength(1);
    expect(res.data.messages[0].messageSid).toBe(sid);
    expect(res.data.messages[0].body).toBe('Test message');

    // The poll endpoint responds before committing the retrieved status (at-least-once).
    // Give the async Firestore commit a moment to land before checking.
    await new Promise(resolve => setTimeout(resolve, 1500));
    const doc = await db.collection('pending_messages').doc(sid).get();
    expect(doc.data()!.retrievalStatus).toBe('retrieved');
  });

  test('does not return already-retrieved messages', async () => {
    const sid = 'SM' + 'B'.repeat(32);
    await db.collection('pending_messages').doc(sid).set({
      messageSid: sid,
      from: '+15005550001',
      to: '+13035555678',
      body: 'Old message',
      createdAt: new Date().toISOString(),
      retrievalStatus: 'retrieved',
      retrievedAt: new Date().toISOString(),
    });

    const res = await axios.get(`${BASE_URL}/poll?phoneNumber=%2B13035555678`);
    expect(res.data.messages).toHaveLength(0);
  });

  test('returns 400 for missing phoneNumber param', async () => {
    const res = await axios.get(`${BASE_URL}/poll`, { validateStatus: () => true });
    expect(res.status).toBe(400);
    expect(res.data.error).toBe('MISSING_FIELDS');
  });
});

// ── /config ────────────────────────────────────────────────────────────────────

describe('GET /config', () => {
  test('returns empty array when routing table is empty', async () => {
    const res = await axios.get(`${BASE_URL}/config`);
    expect(res.data).toEqual([]);
  });

  test('returns routing table entries', async () => {
    await db.collection('routing_table').doc('+13035551111').set({ webhookUrl: 'https://example.com/sms' });

    const res = await axios.get(`${BASE_URL}/config`);
    expect(res.data).toContainEqual({ phoneNumber: '+13035551111', webhookUrl: 'https://example.com/sms' });
  });
});

describe('PUT /config', () => {
  test('replaces routing table wholesale', async () => {
    await db.collection('routing_table').doc('+13035551111').set({ webhookUrl: 'https://old.example.com/sms' });

    const res = await axios.put(`${BASE_URL}/config`, [
      { phoneNumber: '+13035552222', webhookUrl: 'https://new.example.com/sms' },
    ]);
    expect(res.data.success).toBe(true);

    const snap = await db.collection('routing_table').get();
    const ids = snap.docs.map(d => d.id);
    expect(ids).not.toContain('+13035551111');
    expect(ids).toContain('+13035552222');
  });

  test('returns validation errors for invalid phone number', async () => {
    const res = await axios.put(
      `${BASE_URL}/config`,
      [{ phoneNumber: 'notaphone', webhookUrl: 'https://example.com/sms' }],
      { validateStatus: () => true }
    );
    expect(res.status).toBe(422);
    expect(res.data.errors[0].category).toBe('INVALID_PHONE');
  });

  test('returns validation errors for duplicate phone numbers', async () => {
    const res = await axios.put(
      `${BASE_URL}/config`,
      [
        { phoneNumber: '+13035551111', webhookUrl: 'https://example.com/sms' },
        { phoneNumber: '+13035551111', webhookUrl: 'https://other.example.com/sms' },
      ],
      { validateStatus: () => true }
    );
    expect(res.status).toBe(422);
    expect(res.data.errors.some((e: { category: string }) => e.category === 'DUPLICATE_PHONE')).toBe(true);
  });

  test('blocks localhost webhook URLs (SSRF guard)', async () => {
    const res = await axios.put(
      `${BASE_URL}/config`,
      [{ phoneNumber: '+13035551111', webhookUrl: 'http://localhost:3000/sms' }],
      { validateStatus: () => true }
    );
    expect(res.status).toBe(422);
    expect(res.data.errors[0].category).toBe('UNSAFE_TARGET');
  });

  test('returns validation errors for missing http/https scheme', async () => {
    const res = await axios.put(
      `${BASE_URL}/config`,
      [{ phoneNumber: '+13035551111', webhookUrl: 'ftp://example.com/sms' }],
      { validateStatus: () => true }
    );
    expect(res.status).toBe(422);
    expect(res.data.errors[0].category).toBe('INVALID_URL');
  });
});
