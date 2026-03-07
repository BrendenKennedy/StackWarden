"""Pure build optimization heuristics derived from profile facts.

This module only computes decisions. It does not inspect Docker, filesystem,
or runtime state.
"""

from __future__ import annotations

from stackwarden.domain.models import LayerSpec, BuildOptimizationDecision, Profile, StackSpec

_DEFAULT_JOBS = 2
_DEFAULT_MEMORY_GB = 4.0
_SYSTEM_HEADROOM_GB = 2.0
_MIN_BUDGET_GB = 1.5
_PER_JOB_MEMORY_GB = 1.5
_BASE_BUILD_MEMORY_GB = 1.5


def _stack_requires_gpu(layers: list[LayerSpec] | None) -> bool:
    if not layers:
        return False
    for layer in layers:
        req = layer.requires or {}
        if req.get("gpu_vendor") or req.get("cuda_runtime") or req.get("container_runtime") == "nvidia":
            return True
    return False


def _layer_tokens(layers: list[LayerSpec] | None) -> set[str]:
    out: set[str] = set()
    for layer in layers or []:
        for raw in [layer.id, *(layer.tags or [])]:
            normalized = str(raw).strip().lower().replace("-", "_")
            if normalized:
                out.add(normalized)
            for token in normalized.split("_"):
                token = token.strip()
                if token:
                    out.add(token)
    return out


def _profile_optimization_route(profile: Profile) -> str:
    gpu_vendor = str(profile.gpu.vendor_id or profile.gpu.vendor or "").strip().lower()
    # Aggressive-by-default for accelerator-backed systems; balanced for CPU-only.
    return "aggressive" if gpu_vendor in {"nvidia", "amd", "intel"} else "balanced"


def _workload_family(stack: StackSpec, layer_tokens: set[str]) -> str:
    task = str(stack.task.value).strip().lower()
    if task in {"llm", "diffusion", "vision", "asr", "tts"}:
        return task
    if task == "embedding":
        return "embeddings"
    if any(token in layer_tokens for token in {"rag", "retrieval", "agentic"}):
        return "rag"
    if any(token in layer_tokens for token in {"embedding", "sentence", "vector"}):
        return "embeddings"
    if any(token in layer_tokens for token in {"whisper", "asr", "speech"}):
        return "asr"
    if any(token in layer_tokens for token in {"vision", "onnx", "detector", "segmentation"}):
        return "vision"
    if any(token in layer_tokens for token in {"diffusion", "flux", "syncdreamer", "hunyuan"}):
        return "diffusion"
    if any(token in layer_tokens for token in {"llm", "vllm", "sglang"}):
        return "llm"
    return "general"


def _serving_stack(stack: StackSpec, layer_tokens: set[str]) -> str:
    api = str(stack.api.value).strip().lower()
    if api == "grpc" or "grpc" in layer_tokens:
        return "grpc"
    if api == "fastapi" or "fastapi" in layer_tokens:
        return "fastapi"
    if "triton" in layer_tokens:
        return "triton"
    return "generic"


def _bounded_knobs(
    *,
    profile_route: str,
    is_nvidia: bool,
    has_inference_layer: bool,
    has_serving_layer: bool,
    serving: str,
) -> dict[str, str]:
    """Small stable knob set for long-term maintainability.

    The resolver intentionally avoids per-workload micro-heuristics here.
    """
    if profile_route == "aggressive":
        knobs = {
            "dtype": "bf16" if is_nvidia else "fp16",
            "attention": "sdpa_flash_prefer" if is_nvidia else "sdpa_auto",
            "compile_enabled": "1" if has_inference_layer else "0",
            "compile_mode": "max_autotune",
            "serving_tuning": "aggressive",
            "batch_profile": "throughput_high",
            "memory_strategy": "device_first",
            "cuda_graph": "hybrid",
            "prefill_policy": "none",
        }
    else:
        knobs = {
            "dtype": "fp16",
            "attention": "sdpa_auto",
            "compile_enabled": "1" if has_inference_layer else "0",
            "compile_mode": "default",
            "serving_tuning": "balanced",
            "batch_profile": "balanced",
            "memory_strategy": "portable",
            "cuda_graph": "off",
            "prefill_policy": "none",
        }

    if not has_serving_layer:
        knobs["serving_tuning"] = "none"
    elif profile_route == "aggressive":
        if serving == "grpc":
            knobs["serving_tuning"] = "grpc_channel_pool_aggressive"
        elif serving == "triton":
            knobs["serving_tuning"] = "triton_dynamic_batching_aggressive"
        elif serving == "fastapi":
            knobs["serving_tuning"] = "fastapi_worker_replica_aggressive"
    return knobs


def _gpu_compute_capability(profile: Profile) -> str:
    if profile.gpu.compute_capability:
        return str(profile.gpu.compute_capability)
    for device in profile.gpu_devices:
        if device.compute_capability:
            return str(device.compute_capability)
    return ""


