"""Guided stack create wizard."""

from __future__ import annotations

import re
from typing import Any

from rich.console import Console

from stackwarden.application.create_flows import (
    compose_stack_preview,
    create_stack,
    dry_run_stack,
    validate_stack_create_request,
)
from stackwarden.application.layer_option_classifier import classify_layer_options
from stackwarden.config import list_layer_ids, list_profile_ids, load_layer, load_profile
from stackwarden.contracts import ALLOWED_BUILD_STRATEGIES, SPEC_ID_PATTERN

from stackwarden.ui.create_wizard_engine import CreateWizardResult, WizardPrompts

LAYER_ORDER = [
    "system_runtime_layer",
    "driver_accelerator_layer",
    "core_compute_layer",
    "inference_engine_layer",
    "optimization_compilation_layer",
    "serving_layer",
    "application_orchestration_layer",
    "observability_operations_layer",
]
REQUIRED_LAYER_GROUPS = {"system_runtime_layer", "inference_engine_layer", "serving_layer"}

_INFERENCE_NEEDS: dict[str, list[str]] = {
    "llm_chat": ["llm", "inference", "serving"],
    "embeddings": ["embeddings", "inference", "serving"],
    "multimodal_generation": ["multimodal", "generation", "serving"],
    "asr": ["speech", "asr", "serving"],
    "general_api_inference": ["inference", "serving"],
}

_INFERENCE_SUMMARY: dict[str, str] = {
    "llm_chat": "Chat-style LLM inference endpoint.",
    "embeddings": "Vector embedding inference endpoint.",
    "multimodal_generation": "Multimodal generation inference endpoint.",
    "asr": "Speech recognition inference endpoint.",
    "general_api_inference": "General model inference API endpoint.",
}

def _all_layers() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for layer_id in list_layer_ids():
        try:
            layer = load_layer(layer_id)
        except Exception:  # noqa: BLE001 - skip malformed layers in mixed catalogs
            continue
        result[layer_id] = layer
    return result


def _recommend_layers(
    *,
    inference_type: str,
    target_profile_id: str | None,
    all_layers: dict[str, Any],
) -> tuple[dict[str, str], list[str], list[str]]:
    decision_trace: list[str] = []
    selected_features: list[str] = [f"inference_type:{inference_type}"]
    if target_profile_id:
        selected_features.append(f"target_profile:{target_profile_id}")

    recommendation: dict[str, str] = {}
    groups = classify_layer_options(
        selected_layers=[],
        inference_type=inference_type,
        inference_profile=None,
        target_profile_id=target_profile_id,
    )
    grouped = {group.stack_layer: group.options for group in groups}
    for stack_layer, options in grouped.items():
        if not options or stack_layer not in LAYER_ORDER:
            continue
        preferred = next((opt for opt in options if opt.tier == "recommended"), None)
        if preferred is not None:
            chosen = preferred
        elif stack_layer in REQUIRED_LAYER_GROUPS:
            chosen = next((opt for opt in options if opt.tier == "compatible"), options[0])
        else:
            continue
        recommendation[stack_layer] = chosen.id
        selected_features.append(f"{stack_layer}:{chosen.id}")
        decision_trace.append(
            f"Recommended {chosen.id} for {stack_layer} via intent-first option classification."
        )

    return recommendation, selected_features, decision_trace


def _review_layers(
    *,
    prompts: WizardPrompts,
    all_layers: dict[str, Any],
    recommended: dict[str, str],
    inference_type: str,
    target_profile_id: str | None,
) -> tuple[list[str], list[str]]:
    selected: list[str] = []
    review_trace: list[str] = []

    for stack_layer in LAYER_ORDER:
        groups = classify_layer_options(
            selected_layers=selected,
            inference_type=inference_type,
            inference_profile=None,
            target_profile_id=target_profile_id,
        )
        grouped = {group.stack_layer: group.options for group in groups}
        classified_options = grouped.get(stack_layer, [])
        options = [opt.id for opt in classified_options]
        if not options:
            continue
        default = recommended.get(stack_layer) or options[0]
        label_to_id: dict[str, str] = {"skip": "skip"}
        choices = ["skip"]
        for opt in classified_options:
            label = opt.id
            if opt.tier == "recommended":
                label = f"{opt.id} [recommended]"
            elif opt.tier == "incompatible":
                reason = opt.reasons[0] if opt.reasons else "compatibility warning"
                label = f"{opt.id} [incompatible: {reason}]"
            elif opt.reasons:
                label = f"{opt.id} [compatible: {opt.reasons[0]}]"
            label_to_id[label] = opt.id
            choices.append(label)
        if stack_layer == "system_runtime_layer":
            choices = [label for label in choices if label != "skip"]
        if stack_layer == "inference_engine_layer":
            prompt = (
                "Inference engine layer (runtime execution engine, not model framework): pick layer"
            )
        else:
            prompt = f"{stack_layer.replace('_', ' ').title()}: pick layer"
        default_choice = next((label for label, layer_id in label_to_id.items() if layer_id == default), choices[0])
        chosen_label = prompts.choose(prompt, choices, default=default_choice)
        chosen = label_to_id.get(chosen_label, chosen_label)
        if chosen == "skip":
            continue
        selected.append(chosen)
        if chosen != default:
            review_trace.append(f"User changed {stack_layer} from {default} to {chosen}.")
        else:
            review_trace.append(f"Accepted recommended {chosen} for {stack_layer}.")
        selected_opt = next((opt for opt in classified_options if opt.id == chosen), None)
        if selected_opt and selected_opt.tier == "incompatible":
            review_trace.append(
                f"User intentionally selected incompatible layer {chosen} for {stack_layer}: "
                f"{'; '.join(selected_opt.reasons) or 'compatibility warning'}."
            )

    # Enforce minimum viable inference stack.
    required_layers = REQUIRED_LAYER_GROUPS
    selected_stack_layers = {all_layers[layer_id].stack_layer for layer_id in selected}
    missing = sorted(required_layers - selected_stack_layers)
    if missing:
        raise ValueError(f"Missing required layer groups for inference stack: {', '.join(missing)}")
    review_trace.append(f"Final layer set for {inference_type}: {', '.join(selected)}")
    return selected, review_trace


