"""Create and dry-run endpoints for stacks and profiles."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

from stackwarden.application.create_flows import (
    AppConflictError,
    AppInternalError,
    AppNotFoundError,
    AppValidationError,
    compose_stack_preview as app_compose_stack_preview,
    create_block as app_create_block,
    create_profile as app_create_profile,
    create_stack as app_create_stack,
    dry_run_block as app_dry_run_block,
    dry_run_profile as app_dry_run_profile,
    dry_run_stack as app_dry_run_stack,
    duplicate_profile as app_duplicate_profile,
    duplicate_stack as app_duplicate_stack,
)
from stackwarden.web.schemas import (
    BlockCreateRequest,
    BlockCreateResponse,
    ComposePreviewResponse,
    DryRunResponse,
    DuplicateProfileRequest,
    DuplicateStackRequest,
    ProfileCreateRequest,
    ProfileCreateResponse,
    StackCreateRequest,
    StackCreateResponse,
)
from stackwarden.web.util.responses import validation_422

log = logging.getLogger(__name__)

router = APIRouter(tags=["create"])


def _internal_500(exc: Exception) -> HTTPException:
    return HTTPException(status_code=500, detail=str(exc))


def _emit_metric(
    event_name: str,
    *,
    entity_type: str,
    entity_id: str,
    schema_version: int,
    outcome: str,
    duration_ms: int = 0,
    failure_reason: str | None = None,
    has_override: bool | None = None,
    host_class: str | None = None,
    runtime_family: str | None = None,
) -> None:
    """Emit structured metric events via logger for Phase 0 telemetry."""
    payload = {
        "event_name": event_name,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "schema_version": schema_version,
        "outcome": outcome,
        "duration_ms": duration_ms,
        "failure_reason": failure_reason,
        "has_override": has_override,
        "host_class": host_class,
        "runtime_family": runtime_family,
    }
    log.info("metric_event %s", payload)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/stacks", response_model=StackCreateResponse, status_code=201)
async def create_stack(req: StackCreateRequest):
    started = time.perf_counter()
    _emit_metric(
        "create_attempt",
        entity_type="stack",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="attempt",
        runtime_family=(req.build_strategy or "unknown"),
    )
    try:
        target = app_create_stack(req)
    except AppValidationError as exc:
        _emit_metric(
            "create_result",
            entity_type="stack",
            entity_id=req.id,
            schema_version=req.schema_version,
            outcome="validation_error",
            duration_ms=int((time.perf_counter() - started) * 1000),
            failure_reason="policy_restriction",
        )
        return validation_422(exc.errors)
    except AppConflictError as exc:
        _emit_metric(
            "create_result",
            entity_type="stack",
            entity_id=req.id,
            schema_version=req.schema_version,
            outcome="conflict",
            duration_ms=int((time.perf_counter() - started) * 1000),
            failure_reason="policy_restriction",
        )
        raise HTTPException(status_code=409, detail=exc.message)

    log.info("Created stack %s at %s", req.id, target)
    _emit_metric(
        "create_result",
        entity_type="stack",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="success",
        duration_ms=int((time.perf_counter() - started) * 1000),
        runtime_family=(req.build_strategy or "unknown"),
    )

    return StackCreateResponse(id=req.id, display_name=req.display_name, path=str(target))


@router.post("/stacks/dry-run", response_model=DryRunResponse)
async def dry_run_stack(req: StackCreateRequest):
    started = time.perf_counter()
    _emit_metric(
        "dry_run_attempt",
        entity_type="stack",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="attempt",
        runtime_family=(req.build_strategy or "unknown"),
    )
    result = app_dry_run_stack(req)
    if not result.valid:
        _emit_metric(
            "dry_run_result",
            entity_type="stack",
            entity_id=req.id,
            schema_version=req.schema_version,
            outcome="validation_error",
            duration_ms=int((time.perf_counter() - started) * 1000),
            failure_reason="dependency_conflict",
        )
        return DryRunResponse(yaml="", valid=False, errors=result.errors)
    _emit_metric(
        "dry_run_result",
        entity_type="stack",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="success",
        duration_ms=int((time.perf_counter() - started) * 1000),
        runtime_family=(req.build_strategy or "unknown"),
    )
    return DryRunResponse(yaml=result.yaml, valid=True, errors=[])


@router.post("/stacks/compose", response_model=ComposePreviewResponse)
async def compose_stack_preview(req: StackCreateRequest):
    started = time.perf_counter()
    _emit_metric(
        "compose_attempt",
        entity_type="stack",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="attempt",
    )
    try:
        result = app_compose_stack_preview(req)
    except AppInternalError as exc:
        _emit_metric(
            "compose_result",
            entity_type="stack",
            entity_id=req.id,
            schema_version=req.schema_version,
            outcome="internal_error",
            duration_ms=int((time.perf_counter() - started) * 1000),
            failure_reason="internal_fault",
        )
        raise _internal_500(exc) from exc
    if result.valid:
        _emit_metric(
            "compose_result",
            entity_type="stack",
            entity_id=req.id,
            schema_version=req.schema_version,
            outcome="success",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        return ComposePreviewResponse(
            valid=True,
            errors=[],
            yaml=result.yaml,
            resolved_spec=result.resolved_spec,
            dependency_conflicts=result.dependency_conflicts,
            tuple_conflicts=result.tuple_conflicts,
            runtime_conflicts=result.runtime_conflicts,
        )
    _emit_metric(
        "compose_result",
        entity_type="stack",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="failure",
        duration_ms=int((time.perf_counter() - started) * 1000),
        failure_reason="dependency_conflict",
    )
    return ComposePreviewResponse(
        valid=False,
        errors=result.errors,
        yaml="",
        resolved_spec=None,
        dependency_conflicts=result.dependency_conflicts,
        tuple_conflicts=result.tuple_conflicts,
        runtime_conflicts=result.runtime_conflicts,
    )
@router.post("/profiles", response_model=ProfileCreateResponse, status_code=201)
async def create_profile(req: ProfileCreateRequest):
    started = time.perf_counter()
    _emit_metric(
        "create_attempt",
        entity_type="profile",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="attempt",
        has_override=req.advanced_override,
        host_class="gpu" if (req.gpu.vendor_id or req.gpu.vendor) else "cpu",
        runtime_family=req.container_runtime,
    )
    try:
        target = app_create_profile(req)
    except AppValidationError as exc:
        _emit_metric(
            "create_result",
            entity_type="profile",
            entity_id=req.id,
            schema_version=req.schema_version,
            outcome="validation_error",
            duration_ms=int((time.perf_counter() - started) * 1000),
            failure_reason="host_mismatch",
        )
        return validation_422(exc.errors)
    except AppConflictError as exc:
        _emit_metric(
            "create_result",
            entity_type="profile",
            entity_id=req.id,
            schema_version=req.schema_version,
            outcome="conflict",
            duration_ms=int((time.perf_counter() - started) * 1000),
            failure_reason="policy_restriction",
        )
        raise HTTPException(status_code=409, detail=exc.message)
    log.info("Created profile %s at %s", req.id, target)
    _emit_metric(
        "create_result",
        entity_type="profile",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="success",
        duration_ms=int((time.perf_counter() - started) * 1000),
        has_override=req.advanced_override,
        host_class="gpu" if (req.gpu.vendor_id or req.gpu.vendor) else "cpu",
        runtime_family=req.container_runtime,
    )

    return ProfileCreateResponse(id=req.id, display_name=req.display_name, path=str(target))


@router.post("/profiles/dry-run", response_model=DryRunResponse)
async def dry_run_profile(req: ProfileCreateRequest):
    started = time.perf_counter()
    _emit_metric(
        "dry_run_attempt",
        entity_type="profile",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="attempt",
        has_override=req.advanced_override,
        host_class="gpu" if (req.gpu.vendor_id or req.gpu.vendor) else "cpu",
        runtime_family=req.container_runtime,
    )
    result = app_dry_run_profile(req)
    if not result.valid:
        _emit_metric(
            "dry_run_result",
            entity_type="profile",
            entity_id=req.id,
            schema_version=req.schema_version,
            outcome="validation_error",
            duration_ms=int((time.perf_counter() - started) * 1000),
            failure_reason="dependency_conflict",
        )
        return DryRunResponse(yaml="", valid=False, errors=result.errors)
    _emit_metric(
        "dry_run_result",
        entity_type="profile",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="success",
        duration_ms=int((time.perf_counter() - started) * 1000),
        has_override=req.advanced_override,
        host_class="gpu" if (req.gpu.vendor_id or req.gpu.vendor) else "cpu",
        runtime_family=req.container_runtime,
    )
    return DryRunResponse(yaml=result.yaml, valid=True, errors=[])


@router.post("/blocks", response_model=BlockCreateResponse, status_code=201)
async def create_block(req: BlockCreateRequest):
    started = time.perf_counter()
    _emit_metric(
        "create_attempt",
        entity_type="block",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="attempt",
        runtime_family=(req.build_strategy or "unknown"),
    )
    try:
        target = app_create_block(req)
    except AppValidationError as exc:
        _emit_metric(
            "create_result",
            entity_type="block",
            entity_id=req.id,
            schema_version=req.schema_version,
            outcome="validation_error",
            duration_ms=int((time.perf_counter() - started) * 1000),
            failure_reason="policy_restriction",
            runtime_family=(req.build_strategy or "unknown"),
        )
        return validation_422(exc.errors)
    except AppConflictError as exc:
        _emit_metric(
            "create_result",
            entity_type="block",
            entity_id=req.id,
            schema_version=req.schema_version,
            outcome="conflict",
            duration_ms=int((time.perf_counter() - started) * 1000),
            failure_reason="policy_restriction",
            runtime_family=(req.build_strategy or "unknown"),
        )
        raise HTTPException(status_code=409, detail=exc.message)
    log.info("Created block %s at %s", req.id, target)
    _emit_metric(
        "create_result",
        entity_type="block",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="success",
        duration_ms=int((time.perf_counter() - started) * 1000),
        runtime_family=(req.build_strategy or "unknown"),
    )
    return BlockCreateResponse(id=req.id, display_name=req.display_name, path=str(target))


@router.post("/blocks/dry-run", response_model=DryRunResponse)
async def dry_run_block(req: BlockCreateRequest):
    started = time.perf_counter()
    _emit_metric(
        "dry_run_attempt",
        entity_type="block",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="attempt",
        runtime_family=(req.build_strategy or "unknown"),
    )
    result = app_dry_run_block(req)
    if not result.valid:
        _emit_metric(
            "dry_run_result",
            entity_type="block",
            entity_id=req.id,
            schema_version=req.schema_version,
            outcome="validation_error",
            duration_ms=int((time.perf_counter() - started) * 1000),
            failure_reason="dependency_conflict",
            runtime_family=(req.build_strategy or "unknown"),
        )
        return DryRunResponse(yaml="", valid=False, errors=result.errors)
    _emit_metric(
        "dry_run_result",
        entity_type="block",
        entity_id=req.id,
        schema_version=req.schema_version,
        outcome="success",
        duration_ms=int((time.perf_counter() - started) * 1000),
        runtime_family=(req.build_strategy or "unknown"),
    )
    return DryRunResponse(yaml=result.yaml, valid=True, errors=[])


# ---------------------------------------------------------------------------
# Duplicate endpoints
# ---------------------------------------------------------------------------

@router.post("/stacks/{stack_id}/duplicate", response_model=StackCreateResponse, status_code=201)
async def duplicate_stack(stack_id: str, req: DuplicateStackRequest):
    try:
        new_id, display_name, target = app_duplicate_stack(stack_id, req.new_id, req.overrides)
    except AppNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except AppValidationError as exc:
        return validation_422(exc.errors)
    except AppConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.message)
    except AppInternalError as exc:
        raise _internal_500(exc) from exc
    log.info("Duplicated stack %s -> %s at %s", stack_id, req.new_id, target)
    return StackCreateResponse(id=new_id, display_name=display_name, path=str(target))


@router.post("/profiles/{profile_id}/duplicate", response_model=ProfileCreateResponse, status_code=201)
async def duplicate_profile(profile_id: str, req: DuplicateProfileRequest):
    try:
        new_id, display_name, target = app_duplicate_profile(profile_id, req.new_id, req.overrides)
    except AppNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except AppValidationError as exc:
        return validation_422(exc.errors)
    except AppConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.message)
    except AppInternalError as exc:
        raise _internal_500(exc) from exc
    log.info("Duplicated profile %s -> %s at %s", profile_id, req.new_id, target)
    return ProfileCreateResponse(id=new_id, display_name=display_name, path=str(target))
