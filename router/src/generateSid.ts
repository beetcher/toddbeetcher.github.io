import { randomBytes } from 'crypto';

export function generateMessageSid(): string {
  return 'SM' + randomBytes(16).toString('hex').toUpperCase();
}
