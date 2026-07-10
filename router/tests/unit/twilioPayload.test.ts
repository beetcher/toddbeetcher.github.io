import { buildInboundPayload, buildOutboundAcceptance } from '../../src/twilioPayload';

const SID = 'SM1234567890ABCDEF1234567890ABCDEF';
const FROM = '+13035551111';
const TO = '+13035552222';
const BODY = 'Hello test';

describe('buildInboundPayload', () => {
  const p = buildInboundPayload(SID, FROM, TO, BODY);

  test('includes required Twilio SMS fields', () => {
    expect(p.MessageSid).toBe(SID);
    expect(p.SmsMessageSid).toBe(SID);
    expect(p.SmsSid).toBe(SID);
    expect(p.AccountSid).toMatch(/^AC/);
    expect(p.From).toBe(FROM);
    expect(p.To).toBe(TO);
    expect(p.Body).toBe(BODY);
    expect(p.NumMedia).toBe('0');
    expect(p.NumSegments).toBe('1');
    expect(p.ApiVersion).toBe('2010-04-01');
    expect(p.DateCreated).toBeDefined();
  });

  test('returns string values (form-encodable)', () => {
    Object.values(p).forEach(v => expect(typeof v).toBe('string'));
  });
});

describe('buildOutboundAcceptance', () => {
  const r = buildOutboundAcceptance(SID, FROM, TO, BODY) as Record<string, unknown>;

  test('includes expected fields', () => {
    expect(r.sid).toBe(SID);
    expect(r.from).toBe(FROM);
    expect(r.to).toBe(TO);
    expect(r.body).toBe(BODY);
    expect(r.status).toBe('queued');
    expect(r.date_sent).toBeNull();
  });
});
