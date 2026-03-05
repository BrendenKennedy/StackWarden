#!/usr/bin/env python3
"""Diagnose metadata endpoint failures for local web UI."""

from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"
ENDPOINTS = [
    "/api/health",
    "/api/meta/enums",
    "/api/system/config",
    "/api/system/detection-hints",
    "/api/meta/create-contracts?schema=v2",
    "/api/settings/hardware-catalogs",
]


def _classify_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code >= 500:
            return "endpoint_500"
        return f"http_{exc.code}"
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, socket.gaierror):
            return "proxy_error"
        return "backend_unreachable"
    return "unknown_error"


def _get(path: str) -> tuple[str, int | None, str]:
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", "replace")
            return ("ok", status, body[:300])
    except Exception as exc:  # noqa: BLE001
        kind = _classify_error(exc)
        status = getattr(exc, "code", None)
        detail = str(exc)
        return (kind, status, detail[:300])


def main() -> int:
    results = {}
    worst = 0
    for ep in ENDPOINTS:
        kind, status, detail = _get(ep)
        results[ep] = {"status": kind, "http_status": status, "detail": detail}
        if kind != "ok":
            worst = 1
        print(f"{ep}: {kind} ({status})")
        if kind != "ok":
            print(f"  detail: {detail}")
    print("\njson:")
    print(json.dumps(results, indent=2))
    return worst


if __name__ == "__main__":
    sys.exit(main())

