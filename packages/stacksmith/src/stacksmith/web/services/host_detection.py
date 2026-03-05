"""Read-only server-host detection helpers for profile prefill hints."""

from __future__ import annotations

from stacksmith.domain.hardware_catalog import reconcile_detected_fields
from stacksmith.web.schemas import CudaDTO, DetectionHintsDTO, DetectionProbeDTO, GpuDTO
from stacksmith.web.services.host_detection_probes import (
    FACT_REGISTRY,
    build_probe_registry,
    init_context,
    merge_payload,
    probe_bootstrap_invariants,
    probe_execution_context,
    probe_os_router,
    run_probe,
    update_context_from_payload,
)


def detect_server_hints() -> DetectionHintsDTO:
    """Gather best-effort server-host hints for profile prefill.

    Detection chain:
    1) bootstrap invariant facts
    2) execution context
    3) OS-family routing
    4) capability-gated probes (docker, nvidia, resources)
    5) catalog reconciliation + quality metrics
    """
    payload: dict = {
        "host_scope": "server",
        "cuda_available": False,
        "capabilities_suggested": [],
        "confidence": {},
        "probes": [],
    }
    context = init_context()

    bootstrap = run_probe("bootstrap_invariants", probe_bootstrap_invariants, context)
    payload["probes"].append(bootstrap.probe)
    merge_payload(payload, bootstrap.payload)
    update_context_from_payload(context, payload)

    execution = run_probe("execution_context", probe_execution_context, context)
    payload["probes"].append(execution.probe)
    execution_ctx = execution.payload.pop("context", {})
    merge_payload(payload, execution.payload)
    context.docker_available = bool(execution_ctx.get("docker_available"))
    context.docker_socket_present = bool(execution_ctx.get("docker_socket_present"))
    context.nvidia_smi_available = bool(execution_ctx.get("nvidia_smi_available"))
    context.in_container = bool(execution_ctx.get("in_container"))

    os_route = run_probe("os_router", probe_os_router, context)
    payload["probes"].append(os_route.probe)
    merge_payload(payload, os_route.payload)

    for spec in build_probe_registry(context):
        if not spec.applies(context):
            payload["probes"].append(
                DetectionProbeDTO(
                    name=spec.name,
                    status="warn",
                    message="Skipped by capability/OS gate",
                    duration_ms=0,
                )
            )
            continue
        res = run_probe(spec.name, spec.run, context)
        payload["probes"].append(res.probe)
        merge_payload(payload, res.payload)

    if payload.get("cuda") and not payload.get("container_runtime"):
        payload["container_runtime"] = "nvidia"

    if payload.get("os") == "linux":
        pass
    elif payload.get("os"):
        payload["probes"].append(
            DetectionProbeDTO(
                name="os_policy",
                status="warn",
                message="Only linux is currently supported for profile creation.",
                duration_ms=0,
            )
        )

    if isinstance(payload.get("cuda"), dict):
        payload["cuda"] = CudaDTO(**payload["cuda"])
    if isinstance(payload.get("gpu"), dict):
        payload["gpu"] = GpuDTO(**payload["gpu"])
    resolved_ids, matched_by, unmatched = reconcile_detected_fields(payload)
    payload["resolved_ids"] = resolved_ids
    payload["matched_by"] = matched_by
    payload["unmatched_suggestions"] = unmatched
    confidence = payload.get("confidence", {}) or {}
    tracked = [name for name, include_if in FACT_REGISTRY if include_if(payload)]
    unknowns = sum(1 for k in tracked if confidence.get(k, "unknown") == "unknown")
    payload["unknown_rate"] = (unknowns / len(tracked)) if tracked else 0.0
    return DetectionHintsDTO(**payload)
