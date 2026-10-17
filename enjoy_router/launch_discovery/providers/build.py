"""Builds the provider table for the real server: {"gemini": ..., "claude": ..., "openai": ...}.

Keys are read from the process environment by NAME at call time (the model record holds the name, never the key). The Gemini access
token comes from google-auth's application default credentials, imported only when a Gemini call is made.
"""
from __future__ import annotations

import os

from ..http_transport import post_json
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .openai import OpenAIProvider


def env_secret(name):
    value = os.environ.get(name or "", "")
    return value or None


def google_token():
    import google.auth
    import google.auth.transport.requests
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def build_providers(project: str, transport=post_json, secret_fn=env_secret, token_fn=google_token) -> dict:
    return {"gemini": GeminiProvider(transport, token_fn, project), "claude": ClaudeProvider(transport, secret_fn),
            "openai": OpenAIProvider(transport, secret_fn)}
