// Single source of truth for the Router base URL.
// Checks localStorage for an active custom endpoint first; falls back to
// auto-detecting local development (localhost / 127.0.0.1) vs. production.
//
// Emulator URL: http://127.0.0.1:5001/test-phone-router/us-central1/router
// Production URL: https://router-in7qh2jyoq-uc.a.run.app

const _autoDetectUrl =
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://127.0.0.1:5001/test-phone-router/us-central1/router'
    : 'https://router-in7qh2jyoq-uc.a.run.app';

function getRouterBaseUrl() {
  const activeId = localStorage.getItem('testphone_active_router_endpoint');
  if (!activeId || activeId === 'auto-detect') return _autoDetectUrl;
  try {
    const list = JSON.parse(localStorage.getItem('testphone_router_endpoints') || '[]');
    const entry = list.find(e => e.id === activeId);
    return entry ? entry.url : _autoDetectUrl;
  } catch {
    return _autoDetectUrl;
  }
}
