"""Application-owned create request models.

These models intentionally live in the application layer to avoid coupling
core create flows to transport DTO modules under web/.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from stackwarden.contracts import (
    DEFAULT_LAYER_CREATE_SCHEMA_VERSION,
    DEFAULT_PROFILE_CREATE_SCHEMA_VERSION,
    DEFAULT_STACK_CREATE_SCHEMA_VERSION,
)


class PipDepCreateDTO(BaseModel):
    name: str
    version: str = ""
    version_mode: Literal["latest", "custom"] = "latest"

    @model_validator(mode="after")
    def _normalize_mode(self) -> "PipDepCreateDTO":
        if self.version and self.version_mode == "latest":
            self.version_mode = "custom"
        if self.version_mode == "latest":
            self.version = ""
        return self


class NpmDepCreateDTO(BaseModel):
    name: str
    version: str = ""
    version_mode: Literal["latest", "custom"] = "latest"
    package_manager: Literal["npm", "pnpm", "yarn"] = "npm"
    install_scope: Literal["prod", "dev"] = "prod"

    @model_validator(mode="after")
    def _normalize_mode(self) -> "NpmDepCreateDTO":
        if self.version and self.version_mode == "latest":
            self.version_mode = "custom"
        if self.version_mode == "latest":
            self.version = ""
        return self


class CopyItemCreateDTO(BaseModel):
    src: str
    dst: str


class VariantDefCreateDTO(BaseModel):
    type: Literal["bool", "enum"]
    options: list[str] = Field(default_factory=list)
    default: str | bool


class IntentCreateDTO(BaseModel):
    outcome: str | None = None
    summary: str | None = None


class RequirementsCreateDTO(BaseModel):
    needs: list[str] = Field(default_factory=list)
    optimize_for: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


class RejectedCandidateCreateDTO(BaseModel):
    name: str
    reason: str


class StackCreateRequest(BaseModel):
    schema_version: int = DEFAULT_STACK_CREATE_SCHEMA_VERSION
    kind: Literal["stack_recipe"] = "stack_recipe"
    id: str
    display_name: str
    description: str = ""
    build_strategy: str | None = None
    target_profile_id: str | None = None
    layers: list[str] = Field(default_factory=list)
    base_role: str | None = None
    copy_items: list[CopyItemCreateDTO] = Field(default_factory=list)
    variants: dict[str, VariantDefCreateDTO] = Field(default_factory=dict)
    intent: IntentCreateDTO = Field(default_factory=IntentCreateDTO)
    requirements: RequirementsCreateDTO = Field(default_factory=RequirementsCreateDTO)
    derived_capabilities: list[str] = Field(default_factory=list)
    selected_features: list[str] = Field(default_factory=list)
    rejected_candidates: list[RejectedCandidateCreateDTO] = Field(default_factory=list)
    fix_suggestions: list[str] = Field(default_factory=list)
    decision_trace: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_target_profile(self) -> "StackCreateRequest":
        from_constraints = str(self.requirements.constraints.get("target_profile_id", "")).strip()
        candidate = (self.target_profile_id or "").strip() or from_constraints
        if not candidate:
            raise ValueError("target_profile_id is required for stack creation.")
        self.target_profile_id = candidate
        self.requirements.constraints["target_profile_id"] = candidate
        return self


class LayerCreateRequest(BaseModel):
    schema_version: int = DEFAULT_LAYER_CREATE_SCHEMA_VERSION
    id: str
    display_name: str
    description: str = ""
    stack_layer: Literal[
        "system_runtime_layer",
        "driver_accelerator_layer",
        "core_compute_layer",
        "inference_engine_layer",
        "optimization_compilation_layer",
        "serving_layer",
        "application_orchestration_layer",
        "observability_operations_layer",
    ]
    tags: list[str] = Field(default_factory=list)
    build_strategy: str | None = None
    base_role: str | None = None
    pip: list[PipDepCreateDTO] = Field(default_factory=list)
    pip_install_mode: Literal["index", "wheelhouse_prefer", "wheelhouse_only"] = "index"
    pip_wheelhouse_path: str = ""
    npm: list[NpmDepCreateDTO] = Field(default_factory=list)
    npm_install_mode: Literal["spec", "lock_prefer", "lock_only"] = "spec"
    apt: list[str] = Field(default_factory=list)
    apt_constraints: dict[str, str] = Field(default_factory=dict)
    apt_install_mode: Literal["repo", "pin_prefer", "pin_only"] = "repo"
    env: dict[str, str] = Field(default_factory=dict)
    ports: list[int] = Field(default_factory=list)
    entrypoint_cmd: list[str] | None = None
    copy_items: list[CopyItemCreateDTO] = Field(default_factory=list)
    variants: dict[str, VariantDefCreateDTO] = Field(default_factory=dict)
    requires: dict[str, Any] = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)
    incompatible_with: list[str] = Field(default_factory=list)
    provides: dict[str, Any] = Field(default_factory=dict)


class BaseCandidateCreateDTO(BaseModel):
    name: str
    tags: list[str]
    score_bias: int = 0


class CudaCreateDTO(BaseModel):
    major: int
    minor: int
    variant: str = "runtime"


class GpuCreateDTO(BaseModel):
    vendor: str = "nvidia"
    family: str = "gpu"
    vendor_id: str | None = None
    family_id: str | None = None
    model_id: str | None = None
    compute_capability: str | None = None


class HostFactsCreateDTO(BaseModel):
    driver_version: str | None = None
    runtime_version: str | None = None
    cpu_model: str | None = None
    cpu_cores_logical: int | None = None
    cpu_cores_physical: int | None = None
    memory_gb_total: float | None = None
    disk_gb_total: float | None = None
    detected_at: str | None = None
    confidence: dict[str, Literal["detected", "inferred", "unknown"]] = Field(default_factory=dict)


class CapabilityRangeCreateDTO(BaseModel):
    name: str
    min: str | None = None
    max: str | None = None
    values: list[str] = Field(default_factory=list)


class ProfileDefaultsCreateDTO(BaseModel):
    python: str = "3.10"
    user: str = "root"
    workdir: str = "/workspace"


class ProfileConstraintsCreateDTO(BaseModel):
    disallow: dict[str, list[str]] = Field(default_factory=dict)
    require: dict[str, list[str]] = Field(default_factory=dict)


class ProfileCreateRequest(BaseModel):
    schema_version: int = DEFAULT_PROFILE_CREATE_SCHEMA_VERSION
    id: str
    display_name: str
    arch: str
    os: str = "linux"
    os_family: str | None = None
    os_version: str | None = None
    os_family_id: str | None = None
    os_version_id: str | None = None
    container_runtime: str = "nvidia"
    cuda: CudaCreateDTO | None = None
    gpu: GpuCreateDTO = Field(default_factory=GpuCreateDTO)
    base_candidates: list[BaseCandidateCreateDTO] = Field(default_factory=list)
    constraints: ProfileConstraintsCreateDTO = Field(default_factory=ProfileConstraintsCreateDTO)
    defaults: ProfileDefaultsCreateDTO = Field(default_factory=ProfileDefaultsCreateDTO)
    intent: IntentCreateDTO = Field(default_factory=IntentCreateDTO)
    requirements: RequirementsCreateDTO = Field(default_factory=RequirementsCreateDTO)
    derived_capabilities: list[str] = Field(default_factory=list)
    selected_features: list[str] = Field(default_factory=list)
    rejected_candidates: list[RejectedCandidateCreateDTO] = Field(default_factory=list)
    fix_suggestions: list[str] = Field(default_factory=list)
    decision_trace: list[str] = Field(default_factory=list)
    host_facts: HostFactsCreateDTO = Field(default_factory=HostFactsCreateDTO)
    capability_ranges: list[CapabilityRangeCreateDTO] = Field(default_factory=list)
    gpu_devices: list[dict[str, Any]] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    advanced_override: bool = False
