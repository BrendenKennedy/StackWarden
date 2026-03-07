"""Wire-format DTOs for the StackWarden Web API.

Domain models are NEVER returned raw.  Every route maps domain objects to a
response DTO via the ``from_domain`` class method.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from stackwarden.contracts import (
    DEFAULT_LAYER_CREATE_SCHEMA_VERSION,
    DEFAULT_PROFILE_CREATE_SCHEMA_VERSION,
    DEFAULT_STACK_CREATE_SCHEMA_VERSION,
)
from stackwarden.domain.models import (
    ArtifactRecord,
    LayerSpec,
    Plan,
    Profile,
    StackSpec,
)
from stackwarden.domain.verify import VerifyReport

# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

class CudaDTO(BaseModel):
    major: int
    minor: int
    variant: str

class GpuDTO(BaseModel):
    vendor: str
    family: str
    compute_capability: str | None = None

class ProfileSummaryDTO(BaseModel):
    id: str
    display_name: str
    arch: str
    os: str
    cuda: CudaDTO | None = None
    gpu: GpuDTO
    derived_capabilities: list[str] = Field(default_factory=list)
    source: str | None = None
    source_path: str | None = None
    source_repo_url: str | None = None
    source_repo_owner: str | None = None

    @classmethod
    def from_domain(cls, p: Profile, origin: dict[str, str] | None = None) -> ProfileSummaryDTO:
        return cls(
            id=p.id,
            display_name=p.display_name,
            arch=p.arch.value,
            os=p.os,
            cuda=(
                CudaDTO(major=p.cuda.major, minor=p.cuda.minor, variant=p.cuda.variant)
                if p.cuda
                else None
            ),
            gpu=GpuDTO(
                vendor=p.gpu.vendor,
                family=p.gpu.family,
                compute_capability=p.gpu.compute_capability,
            ),
            derived_capabilities=p.derived_capabilities,
            source=(origin or {}).get("source"),
            source_path=(origin or {}).get("source_path"),
            source_repo_url=(origin or {}).get("source_repo_url"),
            source_repo_owner=(origin or {}).get("source_repo_owner"),
        )


class BaseCandidateDTO(BaseModel):
    name: str
    tags: list[str]
    score_bias: int = 0


class ProfileConstraintsDTO(BaseModel):
    disallow: dict[str, list[str]] = Field(default_factory=dict)
    require: dict[str, list[str]] = Field(default_factory=dict)


class ProfileDefaultsDTO(BaseModel):
    python: str = "3.10"
    user: str = "root"
    workdir: str = "/workspace"


class ProfileDetailDTO(ProfileSummaryDTO):
    container_runtime: str
    constraints: ProfileConstraintsDTO = Field(default_factory=ProfileConstraintsDTO)
    base_candidates: list[BaseCandidateDTO] = Field(default_factory=list)
    defaults: ProfileDefaultsDTO = Field(default_factory=ProfileDefaultsDTO)

    @classmethod
    def from_domain(cls, p: Profile, origin: dict[str, str] | None = None) -> "ProfileDetailDTO":
        base = ProfileSummaryDTO.from_domain(p, origin=origin)
        return cls(
            **base.model_dump(),
            container_runtime=p.container_runtime.value,
            constraints=ProfileConstraintsDTO(
                disallow=p.constraints.disallow,
                require=p.constraints.require,
            ),
            base_candidates=[
                BaseCandidateDTO(name=bc.name, tags=bc.tags, score_bias=bc.score_bias)
                for bc in p.base_candidates
            ],
            defaults=ProfileDefaultsDTO(
                python=p.defaults.python,
                user=p.defaults.user,
                workdir=p.defaults.workdir,
            ),
        )


# ---------------------------------------------------------------------------
# Stacks
# ---------------------------------------------------------------------------

class VariantDefDTO(BaseModel):
    type: str
    options: list[str]
    default: str | bool

class StackSummaryDTO(BaseModel):
    id: str
    display_name: str
    task: str
    serve: str
    api: str
    certification: Literal["dgx_certified", "generic_best_effort"] = "generic_best_effort"
    certification_note: str = ""
    variants: dict[str, VariantDefDTO]
    source: str | None = None
    source_path: str | None = None
    source_repo_url: str | None = None
    source_repo_owner: str | None = None

    @classmethod
    def from_domain(cls, s: StackSpec, origin: dict[str, str] | None = None) -> StackSummaryDTO:
        constraints = dict(s.requirements.constraints or {})
        certification = str(constraints.get("stackwarden_certification") or "").strip().lower()
        if certification not in {"dgx_certified", "generic_best_effort"}:
            certification = "generic_best_effort"
        note = str(constraints.get("stackwarden_certification_note") or "").strip()
        variants = {
            k: VariantDefDTO(type=v.type, options=v.options, default=v.default)
            for k, v in s.variants.items()
        }
        return cls(
            id=s.id,
            display_name=s.display_name,
            task=s.task.value,
            serve=s.serve.value,
            api=s.api.value,
            certification=certification,  # type: ignore[arg-type]
            certification_note=note,
            variants=variants,
            source=(origin or {}).get("source"),
            source_path=(origin or {}).get("source_path"),
            source_repo_url=(origin or {}).get("source_repo_url"),
            source_repo_owner=(origin or {}).get("source_repo_owner"),
        )

class StackDetailDTO(StackSummaryDTO):
    build_strategy: str
    ports: list[int]
    env: list[str]

    @classmethod
    def from_domain(cls, s: StackSpec, origin: dict[str, str] | None = None) -> StackDetailDTO:
        base = StackSummaryDTO.from_domain(s, origin=origin)
        return cls(
            **base.model_dump(),
            build_strategy=s.build_strategy.value,
            ports=s.ports,
            env=s.env,
        )


class LayerSummaryDTO(BaseModel):
    id: str
    display_name: str
    stack_layer: str = ""
    tags: list[str]
    requires_keys: list[str] = Field(default_factory=list)
    source: str | None = None
    source_path: str | None = None
    source_repo_url: str | None = None
    source_repo_owner: str | None = None

    @classmethod
    def from_domain(cls, b: LayerSpec, origin: dict[str, str] | None = None) -> "LayerSummaryDTO":
        return cls(
            id=b.id,
            display_name=b.display_name,
            stack_layer=b.stack_layer,
            tags=b.tags,
            requires_keys=sorted(list((b.requires or {}).keys())),
            source=(origin or {}).get("source"),
            source_path=(origin or {}).get("source_path"),
            source_repo_url=(origin or {}).get("source_repo_url"),
            source_repo_owner=(origin or {}).get("source_repo_owner"),
        )


class LayerDetailDTO(LayerSummaryDTO):
    build_strategy: str | None = None
    ports: list[int]
    env: list[str]
    pip_count: int = 0
    npm_count: int = 0
    apt_count: int = 0
    requires: dict[str, Any] = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)
    incompatible_with: list[str] = Field(default_factory=list)
    provides: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, b: LayerSpec, origin: dict[str, str] | None = None) -> "LayerDetailDTO":
        base = LayerSummaryDTO.from_domain(b, origin=origin)
        return cls(
            **base.model_dump(),
            build_strategy=b.build_strategy.value if b.build_strategy else None,
            ports=b.ports,
            env=b.env,
            pip_count=len(b.components.pip),
            npm_count=len(b.components.npm),
            apt_count=len(b.components.apt),
            requires=b.requires,
            conflicts=b.conflicts,
            incompatible_with=b.incompatible_with,
            provides=b.provides,
        )


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------

def _status_str(status: Any) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _created_at_str(created_at: Any) -> str:
    return created_at.isoformat() if isinstance(created_at, datetime) else str(created_at)


class ArtifactSummaryDTO(BaseModel):
    id: str | None
    profile_id: str
    stack_id: str
    tag: str
    fingerprint: str
    status: str
    base_image: str
    build_strategy: str
    created_at: str
    variant_json: str | None = None

    @classmethod
    def from_domain(cls, r: ArtifactRecord) -> ArtifactSummaryDTO:
        return cls(
            id=r.id,
            profile_id=r.profile_id,
            stack_id=r.stack_id,
            tag=r.tag,
            fingerprint=r.fingerprint,
            status=_status_str(r.status),
            base_image=r.base_image,
            build_strategy=r.build_strategy,
            created_at=_created_at_str(r.created_at),
            variant_json=r.variant_json,
        )


class ArtifactDetailDTO(ArtifactSummaryDTO):
    image_id: str | None = None
    digest: str | None = None
    base_digest: str | None = None
    template_hash: str | None = None
    stale_reason: str | None = None
    error_detail: str | None = None

    @classmethod
    def from_domain(cls, r: ArtifactRecord) -> ArtifactDetailDTO:
        base = ArtifactSummaryDTO.from_domain(r)
        return cls(
            **base.model_dump(),
            image_id=r.image_id,
            digest=r.digest,
            base_digest=r.base_digest,
            template_hash=r.template_hash,
            stale_reason=r.stale_reason,
            error_detail=r.error_detail,
        )


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

class PlanRequestDTO(BaseModel):
    profile_id: str
    stack_id: str
    variants: dict[str, Any] | None = None
    flags: dict[str, bool] = Field(default_factory=dict)

    @field_validator("flags")
    @classmethod
    def _validate_flags(cls, value: dict[str, bool]) -> dict[str, bool]:
        allowed = {"explain"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            allowed_csv = ", ".join(sorted(allowed))
            raise ValueError(
                f"Unknown plan flag(s): {', '.join(unknown)}. Allowed flags: {allowed_csv}",
            )
        return value


class CompatibilityPreviewRequestDTO(BaseModel):
    profile_id: str
    stack_id: str


class LayerOptionsClassifyRequestDTO(BaseModel):
    selected_layers: list[str] = Field(default_factory=list)
    inference_type: str | None = None
    inference_profile: str | None = None
    target_profile_id: str


class LayerOptionDTO(BaseModel):
    id: str
    display_name: str
    stack_layer: str
    tags: list[str] = Field(default_factory=list)
    tier: Literal["recommended", "compatible", "incompatible"]
    score: int = 0
    reasons: list[str] = Field(default_factory=list)
    selected: bool = False


class LayerOptionGroupDTO(BaseModel):
    stack_layer: str
    options: list[LayerOptionDTO] = Field(default_factory=list)


class LayerOptionsClassifyResponseDTO(BaseModel):
    groups: list[LayerOptionGroupDTO] = Field(default_factory=list)

class PlanStepDTO(BaseModel):
    type: str
    image: str | None = None
    tags: list[str] = Field(default_factory=list)

class PlanResponseDTO(BaseModel):
    plan_id: str
    profile_id: str
    stack_id: str
    base_image: str
    base_digest: str | None
    builder: str
    warnings: list[str]
    tag: str
    fingerprint: str
    steps: list[PlanStepDTO]
    rationale: dict[str, Any] | None = None
    tuple_decision: dict[str, Any] = Field(default_factory=dict)
    build_optimization: dict[str, Any] | None = None

    @classmethod
    def from_domain(cls, plan: Plan) -> PlanResponseDTO:
        steps = [
            PlanStepDTO(type=s.type, image=s.image, tags=s.tags)
            for s in plan.steps
        ]
        rationale = None
        if plan.decision.rationale:
            rationale = plan.decision.rationale.model_dump(mode="json")
        return cls(
            plan_id=plan.plan_id,
            profile_id=plan.profile_id,
            stack_id=plan.stack_id,
            base_image=plan.decision.base_image,
            base_digest=plan.decision.base_digest,
            builder=plan.decision.builder,
            warnings=plan.decision.warnings,
            tag=plan.artifact.tag,
            fingerprint=plan.artifact.fingerprint,
            steps=steps,
            rationale=rationale,
            tuple_decision=plan.decision.tuple_decision,
            build_optimization=(
                plan.decision.build_optimization.model_dump(mode="json")
                if plan.decision.build_optimization
                else None
            ),
        )


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

class VerifyRequestDTO(BaseModel):
    tag_or_id: str
    strict: bool = False
    fix: bool = False

class VerifyResponseDTO(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str]
    facts: dict[str, str]
    recomputed_fingerprint: str | None = None
    label_fingerprint: str | None = None
    catalog_fingerprint: str | None = None
    actions: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, report: VerifyReport, actions: list[str] | None = None) -> VerifyResponseDTO:
        return cls(
            ok=report.ok,
            errors=report.errors,
            warnings=report.warnings,
            facts=report.facts,
            recomputed_fingerprint=report.recomputed_fingerprint,
            label_fingerprint=report.label_fingerprint,
            catalog_fingerprint=report.catalog_fingerprint,
            actions=actions or [],
        )


# ---------------------------------------------------------------------------
# Ensure / Jobs
# ---------------------------------------------------------------------------

class EnsureRequestDTO(BaseModel):
    profile_id: str
    stack_id: str
    variants: dict[str, Any] | None = None
    flags: dict[str, bool] = Field(default_factory=dict)

    @field_validator("flags")
    @classmethod
    def _validate_flags(cls, value: dict[str, bool]) -> dict[str, bool]:
        allowed = {"rebuild", "upgrade_base", "immutable", "no_hooks", "explain"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            allowed_csv = ", ".join(sorted(allowed))
            raise ValueError(
                f"Unknown ensure flag(s): {', '.join(unknown)}. Allowed flags: {allowed_csv}",
            )
        return value

class EnsureResponseDTO(BaseModel):
    job_id: str

class JobSummaryDTO(BaseModel):
    job_id: str
    status: str
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    profile_id: str
    stack_id: str

class JobDetailDTO(JobSummaryDTO):
    variants: dict[str, Any] | None = None
    flags: dict[str, bool] = Field(default_factory=dict)
    build_optimization: dict[str, Any] = Field(default_factory=dict)
    result_artifact_id: str | None = None
    result_tag: str | None = None
    error_message: str | None = None
    log_path: str | None = None


class CompatibilityFixDTO(BaseModel):
    """Preview of a compatibility fix for a failed build."""

    applicable: bool
    message: str
    suggested_overrides: dict[str, str] = Field(default_factory=dict)
    base_image_hint: str = "nvcr.io/nvidia/pytorch"


class RetryWithFixResponseDTO(BaseModel):
    """Response when retrying a failed build with an applied compatibility fix."""

    job_id: str
    applied: bool
    message: str


class CatalogItemDTO(BaseModel):
    row_id: str
    source: Literal["artifact"]
    status: str
    profile_id: str
    stack_id: str
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    job_id: str | None = None
    artifact_id: str | None = None
    tag: str | None = None
    fingerprint: str | None = None
    base_image: str | None = None
    build_strategy: str | None = None
    variant_json: str | None = None
    error_message: str | None = None
    stale_reason: str | None = None
    log_path: str | None = None


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

class SystemConfigDTO(BaseModel):
    catalog_path: str | None = None
    catalog_local_path: str | None = None
    catalog_local_overrides_path: str | None = None
    log_dir: str | None = None
    default_profile: str | None = None
    registry_allow: list[str] = Field(default_factory=list)
    registry_deny: list[str] = Field(default_factory=list)
    auth_enabled: bool = False
    blocks_first_enabled: bool = True
    tuple_layer_mode: str = "enforce"


class SettingsConfigUpdateRequestDTO(BaseModel):
    default_profile: str | None = None
    registry_allow: list[str] | None = None
    registry_deny: list[str] | None = None
    catalog_local_path: str | None = None
    catalog_local_overrides_path: str | None = None
    tuple_layer_mode: str | None = None


class AuthSessionStatusDTO(BaseModel):
    setup_required: bool
    authenticated: bool
    username: str | None = None


class AuthSetupRequestDTO(BaseModel):
    username: str
    password: str


class AuthLoginRequestDTO(BaseModel):
    username: str
    password: str


class AuthChangePasswordRequestDTO(BaseModel):
    current_password: str
    new_password: str


# Detection hints (server-host probing)
class DetectionProbeDTO(BaseModel):
    name: str
    status: Literal["ok", "warn", "error"]
    message: str = ""
    duration_ms: int = 0


class DetectionHintsDTO(BaseModel):
    host_scope: str = "server"
    arch: str | None = None
    os: str | None = None
    os_family: str | None = None
    os_version: str | None = None
    container_runtime: str | None = None
    cuda_available: bool = False
    cuda: CudaDTO | None = None
    gpu: GpuDTO | None = None
    gpu_devices: list[dict[str, Any]] = Field(default_factory=list)
    driver_version: str | None = None
    cpu_model: str | None = None
    cpu_cores_logical: int | None = None
    cpu_cores_physical: int | None = None
    memory_gb_total: float | None = None
    disk_gb_total: float | None = None
    supported_cuda_min: str | None = None
    supported_cuda_max: str | None = None
    confidence: dict[str, Literal["detected", "inferred", "unknown"]] = Field(default_factory=dict)
    unknown_rate: float = 0.0
    resolved_ids: dict[str, str] = Field(default_factory=dict)
    matched_by: dict[str, Literal["exact", "alias", "inferred"]] = Field(default_factory=dict)
    unmatched_suggestions: list[dict[str, str]] = Field(default_factory=list)
    capabilities_suggested: list[str] = Field(default_factory=list)
    probes: list[DetectionProbeDTO] = Field(default_factory=list)


class HardwareCatalogItemDTO(BaseModel):
    id: str
    label: str
    aliases: list[str] = Field(default_factory=list)
    parent_id: str | None = None
    deprecated: bool = False


class HardwareCatalogDTO(BaseModel):
    schema_version: int = 1
    revision: int = 1
    arch: list[HardwareCatalogItemDTO] = Field(default_factory=list)
    os_family: list[HardwareCatalogItemDTO] = Field(default_factory=list)
    os_version: list[HardwareCatalogItemDTO] = Field(default_factory=list)
    container_runtime: list[HardwareCatalogItemDTO] = Field(default_factory=list)
    gpu_vendor: list[HardwareCatalogItemDTO] = Field(default_factory=list)
    gpu_family: list[HardwareCatalogItemDTO] = Field(default_factory=list)
    gpu_model: list[HardwareCatalogItemDTO] = Field(default_factory=list)


class HardwareCatalogUpsertRequestDTO(BaseModel):
    expected_revision: int | None = None
    catalog: str
    item: HardwareCatalogItemDTO


class LayerPresetPipDepDTO(BaseModel):
    name: str
    version: str = ""


class LayerPresetCategoryDTO(BaseModel):
    id: str
    label: str
    description: str = ""


class LayerPresetDTO(BaseModel):
    id: str
    display_name: str
    description: str = ""
    category: str
    tags: list[str] = Field(default_factory=list)
    pip: list[LayerPresetPipDepDTO] = Field(default_factory=list)
    apt: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    ports: list[int] = Field(default_factory=list)
    entrypoint_cmd: list[str] = Field(default_factory=list)
    requires: dict[str, Any] = Field(default_factory=dict)
    provides: dict[str, Any] = Field(default_factory=dict)
    layers: list[str] = Field(default_factory=list)


class LayerPresetCatalogDTO(BaseModel):
    schema_version: int = 1
    revision: int = 1
    categories: list[LayerPresetCategoryDTO] = Field(default_factory=list)
    presets: list[LayerPresetDTO] = Field(default_factory=list)


class RemoteDetectionRequestDTO(BaseModel):
    host: str
    port: int = 22
    username: str
    auth_mode: Literal["ssh_key", "password", "agent"] = "ssh_key"
    key_path: str | None = None
    timeout_sec: int = 15


class RemoteDetectionDeferredResponseDTO(BaseModel):
    status: Literal["deferred"] = "deferred"
    detail: str


# ---------------------------------------------------------------------------
# Create — request DTOs
# ---------------------------------------------------------------------------

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
    intent: "IntentCreateDTO" = Field(default_factory=lambda: IntentCreateDTO())
    requirements: "RequirementsCreateDTO" = Field(default_factory=lambda: RequirementsCreateDTO())
    derived_capabilities: list[str] = Field(default_factory=list)
    selected_features: list[str] = Field(default_factory=list)
    rejected_candidates: list["RejectedCandidateCreateDTO"] = Field(default_factory=list)
    fix_suggestions: list[str] = Field(default_factory=list)
    decision_trace: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_target_profile(self) -> "StackCreateRequest":
        from_constraints = str(self.requirements.constraints.get("target_profile_id", "")).strip()
        candidate = (self.target_profile_id or "").strip() or from_constraints
        if not candidate:
            raise ValueError("target_profile_id is required for stack creation.")
        self.target_profile_id = candidate
        # Keep requirements constraints normalized for downstream compatibility checks.
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


# ---------------------------------------------------------------------------
# Create — response DTOs
# ---------------------------------------------------------------------------

class StackCreateResponse(BaseModel):
    id: str
    display_name: str
    path: str

class ProfileCreateResponse(BaseModel):
    id: str
    display_name: str
    path: str

class DryRunResponse(BaseModel):
    yaml: str
    valid: bool
    errors: list[dict[str, str]] = Field(default_factory=list)


class LayerCreateResponse(BaseModel):
    id: str
    display_name: str
    path: str


class ComposePreviewResponse(BaseModel):
    valid: bool
    errors: list[dict[str, str]] = Field(default_factory=list)
    yaml: str = ""
    resolved_spec: dict[str, Any] | None = None
    dependency_conflicts: list[dict[str, str]] = Field(default_factory=list)
    tuple_conflicts: list[dict[str, str]] = Field(default_factory=list)
    runtime_conflicts: list[dict[str, str]] = Field(default_factory=list)


class CompatibilityIssueDTO(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    rule_id: str | None = None
    rule_version: int | None = None
    source: str | None = None
    field: str | None = None
    fix_hint: str | None = None
    confidence_context: dict[str, str] = Field(default_factory=dict)


class CompatibilityPreviewResponseDTO(BaseModel):
    compatible: bool
    errors: list[CompatibilityIssueDTO] = Field(default_factory=list)
    warnings: list[CompatibilityIssueDTO] = Field(default_factory=list)
    info: list[CompatibilityIssueDTO] = Field(default_factory=list)
    requirements_summary: dict[str, Any] = Field(default_factory=dict)
    suggested_fixes: list[str] = Field(default_factory=list)
    decision_trace: list[str] = Field(default_factory=list)
    tuple_decision: dict[str, Any] = Field(default_factory=dict)


class TupleCatalogSelectorDTO(BaseModel):
    arch: str
    os_family_id: str
    os_version_id: str
    container_runtime: str
    gpu_vendor_id: str
    gpu_family_id: str | None = None
    cuda_min: float | None = None
    cuda_max: float | None = None
    driver_min: float | None = None


class TupleCatalogItemDTO(BaseModel):
    id: str
    status: Literal["supported", "experimental", "unsupported"]
    selector: TupleCatalogSelectorDTO
    base_image: str = ""
    wheelhouse_path: str = ""
    notes: str = ""
    tags: list[str] = Field(default_factory=list)


class TupleCatalogDTO(BaseModel):
    schema_version: int = 1
    revision: int = 1
    tuples: list[TupleCatalogItemDTO] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Duplicate — request DTOs
# ---------------------------------------------------------------------------

class DuplicateStackRequest(BaseModel):
    new_id: str
    overrides: dict[str, Any] = Field(default_factory=dict)

class DuplicateProfileRequest(BaseModel):
    new_id: str
    overrides: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Create contracts metadata
# ---------------------------------------------------------------------------

class FieldConstraintDTO(BaseModel):
    pattern: str | None = None
    enum_values: list[str] = Field(default_factory=list)
    min_items: int | None = None
    max_items: int | None = None
    required_if: dict[str, Any] | None = None
    note: str | None = None


class CreateContractDTO(BaseModel):
    required_fields: list[str] = Field(default_factory=list)
    defaults: dict[str, Any] = Field(default_factory=dict)
    fields: dict[str, FieldConstraintDTO] = Field(default_factory=dict)


class CreateContractsResponseDTO(BaseModel):
    schema_version: int = 2
    profile: CreateContractDTO
    stack: CreateContractDTO
    layer: CreateContractDTO
