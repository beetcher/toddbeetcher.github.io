import { isUnsafeWebhookTarget } from '../../src/ssrfGuard';

describe('isUnsafeWebhookTarget', () => {
  test.each([
    'http://localhost/webhook',
    'http://localhost:3001/webhook',
    'http://127.0.0.1/webhook',
    'http://127.0.0.1:3000/webhook',
    'http://0.0.0.0/webhook',
    'http://10.0.0.1/webhook',
    'http://10.255.255.255/webhook',
    'http://192.168.1.1/webhook',
    'http://192.168.0.254/webhook',
    'http://172.16.0.1/webhook',
    'http://172.31.255.255/webhook',
  ])('blocks private target: %s', (url) => {
    expect(isUnsafeWebhookTarget(url)).toBe(true);
  });

  test.each([
    'https://example.com/webhook',
    'https://my-app.vercel.app/sms',
    'https://abc123.ngrok.io/webhook',
    'http://172.32.0.1/webhook',
    'http://172.15.0.1/webhook',
  ])('allows public target: %s', (url) => {
    expect(isUnsafeWebhookTarget(url)).toBe(false);
  });

  test('blocks unparseable URL', () => {
    expect(isUnsafeWebhookTarget('not a url')).toBe(true);
  });
});
