import {
  processInbound,
  pickRandom,
  RANDOM_RESPONSES,
  RANDOM_JOKES,
} from '../../src/referenceApps';

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeSuccessfulFetch(): typeof fetch {
  return jest.fn().mockResolvedValue({
    status: 201,
    json: async () => ({ status: 'queued', sid: 'SMabc' }),
  }) as unknown as typeof fetch;
}

function makeFailedFetch(status: number): typeof fetch {
  return jest.fn().mockResolvedValue({
    status,
    json: async () => ({ error: 'SOME_ERROR' }),
  }) as unknown as typeof fetch;
}

function makeNetworkErrorFetch(): typeof fetch {
  return jest.fn().mockRejectedValue(new Error('network unreachable')) as unknown as typeof fetch;
}

function makeMalformedFetch(): typeof fetch {
  return jest.fn().mockResolvedValue({
    status: 201,
    json: async () => { throw new SyntaxError('not json'); },
  }) as unknown as typeof fetch;
}

// ── pickRandom ────────────────────────────────────────────────────────────────

describe('pickRandom', () => {
  test('returns an element that belongs to the input array', () => {
    const items = ['a', 'b', 'c'];
    for (let i = 0; i < 30; i++) {
      expect(items).toContain(pickRandom(items));
    }
  });

  test('returns the only element when the array has one item', () => {
    expect(pickRandom(['only'])).toBe('only');
  });
});

// ── Echo ──────────────────────────────────────────────────────────────────────

describe('Echo — processInbound', () => {
  test('returns the exact inbound body unchanged', async () => {
    const fetchFn = makeSuccessfulFetch();
    const result = await processInbound('+15551111111', '+15550000001', 'Hello world', (b) => b, fetchFn);
    expect(result.statusCode).toBe(200);
    expect(result.body.status).toBe('delivered');

    const callArgs = (fetchFn as jest.Mock).mock.calls[0];
    const bodyStr: string = callArgs[1].body;
    const sent = Object.fromEntries(new URLSearchParams(bodyStr));
    expect(sent['Body']).toBe('Hello world');
  });

  test('reverses phone direction: outbound From = inbound To, outbound To = inbound From', async () => {
    const fetchFn = makeSuccessfulFetch();
    await processInbound('+15551111111', '+15550000001', 'Ping', (b) => b, fetchFn);

    const callArgs = (fetchFn as jest.Mock).mock.calls[0];
    const bodyStr: string = callArgs[1].body;
    const sent = Object.fromEntries(new URLSearchParams(bodyStr));
    expect(sent['From']).toBe('+15550000001');
    expect(sent['To']).toBe('+15551111111');
  });

  test('sends outbound request to Router /messages endpoint', async () => {
    const fetchFn = makeSuccessfulFetch();
    await processInbound('+15551111111', '+15550000001', 'Test', (b) => b, fetchFn);

    const callArgs = (fetchFn as jest.Mock).mock.calls[0];
    expect(callArgs[0]).toMatch(/\/messages$/);
  });

  test('uses form-encoded content type for outbound request', async () => {
    const fetchFn = makeSuccessfulFetch();
    await processInbound('+15551111111', '+15550000001', 'Test', (b) => b, fetchFn);

    const callArgs = (fetchFn as jest.Mock).mock.calls[0];
    expect(callArgs[1].headers['Content-Type']).toBe('application/x-www-form-urlencoded');
  });

  test('returns 502 ROUTER_UNREACHABLE when fetch throws', async () => {
    const fetchFn = makeNetworkErrorFetch();
    const result = await processInbound('+15551111111', '+15550000001', 'Hi', (b) => b, fetchFn);
    expect(result.statusCode).toBe(502);
    expect(result.body.error).toBe('ROUTER_UNREACHABLE');
  });

  test('returns 502 ROUTER_REJECTED when Router returns non-201', async () => {
    const fetchFn = makeFailedFetch(500);
    const result = await processInbound('+15551111111', '+15550000001', 'Hi', (b) => b, fetchFn);
    expect(result.statusCode).toBe(502);
    expect(result.body.error).toBe('ROUTER_REJECTED');
  });

  test('treats exactly 201 as success', async () => {
    const fetchFn = makeSuccessfulFetch();
    const result = await processInbound('+15551111111', '+15550000001', 'Hi', (b) => b, fetchFn);
    expect(result.statusCode).toBe(200);
  });

  test('treats 200 as a Router rejection (only 201 is success)', async () => {
    const fetchFn = makeFailedFetch(200);
    const result = await processInbound('+15551111111', '+15550000001', 'Hi', (b) => b, fetchFn);
    expect(result.statusCode).toBe(502);
    expect(result.body.error).toBe('ROUTER_REJECTED');
  });

  test('handles malformed Router JSON gracefully', async () => {
    const fetchFn = makeMalformedFetch();
    const result = await processInbound('+15551111111', '+15550000001', 'Hi', (b) => b, fetchFn);
    // Malformed JSON on a 201 response: status 201 still counts as success
    expect(result.statusCode).toBe(200);
  });
});

