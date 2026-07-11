import { onRequest } from 'firebase-functions/v2/https';
import * as admin from 'firebase-admin';
import express from 'express';
import cors from 'cors';
import { normalizePhoneNumber } from './phoneNormalizer';
import { validateRequest } from './validateRequest';
import { buildInboundPayload, buildOutboundAcceptance } from './twilioPayload';
import { generateMessageSid } from './generateSid';
import { isUnsafeWebhookTarget } from './ssrfGuard';
import { logEvent, logError } from './logger';
import { ensureSeeded } from './seedConfig';

admin.initializeApp();
const db = admin.firestore();

const ROUTING_COLLECTION = 'routing_table';
const MESSAGES_COLLECTION = 'pending_messages';
const REGION = 'us-central1';
const FORWARD_TIMEOUT_MS = 25000;

const app = express();
app.use(cors({ origin: '*' }));
app.use(express.json());
app.use(express.urlencoded({ extended: false }));

// ── POST /incoming ────────────────────────────────────────────────────────────
// Simulated SMS from Test Phone → forward to the application webhook.

app.post('/incoming', async (req, res): Promise<void> => {
  logEvent('endpoint_hit', { endpoint: 'incoming' });

  await ensureSeeded(db);

  validateRequest('', req.headers['x-twilio-signature'] as string ?? '', req.url, req.body);

  const { From, To, Body, MessageSid: callerSid } = req.body as Record<string, string>;
  if (!From || !To || !Body) {
    res.status(400).json({ error: 'MISSING_FIELDS', message: 'From, To, and Body are required' });
    return;
  }

  const normalizedFrom = normalizePhoneNumber(From);
  const normalizedTo = normalizePhoneNumber(To);
  if (!normalizedFrom || !normalizedTo) {
    res.status(400).json({ error: 'INVALID_PHONE', message: 'Could not normalize phone number to E.164' });
    return;
  }

  logEvent('incoming_received', { endpoint: 'incoming', from: normalizedFrom, to: normalizedTo });

  const doc = await db.collection(ROUTING_COLLECTION).doc(normalizedTo).get();
  if (!doc.exists) {
    logEvent('routing_not_found', { endpoint: 'incoming', to: normalizedTo, errorCategory: 'ROUTING_NOT_FOUND' });
    res.status(404).json({
      error: 'ROUTING_NOT_FOUND',
      message: `No routing entry found for ${normalizedTo}`,
      phoneNumber: normalizedTo,
    });
    return;
  }

  const { webhookUrl } = doc.data()!;

  // Preserve the caller's MessageSid so both the original attempt and any retry
  // carry the same id — applications that dedupe on MessageSid won't double-process
  // a message whose response was lost.
  const messageSid = callerSid || generateMessageSid();
  const payload = buildInboundPayload(messageSid, normalizedFrom, normalizedTo, Body);

  logEvent('forwarding', {
    endpoint: 'incoming',
    messageSid,
    from: normalizedFrom,
    to: normalizedTo,
    webhookUrl,
    body: Body,
  });

  const result = await forwardWithRetry(webhookUrl, payload, messageSid);
  if (!result.ok) {
    logEvent('forward_failed', { endpoint: 'incoming', messageSid, webhookUrl, errorCategory: 'FORWARD_FAILED' });
    res.status(502).json({
      error: 'FORWARD_FAILED',
      message: `Could not deliver message to ${webhookUrl} after retry`,
      messageSid,
    });
    return;
  }

  logEvent('forwarded', { endpoint: 'incoming', messageSid, status: 'forwarded' });
  res.status(200).json({ status: 'forwarded', messageSid });
});

// ── POST /messages ─────────────────────────────────────────────────────────────
// Application requests delivery of a message to a Test Phone — accept and queue.

