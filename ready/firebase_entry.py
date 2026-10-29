"""Firebase HTTP function entry; copied to staged main.py by prepare_deploy.py.

READY_API_KEY is a Secret Manager binding. Deployment uses an explicit project.
No memory fallback, seeding, key printing or participant session infrastructure.
"""
import os
from functools import lru_cache
from firebase_functions import https_fn

from ready.application import Application
from ready.crud.firestore_store import FirestoreStore
from ready.services import ReadyService


@lru_cache(maxsize=1)
def application():
    project = os.environ.get("GCLOUD_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise RuntimeError("Firebase runtime project is not configured")
    origins = [value.strip() for value in os.environ.get("READY_ALLOWED_ORIGINS", "").split(",") if value.strip()]
    return Application(ReadyService(FirestoreStore(project)), os.environ.get("READY_API_KEY", ""), origins)


@https_fn.on_request(secrets=["READY_API_KEY"], timeout_sec=60, region="us-central1")
def ready_api(req: https_fn.Request) -> https_fn.Response:
    target = req.path + ("?" + req.query_string.decode() if req.query_string else "")
    status, headers, body = application().handle(req.method, target, dict(req.headers), req.get_data(), req.remote_addr or "unknown")
    return https_fn.Response(body, status=status, headers=headers)