def run_stack_create_wizard(
    *,
    stack_id: str | None = None,
    display_name: str | None = None,
    target_profile_id: str | None = None,
    build_strategy: str | None = None,
    layers: list[str] | None = None,
    non_interactive: bool = False,
    dry_run: bool = False,
    yes: bool = False,
    output: str | None = None,
    console: Console | None = None,
) -> CreateWizardResult:
    prompts = WizardPrompts(console=console, non_interactive=non_interactive)

    profile_ids = list_profile_ids()
    selected_profile_id = target_profile_id
    if not selected_profile_id and profile_ids:
        selected_profile_id = prompts.choose(
            "Target profile",
            profile_ids,
            default=profile_ids[0],
        )
    if not selected_profile_id:
        raise ValueError("A target profile is required for stack creation.")
    if selected_profile_id:
        # Validate profile existence while keeping payload schema unchanged.
        load_profile(selected_profile_id)

    inference_type = prompts.choose(
        "Inference type",
        [
            "llm_chat",
            "embeddings",
            "multimodal_generation",
            "asr",
            "general_api_inference",
        ],
        default="general_api_inference",
    )

    chosen_strategy: str | None = build_strategy
    if chosen_strategy is None:
        strategy_choice = prompts.choose(
            "Build strategy (separate from layer selection)",
            ["default", *ALLOWED_BUILD_STRATEGIES],
            default="default",
        )
        chosen_strategy = None if strategy_choice == "default" else strategy_choice
    elif chosen_strategy == "":
        chosen_strategy = None

    all_layers = _all_layers()
    recommended_layers, selected_features, recommendation_trace = _recommend_layers(
        inference_type=inference_type,
        target_profile_id=selected_profile_id,
        all_layers=all_layers,
    )

    selected_layers: list[str] = list(layers or [])
    if not selected_layers:
        selected_layers, review_trace = _review_layers(
            prompts=prompts,
            all_layers=all_layers,
            recommended=recommended_layers,
            inference_type=inference_type,
            target_profile_id=selected_profile_id,
        )
    else:
        review_trace = ["Layer set provided via CLI --layer overrides."]
        required_layers = REQUIRED_LAYER_GROUPS
        selected_stack_layers = {
            all_layers[layer_id].stack_layer for layer_id in selected_layers if layer_id in all_layers
        }
        missing = sorted(required_layers - selected_stack_layers)
        if missing:
            raise ValueError(f"Missing required layer groups for inference stack: {', '.join(missing)}")

    resolved_id = stack_id or prompts.text("Stack ID", default="new_stack")
    if not re.fullmatch(SPEC_ID_PATTERN, resolved_id):
        raise ValueError("Stack id must match pattern: ^[a-z][a-z0-9_\\-]{2,63}$")
    resolved_name = display_name or prompts.text("Display name", default=resolved_id.replace("_", " ").title())

    payload: dict[str, Any] = {
        "schema_version": 3,
        "kind": "stack_recipe",
        "id": resolved_id,
        "display_name": resolved_name,
        "target_profile_id": selected_profile_id,
        "layers": selected_layers,
        "build_strategy": chosen_strategy,
        "base_role": None,
        "copy_items": [],
        "variants": {},
        "intent": {
            "outcome": f"{inference_type}_service",
            "summary": _INFERENCE_SUMMARY[inference_type],
        },
        "requirements": {
            "needs": _INFERENCE_NEEDS[inference_type],
            "optimize_for": ["latency", "reliability"],
            "constraints": {"target_profile_id": selected_profile_id},
        },
        "selected_features": selected_features,
        "decision_trace": recommendation_trace + review_trace,
    }
    incompatible_notes = [line for line in review_trace if "intentionally selected incompatible layer" in line.lower()]
    if incompatible_notes:
        prompts.console.print("[yellow]Compatibility warnings for selected layers:[/yellow]")
        for line in incompatible_notes:
            prompts.console.print(f"- {line}")
    req = validate_stack_create_request(payload)
    compose = compose_stack_preview(req)
    if not compose.valid:
        return CreateWizardResult(
            entity="stack",
            id=req.id,
            valid=False,
            errors=compose.errors,
            metadata={
                "dependency_conflicts": compose.dependency_conflicts,
                "tuple_conflicts": compose.tuple_conflicts,
                "runtime_conflicts": compose.runtime_conflicts,
            },
        )
    dry = dry_run_stack(req)
    result = CreateWizardResult(
        entity="stack",
        id=req.id,
        valid=dry.valid,
        yaml=dry.yaml,
        errors=dry.errors,
        metadata={
            "target_profile_id": selected_profile_id,
            "dependency_conflicts": compose.dependency_conflicts,
            "tuple_conflicts": compose.tuple_conflicts,
            "runtime_conflicts": compose.runtime_conflicts,
        },
    )
    prompts.print_yaml_preview(dry.yaml)
    prompts.maybe_write_output(output, dry.yaml)
    if not dry.valid or dry_run:
        return result
    if not (yes or non_interactive) and not prompts.confirm("Create stack now?", default=True):
        return result
    target = create_stack(req)
    result.created = True
    result.path = str(target)
    return result
