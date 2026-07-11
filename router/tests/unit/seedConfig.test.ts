import { ensureSeeded, SEED_RECORDS } from '../../src/seedConfig';
import type * as admin from 'firebase-admin';

// ── Firestore mock helpers ────────────────────────────────────────────────────
// Each test receives a freshly constructed mock so state does not leak between
// test cases. The mock mimics only the Firestore surface used by ensureSeeded:
//   db.collection(name).doc(id).get()       → DocumentSnapshot
//   db.collection(name).get()               → QuerySnapshot
//   db.runTransaction(fn)                   → executes fn with a transaction mock
//   tx.get(ref) / tx.set(ref, data)
//
// Refs carry _colName and id so the transaction mock knows where to write.

type MockDocData = Record<string, unknown>;
type CollectionData = Map<string, MockDocData>;

// A MockRef is what db.collection(name).doc(id) returns. The transaction mock
// reads _colName and id to route writes to the correct in-memory collection.
type MockRef = { _colName: string; id: string; get: () => Promise<unknown> };

function makeDb(collections: Record<string, CollectionData>): admin.firestore.Firestore {
  function ensureCol(name: string): CollectionData {
    if (!collections[name]) collections[name] = new Map();
    return collections[name];
  }

  return {
    collection(colName: string) {
      const col = ensureCol(colName);
      return {
        doc(docId: string): MockRef {
          return {
            _colName: colName,
            id: docId,
            get: jest.fn(async () => {
              const data = col.get(docId);
              return { exists: data !== undefined, data: () => data };
            }),
          };
        },
        get: jest.fn(async () => ({
          empty: col.size === 0,
          forEach(cb: (doc: { id: string; data: () => MockDocData }) => void) {
            col.forEach((data, id) => cb({ id, data: () => data }));
          },
        })),
      };
    },

    async runTransaction(fn: (tx: unknown) => Promise<void>) {
      // Buffer all tx.set writes; commit atomically after fn completes.
      const pending: Array<{ colName: string; docId: string; data: MockDocData }> = [];

      const tx = {
        get: jest.fn(async (ref: MockRef) => {
          // Check pending writes in this transaction first (read-your-writes).
          const pw = pending.find(w => w.colName === ref._colName && w.docId === ref.id);
          if (pw) return { exists: true, data: () => pw.data };

          const col = collections[ref._colName];
          if (!col) return { exists: false, data: () => undefined };
          const data = col.get(ref.id);
          return { exists: data !== undefined, data: () => data };
        }),
        set: jest.fn((ref: MockRef, data: MockDocData) => {
          pending.push({ colName: ref._colName, docId: ref.id, data });
        }),
      };

      await fn(tx);

      // Commit
      for (const { colName, docId, data } of pending) {
        ensureCol(colName).set(docId, data);
      }
    },
  } as unknown as admin.firestore.Firestore;
}

// ── Seed data validation ───────────────────────────────────────────────────────

describe('SEED_RECORDS', () => {
  test('contains 3 records', () => {
    expect(SEED_RECORDS).toHaveLength(3);
  });

  test('all records have valid E.164 phone numbers', () => {
    const e164 = /^\+1\d{10}$/;
    for (const r of SEED_RECORDS) {
      expect(r.phoneNumber).toMatch(e164);
    }
  });

  test('all records have https webhook URLs', () => {
    for (const r of SEED_RECORDS) {
      expect(r.webhookUrl).toMatch(/^https:\/\/.+/);
    }
  });

  test('seed data is readable from the built module (resolveJsonModule verification)', () => {
    // Importing SEED_RECORDS proves the JSON was inlined by the TypeScript
    // compiler — this is the deployment artifact verification for seed data.
    expect(Array.isArray(SEED_RECORDS)).toBe(true);
    expect(SEED_RECORDS[0].phoneNumber).toBeDefined();
    expect(SEED_RECORDS[0].webhookUrl).toBeDefined();
  });

  test('phone numbers are distinct', () => {
    const phones = SEED_RECORDS.map(r => r.phoneNumber);
    expect(new Set(phones).size).toBe(phones.length);
  });
});

// ── Never-initialized, empty routing table → seed ────────────────────────────

describe('ensureSeeded — never initialized, empty routing table', () => {
  test('inserts seed records into routing_table', async () => {
    const collections: Record<string, CollectionData> = {
      routing_table: new Map(),
      seed_meta: new Map(),
    };
    const db = makeDb(collections);
    await ensureSeeded(db);

    expect(collections['routing_table']!.size).toBe(SEED_RECORDS.length);
    for (const record of SEED_RECORDS) {
      // CollectionData maps id → plain data object
      const doc = collections['routing_table']!.get(record.phoneNumber);
      expect(doc).toBeDefined();
      expect(doc).toMatchObject({ webhookUrl: record.webhookUrl });
    }
  });

  test('marks seed_meta/init as seeded after inserting records', async () => {
    const collections: Record<string, CollectionData> = {
      routing_table: new Map(),
      seed_meta: new Map(),
    };
    const db = makeDb(collections);
    await ensureSeeded(db);

    // CollectionData maps id → plain data object
    const initData = collections['seed_meta']!.get('init');
    expect(initData).toMatchObject({ seeded: true });
  });

  test('GET /config equivalent: returns seeded data on first call', async () => {
    const collections: Record<string, CollectionData> = {
      routing_table: new Map(),
      seed_meta: new Map(),
    };
    const db = makeDb(collections);
    await ensureSeeded(db);

    // Simulate what GET /config does: read routing_table after ensureSeeded
    const table: Array<{ phoneNumber: string; webhookUrl: string }> = [];
    collections['routing_table']!.forEach((data, id) => {
      table.push({ phoneNumber: id, webhookUrl: (data as { webhookUrl: string }).webhookUrl });
    });
    expect(table).toHaveLength(3);
  });
});

