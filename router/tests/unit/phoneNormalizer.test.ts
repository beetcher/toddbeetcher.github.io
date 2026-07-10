import { normalizePhoneNumber } from '../../src/phoneNormalizer';

describe('normalizePhoneNumber', () => {
  test.each([
    ['3035551212',          '+13035551212'],
    ['(303) 555-1212',     '+13035551212'],
    ['303-555-1212',       '+13035551212'],
    ['+1 303 555 1212',    '+13035551212'],
    ['13035551212',        '+13035551212'],
    ['+13035551212',       '+13035551212'],
    ['(303)555-1212',      '+13035551212'],
    ['303.555.1212',       '+13035551212'],
  ])('normalizes %s → %s', (input, expected) => {
    expect(normalizePhoneNumber(input)).toBe(expected);
  });

  test.each([
    [''],
    ['123'],
    ['12345'],
    ['abcdefghij'],
    ['555-000'],
  ])('returns null for invalid input "%s"', (input) => {
    expect(normalizePhoneNumber(input)).toBeNull();
  });
});
