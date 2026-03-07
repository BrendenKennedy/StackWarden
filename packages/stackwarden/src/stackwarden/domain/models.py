"""Pydantic v2 domain models for StackWarden."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from stackwarden.contracts import STACK_LAYER_IDS
from stackwarden.domain.enums import (
    ApiType,
    Arch,
    ArtifactStatus,
    BuildStrategy,
    ContainerRuntime,
    LicenseSeverity,
    ServeType,
    TaskType,
)


# ---------------------------------------------------------------------------
# Profile models
# ---------------------------------------------------------------------------


class CudaSpec(BaseModel):
    major: int
    minor: int
    variant: str


class GpuSpec(BaseModel):
    vendor: str
    family: str
    vendor_id: str | None = None
    family_id: str | None = None
    model_id: str | None = None
    notes: str = ""
    compute_capability: str | None = None


class GpuDeviceSpec(BaseModel):
    index: int
    model: str | None = None
    family: str | None = None
    compute_capability: str | None = None
    memory_gb: float | None = None


class HostDiscoveryFacts(BaseModel):
    driver_version: str | None = None
    runtime_version: str | None = None
    cpu_model: str | None = None
    cpu_cores_logical: int | None = None
    cpu_cores_physical: int | None = None
    memory_gb_total: float | None = None
    disk_gb_total: float | None = None
    detected_at: str | None = None
    confidence: dict[str, Literal["detected", "inferred", "unknown"]] = Field(default_factory=dict)


class CapabilityRange(BaseModel):
    name: str
    min: str | None = None
    max: str | None = None
    values: list[str] = Field(default_factory=list)


class ProfileConstraints(BaseModel):
    disallow: dict[str, list[str]] = Field(default_factory=dict)
    require: dict[str, list[str]] = Field(default_factory=dict)


class BaseCandidate(BaseModel):
    name: str
    tags: list[str]
    score_bias: int = 0


class ProfileDefaults(BaseModel):
    python: str = "3.10"
    user: str = "root"
    workdir: str = "/workspace"


class IntentSpec(BaseModel):
    outcome: str | None = None
    summary: str | None = None


class RequirementsSpec(BaseModel):
    needs: list[str] = Field(default_factory=list)
    optimize_for: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


class RejectedCandidateSpec(BaseModel):
    name: str
    reason: str


class Profile(BaseModel):
    schema_version: int = 1
    id: str
    display_name: str
    arch: Arch
    os: str = "linux"
    os_family: str | None = None
    os_version: str | None = None
    os_family_id: str | None = None
    os_version_id: str | None = None
    container_runtime: ContainerRuntime = ContainerRuntime.NVIDIA
    cuda: CudaSpec | None = None
    gpu: GpuSpec
    gpu_devices: list[GpuDeviceSpec] = Field(default_factory=list)
    constraints: ProfileConstraints = Field(default_factory=ProfileConstraints)
    base_candidates: list[BaseCandidate] = Field(default_factory=list)
    defaults: ProfileDefaults = Field(default_factory=ProfileDefaults)
    intent: IntentSpec = Field(default_factory=IntentSpec)
    requirements: RequirementsSpec = Field(default_factory=RequirementsSpec)
    derived_capabilities: list[str] = Field(default_factory=list)
    selected_features: list[str] = Field(default_factory=list)
    rejected_candidates: list[RejectedCandidateSpec] = Field(default_factory=list)
    fix_suggestions: list[str] = Field(default_factory=list)
    decision_trace: list[str] = Field(default_factory=list)
    host_facts: HostDiscoveryFacts = Field(default_factory=HostDiscoveryFacts)
    capability_ranges: list[CapabilityRange] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    advanced_override: bool = False


# ---------------------------------------------------------------------------
# Stack models
# ---------------------------------------------------------------------------


_PIP_NAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?(\[[\w,]+\])?$")
_APT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.+\-]+$")
_NPM_NAME_RE = re.compile(r"^(@[a-z0-9._-]+/)?[a-z0-9._-]+$")
_WHEELHOUSE_MODE = Literal["index", "wheelhouse_prefer", "wheelhouse_only"]
_NPM_INSTALL_MODE = Literal["spec", "lock_prefer", "lock_only"]
_APT_INSTALL_MODE = Literal["repo", "pin_prefer", "pin_only"]
_LOCKFILE_NAMES = frozenset({"package-lock.json", "pnpm-lock.yaml", "yarn.lock"})
_STACK_LAYER_IDS = frozenset(STACK_LAYER_IDS)


class PipDep(BaseModel):
    name: str
    version: str = ""
    version_mode: Literal["latest", "custom"] = "latest"

    @field_validator("name")
    @classmethod
    def _validate_pip_name(cls, v: str) -> str:
        if not _PIP_NAME_RE.match(v):
            raise ValueError(
                f"Invalid pip package name: {v!r}. "
                "Must match PEP 508 name (letters, digits, '.', '-', '_')."
            )
        return v

    @model_validator(mode="after")
    def _validate_version_mode(self) -> "PipDep":
        # Backward compatibility: existing specs may set version without version_mode.
        if self.version and self.version_mode == "latest":
            self.version_mode = "custom"
        if self.version_mode == "custom" and not self.version.strip():
            raise ValueError("Custom pip version mode requires a non-empty version constraint")
        if self.version_mode == "latest":
            self.version = ""
        return self


class NpmDep(BaseModel):
    name: str
    version: str = ""
    version_mode: Literal["latest", "custom"] = "latest"
    package_manager: Literal["npm", "pnpm", "yarn"] = "npm"
    install_scope: Literal["prod", "dev"] = "prod"

    @field_validator("name")
    @classmethod
    def _validate_npm_name(cls, v: str) -> str:
        if not _NPM_NAME_RE.match(v):
            raise ValueError(
                f"Invalid npm package name: {v!r}. "
                "Must be a standard npm package name, optionally scoped."
            )
        return v

    @model_validator(mode="after")
    def _validate_version_mode(self) -> "NpmDep":
        if self.version and self.version_mode == "latest":
            self.version_mode = "custom"
        if self.version_mode == "custom" and not self.version.strip():
            raise ValueError("Custom npm version mode requires a non-empty version constraint")
        if self.version_mode == "latest":
            self.version = ""
        return self


class _StackComponentsBase(BaseModel):
    pip: list[PipDep] = Field(default_factory=list)
    npm: list[NpmDep] = Field(default_factory=list)
    apt: list[str] = Field(default_factory=list)
    apt_constraints: dict[str, str] = Field(default_factory=dict)
    apt_install_mode: _APT_INSTALL_MODE = "repo"
    pip_install_mode: _WHEELHOUSE_MODE = "index"
    pip_wheelhouse_path: str = ""
    npm_install_mode: _NPM_INSTALL_MODE = "spec"

    @field_validator("apt", mode="before")
    @classmethod
    def _validate_apt_names(cls, v: list[str]) -> list[str]:
        for pkg in v:
            if not _APT_NAME_RE.match(pkg):
                raise ValueError(
                    f"Invalid apt package name: {pkg!r}. "
                    "Must contain only lowercase letters, digits, '.', '+', '-'."
                )
        return v

    @model_validator(mode="after")
    def _validate_component_policies(self):
        for pkg_name, constraint in self.apt_constraints.items():
            if pkg_name not in self.apt:
                raise ValueError(f"apt constraint references unknown package: {pkg_name!r}")
            if "\n" in constraint or "\r" in constraint:
                raise ValueError(f"apt constraint must not contain newlines: {pkg_name!r}")
        if self.apt_install_mode == "pin_only":
            missing = [pkg for pkg in self.apt if pkg not in self.apt_constraints]
            if missing:
                raise ValueError(
                    "apt_install_mode='pin_only' requires constraints for all apt packages; "
                    f"missing: {', '.join(sorted(missing))}"
                )
        mode = self.pip_install_mode
        path = self.pip_wheelhouse_path.strip()
        if mode != "index" and not path:
            raise ValueError("pip_wheelhouse_path is required when pip_install_mode uses wheelhouse")
        if mode == "index":
            self.pip_wheelhouse_path = ""
        else:
            self.pip_wheelhouse_path = path
        return self


class StackComponents(_StackComponentsBase):
    base_role: str


class StackComponentsPartial(_StackComponentsBase):
    base_role: str | None = None


class StackEntrypoint(BaseModel):
    cmd: list[str]

    @field_validator("cmd")
    @classmethod
    def _validate_cmd(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Entrypoint cmd must have at least one element")
        return v


class CopyItem(BaseModel):
    src: str
    dst: str

    @model_validator(mode="after")
    def _validate_no_traversal(self) -> CopyItem:
        for label, val in [("src", self.src), ("dst", self.dst)]:
            normalized = val.replace("\\", "/")
            if ".." in normalized.split("/"):
                raise ValueError(f"Path traversal not allowed in copy {label}: {val!r}")
        if self.src.startswith("/"):
            raise ValueError(
                f"Absolute source path not allowed in copy src: {self.src!r}"
            )
        return self


class StackFiles(BaseModel):
    model_config = {"populate_by_name": True}

    copy_items: list[CopyItem] = Field(default_factory=list, alias="copy")


def _has_supported_lockfile(files: StackFiles) -> bool:
    for item in files.copy_items:
        normalized = item.src.replace("\\", "/").rstrip("/")
        leaf = normalized.rsplit("/", 1)[-1]
        if leaf in _LOCKFILE_NAMES:
            return True
    return False


class VariantDef(BaseModel):
    type: Literal["bool", "enum"]
    options: list[str] = Field(default_factory=list)
    default: str | bool

    @model_validator(mode="after")
    def _validate_type_constraints(self) -> "VariantDef":
        if self.type == "enum" and not self.options:
            raise ValueError("enum variant must declare options")
        if self.type == "bool" and not isinstance(self.default, bool):
            raise ValueError("bool variant must have a bool default")
        return self


_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=[^\n\r]*$")


def _validate_env_entries(v: list[str]) -> list[str]:
    for entry in v:
        if not _ENV_RE.match(entry):
            raise ValueError(
                f"Invalid env entry: {entry!r}. "
                "Must be KEY=VALUE with no newlines."
            )
    return v


def _validate_port_values(v: list[int]) -> list[int]:
    for port in v:
        if not (1 <= port <= 65535):
            raise ValueError(
                f"Invalid port: {port}. Must be between 1 and 65535."
            )
    return v


class StackSpec(BaseModel):
    kind: Literal["stack"] = "stack"
    schema_version: int = 1
    id: str
    display_name: str
    description: str = ""
    task: TaskType
    serve: ServeType
    api: ApiType
    build_strategy: BuildStrategy
    components: StackComponents
    env: list[str] = Field(default_factory=list)
    ports: list[int] = Field(default_factory=list)
    entrypoint: StackEntrypoint
    files: StackFiles = Field(default_factory=StackFiles)
    variants: dict[str, VariantDef] = Field(default_factory=dict)
    layers: list[str] = Field(default_factory=list)
    intent: IntentSpec = Field(default_factory=IntentSpec)
    requirements: RequirementsSpec = Field(default_factory=RequirementsSpec)
    derived_capabilities: list[str] = Field(default_factory=list)
    selected_features: list[str] = Field(default_factory=list)
    rejected_candidates: list[RejectedCandidateSpec] = Field(default_factory=list)
    fix_suggestions: list[str] = Field(default_factory=list)
    decision_trace: list[str] = Field(default_factory=list)
    policy_overrides: dict[str, Any] = Field(default_factory=dict)

    @field_validator("env", mode="before")
    @classmethod
    def _validate_env(cls, v: list[str]) -> list[str]:
        return _validate_env_entries(v)

    @field_validator("ports", mode="before")
    @classmethod
    def _validate_ports(cls, v: list[int]) -> list[int]:
        return _validate_port_values(v)

    @model_validator(mode="after")
    def _validate_npm_lock_policy(self) -> "StackSpec":
        if self.components.npm_install_mode == "lock_only" and not _has_supported_lockfile(self.files):
            raise ValueError(
                "npm_install_mode='lock_only' requires copying one lockfile in files.copy: "
                "package-lock.json, pnpm-lock.yaml, or yarn.lock"
            )
        return self


class LayerSpec(BaseModel):
    kind: Literal["layer"] = "layer"
    schema_version: int = 1
    id: str
    display_name: str
    description: str = ""
    block_kind: str | None = None
    stack_layer: str = ""
    tags: list[str] = Field(default_factory=list)
    build_strategy: BuildStrategy | None = None
    components: StackComponentsPartial = Field(default_factory=StackComponentsPartial)
    env: list[str] = Field(default_factory=list)
    ports: list[int] = Field(default_factory=list)
    entrypoint: StackEntrypoint | None = None
    files: StackFiles = Field(default_factory=StackFiles)
    variants: dict[str, VariantDef] = Field(default_factory=dict)
    requires: dict[str, Any] = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)
    incompatible_with: list[str] = Field(default_factory=list)
    provides: dict[str, Any] = Field(default_factory=dict)

    @field_validator("env", mode="before")
    @classmethod
    def _validate_env(cls, v: list[str]) -> list[str]:
        return _validate_env_entries(v)

    @field_validator("ports", mode="before")
    @classmethod
    def _validate_ports(cls, v: list[int]) -> list[int]:
        return _validate_port_values(v)

    @model_validator(mode="after")
    def _validate_npm_lock_policy(self) -> "LayerSpec":
        if self.components.npm_install_mode == "lock_only" and not _has_supported_lockfile(self.files):
            raise ValueError(
                "npm_install_mode='lock_only' requires copying one lockfile in files.copy: "
                "package-lock.json, pnpm-lock.yaml, or yarn.lock"
            )
        resolved_layer = self.stack_layer.strip().lower()
        if resolved_layer not in _STACK_LAYER_IDS:
            allowed = ", ".join(sorted(_STACK_LAYER_IDS))
            raise ValueError(
                "Layer must declare a valid stack_layer. "
                f"Allowed values: {allowed}"
            )
        self.stack_layer = resolved_layer
        return self


class StackRecipeSpec(BaseModel):
    kind: Literal["stack_recipe"] = "stack_recipe"
    schema_version: int = 1
    id: str
    display_name: str
    description: str = ""
    layers: list[str] = Field(default_factory=list)
    build_strategy: BuildStrategy | None = None
    components: StackComponentsPartial = Field(default_factory=StackComponentsPartial)
    env: list[str] = Field(default_factory=list)
    ports: list[int] = Field(default_factory=list)
    entrypoint: StackEntrypoint | None = None
    files: StackFiles = Field(default_factory=StackFiles)
    variants: dict[str, VariantDef] = Field(default_factory=dict)
    intent: IntentSpec = Field(default_factory=IntentSpec)
    requirements: RequirementsSpec = Field(default_factory=RequirementsSpec)
    derived_capabilities: list[str] = Field(default_factory=list)
    selected_features: list[str] = Field(default_factory=list)
    rejected_candidates: list[RejectedCandidateSpec] = Field(default_factory=list)
    fix_suggestions: list[str] = Field(default_factory=list)
    decision_trace: list[str] = Field(default_factory=list)

    @field_validator("env", mode="before")
    @classmethod
    def _validate_env(cls, v: list[str]) -> list[str]:
        return _validate_env_entries(v)

    @field_validator("ports", mode="before")
    @classmethod
    def _validate_ports(cls, v: list[int]) -> list[int]:
        return _validate_port_values(v)

    @field_validator("layers")
    @classmethod
    def _validate_layers_nonempty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("stack_recipe must include at least one layer")
        return v

    @model_validator(mode="after")
    def _validate_npm_lock_policy(self) -> "StackRecipeSpec":
        if self.components.npm_install_mode == "lock_only" and not _has_supported_lockfile(self.files):
            raise ValueError(
                "npm_install_mode='lock_only' requires copying one lockfile in files.copy: "
                "package-lock.json, pnpm-lock.yaml, or yarn.lock"
            )
        return self


class CompatibilityIssue(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    rule_id: str | None = None
    rule_version: int | None = None
    source: str | None = None
    field: str | None = None
    fix_hint: str | None = None
    confidence_context: dict[str, str] = Field(default_factory=dict)


class CompatibilityReport(BaseModel):
    compatible: bool
    errors: list[CompatibilityIssue] = Field(default_factory=list)
    warnings: list[CompatibilityIssue] = Field(default_factory=list)
    info: list[CompatibilityIssue] = Field(default_factory=list)
    requirements_summary: dict[str, Any] = Field(default_factory=dict)
    decision_trace: list[str] = Field(default_factory=list)
    suggested_fixes: list[str] = Field(default_factory=list)
    tuple_decision: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Plan models (resolver output)
# ---------------------------------------------------------------------------


class ScoreBreakdown(BaseModel):
    candidate_name: str
    candidate_tag: str
    score_bias: int
    role_match: int
    cuda_match: int
    total: int


class DecisionRationale(BaseModel):
    rules_fired: list[dict[str, str]] = Field(default_factory=list)
    candidates: list[ScoreBreakdown] = Field(default_factory=list)
    selected_reason: str = ""
    variant_effects: list[str] = Field(default_factory=list)
    base_digest_status: str = "unknown_until_pull"
    compatibility_report: dict[str, Any] = Field(default_factory=dict)


class BuildOptimizationDecision(BaseModel):
    """Computed build optimization settings derived from host facts."""

    enabled: bool = True
    strategy: str = "auto"
    policy: Literal["strict_host_specific", "portable", "conservative"] = "portable"
    strict_host_specific: bool = False
    host_signature: str = ""
    gpu_family: str = ""
    gpu_compute_capability: str = ""
    driver_version: str = ""
    torch_dtype: str = "fp16"
    attention_backend: str = "sdpa_auto"
    torch_compile_enabled: bool = True
    tf32_enabled: bool = False
    cpu_parallelism: int = 2
    memory_budget_gb: float | None = None
    estimated_build_memory_gb: float | None = None
    oom_risk: Literal["low", "medium", "high"] = "medium"
    build_args: dict[str, str] = Field(default_factory=dict)
    optimization_env: dict[str, str] = Field(default_factory=dict)
    buildx_flags: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PlanDecision(BaseModel):
    base_image: str
    base_digest: str | None = None
    builder: str
    warnings: list[str] = Field(default_factory=list)
    rationale: DecisionRationale | None = None
    tuple_decision: dict[str, Any] = Field(default_factory=dict)
    build_optimization: BuildOptimizationDecision | None = None


class PlanStep(BaseModel):
    type: str
    image: str | None = None
    dockerfile_template: str | None = None
    context_dir: str | None = None
    build_args: dict[str, str] = Field(default_factory=dict)
    buildx_flags: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)


class PlanArtifact(BaseModel):
    tag: str
    fingerprint: str
    labels: dict[str, str] = Field(default_factory=dict)


class Plan(BaseModel):
    plan_id: str
    profile_id: str
    stack_id: str
    decision: PlanDecision
    steps: list[PlanStep]
    artifact: PlanArtifact

    def to_json(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Artifact / catalog record models
# ---------------------------------------------------------------------------


class ArtifactRecord(BaseModel):
    id: str | None = None
    profile_id: str
    stack_id: str
    tag: str
    fingerprint: str
    image_id: str | None = None
    digest: str | None = None
    base_image: str
    base_digest: str | None = None
    build_strategy: str
    template_hash: str | None = None
    stack_schema_version: int = 1
    profile_schema_version: int = 1
    layer_schema_version: int = 1
    manifest_path: str | None = None
    sbom_path: str | None = None
    profile_snapshot_path: str | None = None
    stack_snapshot_path: str | None = None
    plan_path: str | None = None
    variant_json: str | None = None
    host_id: str | None = None
    docker_context: str | None = None
    daemon_arch: str | None = None
    status: ArtifactStatus = ArtifactStatus.PLANNED
    stale_reason: str | None = None
    error_detail: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ArtifactComponent(BaseModel):
    artifact_id: str
    type: str
    name: str
    version: str = ""
    license_spdx: str | None = None
    license_severity: LicenseSeverity | None = None
