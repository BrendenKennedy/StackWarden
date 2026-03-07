"""Shared helpers for job routes: plan resolution and failure context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from stackwarden.config import (
    compatibility_strict_default,
    load_layer,
    load_profile,
    load_stack,
    strict_host_optimization_default,
)
from stackwarden.resolvers.resolver import resolve

if TYPE_CHECKING:
    from stackwarden.domain.models import Plan

from stackwarden.web.jobs.models import JobRecord


def resolve_plan_for_job(record: JobRecord) -> "Plan | None":
    """Resolve the plan for a job record. Returns None on any error."""
    try:
        profile = load_profile(record.profile_id)
        stack = load_stack(record.stack_id)
        layers = [load_layer(lid) for lid in (stack.layers or [])]
        return resolve(
            profile,
            stack,
            layers=layers,
            variants=record.variants,
            strict_mode=compatibility_strict_default(),
            strict_host_optimization=strict_host_optimization_default(),
        )
    except Exception:
        return None


def get_failure_context(record: JobRecord) -> tuple[str, str | None, str | None]:
    """Extract error message, log content, and base image for compatibility fix analysis."""
    error_message = record.error_message or ""
    log_content = None
    if record.log_path:
        try:
            with open(record.log_path, encoding="utf-8", errors="replace") as f:
                log_content = f.read()
        except OSError:
            pass
    base_image = None
    plan = resolve_plan_for_job(record)
    if plan:
        base_image = plan.decision.base_image
    return (error_message, log_content, base_image)
