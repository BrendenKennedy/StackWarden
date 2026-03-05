"""Job and ensure endpoints, including SSE event streaming."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from stackwarden.web.deps import get_job_manager
from stackwarden.web.jobs.admission import decide_admission
from stackwarden.web.jobs.manager import JobManager
from stackwarden.web.jobs.models import JobRecord, JobStatus
from stackwarden.web.jobs.runners import run_ensure_job
from stackwarden.web.schemas import (
    CompatibilityFixDTO,
    EnsureRequestDTO,
    EnsureResponseDTO,
    JobDetailDTO,
    JobSummaryDTO,
    RetryWithFixResponseDTO,
)
from stackwarden.config import compatibility_strict_default, load_block, load_profile, load_stack
from stackwarden.domain.variants import validate_variant_flags
from stackwarden.resolvers.resolver import resolve

router = APIRouter(tags=["jobs"])

_active_tasks: set[asyncio.Task] = set()
_active_task_memory_gb: dict[asyncio.Task, float] = {}
_task_lock = asyncio.Lock()


@router.post("/ensure", response_model=EnsureResponseDTO)
async def ensure_build(
    body: EnsureRequestDTO,
    manager: JobManager = Depends(get_job_manager),
):
    # Fail fast before enqueueing long-running build jobs.
    profile = load_profile(body.profile_id)
    stack = load_stack(body.stack_id)
    block_specs = [load_block(block_id) for block_id in (stack.blocks or [])]
    if body.variants:
        validate_variant_flags(stack, body.variants)
    plan = resolve(
        profile,
        stack,
        blocks=block_specs,
        variants=body.variants,
        strict_mode=compatibility_strict_default(),
    )
    requested_memory_gb = 2.0
    if plan.decision.build_optimization and plan.decision.build_optimization.estimated_build_memory_gb:
        requested_memory_gb = max(1.0, plan.decision.build_optimization.estimated_build_memory_gb)

    async with _task_lock:
        reserved_memory_gb = round(sum(_active_task_memory_gb.values()), 2)
        admission = decide_admission(
            profile=profile,
            requested_memory_gb=requested_memory_gb,
            reserved_memory_gb=reserved_memory_gb,
            active_builds=len(_active_tasks),
        )
        if not admission.allowed:
            raise HTTPException(
                status_code=429,
                detail=admission.detail,
            )
        record = manager.create_job(
            profile_id=body.profile_id,
            stack_id=body.stack_id,
            variants=body.variants,
            flags=body.flags,
            build_optimization=(
                plan.decision.build_optimization.model_dump(mode="json")
                if plan.decision.build_optimization
                else {}
            ),
        )
        task = asyncio.create_task(run_ensure_job(record, manager))
        _active_tasks.add(task)
        _active_task_memory_gb[task] = requested_memory_gb

    def _cleanup(t: asyncio.Task) -> None:
        _active_tasks.discard(t)
        _active_task_memory_gb.pop(t, None)

    task.add_done_callback(_cleanup)
    return EnsureResponseDTO(job_id=record.job_id)


@router.get("/jobs", response_model=list[JobSummaryDTO])
async def list_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    manager: JobManager = Depends(get_job_manager),
):
    records = manager.list_jobs(limit=limit)
    return [_to_summary(r) for r in records]


@router.get("/jobs/{job_id}", response_model=JobDetailDTO)
async def get_job(
    job_id: str,
    manager: JobManager = Depends(get_job_manager),
):
    record = manager.get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return _to_detail(record)


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: str,
    manager: JobManager = Depends(get_job_manager),
):
    record = manager.get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    async def event_generator() -> AsyncIterator[dict]:
        async for event in manager.subscribe(job_id):
            yield {
                "event": event.type,
                "data": json.dumps({
                    "ts": event.ts.isoformat(),
                    "payload": event.payload,
                }),
            }

    return EventSourceResponse(
        event_generator(),
        ping=15,
        ping_message_factory=lambda: {"comment": "keepalive"},
    )


@router.get("/jobs/{job_id}/compatibility-fix", response_model=CompatibilityFixDTO)
async def get_compatibility_fix(
    job_id: str,
    manager: JobManager = Depends(get_job_manager),
):
    """Check if a failed build has an applicable compatibility fix."""
    record = manager.get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if record.status != JobStatus.FAILED:
        return CompatibilityFixDTO(
            applicable=False,
            message=f"Job is not failed (status: {record.status.value})",
        )
    error_message = record.error_message or ""
    log_content = None
    if record.log_path:
        try:
            with open(record.log_path, encoding="utf-8", errors="replace") as f:
                log_content = f.read()
        except OSError:
            pass
    base_image = None
    try:
        profile = load_profile(record.profile_id)
        stack = load_stack(record.stack_id)
        blocks = [load_block(bid) for bid in (stack.blocks or [])]
        plan = resolve(
            profile,
            stack,
            blocks=blocks,
            variants=record.variants,
            strict_mode=compatibility_strict_default(),
        )
        base_image = plan.decision.base_image
    except Exception:
        pass

    from stackwarden.domain.compatibility_fix import analyze_build_failure

    result = analyze_build_failure(error_message, log_content=log_content, base_image=base_image)
    return CompatibilityFixDTO(
        applicable=result.applicable,
        message=result.message,
        suggested_overrides=result.suggested_overrides,
        base_image_hint=result.base_image_hint,
    )


@router.post("/jobs/{job_id}/retry", response_model=EnsureResponseDTO)
async def retry_job(
    job_id: str,
    manager: JobManager = Depends(get_job_manager),
):
    """Create a new job with the same params as a failed job (simple retry without fix)."""
    record = manager.get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if record.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not failed (status: {record.status.value})",
        )
    new_record = manager.create_job(
        profile_id=record.profile_id,
        stack_id=record.stack_id,
        variants=record.variants,
        flags=record.flags,
        build_optimization=record.build_optimization,
    )
    task = asyncio.create_task(run_ensure_job(new_record, manager))
    _active_tasks.add(task)
    requested_memory_gb = 2.0
    if record.build_optimization and record.build_optimization.get("estimated_build_memory_gb"):
        requested_memory_gb = max(1.0, record.build_optimization["estimated_build_memory_gb"])
    _active_task_memory_gb[task] = requested_memory_gb

    def _cleanup(t: asyncio.Task) -> None:
        _active_tasks.discard(t)
        _active_task_memory_gb.pop(t, None)

    task.add_done_callback(_cleanup)
    return EnsureResponseDTO(job_id=new_record.job_id)


@router.post("/jobs/{job_id}/retry-with-fix", response_model=RetryWithFixResponseDTO)
async def retry_with_fix(
    job_id: str,
    manager: JobManager = Depends(get_job_manager),
):
    """Apply compatibility fix and create a new job with the same params."""
    record = manager.get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if record.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not failed (status: {record.status.value})",
        )
    error_message = record.error_message or ""
    log_content = None
    if record.log_path:
        try:
            with open(record.log_path, encoding="utf-8", errors="replace") as f:
                log_content = f.read()
        except OSError:
            pass
    base_image = None
    try:
        profile = load_profile(record.profile_id)
        stack = load_stack(record.stack_id)
        blocks = [load_block(bid) for bid in (stack.blocks or [])]
        plan = resolve(
            profile,
            stack,
            blocks=blocks,
            variants=record.variants,
            strict_mode=compatibility_strict_default(),
        )
        base_image = plan.decision.base_image
    except Exception:
        pass

    from stackwarden.domain.compatibility_fix import analyze_build_failure, apply_compatibility_fix

    result = analyze_build_failure(error_message, log_content=log_content, base_image=base_image)
    if not result.applicable or not result.suggested_overrides:
        raise HTTPException(
            status_code=400,
            detail=result.message or "No compatibility fix available for this failure",
        )

    applied = apply_compatibility_fix(
        result.suggested_overrides,
        base_image_contains=result.base_image_hint,
    )
    new_record = manager.create_job(
        profile_id=record.profile_id,
        stack_id=record.stack_id,
        variants=record.variants,
        flags=record.flags,
        build_optimization=record.build_optimization,
    )
    task = asyncio.create_task(run_ensure_job(new_record, manager))
    _active_tasks.add(task)
    requested_memory_gb = 2.0
    if record.build_optimization and record.build_optimization.get("estimated_build_memory_gb"):
        requested_memory_gb = max(1.0, record.build_optimization["estimated_build_memory_gb"])
    _active_task_memory_gb[task] = requested_memory_gb

    def _cleanup(t: asyncio.Task) -> None:
        _active_tasks.discard(t)
        _active_task_memory_gb.pop(t, None)

    task.add_done_callback(_cleanup)
    return RetryWithFixResponseDTO(
        job_id=new_record.job_id,
        applied=applied,
        message=f"Fix applied. New job {new_record.job_id} started.",
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    manager: JobManager = Depends(get_job_manager),
):
    record = manager.get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if record.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
        return {
            "canceled": False,
            "job_id": job_id,
            "detail": f"Job is already {record.status.value}",
        }

    cancelled = manager.request_cancel(job_id)
    if not cancelled:
        fresh = manager.get_job(job_id)
        status_val = fresh.status.value if fresh else "unknown"
        return {
            "canceled": False,
            "job_id": job_id,
            "detail": f"Job completed before cancel: {status_val}",
        }
    manager.publish_sentinel(job_id)
    return {"canceled": True, "job_id": job_id, "detail": "canceled"}


def _to_summary(r: JobRecord) -> JobSummaryDTO:
    return JobSummaryDTO(
        job_id=r.job_id,
        status=r.status.value,
        created_at=r.created_at.isoformat(),
        started_at=r.started_at.isoformat() if r.started_at else None,
        ended_at=r.ended_at.isoformat() if r.ended_at else None,
        profile_id=r.profile_id,
        stack_id=r.stack_id,
    )


def _to_detail(r: JobRecord) -> JobDetailDTO:
    return JobDetailDTO(
        job_id=r.job_id,
        status=r.status.value,
        created_at=r.created_at.isoformat(),
        started_at=r.started_at.isoformat() if r.started_at else None,
        ended_at=r.ended_at.isoformat() if r.ended_at else None,
        profile_id=r.profile_id,
        stack_id=r.stack_id,
        variants=r.variants,
        flags=r.flags,
        build_optimization=r.build_optimization,
        result_artifact_id=r.result_artifact_id,
        result_tag=r.result_tag,
        error_message=r.error_message,
        log_path=r.log_path,
    )
