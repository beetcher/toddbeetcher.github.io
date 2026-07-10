// Tiny throwaway HTTP server that echoes inbound Twilio payloads.
// Run standalone: node tests/integration/mockWebhook.js
// Or require() it in tests for programmatic control.
//
// Dedupes on MessageSid — logs a warning if the same id arrives twice,
// which would indicate the Router fired an unnecessary retry.

const http = require('http');
const { URLSearchParams } = require('url');

const PORT = parseInt(process.env.MOCK_WEBHOOK_PORT || '3099', 10);
const seen = new Set();
const received = [];

function createServer(port) {
  const server = http.createServer((req, res) => {
    if (req.method !== 'POST') {
      res.writeHead(405);
      res.end();
      return;
    }

    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      const params = Object.fromEntries(new URLSearchParams(body));
      const sid = params.MessageSid;

      if (sid && seen.has(sid)) {
        console.warn(`[mock-webhook] DUPLICATE MessageSid: ${sid}`);
      } else if (sid) {
        seen.add(sid);
      }

      received.push({ timestamp: Date.now(), params });
      console.log(`[mock-webhook] Received #${received.length}: From=${params.From} Body=${params.Body}`);

      res.writeHead(200, { 'Content-Type': 'text/xml' });
      res.end('<Response></Response>');
    });
  });

  server.listen(port, () => {
    console.log(`[mock-webhook] Listening on http://localhost:${port}`);
  });

  return server;
}

const server = createServer(PORT);

module.exports = { server, received, seen, PORT, createServer };
