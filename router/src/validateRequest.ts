// V1 stub — always returns true.
// To add real validation, implement Twilio HMAC-SHA1 signature verification here:
// https://www.twilio.com/docs/usage/security
export function validateRequest(
  _authToken: string,
  _signature: string,
  _url: string,
  _params: Record<string, string>
): boolean {
  return true;
}
