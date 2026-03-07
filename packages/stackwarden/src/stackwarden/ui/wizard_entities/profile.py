"""Guided profile create wizard."""

from __future__ import annotations

import re
from typing import Any

from rich.console import Console

from stackwarden.application.create_flows import (
    create_profile,
    dry_run_profile,
    validate_profile_create_request,
)
from stackwarden.contracts import SPEC_ID_PATTERN
from stackwarden.domain.hardware_catalog import load_hardware_catalog
from stackwarden.web.services.host_detection import detect_server_hints

from stackwarden.ui.create_wizard_engine import CreateWizardResult, WizardPrompts


def run_profile_create_wizard(
    *,
    profile_id: str | None = None,
    display_name: str | None = None,
    arch: str | None = None,
    container_runtime: str | None = None,
    non_interactive: bool = False,
    dry_run: bool = False,
    yes: bool = False,
    output: str | None = None,
    console: Console | None = None,
) -> CreateWizardResult:
    prompts = WizardPrompts(console=console, non_interactive=non_interactive)
    hardware = load_hardware_catalog()

    try:
        hints = detect_server_hints()
        resolved_ids = dict(hints.resolved_ids or {})
    except Exception:
        hints = None
        resolved_ids = {}

    arch_choices = [i.id for i in hardware.arch]
    runtime_choices = [i.id for i in hardware.container_runtime]
    os_family_choices = [i.id for i in hardware.os_family]
    gpu_vendor_choices = [i.id for i in hardware.gpu_vendor]
    gpu_family_choices = [i.id for i in hardware.gpu_family]

    chosen_arch = arch or prompts.choose(
        "Architecture",
        arch_choices,
        default=resolved_ids.get("arch_id") or (hints.arch if hints else None),
    )
    chosen_runtime = container_runtime or prompts.choose(
        "Container runtime",
        runtime_choices,
        default=resolved_ids.get("container_runtime_id") or (hints.container_runtime if hints else "nvidia"),
    )
    chosen_os_family = prompts.choose(
        "OS family",
        os_family_choices,
        default=resolved_ids.get("os_family_id") or "linux",
    )
    os_versions = [i.id for i in hardware.os_version if not i.parent_id or i.parent_id == chosen_os_family]
    if not os_versions:
        os_versions = [i.id for i in hardware.os_version]
    chosen_os_version = prompts.choose(
        "OS version",
        os_versions,
        default=resolved_ids.get("os_version_id"),
    )
    chosen_gpu_vendor = prompts.choose(
        "GPU vendor",
        gpu_vendor_choices,
        default=resolved_ids.get("gpu_vendor_id") or "nvidia",
    )
    gpu_families = [i.id for i in hardware.gpu_family if not i.parent_id or i.parent_id == chosen_gpu_vendor]
    if not gpu_families:
        gpu_families = gpu_family_choices
    chosen_gpu_family = prompts.choose(
        "GPU family",
        gpu_families,
        default=resolved_ids.get("gpu_family_id"),
    )

    resolved_id = profile_id or prompts.text("Profile ID", default="new_profile")
    if not re.fullmatch(SPEC_ID_PATTERN, resolved_id):
        raise ValueError(
            "Profile id must match pattern: "
            "^[a-z][a-z0-9_\\-]{2,63}$"
        )
    resolved_name = display_name or prompts.text("Display name", default=resolved_id.replace("_", " ").title())

    payload: dict[str, Any] = {
        "schema_version": 3,
        "id": resolved_id,
        "display_name": resolved_name,
        "arch": chosen_arch,
        "os": "linux",
        "os_family": chosen_os_family,
        "os_version": chosen_os_version,
        "os_family_id": chosen_os_family,
        "os_version_id": chosen_os_version,
        "container_runtime": chosen_runtime,
        "gpu": {
            "vendor": chosen_gpu_vendor,
            "family": chosen_gpu_family,
            "vendor_id": chosen_gpu_vendor,
            "family_id": chosen_gpu_family,
            "model_id": resolved_ids.get("gpu_model_id"),
            "compute_capability": hints.gpu.compute_capability if hints and hints.gpu else None,
        },
        "cuda": (
            {
                "major": hints.cuda.major,
                "minor": hints.cuda.minor,
                "variant": hints.cuda.variant,
            }
            if hints and hints.cuda
            else None
        ),
        "gpu_devices": hints.gpu_devices if hints else [],
        "constraints": {"disallow": {}, "require": {}},
        "requirements": {"needs": [], "optimize_for": [], "constraints": {}},
        "advanced_override": False,
    }
    req = validate_profile_create_request(payload)
    dry = dry_run_profile(req)
    result = CreateWizardResult(
        entity="profile",
        id=req.id,
        valid=dry.valid,
        yaml=dry.yaml,
        errors=dry.errors,
    )
    prompts.print_yaml_preview(dry.yaml)
    prompts.maybe_write_output(output, dry.yaml)
    if not dry.valid or dry_run:
        return result
    if not (yes or non_interactive) and not prompts.confirm("Create profile now?", default=True):
        return result
    target = create_profile(req)
    result.created = True
    result.path = str(target)
    return result