// ── Random Response ───────────────────────────────────────────────────────────

describe('Random Response — processInbound', () => {
  test('returns one item from RANDOM_RESPONSES', async () => {
    const fetchFn = makeSuccessfulFetch();
    await processInbound('+15551111111', '+15550000002', 'Hello', () => pickRandom(RANDOM_RESPONSES), fetchFn);

    const callArgs = (fetchFn as jest.Mock).mock.calls[0];
    const bodyStr: string = callArgs[1].body;
    const sent = Object.fromEntries(new URLSearchParams(bodyStr));
    expect(RANDOM_RESPONSES).toContain(sent['Body']);
  });

  test('RANDOM_RESPONSES contains exactly 10 items', () => {
    expect(RANDOM_RESPONSES).toHaveLength(10);
  });

  test('all RANDOM_RESPONSES are non-empty strings', () => {
    for (const r of RANDOM_RESPONSES) {
      expect(typeof r).toBe('string');
      expect(r.length).toBeGreaterThan(0);
    }
  });

  test('reverses phone direction', async () => {
    const fetchFn = makeSuccessfulFetch();
    await processInbound('+15551111111', '+15550000002', 'Hi', () => pickRandom(RANDOM_RESPONSES), fetchFn);

    const callArgs = (fetchFn as jest.Mock).mock.calls[0];
    const sent = Object.fromEntries(new URLSearchParams(callArgs[1].body));
    expect(sent['From']).toBe('+15550000002');
    expect(sent['To']).toBe('+15551111111');
  });

  test('returns 502 when Router is unreachable', async () => {
    const fetchFn = makeNetworkErrorFetch();
    const result = await processInbound('+15551111111', '+15550000002', 'Hi', () => pickRandom(RANDOM_RESPONSES), fetchFn);
    expect(result.statusCode).toBe(502);
    expect(result.body.error).toBe('ROUTER_UNREACHABLE');
  });

  test('returns 502 when Router rejects outbound message', async () => {
    const fetchFn = makeFailedFetch(422);
    const result = await processInbound('+15551111111', '+15550000002', 'Hi', () => pickRandom(RANDOM_RESPONSES), fetchFn);
    expect(result.statusCode).toBe(502);
    expect(result.body.error).toBe('ROUTER_REJECTED');
  });
});

// ── Random Joke ───────────────────────────────────────────────────────────────

describe('Random Joke — processInbound', () => {
  test('returns one item from RANDOM_JOKES', async () => {
    const fetchFn = makeSuccessfulFetch();
    await processInbound('+15551111111', '+15550000003', 'Tell me', () => pickRandom(RANDOM_JOKES), fetchFn);

    const callArgs = (fetchFn as jest.Mock).mock.calls[0];
    const bodyStr: string = callArgs[1].body;
    const sent = Object.fromEntries(new URLSearchParams(bodyStr));
    expect(RANDOM_JOKES).toContain(sent['Body']);
  });

  test('RANDOM_JOKES contains exactly 10 items', () => {
    expect(RANDOM_JOKES).toHaveLength(10);
  });

  test('all RANDOM_JOKES are non-empty strings', () => {
    for (const j of RANDOM_JOKES) {
      expect(typeof j).toBe('string');
      expect(j.length).toBeGreaterThan(0);
    }
  });

  test('reverses phone direction', async () => {
    const fetchFn = makeSuccessfulFetch();
    await processInbound('+15551111111', '+15550000003', 'Hi', () => pickRandom(RANDOM_JOKES), fetchFn);

    const callArgs = (fetchFn as jest.Mock).mock.calls[0];
    const sent = Object.fromEntries(new URLSearchParams(callArgs[1].body));
    expect(sent['From']).toBe('+15550000003');
    expect(sent['To']).toBe('+15551111111');
  });

  test('returns 502 when Router is unreachable', async () => {
    const fetchFn = makeNetworkErrorFetch();
    const result = await processInbound('+15551111111', '+15550000003', 'Hi', () => pickRandom(RANDOM_JOKES), fetchFn);
    expect(result.statusCode).toBe(502);
    expect(result.body.error).toBe('ROUTER_UNREACHABLE');
  });

  test('returns 502 when Router rejects outbound message', async () => {
    const fetchFn = makeFailedFetch(503);
    const result = await processInbound('+15551111111', '+15550000003', 'Hi', () => pickRandom(RANDOM_JOKES), fetchFn);
    expect(result.statusCode).toBe(502);
    expect(result.body.error).toBe('ROUTER_REJECTED');
  });
});