app.post('/messages', async (req, res): Promise<void> => {
  logEvent('endpoint_hit', { endpoint: 'messages' });

  validateRequest('', '', req.url, req.body);

  const { From, To, Body } = req.body as Record<string, string>;
  if (!From || !To || !Body) {
    res.status(400).json({ error: 'MISSING_FIELDS', message: 'From, To, and Body are required' });
    return;
  }

  const normalizedFrom = normalizePhoneNumber(From);
  const normalizedTo = normalizePhoneNumber(To);
  if (!normalizedFrom || !normalizedTo) {
    res.status(400).json({ error: 'INVALID_PHONE', message: 'Could not normalize phone number to E.164' });
    return;
  }

  const messageSid = generateMessageSid();
  const createdAt = new Date().toISOString();

  await db.collection(MESSAGES_COLLECTION).doc(messageSid).set({
    messageSid,
    from: normalizedFrom,
    to: normalizedTo,
    body: Body,
    createdAt,
    retrievalStatus: 'pending',
    retrievedAt: null,
  });

  logEvent('message_queued', {
    endpoint: 'messages',
    messageSid,
    from: normalizedFrom,
    to: normalizedTo,
    status: 'queued',
    body: Body,
  });

  res.status(201).json(buildOutboundAcceptance(messageSid, normalizedFrom, normalizedTo, Body));
});

// ── GET /poll ──────────────────────────────────────────────────────────────────
// Test Phone polls for pending inbound messages. Returns at-least-once — see README.

app.get('/poll', async (req, res): Promise<void> => {
  const rawNumber = (req.query.phoneNumber as string) ?? '';
  if (!rawNumber) {
    res.status(400).json({ error: 'MISSING_FIELDS', message: 'phoneNumber query param required' });
    return;
  }

  const phoneNum = normalizePhoneNumber(rawNumber);
  if (!phoneNum) {
    res.status(400).json({ error: 'INVALID_PHONE', message: 'Could not normalize phoneNumber to E.164' });
    return;
  }

  const snapshot = await db
    .collection(MESSAGES_COLLECTION)
    .where('to', '==', phoneNum)
    .where('retrievalStatus', '==', 'pending')
    .orderBy('createdAt')
    .get();

  if (snapshot.empty) {
    res.status(200).json({ messages: [] });
    return;
  }

  const now = new Date().toISOString();
  const batch = db.batch();
  const msgs: object[] = [];

  snapshot.forEach(doc => {
    batch.update(doc.ref, { retrievalStatus: 'retrieved', retrievedAt: now });
    const d = doc.data();
    msgs.push({
      messageSid: d.messageSid,
      from: d.from,
      to: d.to,
      body: d.body,
      createdAt: d.createdAt,
    });
  });

  // Respond first, then mark retrieved — at-least-once delivery guarantee.
  // If the Firestore commit fails after we respond, messages stay pending and
  // are re-delivered on the next poll; the Emulator's MessageSid dedupe absorbs
  // the duplicate. The unavoidable edge case (response succeeds but commit also
  // succeeds after a network drop) is handled by client-side dedupe, not here.
  res.status(200).json({ messages: msgs });

  logEvent('messages_retrieved', { endpoint: 'poll', to: phoneNum, status: `${msgs.length} messages` });
  await batch.commit();
});

// ── GET /config ────────────────────────────────────────────────────────────────

app.get('/config', async (_req, res): Promise<void> => {
  await ensureSeeded(db);

  const snapshot = await db.collection(ROUTING_COLLECTION).get();
  const table: object[] = [];
  snapshot.forEach(doc => {
    table.push({ phoneNumber: doc.id, webhookUrl: doc.data().webhookUrl });
  });
  logEvent('config_read', { endpoint: 'config' });
  res.status(200).json(table);
});

// ── PUT /config (also POST for compatibility) ──────────────────────────────────