def _host_signature(profile: Profile) -> str:
    facts = profile.host_facts
    tokens = [
        str(profile.arch.value),
        str(profile.container_runtime.value),
        str(profile.gpu.vendor or ""),
        str(profile.gpu.family_id or profile.gpu.family or ""),
        str(_gpu_compute_capability(profile)),
        str(facts.driver_version or ""),
        str(facts.cpu_cores_logical or ""),
        str(facts.memory_gb_total or ""),
    ]
    return "|".join(tokens)


def _validate_strict_host_facts(profile: Profile, *, requires_gpu: bool) -> None:
    missing: list[str] = []
    facts = profile.host_facts
    if not facts.cpu_cores_logical:
        missing.append("host_facts.cpu_cores_logical")
    if not facts.memory_gb_total:
        missing.append("host_facts.memory_gb_total")
    if requires_gpu:
        if not facts.driver_version:
            missing.append("host_facts.driver_version")
        if not _gpu_compute_capability(profile):
            missing.append("gpu.compute_capability (or gpu_devices[].compute_capability)")
    if missing:
        joined = ", ".join(missing)
        raise ValueError(
            "Strict host-specific optimization requires detected host facts. "
            f"Missing: {joined}"
        )


def _is_curated_profile(profile: Profile) -> bool:
    tags = {str(tag).strip().lower() for tag in (profile.tags or [])}
    if "curated" in tags:
        return True
    labels = {
        str(key).strip().lower(): str(value).strip().lower()
        for key, value in (profile.labels or {}).items()
    }
    return labels.get("optimization_scope") == "curated_authoritative"


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


