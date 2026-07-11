// Reference SMS Applications — three small webhook endpoints used to verify
// the complete Test Phone → Router → application → Router → Test Phone round trip.
//
// Each endpoint receives a Twilio-compatible inbound webhook from the Router,
// generates a response, and sends it back through the Router's /messages endpoint.
// They communicate only with the Router; they never write to Firestore directly.
//
// Public invocation with no authentication is an accepted, intentional risk for
// a development-only tool, consistent with the Router's own Config API posture.
// See README section "Security — Reference Applications" for details.

import { onRequest } from 'firebase-functions/v2/https';
import type { Request, Response } from 'express';
import { ROUTER_BASE_URL } from './config/routerConfig';
const REGION = 'us-central1';

export const RANDOM_RESPONSES: ReadonlyArray<string> = [
  'Message received.',
  'That sounds promising.',
  'Try the next step.',
  'Interesting.',
  'Keep going.',
  'Got it.',
  'Noted.',
  'Understood.',
  'Sounds good.',
  'Moving forward.',
];

export const RANDOM_JOKES: ReadonlyArray<string> = [
  "Why don't scientists trust atoms? Because they make up everything.",
  'I told my wife she should embrace her mistakes. She gave me a hug.',
  "What do you call a fish with no eyes? A fsh.",
  'Why did the scarecrow win an award? Because he was outstanding in his field.',
  "I'm reading a book about anti-gravity. It's impossible to put down.",
  "Why don't eggs tell jokes? They'd crack each other up.",
  'What did the ocean say to the beach? Nothing, it just waved.',
  'Why did the bicycle fall over? Because it was two-tired.',
  "What do you call cheese that isn't yours? Nacho cheese.",
  'Why did the math book look so sad? Because it had too many problems.',
];

export function pickRandom<T>(items: ReadonlyArray<T>): T {
  return items[Math.floor(Math.random() * items.length)];
}

// Outbound reply result type, returned from the core handler so tests can
// assert behavior without setting up an HTTP server.
export type HandlerResult = {
  statusCode: number;
  body: Record<string, unknown>;
};

// Core handler logic — separated from the Cloud Function declaration so unit
// tests can call it directly with injected fetch and body generator.
export async function processInbound(
  from: string,
  to: string,
  inboundBody: string,
  generateResponse: (body: string) => string,
  fetchFn: typeof fetch = fetch
): Promise<HandlerResult> {
  const responseText = generateResponse(inboundBody);
  const params = new URLSearchParams({ From: to, To: from, Body: responseText });

  let res: Awaited<ReturnType<typeof fetch>>;
  let data: unknown;
  try {
    res = await fetchFn(`${ROUTER_BASE_URL}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params.toString(),
    });
    data = await res.json().catch(() => null);
  } catch {
    return {
      statusCode: 502,
      body: { error: 'ROUTER_UNREACHABLE', message: 'Could not reach Router /messages endpoint' },
    };
  }

  if (res.status !== 201) {
    return {
      statusCode: 502,
      body: { error: 'ROUTER_REJECTED', message: `Router returned ${res.status}`, routerResponse: data },
    };
  }

  return { statusCode: 200, body: { status: 'delivered' } };
}

function extractFields(req: Request): { from: string | undefined; to: string | undefined; body: string | undefined } {
  const b = (req.body ?? {}) as Record<string, string>;
  return { from: b['From'], to: b['To'], body: b['Body'] };
}

async function handleRequest(
  req: Request,
  res: Response,
  generateResponse: (body: string) => string
): Promise<void> {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'METHOD_NOT_ALLOWED' });
    return;
  }

  const { from, to, body } = extractFields(req);
  if (!from || !to || !body) {
    res.status(400).json({ error: 'MISSING_FIELDS', message: 'From, To, and Body are required' });
    return;
  }

  const result = await processInbound(from, to, body, generateResponse);
  res.status(result.statusCode).json(result.body);
}

// ── Echo ──────────────────────────────────────────────────────────────────────
// Returns the inbound Body unchanged. Verifies the complete message path with
// the least possible application logic.

export const echo = onRequest({ region: REGION, invoker: 'public' }, async (req, res) => {
  await handleRequest(req as unknown as Request, res as unknown as Response, (b) => b);
});

// ── Random Response ───────────────────────────────────────────────────────────
// Returns one of 10 hard-coded neutral responses chosen at random.
// Verifies that application-side logic executes before the response is returned.

export const randomresponse = onRequest({ region: REGION, invoker: 'public' }, async (req, res) => {
  await handleRequest(req as unknown as Request, res as unknown as Response, () => pickRandom(RANDOM_RESPONSES));
});

// ── Random Joke ───────────────────────────────────────────────────────────────
// Returns one of 10 hard-coded jokes chosen at random.
// Provides a clearly recognizable reference behavior distinct from Random Response.

export const randomjoke = onRequest({ region: REGION, invoker: 'public' }, async (req, res) => {
  await handleRequest(req as unknown as Request, res as unknown as Response, () => pickRandom(RANDOM_JOKES));
});
