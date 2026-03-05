"""In-process job manager with SQLite persistence and SSE fan-out."""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from stacksmith.paths import get_logs_root
from stacksmith.web.jobs.models import JobEvent, JobRecord, JobStatus
from stacksmith.web.jobs.store import JobStore

log = logging.getLogger(__name__)

_SENTINEL = object()


class JobManager:
    """Manages job lifecycle, persistence, and SSE event fan-out."""

    def __init__(self, store: JobStore) -> None:
        self._store = store
        self._subscribers: dict[str, list[asyncio.Queue[JobEvent | object]]] = {}
        self._cancel_signals: dict[str, threading.Event] = {}

        orphaned = store.mark_orphaned_running_as_failed()
        if orphaned:
            log.warning("Marked %d orphaned running job(s) as failed on startup", orphaned)

    def create_job(
        self,
        profile_id: str,
        stack_id: str,
        variants: dict[str, Any] | None = None,
        flags: dict[str, bool] | None = None,
        build_optimization: dict[str, Any] | None = None,
    ) -> JobRecord:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        log_dir = get_logs_root() / "jobs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{job_id}.log"

        record = JobRecord(
            job_id=job_id,
            status=JobStatus.QUEUED,
            created_at=datetime.now(timezone.utc),
            profile_id=profile_id,
            stack_id=stack_id,
            variants=variants,
            flags=flags or {},
            build_optimization=build_optimization or {},
            log_path=str(log_path),
        )
        self._store.insert(record)
        self._cancel_signals[job_id] = threading.Event()
        return record

    def get_job(self, job_id: str) -> JobRecord | None:
        return self._store.get(job_id)

    def list_jobs(self, limit: int | None = 50, offset: int | None = None) -> list[JobRecord]:
        return self._store.list_recent(limit=limit, offset=offset)

    def update_job(self, record: JobRecord) -> None:
        self._store.update(record)

    def cancel_job_if_active(self, job_id: str) -> bool:
        """Atomically cancel a job if it is still queued or running."""
        return self._store.cancel_if_active(job_id)

    def request_cancel(self, job_id: str) -> bool:
        """Persist cancel state and trigger cooperative cancellation signal."""
        cancelled = self.cancel_job_if_active(job_id)
        if cancelled:
            self._cancel_signals.setdefault(job_id, threading.Event()).set()
        return cancelled

    def is_cancel_requested(self, job_id: str) -> bool:
        ev = self._cancel_signals.get(job_id)
        return bool(ev and ev.is_set())

    def clear_cancel_signal(self, job_id: str) -> None:
        self._cancel_signals.pop(job_id, None)

    def publish_event(self, job_id: str, event: JobEvent) -> None:
        queues = self._subscribers.get(job_id, [])
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                log.debug("Event queue full for job %s, dropping event", job_id)

    def publish_sentinel(self, job_id: str) -> None:
        """Signal all subscribers that the job is done.

        For the sentinel we drain the oldest event if the queue is full,
        because missing the termination signal would leave clients hanging.
        """
        queues = self._subscribers.get(job_id, [])
        for q in queues:
            try:
                q.put_nowait(_SENTINEL)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(_SENTINEL)
                except asyncio.QueueFull:
                    log.warning("Could not deliver sentinel for job %s", job_id)

    async def subscribe(self, job_id: str) -> AsyncIterator[JobEvent]:
        q: asyncio.Queue[JobEvent | object] = asyncio.Queue(maxsize=1000)
        subs = self._subscribers.setdefault(job_id, [])
        subs.append(q)
        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield JobEvent(
                        type="progress",
                        ts=datetime.now(timezone.utc),
                        payload="keepalive",
                    )
                    continue
                if item is _SENTINEL:
                    break
                yield item  # type: ignore[misc]
        finally:
            subs.remove(q)
            if not subs:
                self._subscribers.pop(job_id, None)
