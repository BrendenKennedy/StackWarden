"""Memory-aware admission policy for build jobs."""

from __future__ import annotations

from dataclasses import dataclass

from stacksmith.domain.models import Profile

_FALLBACK_MAX_CONCURRENCY = 4
_SYSTEM_HEADROOM_GB = 2.0


@dataclass(frozen=True)
class AdmissionDecision:
    allowed: bool
    detail: str
    requested_memory_gb: float
    reserved_memory_gb: float
    memory_budget_gb: float | None


def decide_admission(
    profile: Profile,
    requested_memory_gb: float,
    reserved_memory_gb: float,
    active_builds: int,
) -> AdmissionDecision:
    """Decide whether a new build can be admitted."""
    total = profile.host_facts.memory_gb_total
    if not total:
        if active_builds >= _FALLBACK_MAX_CONCURRENCY:
            return AdmissionDecision(
                allowed=False,
                detail=(
                    f"Too many concurrent builds ({_FALLBACK_MAX_CONCURRENCY}) with unknown host memory. "
                    "Try again later."
                ),
                requested_memory_gb=requested_memory_gb,
                reserved_memory_gb=reserved_memory_gb,
                memory_budget_gb=None,
            )
        return AdmissionDecision(
            allowed=True,
            detail="Allowed with fallback concurrency policy (host memory unknown).",
            requested_memory_gb=requested_memory_gb,
            reserved_memory_gb=reserved_memory_gb,
            memory_budget_gb=None,
        )

    budget = round(max(2.0, total - _SYSTEM_HEADROOM_GB), 2)
    projected = round(reserved_memory_gb + requested_memory_gb, 2)
    if projected > budget:
        return AdmissionDecision(
            allowed=False,
            detail=(
                "Insufficient build memory budget. "
                f"requested={requested_memory_gb:.2f}GB, reserved={reserved_memory_gb:.2f}GB, budget={budget:.2f}GB."
            ),
            requested_memory_gb=requested_memory_gb,
            reserved_memory_gb=reserved_memory_gb,
            memory_budget_gb=budget,
        )
    return AdmissionDecision(
        allowed=True,
        detail="Allowed by memory-aware admission policy.",
        requested_memory_gb=requested_memory_gb,
        reserved_memory_gb=reserved_memory_gb,
        memory_budget_gb=budget,
    )
