"""Shared helpers for web session cookie parsing and token hashing."""

from __future__ import annotations

import hashlib

SESSION_COOKIE_NAME = "stackwarden_session"


def hash_session_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def parse_session_cookie(raw: str | None) -> tuple[str, str] | None:
    if not raw or "." not in raw:
        return None
    session_id, token_secret = raw.split(".", 1)
    if not session_id or not token_secret:
        return None
    return session_id, token_secret
