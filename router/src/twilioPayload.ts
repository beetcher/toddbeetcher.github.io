const FAKE_ACCOUNT_SID = 'AC00000000000000000000000000000000';
const API_VERSION = '2010-04-01';

export function buildInboundPayload(
  messageSid: string,
  from: string,
  to: string,
  body: string
): Record<string, string> {
  const now = new Date().toUTCString();
  return {
    MessageSid: messageSid,
    SmsSid: messageSid,
    SmsMessageSid: messageSid,
    AccountSid: FAKE_ACCOUNT_SID,
    From: from,
    To: to,
    Body: body,
    NumMedia: '0',
    NumSegments: '1',
    SmsStatus: 'received',
    ApiVersion: API_VERSION,
    DateCreated: now,
    DateSent: now,
  };
}

export function buildOutboundAcceptance(
  messageSid: string,
  from: string,
  to: string,
  body: string
): object {
  const now = new Date().toISOString();
  return {
    sid: messageSid,
    account_sid: FAKE_ACCOUNT_SID,
    from,
    to,
    body,
    status: 'queued',
    num_media: '0',
    num_segments: '1',
    api_version: API_VERSION,
    date_created: now,
    date_sent: null,
    direction: 'outbound-api',
  };
}
