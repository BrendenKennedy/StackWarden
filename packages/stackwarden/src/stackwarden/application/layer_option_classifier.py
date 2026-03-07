"""Intent-first layer option classification for guided stack builders."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from stackwarden.config import list_layer_ids, load_layer, load_profile
from stackwarden.contracts.constants import STACK_LAYER_IDS
from stackwarden.domain.models import LayerSpec, Profile
from stackwarden.resolvers.compatibility import _REQUIREMENT_HANDLERS, _Req

@dataclass(frozen=True)
class _Rule:
    allowed: tuple[str, ...] = ()
    preferred: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()


_CANONICAL_INFERENCE: dict[str, str] = {
    "general": "general_api_inference",
    "general_api_inference": "general_api_inference",
    "custom": "general_api_inference",
    "llm": "llm_chat",
    "llm_chat": "llm_chat",
    "llm_serving": "llm_chat",
    "finetune": "llm_finetune",
    "training": "llm_finetune",
    "llm_finetune": "llm_finetune",
    "llm_training": "llm_finetune",
    "diffusion": "multimodal_generation",
    "multimodal_generation": "multimodal_generation",
    "vision": "vision",
    "embedding": "embeddings",
    "embeddings": "embeddings",
    "rag": "embeddings",
    "asr": "asr",
    "speech": "asr",
    "tts": "tts",
}

# Strict capability matrix for recommendation logic.
_CAPABILITY_MATRIX: dict[str, dict[str, _Rule]] = {
    "general_api_inference": {
        "optimization_compilation_layer": _Rule(
            preferred=("optimization", "compile", "attention", "sdpa", "flash"),
        ),
        "serving_layer": _Rule(preferred=("serving", "api", "grpc")),
        "application_orchestration_layer": _Rule(preferred=("orchestration", "worker", "agent")),
        "observability_operations_layer": _Rule(preferred=("observability", "metrics", "trace", "otel", "prometheus")),
    },
    "llm_chat": {
        "inference_engine_layer": _Rule(
            allowed=("llm", "vllm", "sglang", "transformer", "chat"),
            preferred=("vllm", "sglang", "llm"),
            blocked=("diffusion", "flux", "asr", "tts", "embedding", "vision"),
        ),
        "optimization_compilation_layer": _Rule(
            preferred=("attention", "sdpa", "flash", "quantization", "tensorrt"),
            blocked=("unsloth", "finetune", "training", "lora", "qlora"),
        ),
        "serving_layer": _Rule(preferred=("serving", "api", "grpc")),
    },
    "llm_finetune": {
        "inference_engine_layer": _Rule(
            allowed=("llm", "transformer", "model", "runtime"),
            preferred=("llm", "transformer"),
            blocked=("vllm", "sglang", "asr", "tts", "vision", "diffusion", "flux"),
        ),
        "optimization_compilation_layer": _Rule(
            preferred=("unsloth", "finetune", "training", "lora", "qlora", "peft", "bitsandbytes"),
            blocked=("serving", "triton"),
        ),
        "core_compute_layer": _Rule(
            preferred=("torch", "compute"),
        ),
        "driver_accelerator_layer": _Rule(
            preferred=("cuda", "accelerator", "nccl"),
        ),
    },
    "embeddings": {
        "inference_engine_layer": _Rule(
            allowed=("embedding", "retrieval", "sentence", "vector"),
            preferred=("embedding", "sentence", "retrieval"),
            blocked=("diffusion", "flux", "asr", "tts"),
        ),
        "optimization_compilation_layer": _Rule(
            preferred=("optimization", "compile", "attention", "sdpa"),
            blocked=("unsloth", "finetune", "training", "lora", "qlora"),
        ),
        "serving_layer": _Rule(preferred=("serving", "api", "grpc")),
        "observability_operations_layer": _Rule(preferred=("observability", "metrics", "trace", "otel")),
    },
    "multimodal_generation": {
        "inference_engine_layer": _Rule(
            allowed=("diffusion", "flux", "syncdreamer", "image-gen", "multimodal"),
            preferred=("flux", "diffusion", "syncdreamer"),
            blocked=("llm", "asr", "tts", "embedding"),
        ),
        "optimization_compilation_layer": _Rule(
            preferred=("compile", "optimization", "attention"),
            blocked=("unsloth", "finetune", "training", "lora", "qlora"),
        ),
        "serving_layer": _Rule(preferred=("serving", "api", "grpc")),
    },
    "vision": {
        "inference_engine_layer": _Rule(
            allowed=("vision", "detector", "onnx", "classification", "segmentation"),
            preferred=("vision", "onnx", "detector"),
            blocked=("diffusion", "flux", "syncdreamer", "asr", "tts", "llm", "embedding"),
        ),
        "optimization_compilation_layer": _Rule(
            preferred=("optimization", "compile", "attention", "sdpa", "flash"),
            blocked=("unsloth", "finetune", "training", "lora", "qlora"),
        ),
        "serving_layer": _Rule(preferred=("serving", "api", "grpc")),
        "observability_operations_layer": _Rule(preferred=("observability", "metrics", "trace", "otel")),
    },
    "asr": {
        "inference_engine_layer": _Rule(
            allowed=("asr", "speech", "whisper"),
            preferred=("whisper", "asr", "speech"),
            blocked=("diffusion", "flux", "tts", "llm", "embedding"),
        ),
        "optimization_compilation_layer": _Rule(
            preferred=("optimization", "compile", "attention", "sdpa"),
            blocked=("unsloth", "finetune", "training", "lora", "qlora"),
        ),
        "serving_layer": _Rule(preferred=("serving", "api", "grpc")),
        "observability_operations_layer": _Rule(preferred=("observability", "metrics", "trace", "otel")),
    },
    "tts": {
        "inference_engine_layer": _Rule(
            allowed=("tts", "speech", "voice"),
            preferred=("tts", "voice"),
            blocked=("diffusion", "flux", "asr", "llm", "embedding"),
        ),
        "optimization_compilation_layer": _Rule(
            preferred=("optimization", "compile", "attention", "sdpa"),
            blocked=("unsloth", "finetune", "training", "lora", "qlora"),
        ),
        "serving_layer": _Rule(preferred=("serving", "api", "grpc")),
        "observability_operations_layer": _Rule(preferred=("observability", "metrics", "trace", "otel")),
    },
}


@dataclass(frozen=True)
class LayerOptionClassification:
    id: str
    display_name: str
    stack_layer: str
    tags: list[str]
    tier: str
    score: int
    reasons: list[str]
    selected: bool = False


@dataclass(frozen=True)
class ClassifiedLayerOptions:
    stack_layer: str
    options: list[LayerOptionClassification]


def _safe_all_layers() -> dict[str, LayerSpec]:
    out: dict[str, LayerSpec] = {}
    for layer_id in list_layer_ids():
        try:
            layer = load_layer(layer_id)
        except Exception:  # noqa: BLE001 - keep wizard resilient in mixed catalogs
            continue
        out[layer.id] = layer
    return out


def _canonical_inference_type(inference_type: str | None) -> str:
    key = (inference_type or "").strip().lower()
    return _CANONICAL_INFERENCE.get(key, "general_api_inference")


def _token_set(layer: LayerSpec) -> set[str]:
    tokens = set()
    for raw in [layer.id, layer.display_name, *(layer.tags or [])]:
        for token in str(raw).lower().replace("-", "_").split("_"):
            token = token.strip()
            if token:
                tokens.add(token)
    return tokens


def _matrix_eval(layer: LayerSpec, *, inference_type: str) -> tuple[bool, int, list[str]]:
    rules_for_inference = _CAPABILITY_MATRIX.get(inference_type, {})
    rule = rules_for_inference.get(layer.stack_layer)
    if not rule:
        return False, 0, []
    tokens = _token_set(layer)
    reasons: list[str] = []
    if rule.blocked and any(token in tokens for token in rule.blocked):
        return True, -1, [
            f"Blocked by {inference_type} matrix for {layer.stack_layer}."
        ]
    if rule.allowed and not any(token in tokens for token in rule.allowed):
        return True, -1, [
            f"Not in allowed set for {inference_type} on {layer.stack_layer}."
        ]
    score = 0
    if rule.preferred and any(token in tokens for token in rule.preferred):
        score += 2
        reasons.append(f"Preferred for {inference_type} in {layer.stack_layer}.")
    elif rule.allowed:
        score += 1
        reasons.append(f"Allowed by {inference_type} matrix for {layer.stack_layer}.")
    return False, score, reasons


def _requirement_issues(layer: LayerSpec, profile: Profile | None) -> list[str]:
    if profile is None:
        return []
    issues: list[str] = []
    confidence = profile.host_facts.confidence or {}
    for key, value in (layer.requires or {}).items():
        handler = _REQUIREMENT_HANDLERS.get(key)
        if not handler:
            continue
        req = _Req(layer_id=layer.id, key=key, value=value)
        for issue in handler(req, profile, confidence):
            issues.append(issue.message)
    return issues


def classify_layer_options(
    *,
    selected_layers: list[str] | None = None,
    inference_type: str | None = None,
    inference_profile: str | None = None,
    target_profile_id: str | None = None,
) -> list[ClassifiedLayerOptions]:
    all_layers = _safe_all_layers()
    selected_ids = set(selected_layers or [])
    selected_specs = [all_layers[layer_id] for layer_id in selected_layers or [] if layer_id in all_layers]
    profile = load_profile(target_profile_id) if target_profile_id else None
    _ = inference_profile  # Reserved for future tuning modes; strict matrix ignores token profiles.
    canonical_inference = _canonical_inference_type(inference_type)

    by_stack_layer: dict[str, list[LayerOptionClassification]] = defaultdict(list)
    for candidate in all_layers.values():
        reasons: list[str] = []
        incompatible = False

        matrix_blocked, score, matrix_reasons = _matrix_eval(candidate, inference_type=canonical_inference)
        if matrix_blocked:
            incompatible = True
            reasons.extend(matrix_reasons)
        else:
            reasons.extend(matrix_reasons)

        conflict_with_selected = sorted(selected_ids & set(candidate.incompatible_with or []))
        if conflict_with_selected:
            incompatible = True
            reasons.append(
                f"Incompatible with selected layer(s): {', '.join(conflict_with_selected)}"
            )
        for layer in selected_specs:
            if candidate.id in (layer.incompatible_with or []):
                incompatible = True
                reasons.append(f"Incompatible with selected layer '{layer.id}'")

        requirement_errors = _requirement_issues(candidate, profile)
        if requirement_errors:
            incompatible = True
            reasons.extend(requirement_errors)

        if score > 0 and not incompatible and not reasons:
            reasons.append("Matches strict capability matrix for selected intent.")

        tier = "incompatible" if incompatible else ("recommended" if score > 0 else "compatible")
        by_stack_layer[candidate.stack_layer].append(
            LayerOptionClassification(
                id=candidate.id,
                display_name=candidate.display_name,
                stack_layer=candidate.stack_layer,
                tags=list(candidate.tags or []),
                tier=tier,
                score=score,
                reasons=reasons,
                selected=candidate.id in selected_ids,
            )
        )

    ordered_groups: list[ClassifiedLayerOptions] = []
    for stack_layer in STACK_LAYER_IDS:
        options = by_stack_layer.get(stack_layer, [])
        options.sort(key=lambda row: (0 if row.tier == "recommended" else 1 if row.tier == "compatible" else 2, -row.score, row.id))
        ordered_groups.append(ClassifiedLayerOptions(stack_layer=stack_layer, options=options))
    return ordered_groups
