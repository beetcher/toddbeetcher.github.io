const phoneNumber = (() => {
  function normalize(input) {
    if (!input || typeof input !== 'string') return null;
    const trimmed = input.trim();
    const digits = trimmed.replace(/\D/g, '');

    if (digits.length === 10) return `+1${digits}`;
    if (digits.length === 11 && digits[0] === '1') return `+${digits}`;
    // International: more than 11 digits and original started with +
    if (digits.length > 11 && trimmed.startsWith('+')) return `+${digits}`;
    return null;
  }

  function isValid(input) {
    return normalize(input) !== null;
  }

  // Formats a normalized E.164 US number (+1XXXXXXXXXX) to (xxx) xxx-xxxx.
  // Returns the original string unchanged for non-US or unrecognized formats.
  function formatForDisplay(e164) {
    if (!e164 || typeof e164 !== 'string') return e164;
    const m = e164.match(/^\+1(\d{3})(\d{3})(\d{4})$/);
    if (!m) return e164;
    return `(${m[1]}) ${m[2]}-${m[3]}`;
  }

  return { normalize, isValid, formatForDisplay };
})();