async function handleConfigSave(req: express.Request, res: express.Response): Promise<void> {
  if (!Array.isArray(req.body)) {
    res.status(400).json({ error: 'INVALID_JSON', message: 'Request body must be a JSON array' });
    return;
  }

  const table = req.body as Array<{ phoneNumber: string; webhookUrl: string }>;
  const errors: Array<{ row: number; field: string; category: string; message: string }> = [];
  const seenNumbers = new Set<string>();
  const validRows: Array<{ phoneNumber: string; webhookUrl: string }> = [];

  table.forEach((row, i) => {
    const rawPhone = String(row.phoneNumber ?? '');
    const rawUrl = String(row.webhookUrl ?? '').trim();

    const phone = normalizePhoneNumber(rawPhone);
    let phoneOk = false;

    if (!phone) {
      errors.push({ row: i, field: 'phoneNumber', category: 'INVALID_PHONE', message: 'Invalid phone number format' });
    } else if (seenNumbers.has(phone)) {
      errors.push({ row: i, field: 'phoneNumber', category: 'DUPLICATE_PHONE', message: 'Duplicate phone number' });
    } else {
      seenNumbers.add(phone);
      phoneOk = true;
    }

    let urlOk = false;
    if (!rawUrl || !/^https?:\/\/.+/.test(rawUrl)) {
      errors.push({ row: i, field: 'webhookUrl', category: 'INVALID_URL', message: 'Must start with http:// or https://' });
    } else if (isUnsafeWebhookTarget(rawUrl)) {
      errors.push({ row: i, field: 'webhookUrl', category: 'UNSAFE_TARGET', message: 'Webhook URL must not point to localhost or private IP ranges' });
    } else {
      urlOk = true;
    }

    if (phoneOk && urlOk) {
      validRows.push({ phoneNumber: phone!, webhookUrl: rawUrl });
    }
  });

  if (errors.length > 0) {
    res.status(422).json({ success: false, errors });
    return;
  }

  const batch = db.batch();
  const existing = await db.collection(ROUTING_COLLECTION).get();
  existing.forEach(doc => batch.delete(doc.ref));
  validRows.forEach(({ phoneNumber, webhookUrl }) => {
    batch.set(db.collection(ROUTING_COLLECTION).doc(phoneNumber), { webhookUrl });
  });
  await batch.commit();

  logEvent('config_saved', { endpoint: 'config', status: `${validRows.length} entries` });
  res.status(200).json({ success: true, errors: [] });
}

app.put('/config', handleConfigSave);
app.post('/config', handleConfigSave);

// ── Forwarding helper ──────────────────────────────────────────────────────────

async function forwardWithRetry(
  url: string,
  payload: Record<string, string>,
  messageSid: string
): Promise<{ ok: boolean }> {
  const body = new URLSearchParams(payload).toString();
  const headers = { 'Content-Type': 'application/x-www-form-urlencoded' };

  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), FORWARD_TIMEOUT_MS);
      const response = await fetch(url, { method: 'POST', headers, body, signal: controller.signal });
      clearTimeout(timer);
      if (response.ok) return { ok: true };
      logEvent('forward_attempt_failed', {
        messageSid,
        webhookUrl: url,
        status: String(response.status),
        attempt: String(attempt + 1),
      });
    } catch (err) {
      logError('forward_attempt_error', { messageSid, webhookUrl: url, attempt: String(attempt + 1) }, err);
    }
  }

  return { ok: false };
}

// ── Test-only: direct Firestore seed endpoint ──────────────────────────────────
// Only registered when running in the emulator (FUNCTIONS_EMULATOR is set by Firebase).
// Bypasses the SSRF guard so integration tests can configure localhost webhook URLs.
// Dead code in production — the route is never registered there.

if (process.env.FUNCTIONS_EMULATOR) {
  app.put('/test/direct-seed', async (req, res): Promise<void> => {
    if (!Array.isArray(req.body)) {
      res.status(400).json({ error: 'INVALID_JSON', message: 'Request body must be a JSON array' });
      return;
    }
    const table = req.body as Array<{ phoneNumber: string; webhookUrl: string }>;
    const batch = db.batch();
    // Replace routing table with the supplied entries (no SSRF guard — emulator only).
    const existingRouting = await db.collection(ROUTING_COLLECTION).get();
    existingRouting.forEach(doc => batch.delete(doc.ref));
    for (const row of table) {
      const phone = normalizePhoneNumber(String(row.phoneNumber ?? ''));
      if (phone && row.webhookUrl) {
        batch.set(db.collection(ROUTING_COLLECTION).doc(phone), { webhookUrl: String(row.webhookUrl) });
      }
    }
    // Also clear pending_messages so stale replies from prior tests don't leak into the next test.
    const existingMessages = await db.collection(MESSAGES_COLLECTION).get();
    existingMessages.forEach(doc => batch.delete(doc.ref));
    await batch.commit();
    res.status(200).json({ success: true });
  });
}

// ── Exports ────────────────────────────────────────────────────────────────────

export const router = onRequest({ region: REGION }, app);

export { echo, randomresponse, randomjoke } from './referenceApps';