def compute_build_optimization(
    profile: Profile,
    stack: StackSpec,
    *,
    layers: list[LayerSpec] | None = None,
    strict_host_specific: bool = False,
) -> BuildOptimizationDecision:
    """Compute hardware-aware build args and buildx flags.

    Defaults to conservative settings when host facts are missing.
    """
    requires_gpu = _stack_requires_gpu(layers)
    facts = profile.host_facts
    cpu_logical = facts.cpu_cores_logical
    memory_total = facts.memory_gb_total
    est_mem = estimate_build_memory_gb(stack)

    warnings: list[str] = []
    notes: list[str] = []
    notes.append("Applied bounded heuristic optimization profile.")

    if strict_host_specific and requires_gpu:
        try:
            _validate_strict_host_facts(profile, requires_gpu=requires_gpu)
        except ValueError:
            if _is_curated_profile(profile):
                warnings.append(
                    "Strict host-specific optimization facts missing on curated profile; "
                    "falling back to conservative host tuning defaults."
                )
            else:
                raise

    if not cpu_logical:
        warnings.append("Host logical CPU count unavailable; using conservative parallelism")
    if not memory_total:
        warnings.append("Host memory facts unavailable; using conservative memory budget")

    gpu_family = str(profile.gpu.family_id or profile.gpu.family or "")
    gpu_cc = _gpu_compute_capability(profile)
    layer_tokens = _layer_tokens(layers)
    profile_route = _profile_optimization_route(profile)
    policy = "strict_host_specific" if profile_route == "aggressive" else "portable"
    is_nvidia = str(profile.gpu.vendor_id or profile.gpu.vendor).lower() == "nvidia"
    workload = _workload_family(stack, layer_tokens)
    serving = _serving_stack(stack, layer_tokens)

    has_inference_layer = "inference" in layer_tokens or "runtime" in layer_tokens
    has_serving_layer = "serving" in layer_tokens or "fastapi" in layer_tokens or "grpc" in layer_tokens

    knobs = _bounded_knobs(
        profile_route=profile_route,
        is_nvidia=is_nvidia,
        has_inference_layer=has_inference_layer,
        has_serving_layer=has_serving_layer,
        serving=serving,
    )
    torch_dtype = knobs["dtype"]
    attention_backend = knobs["attention"]
    torch_compile = knobs["compile_enabled"] == "1"
    tf32_enabled = is_nvidia

    cpu_limit = max(1, int(cpu_logical or _DEFAULT_JOBS))
    memory_budget = None
    if memory_total:
        memory_budget = round(max(_MIN_BUDGET_GB, memory_total - _SYSTEM_HEADROOM_GB), 2)
    else:
        memory_budget = _DEFAULT_MEMORY_GB

    memory_bound_jobs = max(1, int(memory_budget // _PER_JOB_MEMORY_GB))
    cpu_bound_jobs = max(1, cpu_limit if profile_route == "aggressive" else cpu_limit - 1)
    parallel_jobs = max(1, min(cpu_bound_jobs, memory_bound_jobs))

    oom_risk = "low"
    if est_mem > (memory_budget * 0.85):
        oom_risk = "high"
    elif est_mem > (memory_budget * 0.65):
        oom_risk = "medium"

    if oom_risk == "high":
        notes.append("High OOM risk detected; throttling build parallelism")
        parallel_jobs = max(1, min(parallel_jobs, 2))

    serving_profile = knobs["serving_tuning"]
    compile_mode = knobs["compile_mode"] if torch_compile else "default"

    build_args = {
        "STACKWARDEN_BUILD_JOBS": str(parallel_jobs),
        "STACKWARDEN_BUILD_MEMORY_BUDGET_GB": f"{memory_budget:.2f}",
        "STACKWARDEN_EST_BUILD_MEMORY_GB": f"{est_mem:.2f}",
        "STACKWARDEN_OOM_RISK": oom_risk,
        "STACKWARDEN_OPT_MODE": "build_time",
        "STACKWARDEN_OPT_POLICY": policy,
        "STACKWARDEN_OPT_PROFILE": profile_route,
        "STACKWARDEN_OPT_WORKLOAD": workload,
        "STACKWARDEN_OPT_SERVING": serving,
        "STACKWARDEN_OPT_HOST_SIGNATURE": _host_signature(profile),
        "STACKWARDEN_OPT_GPU_FAMILY": gpu_family,
        "STACKWARDEN_OPT_GPU_COMPUTE_CAPABILITY": gpu_cc,
        "STACKWARDEN_OPT_DRIVER_VERSION": str(facts.driver_version or ""),
        "STACKWARDEN_TORCH_DTYPE": torch_dtype,
        "STACKWARDEN_TORCH_ATTENTION": attention_backend,
        "STACKWARDEN_TORCH_COMPILE": "1" if torch_compile else "0",
        "STACKWARDEN_TORCH_COMPILE_MODE": compile_mode,
        "STACKWARDEN_TORCH_TF32": "1" if tf32_enabled else "0",
        "STACKWARDEN_SERVING_TUNING": serving_profile,
        "STACKWARDEN_BATCH_PROFILE": knobs["batch_profile"],
        "STACKWARDEN_MEMORY_STRATEGY": knobs["memory_strategy"],
        "STACKWARDEN_CUDA_GRAPH": knobs["cuda_graph"],
        "STACKWARDEN_PREFILL_POLICY": knobs["prefill_policy"],
    }
    optimization_env = {
        "STACKWARDEN_OPT_MODE": "build_time",
        "STACKWARDEN_OPT_POLICY": policy,
        "STACKWARDEN_OPT_PROFILE": profile_route,
        "STACKWARDEN_OPT_WORKLOAD": workload,
        "STACKWARDEN_OPT_SERVING": serving,
        "STACKWARDEN_OPT_HOST_SIGNATURE": _host_signature(profile),
        "STACKWARDEN_OPT_GPU_FAMILY": gpu_family,
        "STACKWARDEN_OPT_GPU_COMPUTE_CAPABILITY": gpu_cc,
        "STACKWARDEN_OPT_DRIVER_VERSION": str(facts.driver_version or ""),
        "STACKWARDEN_TORCH_DTYPE": torch_dtype,
        "STACKWARDEN_TORCH_ATTENTION": attention_backend,
        "STACKWARDEN_TORCH_COMPILE": "1" if torch_compile else "0",
        "STACKWARDEN_TORCH_COMPILE_MODE": compile_mode,
        "STACKWARDEN_TORCH_TF32": "1" if tf32_enabled else "0",
        "STACKWARDEN_SERVING_TUNING": serving_profile,
        "STACKWARDEN_BATCH_PROFILE": knobs["batch_profile"],
        "STACKWARDEN_MEMORY_STRATEGY": knobs["memory_strategy"],
        "STACKWARDEN_CUDA_GRAPH": knobs["cuda_graph"],
        "STACKWARDEN_PREFILL_POLICY": knobs["prefill_policy"],
    }
    buildx_flags = ["--progress=plain"]

    return BuildOptimizationDecision(
        enabled=True,
        strategy=profile_route,
        policy=policy,  # type: ignore[arg-type]
        strict_host_specific=strict_host_specific,
        host_signature=_host_signature(profile),
        gpu_family=gpu_family,
        gpu_compute_capability=gpu_cc,
        driver_version=str(facts.driver_version or ""),
        torch_dtype=torch_dtype,
        attention_backend=attention_backend,
        torch_compile_enabled=torch_compile,
        tf32_enabled=tf32_enabled,
        cpu_parallelism=parallel_jobs,
        memory_budget_gb=memory_budget,
        estimated_build_memory_gb=est_mem,
        oom_risk=oom_risk,  # type: ignore[arg-type]
        build_args=build_args,
        optimization_env=optimization_env,
        buildx_flags=buildx_flags,
        warnings=warnings,
        notes=notes,
    )