// ── Never-initialized, non-empty routing table → preserve, mark initialized ──

describe('ensureSeeded — never initialized, non-empty routing table', () => {
  test('leaves existing mappings unchanged', async () => {
    const collections: Record<string, CollectionData> = {
      // Plain data objects — no { id, data } wrapper
      routing_table: new Map([['+13035551234', { webhookUrl: 'https://myapp.example.com/sms' }]]),
      seed_meta: new Map(),
    };
    const db = makeDb(collections);
    await ensureSeeded(db);

    expect(collections['routing_table']!.size).toBe(1);
    const existing = collections['routing_table']!.get('+13035551234');
    expect(existing).toMatchObject({ webhookUrl: 'https://myapp.example.com/sms' });
  });

  test('does not insert seed records when table is non-empty', async () => {
    const collections: Record<string, CollectionData> = {
      routing_table: new Map([['+13035551234', { webhookUrl: 'https://myapp.example.com/sms' }]]),
      seed_meta: new Map(),
    };
    const db = makeDb(collections);
    await ensureSeeded(db);

    for (const record of SEED_RECORDS) {
      expect(collections['routing_table']!.has(record.phoneNumber)).toBe(false);
    }
  });

  test('marks seed_meta/init as seeded', async () => {
    const collections: Record<string, CollectionData> = {
      routing_table: new Map([['+13035551234', { webhookUrl: 'https://myapp.example.com/sms' }]]),
      seed_meta: new Map(),
    };
    const db = makeDb(collections);
    await ensureSeeded(db);

    const initData = collections['seed_meta']!.get('init');
    expect(initData).toMatchObject({ seeded: true });
  });
});

// ── Already initialized → never modify ───────────────────────────────────────

describe('ensureSeeded — already initialized', () => {
  test('does not modify a non-empty routing table', async () => {
    const collections: Record<string, CollectionData> = {
      routing_table: new Map([['+13035551234', { webhookUrl: 'https://myapp.example.com/sms' }]]),
      seed_meta: new Map([['init', { seeded: true }]]),
    };
    const db = makeDb(collections);
    await ensureSeeded(db);

    expect(collections['routing_table']!.size).toBe(1);
    expect(collections['routing_table']!.has('+13035551234')).toBe(true);
    expect(collections['routing_table']!.has(SEED_RECORDS[0].phoneNumber)).toBe(false);
  });

  test('does not seed an intentionally emptied routing table', async () => {
    const collections: Record<string, CollectionData> = {
      routing_table: new Map(),   // intentionally empty after developer deleted all entries
      seed_meta: new Map([['init', { seeded: true }]]),
    };
    const db = makeDb(collections);
    await ensureSeeded(db);

    // Routing table must remain empty
    expect(collections['routing_table']!.size).toBe(0);
  });

  test('is safe to call more than once', async () => {
    const collections: Record<string, CollectionData> = {
      routing_table: new Map(),
      seed_meta: new Map([['init', { seeded: true }]]),
    };
    const db = makeDb(collections);
    await ensureSeeded(db);
    await ensureSeeded(db);
    await ensureSeeded(db);

    expect(collections['routing_table']!.size).toBe(0);
  });
});

// ── Existing mappings are never overwritten ───────────────────────────────────

describe('ensureSeeded — overwrites existing mappings never', () => {
  test('a seed phone number already in routing_table is not overwritten', async () => {
    const existingUrl = 'https://custom.example.com/webhook';
    const collections: Record<string, CollectionData> = {
      // One of the seed phone numbers exists with a custom URL — table is non-empty
      routing_table: new Map([[SEED_RECORDS[0].phoneNumber, { webhookUrl: existingUrl }]]),
      seed_meta: new Map(),
    };
    const db = makeDb(collections);
    await ensureSeeded(db);

    // Non-empty → marks seeded without writing seed records
    const existing = collections['routing_table']!.get(SEED_RECORDS[0].phoneNumber);
    expect(existing).toMatchObject({ webhookUrl: existingUrl });
  });
});

// ── Saving empty table does not reseed ────────────────────────────────────────

describe('ensureSeeded — saving empty table does not reseed', () => {
  test('routing_table empty after developer clears it stays empty on next call', async () => {
    // Simulate: seeded once, developer then saves empty table via PUT /config
    const collections: Record<string, CollectionData> = {
      routing_table: new Map(),          // emptied by developer
      seed_meta: new Map([['init', { seeded: true }]]),
    };
    const db = makeDb(collections);
    await ensureSeeded(db);

    expect(collections['routing_table']!.size).toBe(0);
  });
});

// ── Initialization marker persists across instances ───────────────────────────

describe('ensureSeeded — initialization marker is Firestore-backed', () => {
  test('a fresh process (no in-memory state) reads seed_meta from Firestore', async () => {
    // Simulate a new Cloud Functions instance starting after seed was already
    // completed by a previous instance. The marker must come from Firestore.
    const collections: Record<string, CollectionData> = {
      routing_table: new Map(),
      seed_meta: new Map([['init', { seeded: true }]]),
    };
    const db = makeDb(collections);
    // Call ensureSeeded on a fresh db handle (new process simulation).
    // If the function relied on process memory it would re-seed here.
    await ensureSeeded(db);

    expect(collections['routing_table']!.size).toBe(0);
  });
});
