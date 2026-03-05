"""Metadata endpoints (enum values, etc.)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Response

from stackwarden.contracts import ALLOWED_BUILD_STRATEGIES, SPEC_ID_PATTERN
from stackwarden.domain.enums import (
    ApiType,
    Arch,
    ContainerRuntime,
    ServeType,
    TaskType,
)
from stackwarden.web.schemas import CreateContractDTO, CreateContractsResponseDTO, FieldConstraintDTO
from stackwarden.web.util.versioning import apply_version_headers, resolve_schema_version

router = APIRouter(tags=["meta"])
log = logging.getLogger(__name__)

_ALLOWED_BUILD_STRATEGIES = list(ALLOWED_BUILD_STRATEGIES)


@router.get("/meta/enums")
async def get_enums():
    try:
        return {
            "task": [e.value for e in TaskType],
            "serve": [e.value for e in ServeType],
            "api": [e.value for e in ApiType],
            "arch": [e.value for e in Arch],
            "build_strategy": _ALLOWED_BUILD_STRATEGIES,
            "container_runtime": [e.value for e in ContainerRuntime],
        }
    except Exception:
        log.exception("Failed to serve /meta/enums")
        raise


@router.get("/meta/create-contracts", response_model=CreateContractsResponseDTO)
async def get_create_contracts(response: Response, schema: str | None = Query(default=None)):
    try:
        requested = resolve_schema_version(schema, default=1)
        apply_version_headers(response, requested=requested)
        if requested >= 2:
            profile_required = [
                "id",
                "display_name",
                "arch",
                "container_runtime",
            ]
            profile_defaults = {
                "os": "linux",
                "container_runtime": "nvidia",
                "gpu.vendor": "nvidia",
                "gpu.family": "gpu",
                "defaults.python": "3.10",
                "defaults.user": "root",
                "defaults.workdir": "/workspace",
            }
            profile_fields = {
                "id": FieldConstraintDTO(pattern=SPEC_ID_PATTERN),
                "arch": FieldConstraintDTO(enum_values=[e.value for e in Arch]),
                "os": FieldConstraintDTO(enum_values=["linux"]),
                "os_family": FieldConstraintDTO(
                    note="Normalized distro family when detected (ubuntu, debian, rhel, etc)."
                ),
                "os_version": FieldConstraintDTO(
                    note="Normalized distro version when detected (20.04, 22.04, etc)."
                ),
                "os_family_id": FieldConstraintDTO(
                    note="Canonical catalog id for OS family."
                ),
                "os_version_id": FieldConstraintDTO(
                    note="Canonical catalog id for OS version."
                ),
                "container_runtime": FieldConstraintDTO(
                    enum_values=[e.value for e in ContainerRuntime]
                ),
                "gpu_devices": FieldConstraintDTO(
                    note="Optional per-device GPU summary list; used for multi-GPU-aware diagnostics."
                ),
                "gpu.vendor_id": FieldConstraintDTO(note="Canonical catalog id for GPU vendor."),
                "gpu.family_id": FieldConstraintDTO(note="Canonical catalog id for GPU family."),
                "gpu.model_id": FieldConstraintDTO(note="Canonical catalog id for GPU model."),
                "host_facts.confidence": FieldConstraintDTO(
                    note="Per-field confidence metadata: detected, inferred, or unknown."
                ),
                "host_facts.cpu_model": FieldConstraintDTO(
                    note="Detected CPU model string from local host probes."
                ),
                "host_facts.cpu_cores_logical": FieldConstraintDTO(
                    note="Detected logical CPU core count from local host probes."
                ),
                "host_facts.cpu_cores_physical": FieldConstraintDTO(
                    note="Detected physical CPU core count when available from host probes."
                ),
                "host_facts.memory_gb_total": FieldConstraintDTO(
                    note="Detected total system memory in GiB from local host probes."
                ),
                "host_facts.disk_gb_total": FieldConstraintDTO(
                    note="Detected total root filesystem capacity in GiB from local host probes."
                ),
                "intent": FieldConstraintDTO(
                    note="Intent object: outcome and summary for declarative planning."
                ),
                "requirements": FieldConstraintDTO(
                    note="Requirements object with needs, optimize_for, and explicit constraints."
                ),
                "derived_capabilities": FieldConstraintDTO(
                    note="System-computed capability set; user-provided values are normalized."
                ),
                "selected_features": FieldConstraintDTO(
                    note="Reserved derived output placeholder for selected feature flags."
                ),
                "rejected_candidates": FieldConstraintDTO(
                    note="Reserved derived output placeholder listing rejected options and rationale."
                ),
                "fix_suggestions": FieldConstraintDTO(
                    note="Reserved derived output placeholder with remediation suggestions."
                ),
                "decision_trace": FieldConstraintDTO(
                    note="Ordered derivation rationale, including normalization decisions."
                ),
            }
        else:
            profile_required = [
                "id",
                "display_name",
                "arch",
                "container_runtime",
                "cuda.major",
                "cuda.minor",
                "cuda.variant",
                "base_candidates",
            ]
            profile_defaults = {
                "os": "linux",
                "container_runtime": "nvidia",
                "cuda.variant": "runtime",
                "gpu.vendor": "nvidia",
                "gpu.family": "gpu",
                "defaults.python": "3.10",
                "defaults.user": "root",
                "defaults.workdir": "/workspace",
            }
            profile_fields = {
                "id": FieldConstraintDTO(pattern=SPEC_ID_PATTERN),
                "arch": FieldConstraintDTO(enum_values=[e.value for e in Arch]),
                "os": FieldConstraintDTO(enum_values=["linux"]),
                "container_runtime": FieldConstraintDTO(
                    enum_values=[e.value for e in ContainerRuntime]
                ),
                "base_candidates": FieldConstraintDTO(min_items=1),
                "base_candidates[].tags": FieldConstraintDTO(min_items=1),
                "cuda.major": FieldConstraintDTO(
                    note="Must be > 0 when cuda details are provided.",
                ),
                "cuda.minor": FieldConstraintDTO(
                    note="Must be >= 0 when cuda details are provided.",
                ),
            }
        profile_contract = CreateContractDTO(
            required_fields=profile_required,
            defaults=profile_defaults,
            fields=profile_fields,
        )

        stack_contract = CreateContractDTO(
            required_fields=[
                "id",
                "display_name",
                "blocks",
            ],
            defaults={},
            fields={
                "id": FieldConstraintDTO(pattern=SPEC_ID_PATTERN),
                "kind": FieldConstraintDTO(enum_values=["stack_recipe"]),
                "build_strategy": FieldConstraintDTO(enum_values=_ALLOWED_BUILD_STRATEGIES),
                "intent": FieldConstraintDTO(
                    note="Intent object: outcome and summary for declarative planning."
                ),
                "requirements": FieldConstraintDTO(
                    note="Requirements object with needs, optimize_for, and explicit constraints."
                ),
                "derived_capabilities": FieldConstraintDTO(
                    note="System-computed capability set; user-provided values are normalized."
                ),
                "selected_features": FieldConstraintDTO(
                    note="Reserved derived output placeholder for selected feature flags."
                ),
                "rejected_candidates": FieldConstraintDTO(
                    note="Reserved derived output placeholder listing rejected options and rationale."
                ),
                "fix_suggestions": FieldConstraintDTO(
                    note="Reserved derived output placeholder with remediation suggestions."
                ),
                "decision_trace": FieldConstraintDTO(
                    note="Ordered derivation rationale, including normalization decisions."
                ),
                "base_role": FieldConstraintDTO(
                    note="Optional override; usually inferred from selected blocks."
                ),
                "blocks": FieldConstraintDTO(
                    min_items=1,
                    note="Primary intent contract: users declare desired functionality via block selection and order.",
                ),
            },
        )

        block_contract = CreateContractDTO(
            required_fields=["id", "display_name"],
            defaults={
                "requires.os": "linux",
            },
            fields={
                "id": FieldConstraintDTO(pattern=SPEC_ID_PATTERN),
                "build_strategy": FieldConstraintDTO(enum_values=_ALLOWED_BUILD_STRATEGIES),
                "tags": FieldConstraintDTO(note="Recommended from presets; fully editable."),
                "pip[].version_mode": FieldConstraintDTO(
                    enum_values=["latest", "custom"],
                    note="latest omits explicit constraints; custom enables advanced pip specifiers.",
                ),
                "pip_install_mode": FieldConstraintDTO(
                    enum_values=["index", "wheelhouse_prefer", "wheelhouse_only"],
                    note="index uses default pip index; wheelhouse modes install from local wheel artifacts.",
                ),
                "pip_wheelhouse_path": FieldConstraintDTO(
                    note="Workspace-relative path containing .whl files; required for wheelhouse modes.",
                ),
                "npm[].package_manager": FieldConstraintDTO(
                    enum_values=["npm", "pnpm", "yarn"],
                ),
                "npm[].install_scope": FieldConstraintDTO(
                    enum_values=["prod", "dev"],
                ),
                "npm[].version_mode": FieldConstraintDTO(
                    enum_values=["latest", "custom"],
                    note="latest resolves to concrete installed versions at build time; custom constraints are advanced usage.",
                ),
                "npm_install_mode": FieldConstraintDTO(
                    enum_values=["spec", "lock_prefer", "lock_only"],
                    note="spec installs declared npm deps; lock modes use copied lockfiles when available/required.",
                ),
                "apt_constraints": FieldConstraintDTO(
                    note="Optional map of apt package -> advanced version constraint text."
                ),
                "apt_install_mode": FieldConstraintDTO(
                    enum_values=["repo", "pin_prefer", "pin_only"],
                    note="repo/pin_prefer allow partial constraints; pin_only requires constraints for every apt package.",
                ),
                "requires": FieldConstraintDTO(
                    note=(
                        "Compatibility requirements map. Common keys: arch, os, os_family_id, "
                        "os_version_id, gpu_vendor, gpu_vendor_id, gpu_family_id, container_runtime, "
                        "driver_min, cuda_runtime."
                    )
                ),
                "incompatible_with": FieldConstraintDTO(note="List of block ids that cannot be used together."),
                "provides": FieldConstraintDTO(note="Optional capability map advertised by this block."),
            },
        )

        return CreateContractsResponseDTO(
            schema_version=requested,
            profile=profile_contract,
            stack=stack_contract,
            block=block_contract,
        )
    except Exception:
        log.exception("Failed to serve /meta/create-contracts")
        raise
