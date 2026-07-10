import * as functions from 'firebase-functions/logger';

interface LogContext {
  endpoint?: string;
  messageSid?: string;
  from?: string;
  to?: string;
  webhookUrl?: string;
  status?: string;
  errorCategory?: string;
  attempt?: string;
  [key: string]: unknown;
}

// Body content is isolated here — replace this function to add redaction.
function extractBodyMeta(body: string): { bodyLength: number } {
  return { bodyLength: body.length };
}

export function logEvent(event: string, context: LogContext & { body?: string }): void {
  const { body, ...rest } = context;
  const entry: Record<string, unknown> = {
    event,
    timestamp: new Date().toISOString(),
    ...rest,
  };
  if (body !== undefined) {
    Object.assign(entry, extractBodyMeta(body));
  }
  functions.info(entry);
}

export function logError(event: string, context: LogContext, err: unknown): void {
  functions.error({
    event,
    timestamp: new Date().toISOString(),
    ...context,
    error: err instanceof Error ? err.message : String(err),
  });
}
