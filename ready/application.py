"""Thin authenticated HTTP boundary; service owns the domain, callers administer tests.

Same application is used by local stdlib server and Firebase HTTP function. Initial
secret is a super-admin API key; no embedded credential, cookies or participant
session. Static management files are harmless without the separately supplied key.
"""
from collections import defaultdict, deque
import hmac
import json
import logging
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

from .services import ReadyService, ServiceError, CONTRACTS, HANDLERS
from .contracts import DIRECTORY, output_validator

ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger("ready")
BODY_LIMIT = 262144
MIME = {".png": "image/png", ".svg": "image/svg+xml", ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}


class Application:
    def __init__(self, service, api_key, allowed_origins=()):
        self.service, self.api_key = service, api_key
        self.allowed_origins = set(allowed_origins)
        self._rates = defaultdict(deque)
        self._lock = threading.Lock()

    def handle(self, method, target, headers=None, body=b"", remote="local"):
        headers = {key.lower(): value for key, value in (headers or {}).items()}
        request_id = str(uuid4())
        base = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer", "X-Request-ID": request_id}
        origin = headers.get("origin")
        if origin in self.allowed_origins:
            base.update({"Access-Control-Allow-Origin": origin, "Vary": "Origin",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, Idempotency-Key, If-Match",
                "Access-Control-Allow-Methods": "GET, POST, PATCH, PUT, DELETE, OPTIONS"})
        def respond(status, data, error=False, extras=None):
            payload = {"ok": not error, "error" if error else "data": data, "request_id": request_id}
            return status, {**base, "Content-Type": "application/json; charset=utf-8", **(extras or {})}, json.dumps(payload, allow_nan=False).encode()
        try:
            parsed = urlsplit(target)
            path = unquote(parsed.path).rstrip("/") or "/"
            if method == "GET" and parsed.path in ("/", "/ready"):
                return 308, {**base, "Location": "/ready/"}, b""
            if method == "OPTIONS":
                if origin and origin not in self.allowed_origins:
                    return respond(403, {"code": "forbidden", "message": "Origin is not configured."}, True)
                return 204, base, b""
            static = {"/ready/apple-touch-icon.png": "apple-touch-icon.png", "/ready/favicon-eyes.svg": "favicon-eyes.svg", "/ready/favicon.svg": "favicon.svg", "/": "index.html", "/ready": "index.html", "/ready/main.js": "main.js", "/ready/style.css": "style.css"}
            if method == "GET" and path in static:
                file = ROOT / "web" / static[path]
                policy = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
                return 200, {**base, "Content-Type": MIME[file.suffix], "Content-Security-Policy": policy}, file.read_bytes()
            if method == "GET" and path == "/ready/seed.json":
                return 200, {**base, "Content-Type": "application/json"}, (ROOT / "seed/ai_readiness.json").read_bytes()
            if method == "GET" and path == "/v1/health":
                return respond(200, {"status": "ok", "api_version": "v1"})
            if not self.api_key or len(self.api_key) < 32:
                return respond(503, {"code": "service_unavailable", "message": "Super-admin key is not configured."}, True)
            auth = headers.get("authorization", "")
            expected = "Bearer " + self.api_key
            if not hmac.compare_digest(auth.encode(), expected.encode()):
                return respond(401, {"code": "unauthenticated", "message": "A valid API key is required."}, True)
            if len(body) > BODY_LIMIT:
                return respond(413, {"code": "payload_too_large", "message": "Request exceeds 256 KiB."}, True)
            with self._lock:
                now = time.monotonic()
                queue = self._rates[remote]
                while queue and now-queue[0] > 60:
                    queue.popleft()
                if len(queue) >= 180:
                    return respond(429, {"code": "rate_limited", "message": "Try again shortly."}, True, {"Retry-After": "60"})
                queue.append(now)
                if len(self._rates) > 2000:
                    for key in list(self._rates):
                        if not self._rates[key] or now-self._rates[key][-1] > 60:
                            del self._rates[key]
            if body and not headers.get("content-type", "").lower().startswith("application/json"):
                raise ServiceError("invalid_request", issue="application_json_required")
            def invalid_number(_):
                raise ValueError("non_finite_json")
            def unique_keys(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("duplicate_json_key")
                    result[key] = value
                return result
            try:
                data = json.loads(body, parse_constant=invalid_number, object_pairs_hook=unique_keys) if body else {}
            except (ValueError, UnicodeDecodeError):
                raise ServiceError("invalid_request", issue="invalid_json")
            if not isinstance(data, dict):
                raise ServiceError("invalid_request", issue="object_required")
            query = parse_qs(parsed.query, keep_blank_values=True)
            if any(len(values) != 1 for values in query.values()):
                raise ServiceError("invalid_request", issue="duplicate_query_parameter")
            query = {key: values[0] for key, values in query.items()}
            pdf_parts = path.strip("/").split("/")
            if method == "GET" and len(pdf_parts) == 4 and pdf_parts[:2] == ["v1", "tests"] and pdf_parts[3] == "pdf":
                if query or data:
                    raise ServiceError("invalid_request", field="pdf", issue="no_parameters_allowed")
                saved = self.service.get("tests", pdf_parts[2])
                if not output_validator("test_record").is_valid(saved):
                    raise RuntimeError("output_contract_violation")
                from .pdf_export import render_test_pdf
                return 200, {**base, "Content-Type": "application/pdf",
                    "Content-Disposition": 'attachment; filename="ready-test-' + saved["id"] + '.pdf"'}, render_test_pdf(saved)
            status, result, replay = self.route(method, path, query, data, headers)
            route_parts = path.strip("/").split("/")[1:]
            kind = route_parts[0] if route_parts else ""
            names = {"questions": "question", "answers": "answer", "sets": "question_answer_set", "tests": "test", "attempts": "attempt"}
            output_name = None
            if kind in names:
                if len(route_parts) == 3 and route_parts[-1] in ("relationships", "answers"):
                    output_name = "relationship_page"
                elif len(route_parts) == 3 and route_parts[-1] == "attempts":
                    output_name = "attempt_page"
                elif "records" in result:
                    output_name = names[kind] + "_page"
                elif kind == "attempts":
                    output_name = "result_detail" if "attempt_id" in result else "attempt_record"
                elif kind == "sets" and "bundle" in result:
                    output_name = "set_detail"
                else:
                    output_name = names[kind] + "_record"
            elif kind == "selections":
                output_name = "selection_output"
            elif route_parts == ["content", "imports"]:
                output_name = "import_output"
            if output_name and not output_validator(output_name).is_valid(result):
                raise RuntimeError("output_contract_violation")
            extras = {"Idempotency-Replayed": "true"} if replay else {}
            if isinstance(result, dict) and "record_version" in result:
                extras["ETag"] = '"' + str(result["record_version"]) + '"'
            return respond(status, result, extras=extras)
        except ServiceError as exc:
            status = {"not_found": 404, "conflict": 409, "invalid_request": 400, "forbidden": 403, "method_not_allowed": 405}.get(exc.code, 422)
            message = {404: "Record not found.", 409: "Request conflicts with retained data.", 400: "Check the request format.", 405: "Method not supported."}.get(status, "Check the submitted fields.")
            return respond(status, {"code": exc.code, "message": message,
                "fields": [{"field": exc.field, "code": exc.issue}], "details": exc.details}, True)
        except Exception:
            # Deliberately exclude body/key/person IDs and SDK exception messages.
            LOG.error("request_failed request_id=%s", request_id)
            return respond(500, {"code": "server_error", "message": "Request could not be completed."}, True)

    def route(self, method, path, query, data, headers):
        """Route calls only; inputs/domain/persistence belong to contracts/services."""
        parts = path.strip("/").split("/")
        if not parts or parts[0] != "v1":
            raise ServiceError("not_found")
        parts = parts[1:]
        name = parts[0] if parts else ""
        key = headers.get("idempotency-key")
        if method == "GET" and name == "capabilities":
            return 200, {"api_version": "v1", "role": "super_admin", "question_types": ["single_choice", "multiple_choice"],
                "criteria": ["topics", "audiences", "difficulty", "learning_objectives", "tags"],
                "max_candidate_scan": 1000, "max_import_records": 200, "participant_administration": False,
                "persistence": type(self.service.store).__name__}, False
        if method == "POST" and parts == ["person-ids"]:
            if data:
                raise ServiceError(field="body", issue="empty_object_required")
            return 200, {"person_id": str(uuid4()), "is_persisted": False}, False
        if method == "GET" and name == "schemas":
            catalog = json.loads((DIRECTORY / "registry.json").read_text())["schemas"]
            contracts = json.loads((DIRECTORY / "contracts.json").read_text())["contracts"]
            outputs = json.loads((DIRECTORY / "outputs.json").read_text())["outputs"]
            files = {row["name"]: row["schema"] for row in catalog} | contracts | outputs
            if len(parts) == 1:
                return 200, {"schemas": [{"name": key, "schema_version": 1, "url": "/v1/schemas/"+key} for key in sorted(files)]}, False
            if len(parts) == 2 and parts[1] in files and query.get("schema_version", "1") == "1":
                return 200, {"name": parts[1], "schema_version": 1, "schema": json.loads((DIRECTORY / files[parts[1]]).read_text())}, False
            raise ServiceError("not_found")
        if method == "POST" and parts == ["selections"]:
            return 200, self.service.select(data), False
        if method == "POST" and parts == ["content", "imports"]:
            if not data.get("dry_run", True) and not data.get("idempotency_key"):
                data["idempotency_key"] = key
            result = self.service.import_content(data)
            return (200 if data.get("dry_run") or result.get("replayed") else 201), result, result.get("replayed", False)
        if name not in HANDLERS:
            raise ServiceError("not_found")
        if method == "GET" and len(parts) == 1:
            allowed = {"include_archived", "include_history", "person_id", "test_id", "criteria", "cursor", "limit"}
            if set(query)-allowed:
                raise ServiceError("invalid_request", field="query", issue="unknown_parameter")
            options = {}
            for flag in ("include_archived", "include_history"):
                if flag in query:
                    if query[flag] not in ("true", "false"):
                        raise ServiceError("invalid_request", field=flag, issue="boolean_required")
                    options[flag] = query[flag] == "true"
            for param in ("person_id", "test_id"):
                if param in query:
                    if name != "attempts":
                        raise ServiceError("invalid_request", field=param, issue="results_only")
                    options[param] = query[param]
            try:
                options.update(limit=int(query.get("limit", 25)), cursor=int(query.get("cursor", 0)))
                options["criteria"] = json.loads(query.get("criteria", "{}"))
            except (ValueError, TypeError):
                raise ServiceError("invalid_request", field="query", issue="invalid_value")
            return 200, self.service.list(name, **options), False
        if method == "POST" and len(parts) == 1:
            if name in CONTRACTS:
                result, replay = self.service.create(name, data, key)
            elif name == "tests":
                result, replay = self.service.create_test(data, key)
            else:
                if key and "idempotency_key" not in data:
                    data["idempotency_key"] = key
                result, replay = self.service.submit_result(data)
            return 200 if replay else 201, result, replay
        if len(parts) >= 2:
            record_id = parts[1]
            if method == "GET" and len(parts) == 2:
                result = self.service.result(record_id) if name == "attempts" else self.service.get(name, record_id)
                if name == "sets":
                    result = {**result, "bundle": self.service.bundle(record_id)}
                return 200, result, False
            if method == "PATCH" and len(parts) == 2:
                try:
                    expected = int(headers.get("if-match", "").strip('"'))
                except ValueError:
                    raise ServiceError("invalid_request", field="If-Match", issue="required")
                return 200, self.service.revise(name, record_id, data, expected), False
            if (method == "PUT" and len(parts) == 3 and parts[2] == "archive") or (method == "DELETE" and len(parts) == 2):
                if method == "DELETE" and name in ("tests", "attempts"):
                    raise ServiceError("method_not_allowed")
                if method == "DELETE":
                    data = {**data, "is_archived": True}
                return 200, self.service.archive(name, record_id, data), False
            if method == "POST" and name == "tests" and len(parts) == 3 and parts[2] == "variants":
                result, replay = self.service.create_test(data, key, record_id)
                return 200 if replay else 201, result, replay
            if method == "GET" and name == "tests" and len(parts) == 3 and parts[2] == "attempts":
                return 200, self.service.list("attempts", test_id=record_id, include_history=query.get("include_history") == "true"), False
            if method == "GET" and len(parts) == 3 and ((name == "questions" and parts[2] == "answers") or (name == "answers" and parts[2] == "relationships")):
                if set(query) - {"set_id", "question_id", "role", "limit", "cursor"}:
                    raise ServiceError("invalid_request", field="query", issue="unknown_parameter")
                try:
                    limit, cursor = int(query.get("limit", 25)), int(query.get("cursor", 0))
                except ValueError:
                    raise ServiceError("invalid_request", field="pagination", issue="invalid")
                return 200, self.service.relationships(name, record_id, set_id=query.get("set_id"),
                    question_id=query.get("question_id"), role=query.get("role"), limit=limit, cursor=cursor), False
        raise ServiceError("method_not_allowed")
