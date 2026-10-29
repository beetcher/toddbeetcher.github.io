"""Run the real API/management app locally; demo memory must be explicitly chosen.

Usage: READY_API_KEY=<32+ char secret> python3 -m ready.devserver --demo --seed
For Firestore, omit --demo and pass --project explicitly. Never fallback to memory
when Firestore fails. Bind loopback by default; credentials are never printed.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from uuid import uuid4

from .application import Application, BODY_LIMIT
from .crud.memory_store import MemoryStore
from .services import ReadyService


def make_server(app, host="127.0.0.1", port=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # No request paths/person IDs/keys in development logs.

        def dispatch(self):
            try:
                count = int(self.headers.get("Content-Length", "0"))
                if count < 0:
                    raise ValueError()
            except ValueError:
                self.send_error(400)
                return
            if count > BODY_LIMIT:
                self.send_error(413)
                self.close_connection = True
                return
            body = self.rfile.read(count) if count else b""
            status, headers, payload = app.handle(self.command, self.path, dict(self.headers), body, self.client_address[0])
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = do_OPTIONS = dispatch
    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Explicit ephemeral in-memory development data")
    parser.add_argument("--seed", action="store_true", help="Import tagged synthetic examples into demo memory only")
    parser.add_argument("--project", help="Explicit Firebase/Google Cloud project ID")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    key = os.environ.get("READY_API_KEY", "")
    if len(key) < 32:
        parser.error("Set READY_API_KEY to a secret of at least 32 characters.")
    if args.seed and not args.demo:
        parser.error("--seed is restricted to --demo; live imports use the API's dry-run/commit flow.")
    if args.demo:
        store = MemoryStore()
    else:
        if not args.project:
            parser.error("Choose --demo or supply --project; there is no implicit production project.")
        from .crud.firestore_store import FirestoreStore
        store = FirestoreStore(args.project)
    service = ReadyService(store)
    if args.seed:
        seed = json.loads((Path(__file__).parent / "seed/ai_readiness.json").read_text())
        seed.update(dry_run=False, idempotency_key=str(uuid4()))
        service.import_content(seed)
    app = Application(service, key)
    server = make_server(app, port=args.port)
    print(f"READY management/API: http://127.0.0.1:{server.server_port}/ready/", flush=True)
    print("Persistence: ephemeral demo memory" if args.demo else "Persistence: Firestore (explicit project)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
