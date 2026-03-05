"""Server-host detection hints for profile prefill."""

from __future__ import annotations

import logging
import time
from threading import Lock

from fastapi import APIRouter, Query, Response

from stackwarden.web.schemas import (
    DetectionHintsDTO,
    RemoteDetectionDeferredResponseDTO,
    RemoteDetectionRequestDTO,
)
from stackwarden.web.services.host_detection import detect_server_hints

router = APIRouter(tags=["system"])
log = logging.getLogger(__name__)

_CACHE_TTL_SEC = 10.0
_cache_lock = Lock()
_cache_data: DetectionHintsDTO | None = None
_cache_ts = 0.0


@router.get("/system/detection-hints", response_model=DetectionHintsDTO)
async def detection_hints(refresh: bool = Query(default=False)):
    global _cache_data, _cache_ts
    try:
        now = time.monotonic()
        with _cache_lock:
            if not refresh and _cache_data is not None and (now - _cache_ts) < _CACHE_TTL_SEC:
                return _cache_data

        hints = detect_server_hints()
        with _cache_lock:
            _cache_data = hints
            _cache_ts = now
        return hints
    except Exception:
        log.exception("Failed to serve /system/detection-hints")
        raise


@router.post(
    "/system/detection-hints/remote",
    response_model=RemoteDetectionDeferredResponseDTO,
    status_code=501,
)
async def remote_detection_hints(_body: RemoteDetectionRequestDTO, response: Response):
    try:
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = "Wed, 01 Jul 2026 00:00:00 GMT"
        response.headers["Link"] = '</api/system/detection-hints>; rel="successor-version"'
        return RemoteDetectionDeferredResponseDTO(
            detail=(
                "Remote SSH hardware detection is deferred and will be removed in a "
                "future release. Use /api/system/detection-hints on the server host."
            ),
        )
    except Exception:
        log.exception("Failed to serve /system/detection-hints/remote")
        raise
