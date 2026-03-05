"""Pure build optimization heuristics derived from profile facts.

This module only computes decisions. It does not inspect Docker, filesystem,
or runtime state.
"""

from __future__ import annotations

from stackwarden.domain.models import BuildOptimizationDecision, Profile, StackSpec

_DEFAULT_JOBS = 2
_DEFAULT_MEMORY_GB = 4.0
_SYSTEM_HEADROOM_GB = 2.0
_MIN_BUDGET_GB = 1.5
_PER_JOB_MEMORY_GB = 1.5
_BASE_BUILD_MEMORY_GB = 1.5


def estimate_build_memory_gb(stack: StackSpec) -> float:
    """Estimate memory footprint for a single build.

    The estimate is conservative and deterministic to keep planner behavior
    stable while still reflecting heavier dependency sets.
    """
    weight = (
        len(stack.components.pip) * 0.25
        + len(stack.components.npm) * 0.35
        + len(stack.components.apt) * 0.20
        + len(stack.files.copy_items) * 0.05
    )
    return round(_BASE_BUILD_MEMORY_GB + weight, 2)


def compute_build_optimization(profile: Profile, stack: StackSpec) -> BuildOptimizationDecision:
    """Compute hardware-aware build args and buildx flags.

    Defaults to conservative settings when host facts are missing.
    """
    facts = profile.host_facts
    cpu_logical = facts.cpu_cores_logical
    memory_total = facts.memory_gb_total
    est_mem = estimate_build_memory_gb(stack)

    warnings: list[str] = []
    notes: list[str] = []

    if not cpu_logical:
        warnings.append("Host logical CPU count unavailable; using conservative parallelism")
    if not memory_total:
        warnings.append("Host memory facts unavailable; using conservative memory budget")

    cpu_limit = max(1, int(cpu_logical or _DEFAULT_JOBS))
    memory_budget = None
    if memory_total:
        memory_budget = round(max(_MIN_BUDGET_GB, memory_total - _SYSTEM_HEADROOM_GB), 2)
    else:
        memory_budget = _DEFAULT_MEMORY_GB

    memory_bound_jobs = max(1, int(memory_budget // _PER_JOB_MEMORY_GB))
    cpu_bound_jobs = max(1, cpu_limit - 1)
    parallel_jobs = max(1, min(cpu_bound_jobs, memory_bound_jobs))

    oom_risk = "low"
    if est_mem > (memory_budget * 0.85):
        oom_risk = "high"
    elif est_mem > (memory_budget * 0.65):
        oom_risk = "medium"

    if oom_risk == "high":
        notes.append("High OOM risk detected; throttling build parallelism")
        parallel_jobs = max(1, min(parallel_jobs, 2))

    build_args = {
        "STACKWARDEN_BUILD_JOBS": str(parallel_jobs),
        "STACKWARDEN_BUILD_MEMORY_BUDGET_GB": f"{memory_budget:.2f}",
        "STACKWARDEN_EST_BUILD_MEMORY_GB": f"{est_mem:.2f}",
        "STACKWARDEN_OOM_RISK": oom_risk,
    }
    buildx_flags = ["--progress=plain"]

    return BuildOptimizationDecision(
        enabled=True,
        strategy="auto",
        cpu_parallelism=parallel_jobs,
        memory_budget_gb=memory_budget,
        estimated_build_memory_gb=est_mem,
        oom_risk=oom_risk,  # type: ignore[arg-type]
        build_args=build_args,
        buildx_flags=buildx_flags,
        warnings=warnings,
        notes=notes,
    )
