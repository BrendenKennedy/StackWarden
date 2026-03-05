"""Shared HTTP response helpers for the web API."""

from __future__ import annotations

from fastapi.responses import JSONResponse


def validation_422(errors: list[dict[str, str]]) -> JSONResponse:
    """Return a 422 Unprocessable Entity response with validation error details."""
    return JSONResponse(status_code=422, content={"detail": errors})
