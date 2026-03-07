"""Ensure job runner — executes ensure_internal in a background thread
and streams log events via the JobManager.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from stackwarden.domain.enums import ArtifactStatus
from stackwarden.domain.errors import CancellationRequestedError
from stackwarden.web.jobs.models import JobEvent, JobStatus

if TYPE_CHECKING:
    from stackwarden.web.jobs.manager import JobManager
    from stackwarden.web.jobs.models import JobRecord

log = logging.getLogger(__name__)


async def run_ensure_job(record: JobRecord, manager: JobManager) -> None:
    """Top-level async entry point for running an ensure job."""
    job_id = record.job_id
    log_path = Path(record.log_path)

    fresh = manager.get_job(job_id)
    if fresh and fresh.status == JobStatus.CANCELED:
        _publish(manager, job_id, "status", "canceled")
        manager.publish_sentinel(job_id)
        manager.clear_cancel_signal(job_id)
        return

    record.status = JobStatus.RUNNING
    record.started_at = datetime.now(timezone.utc)
    manager.update_job(record)
    _publish(manager, job_id, "status", "running")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch()

    tail_task = asyncio.create_task(_tail_log(job_id, log_path, manager))

    try:
        result_record, resolved_plan = await asyncio.to_thread(
            _run_ensure_sync,
            record.profile_id,
            record.stack_id,
            record.variants,
            record.flags,
            log_path,
            lambda: manager.is_cancel_requested(job_id),
        )

        fresh = manager.get_job(job_id)
        if fresh and fresh.status == JobStatus.CANCELED:
            log.info("Job %s was canceled during execution", job_id)
            _publish(manager, job_id, "status", "canceled")
        elif result_record.status == ArtifactStatus.BUILT:
            record.build_optimization = (
                resolved_plan.decision.build_optimization.model_dump(mode="json")
                if resolved_plan and resolved_plan.decision.build_optimization
                else record.build_optimization
            )
            record.status = JobStatus.SUCCEEDED
            record.ended_at = datetime.now(timezone.utc)
            record.result_artifact_id = result_record.id
            record.result_tag = result_record.tag
            manager.update_job(record)

            _publish(manager, job_id, "result", json.dumps({
                "artifact_id": result_record.id,
                "tag": result_record.tag,
            }))
            _publish(manager, job_id, "status", "succeeded")
        else:
            record.build_optimization = (
                resolved_plan.decision.build_optimization.model_dump(mode="json")
                if resolved_plan and resolved_plan.decision.build_optimization
                else record.build_optimization
            )
            record.status = JobStatus.FAILED
            record.ended_at = datetime.now(timezone.utc)
            record.result_artifact_id = result_record.id
            record.result_tag = result_record.tag
            record.error_message = result_record.error_detail or "Build did not finish in built state"
            manager.update_job(record)
            _publish(manager, job_id, "status", "failed")
    except CancellationRequestedError as exc:
        record.status = JobStatus.CANCELED
        record.ended_at = datetime.now(timezone.utc)
        record.error_message = str(exc)
        manager.update_job(record)
        _publish(manager, job_id, "status", "canceled")
    except Exception as exc:
        fresh = manager.get_job(job_id)
        if fresh and fresh.status == JobStatus.CANCELED:
            log.info("Job %s was canceled during execution", job_id)
            _publish(manager, job_id, "status", "canceled")
        else:
            record.status = JobStatus.FAILED
            record.ended_at = datetime.now(timezone.utc)
            record.error_message = str(exc)
            manager.update_job(record)

            log.exception("Job %s failed with unexpected error", job_id)
            _publish(manager, job_id, "error", json.dumps({
                "message": "internal_error",
            }))
            _publish(manager, job_id, "status", "failed")

    finally:
        tail_task.cancel()
        tail_offset = 0
        try:
            tail_offset = await tail_task
        except asyncio.CancelledError:
            pass
        await _flush_remaining(job_id, log_path, manager, tail_offset or 0)
        manager.publish_sentinel(job_id)
        manager.clear_cancel_signal(job_id)


def _run_ensure_sync(
    profile_id: str,
    stack_id: str,
    variants: dict | None,
    flags: dict,
    log_path: Path,
    cancel_check,
):
    """Synchronous wrapper — runs in thread via asyncio.to_thread."""
    from stackwarden.domain.ensure import ensure_internal

    return ensure_internal(
        profile_id,
        stack_id,
        variants=variants,
        rebuild=flags.get("rebuild", False),
        upgrade_base=flags.get("upgrade_base", False),
        immutable=flags.get("immutable", False),
        run_hooks=not flags.get("no_hooks", False),
        explain=flags.get("explain", False),
        build_log_path=log_path,
        cancel_check=cancel_check,
    )


async def _tail_log(job_id: str, log_path: Path, manager: JobManager) -> int:
    """Continuously tail the job log file and publish lines as SSE events.

    Returns the final file offset so _flush_remaining can pick up where we left off.
    """
    offset = 0
    try:
        while True:
            await asyncio.sleep(0.3)
            if not log_path.exists():
                continue
            try:
                with open(log_path, "r") as f:
                    f.seek(offset)
                    new_data = f.read()
                    if new_data:
                        offset = f.tell()
                        for line in new_data.splitlines():
                            if line.strip():
                                _publish(manager, job_id, "log", line)
            except OSError:
                pass
    except asyncio.CancelledError:
        return offset
    return offset


async def _flush_remaining(
    job_id: str, log_path: Path, manager: JobManager, tail_offset: int = 0,
) -> None:
    """Read any final lines that arrived after the tail was cancelled."""
    if not log_path.exists():
        return
    try:
        with open(log_path, "r") as f:
            f.seek(tail_offset)
            remaining = f.read()
        if remaining:
            for line in remaining.splitlines():
                if line.strip():
                    _publish(manager, job_id, "log", line)
    except OSError:
        pass


def _publish(manager: JobManager, job_id: str, event_type: str, payload: str) -> None:
    manager.publish_event(job_id, JobEvent(
        type=event_type,  # type: ignore[arg-type]
        ts=datetime.now(timezone.utc),
        payload=payload,
    ))
