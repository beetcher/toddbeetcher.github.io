// Lightweight SSRF guard — rejects webhook URLs pointing at private/loopback addresses.
// Extend this function to add more checks (e.g. DNS rebinding, cloud metadata endpoints)
// without restructuring callers.
const PRIVATE_PATTERNS = [
  /^localhost$/i,
  /^127\.\d+\.\d+\.\d+$/,
  /^0\.0\.0\.0$/,
  /^10\.\d+\.\d+\.\d+$/,
  /^172\.(1[6-9]|2\d|3[01])\.\d+\.\d+$/,
  /^192\.168\.\d+\.\d+$/,
  /^::1$/,
  /^fc[\da-f]{2}:/i,
];

export function isUnsafeWebhookTarget(url: string): boolean {
  try {
    const { hostname } = new URL(url);
    return PRIVATE_PATTERNS.some(p => p.test(hostname));
  } catch {
    return true;
  }
}
