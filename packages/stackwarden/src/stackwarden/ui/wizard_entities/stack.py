"""Guided stack create wizard."""

from __future__ import annotations

import re
from typing import Any

from rich.console import Console

from stackwarden.application.create_flows import compose_stack_preview, create_stack, dry_run_stack
from stackwarden.config import list_block_ids, list_profile_ids, load_block, load_profile
from stackwarden.contracts import ALLOWED_BUILD_STRATEGIES, SPEC_ID_PATTERN
from stackwarden.domain.block_catalog import load_block_catalog
from stackwarden.web.schemas import StackCreateRequest

from stackwarden.ui.create_wizard_engine import CreateWizardResult, WizardPrompts

LAYER_ORDER = [
    "system_runtime_layer",
    "driver_accelerator_layer",
    "core_compute_layer",
    "model_runtime_layer",
    "optimization_compilation_layer",
    "serving_layer",
    "application_orchestration_layer",
    "observability_operations_layer",
]

_TAG_LAYER_MAP: list[tuple[str, str]] = [
    ("observability", "observability_operations_layer"),
    ("monitoring", "observability_operations_layer"),
    ("metrics", "observability_operations_layer"),
    ("tracing", "observability_operations_layer"),
    ("serving", "serving_layer"),
    ("gateway", "serving_layer"),
    ("api", "application_orchestration_layer"),
    ("worker", "application_orchestration_layer"),
    ("agent", "application_orchestration_layer"),
    ("orchestration", "application_orchestration_layer"),
    ("optimization", "optimization_compilation_layer"),
    ("quantization", "optimization_compilation_layer"),
    ("compile", "optimization_compilation_layer"),
    ("cuda", "driver_accelerator_layer"),
    ("accelerator", "driver_accelerator_layer"),
    ("llm", "model_runtime_layer"),
    ("diffusion", "model_runtime_layer"),
    ("vision", "model_runtime_layer"),
    ("asr", "model_runtime_layer"),
    ("tts", "model_runtime_layer"),
    ("torch", "core_compute_layer"),
    ("onnx", "core_compute_layer"),
    ("ubuntu", "system_runtime_layer"),
    ("debian", "system_runtime_layer"),
    ("bookworm", "system_runtime_layer"),
    ("os", "system_runtime_layer"),
    ("infra", "system_runtime_layer"),
    ("system", "system_runtime_layer"),
]


def _infer_layer_from_tags(tags: list[str]) -> str:
    joined = " ".join(tags).lower()
    for token, layer in _TAG_LAYER_MAP:
        if token in joined:
            return layer
    return "application_orchestration_layer"


def _block_layers() -> dict[str, str]:
    preset_layers: dict[str, str] = {}
    catalog = load_block_catalog()
    for preset in catalog.presets:
        if preset.layers:
            preset_layers[preset.id] = preset.layers[0]

    result: dict[str, str] = {}
    for block_id in list_block_ids():
        block = load_block(block_id)
        result[block_id] = preset_layers.get(block_id) or _infer_layer_from_tags(block.tags)
    return result


def run_stack_create_wizard(
    *,
    stack_id: str | None = None,
    display_name: str | None = None,
    target_profile_id: str | None = None,
    build_strategy: str | None = None,
    blocks: list[str] | None = None,
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
    if selected_profile_id:
        # Validate profile existence while keeping payload schema unchanged.
        load_profile(selected_profile_id)

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

    selected_blocks: list[str] = list(blocks or [])
    layer_by_block = _block_layers()
    if not selected_blocks:
        for layer in LAYER_ORDER:
            options = [bid for bid, layer_id in layer_by_block.items() if layer_id == layer]
            if not options:
                continue
            label = layer.replace("_", " ").title()
            choices = options if layer == "system_runtime_layer" else ["skip", *options]
            default = options[0] if layer == "system_runtime_layer" else "skip"
            chosen = prompts.choose(f"{label}: pick block", choices, default=default)
            if chosen == "skip":
                continue
            if chosen not in selected_blocks:
                selected_blocks.append(chosen)

    has_system_runtime = any(layer_by_block.get(block_id) == "system_runtime_layer" for block_id in selected_blocks)
    if not has_system_runtime:
        raise ValueError("At least one system/runtime layer block is required.")

    resolved_id = stack_id or prompts.text("Stack ID", default="new_stack")
    if not re.fullmatch(SPEC_ID_PATTERN, resolved_id):
        raise ValueError("Stack id must match pattern: ^[a-z][a-z0-9_\\-]{2,63}$")
    resolved_name = display_name or prompts.text("Display name", default=resolved_id.replace("_", " ").title())

    payload: dict[str, Any] = {
        "schema_version": 3,
        "kind": "stack_recipe",
        "id": resolved_id,
        "display_name": resolved_name,
        "blocks": selected_blocks,
        "build_strategy": chosen_strategy,
        "base_role": None,
        "copy_items": [],
        "variants": {},
    }
    req = StackCreateRequest.model_validate(payload)
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
