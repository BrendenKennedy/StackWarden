"""API schema version negotiation helpers."""

from __future__ import annotations

from fastapi import Response


def resolve_schema_version(schema: str | None, *, default: int = 1) -> int:
    if not schema:
        return default
    raw = schema.strip().lower().removeprefix("v")
    if raw.isdigit():
        parsed = int(raw)
        return parsed if parsed >= 1 else default
    return default


def apply_version_headers(response: Response, *, requested: int) -> None:
    response.headers["X-Stacksmith-Schema-Version"] = str(requested)
    if requested <= 1:
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = "Wed, 31 Dec 2026 23:59:59 GMT"

