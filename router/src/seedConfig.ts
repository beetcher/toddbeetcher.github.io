import * as admin from 'firebase-admin';
import { normalizePhoneNumber } from './phoneNormalizer';
import seedData from './config/seed.config.json';

const ROUTING_COLLECTION = 'routing_table';
const SEED_META_COLLECTION = 'seed_meta';
const SEED_META_DOC = 'init';

// Exported so tests can validate the source data independently.
export type SeedRecord = { phoneNumber: string; webhookUrl: string };
export const SEED_RECORDS: ReadonlyArray<SeedRecord> = seedData as SeedRecord[];

function validateSeedRecord(record: SeedRecord, index: number): void {
  const phone = normalizePhoneNumber(record.phoneNumber);
  if (!phone) throw new Error(`seed.config.json record ${index}: invalid phoneNumber "${record.phoneNumber}"`);
  if (!record.webhookUrl || !/^https?:\/\/.+/.test(record.webhookUrl)) {
    throw new Error(`seed.config.json record ${index}: invalid webhookUrl "${record.webhookUrl}"`);
  }
}

// Lazy seed initialization. Called from GET /config and POST /incoming before
// any routing table read. The durable state lives in seed_meta/init in Firestore;
// this function never relies solely on process memory.
//
// Rules:
//   - Never initialized, routing table empty  → seed from seed.config.json, mark seeded.
//   - Never initialized, routing table non-empty → mark seeded, leave table unchanged.
//   - Already initialized → return immediately, never modify table.
export async function ensureSeeded(db: admin.firestore.Firestore): Promise<void> {
  const metaRef = db.collection(SEED_META_COLLECTION).doc(SEED_META_DOC);

  // Fast path: already seeded (one Firestore read per invocation).
  const metaSnap = await metaRef.get();
  if (metaSnap.data()?.seeded === true) return;

  // Read routing table to decide whether to seed.
  const routingSnap = await db.collection(ROUTING_COLLECTION).get();

  if (!routingSnap.empty) {
    // Non-empty: preserve existing entries, just mark initialized.
    // Use a transaction so concurrent instances only write the marker once.
    await db.runTransaction(async (tx) => {
      const meta = await tx.get(metaRef);
      if (meta.data()?.seeded === true) return;
      tx.set(metaRef, { seeded: true });
    });
    return;
  }

  // Empty routing table: validate seed records before writing anything.
  // Any validation failure throws here, leaving seed_meta/init unset so
  // the next request retries rather than silently skipping initialization.
  for (let i = 0; i < SEED_RECORDS.length; i++) {
    validateSeedRecord(SEED_RECORDS[i], i);
  }

  // Write seed records + initialization marker atomically. The transaction
  // re-checks the marker so concurrent instances do not double-seed.
  await db.runTransaction(async (tx) => {
    const meta = await tx.get(metaRef);
    if (meta.data()?.seeded === true) return; // lost the race

    for (const record of SEED_RECORDS) {
      const phone = normalizePhoneNumber(record.phoneNumber)!;
      tx.set(db.collection(ROUTING_COLLECTION).doc(phone), { webhookUrl: record.webhookUrl });
    }
    tx.set(metaRef, { seeded: true });
  });
}
