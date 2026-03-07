"""Shared create/update/dry-run orchestration for profile/stack/layer specs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import warnings

import yaml
from pydantic import ValidationError as PydanticValidationError

from stackwarden.application.create_request_models import (
    BaseCandidateCreateDTO,
    LayerCreateRequest,
    ProfileConstraintsCreateDTO,
    ProfileCreateRequest,
    StackCreateRequest,
)

from stackwarden.config import (
    get_layers_dir,
    get_profiles_dir,
    get_stacks_dir,
    load_layer,
    load_profile,
    load_stack,
    unmark_profile_deleted,
)
from stackwarden.domain.composition import (
    analyze_recipe_dependency_conflicts,
    analyze_recipe_runtime_conflicts,
    analyze_recipe_tuple_conflicts,
    compose_stack,
)
from stackwarden.domain.enums import Arch, BuildStrategy, ContainerRuntime
from stackwarden.domain.errors import SchemaValidationError
from stackwarden.domain.errors import LayerNotFoundError
from stackwarden.domain.errors import ProfileNotFoundError
from stackwarden.domain.models import (
    BaseCandidate,
    LayerSpec,
    CapabilityRange,
    CopyItem,
    CudaSpec,
    GpuDeviceSpec,
    GpuSpec,
    HostDiscoveryFacts,
    IntentSpec,
    NpmDep,
    PipDep,
    Profile,
    ProfileConstraints,
    ProfileDefaults,
    RejectedCandidateSpec,
    RequirementsSpec,
    StackComponentsPartial,
    StackEntrypoint,
    StackFiles,
    StackRecipeSpec,
    VariantDef,
)
from stackwarden.resolvers.validators import validate_profile
from stackwarden.application.spec_validation import (
    ConflictError,
    ValidationErrors,
    run_block_security_validation,
    run_profile_security_validation,
    run_stack_security_validation,
    validate_id_available_file,
    validate_id_available_loader,
    validate_spec_id,
)
from stackwarden.application.serialization import atomic_write_yaml, serialize_for_yaml

from .errors import AppConflictError, AppInternalError, AppNotFoundError, AppValidationError

ValidationDetail = list[dict[str, str]]
BLOCK_ALIAS_REMOVE_AFTER = "2026-06-30"


def _block_alias_warning(alias: str, replacement: str) -> str:
    return (
        f"{alias} is deprecated; use {replacement} instead. "
        f"Scheduled for removal after {BLOCK_ALIAS_REMOVE_AFTER}."
    )


def pydantic_to_detail(exc: PydanticValidationError) -> ValidationDetail:
    details = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err.get("loc", []))
        details.append({"field": field, "message": err.get("msg", str(err))})
    return details


def schema_to_detail(exc: SchemaValidationError) -> ValidationDetail:
    return [{"field": exc.field, "message": str(exc)}]


def validate_profile_create_request(payload: dict[str, Any]) -> Any:
    return ProfileCreateRequest.model_validate(payload)


def validate_stack_create_request(payload: dict[str, Any]) -> Any:
    return StackCreateRequest.model_validate(payload)


def validate_layer_create_request(payload: dict[str, Any]) -> Any:
    return LayerCreateRequest.model_validate(payload)


def _dedupe_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        token = str(value).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


def normalize_stack_request(req: StackCreateRequest) -> StackCreateRequest:
    trace = list(req.decision_trace or [])
    if req.derived_capabilities:
        trace.append("Ignored user-supplied derived_capabilities; recomputed from requirements.needs.")
    derived = _dedupe_preserve(list(req.requirements.needs or []))
    if derived:
        trace.append("Computed derived_capabilities from requirements.needs.")
    profile_id = str(req.target_profile_id or req.requirements.constraints.get("target_profile_id", "")).strip()
    constraints = dict(req.requirements.constraints or {})
    constraints["target_profile_id"] = profile_id
    requirements = req.requirements.model_copy(update={"constraints": constraints})
    return req.model_copy(
        update={
            "target_profile_id": profile_id,
            "requirements": requirements,
            "derived_capabilities": derived,
            "decision_trace": trace,
        }
    )


def normalize_profile_request(req: ProfileCreateRequest) -> ProfileCreateRequest:
    trace = list(req.decision_trace or [])
    if req.derived_capabilities:
        trace.append("Ignored user-supplied derived_capabilities; recomputed from requirements.needs.")

    arch = str(req.arch or "").strip().lower()
    os_family_id = str(req.os_family_id or "").strip().lower()
    os_version_id = str(req.os_version_id or "").strip().lower()
    os_family = str(req.os_family or "").strip().lower()
    os_version = str(req.os_version or "").strip()
    gpu_vendor = str(req.gpu.vendor_id or req.gpu.vendor or "").strip().lower()
    gpu_family = str(req.gpu.family_id or req.gpu.family or "").strip().lower()
    gpu_model = str(req.gpu.model_id or "").strip().lower()
    has_cuda = req.cuda is not None and req.cuda.major > 0
    is_blackwell = gpu_vendor == "nvidia" and gpu_family == "blackwell"
    is_dgx_spark = (
        arch == "arm64"
        and is_blackwell
        and gpu_model == "nvidia_gb10"
        and os_version_id == "ubuntu_24_04"
    )

    needs = _dedupe_preserve(list(req.requirements.needs or []))
    if needs:
        derived = needs
        trace.append("Computed derived_capabilities from requirements.needs.")
    else:
        inferred: list[str] = []
        if has_cuda or gpu_vendor == "nvidia":
            inferred.extend(["cuda", "tensor_cores"])
        if is_blackwell:
            inferred.append("fp8")
        if is_dgx_spark:
            inferred.append("unified_memory")
        derived = _dedupe_preserve(inferred)
        if derived:
            trace.append("Auto-derived capabilities from detected hardware/runtime fields.")

    defaults_update = req.defaults.model_copy()
    if not str(req.defaults.python or "").strip():
        defaults_update.python = "3.12" if is_blackwell else "3.11"

    constraints_update = req.constraints.model_copy()
    if gpu_vendor == "nvidia":
        required_env = list(constraints_update.require.get("env", []) or [])
        if "NVIDIA_VISIBLE_DEVICES" not in required_env:
            required_env.append("NVIDIA_VISIBLE_DEVICES")
            merged_require = dict(constraints_update.require or {})
            merged_require["env"] = required_env
            constraints_update = ProfileConstraintsCreateDTO(
                disallow=constraints_update.disallow,
                require=merged_require,
            )
            trace.append("Auto-enriched constraints.require.env with NVIDIA_VISIBLE_DEVICES.")

    candidates_update = list(req.base_candidates or [])
    if not candidates_update:
        if is_dgx_spark or is_blackwell:
            candidates_update = [
                BaseCandidateCreateDTO(name="nvcr.io/nvidia/pytorch", tags=["25.03-py3"], score_bias=180),
                BaseCandidateCreateDTO(name="nvcr.io/nvidia/tritonserver", tags=["25.03-py3"], score_bias=140),
            ]
        elif gpu_vendor == "nvidia":
            candidates_update = [
                BaseCandidateCreateDTO(name="nvcr.io/nvidia/pytorch", tags=["24.08-py3"], score_bias=120),
                BaseCandidateCreateDTO(name="nvcr.io/nvidia/tritonserver", tags=["24.08-py3"], score_bias=100),
            ]
        else:
            candidates_update = [BaseCandidateCreateDTO(name="python", tags=["3.11-slim"], score_bias=0)]
        trace.append("Auto-enriched base_candidates from detected hardware class.")

    if not os_family and os_family_id:
        os_family = os_family_id
        trace.append("Auto-normalized os_family from os_family_id.")
    if not os_version and os_version_id:
        parts = os_version_id.split("_")
        if len(parts) >= 3 and parts[-2].isdigit() and parts[-1].isdigit():
            os_version = f"{parts[-2]}.{parts[-1]}"
            trace.append("Auto-normalized os_version from os_version_id.")

    gpu_update = req.gpu.model_copy(
        update={
            "vendor_id": req.gpu.vendor_id or gpu_vendor or None,
            "family_id": req.gpu.family_id or gpu_family or None,
        }
    )
    requirements_update = req.requirements.model_copy()
    if not requirements_update.optimize_for:
        if is_dgx_spark or (gpu_vendor == "nvidia" and gpu_family == "hopper"):
            requirements_update.optimize_for = ["throughput", "latency", "reproducibility"]
            trace.append("Auto-enriched requirements.optimize_for with curated DGX baseline priorities.")
        else:
            requirements_update.optimize_for = ["latency", "throughput"] if gpu_vendor else ["balanced_reliability"]
            trace.append("Auto-enriched requirements.optimize_for from detected hardware class.")

    return req.model_copy(
        update={
            "derived_capabilities": derived,
            "base_candidates": candidates_update,
            "defaults": defaults_update,
            "constraints": constraints_update,
            "requirements": requirements_update,
            "gpu": gpu_update,
            "os_family": os_family or None,
            "os_version": os_version or None,
            "decision_trace": trace,
        }
    )


def build_stack_recipe(req: StackCreateRequest) -> StackRecipeSpec:
    copy_items = [CopyItem(src=c.src, dst=c.dst) for c in req.copy_items]
    variants = {k: VariantDef(type=v.type, options=v.options, default=v.default) for k, v in req.variants.items()}
    return StackRecipeSpec(
        kind="stack_recipe",
        schema_version=req.schema_version if hasattr(req, "schema_version") else 1,
        id=req.id,
        display_name=req.display_name,
        description=req.description or "",
        layers=req.layers,
        build_strategy=BuildStrategy(req.build_strategy.lower()) if req.build_strategy else None,
        components=StackComponentsPartial(base_role=req.base_role),
        files=StackFiles(copy_items=copy_items),
        variants=variants,
        intent=IntentSpec(outcome=req.intent.outcome, summary=req.intent.summary),
        requirements=RequirementsSpec(
            needs=req.requirements.needs,
            optimize_for=req.requirements.optimize_for,
            constraints=req.requirements.constraints,
        ),
        derived_capabilities=req.derived_capabilities,
        selected_features=req.selected_features,
        rejected_candidates=[RejectedCandidateSpec(name=c.name, reason=c.reason) for c in req.rejected_candidates],
        fix_suggestions=req.fix_suggestions,
        decision_trace=req.decision_trace,
    )


def build_layer(req: LayerCreateRequest) -> LayerSpec:
    env_list = [f"{k}={v}" for k, v in req.env.items()]
    pip_deps = [PipDep(name=d.name, version=d.version, version_mode=d.version_mode) for d in req.pip]
    npm_deps = [
        NpmDep(
            name=d.name,
            version=d.version,
            version_mode=d.version_mode,
            package_manager=d.package_manager,
            install_scope=d.install_scope,
        )
        for d in req.npm
    ]
    copy_items = [CopyItem(src=c.src, dst=c.dst) for c in req.copy_items]
    variants = {k: VariantDef(type=v.type, options=v.options, default=v.default) for k, v in req.variants.items()}
    return LayerSpec(
        kind="layer",
        schema_version=req.schema_version,
        id=req.id,
        display_name=req.display_name,
        description=req.description or "",
        stack_layer=req.stack_layer,
        tags=req.tags,
        build_strategy=BuildStrategy(req.build_strategy.lower()) if req.build_strategy else None,
        components=StackComponentsPartial(
            base_role=req.base_role,
            pip=pip_deps,
            pip_install_mode=req.pip_install_mode,
            pip_wheelhouse_path=req.pip_wheelhouse_path,
            npm=npm_deps,
            npm_install_mode=req.npm_install_mode,
            apt=req.apt,
            apt_constraints=req.apt_constraints,
            apt_install_mode=req.apt_install_mode,
        ),
        env=env_list,
        ports=req.ports,
        entrypoint=StackEntrypoint(cmd=req.entrypoint_cmd) if req.entrypoint_cmd else None,
        files=StackFiles(copy_items=copy_items),
        variants=variants,
        requires=req.requires,
        conflicts=req.conflicts,
        incompatible_with=req.incompatible_with,
        provides=req.provides,
    )


def build_profile(req: ProfileCreateRequest) -> Profile:
    candidates = [BaseCandidate(name=bc.name, tags=bc.tags, score_bias=bc.score_bias) for bc in req.base_candidates]
    return Profile(
        schema_version=req.schema_version,
        id=req.id,
        display_name=req.display_name,
        arch=Arch(req.arch.lower()),
        os=req.os.lower(),
        os_family=(req.os_family or req.os).lower() if (req.os_family or req.os) else None,
        os_version=req.os_version,
        os_family_id=req.os_family_id,
        os_version_id=req.os_version_id,
        container_runtime=ContainerRuntime(req.container_runtime.lower()),
        cuda=CudaSpec(major=req.cuda.major, minor=req.cuda.minor, variant=req.cuda.variant) if req.cuda else None,
        gpu_devices=[
            GpuDeviceSpec(
                index=int(device.get("index", i)),
                model=device.get("model"),
                family=device.get("family"),
                compute_capability=device.get("compute_capability"),
                memory_gb=device.get("memory_gb"),
            )
            for i, device in enumerate(req.gpu_devices)
        ],
        gpu=GpuSpec(
            vendor=req.gpu.vendor,
            family=req.gpu.family,
            vendor_id=req.gpu.vendor_id,
            family_id=req.gpu.family_id,
            model_id=req.gpu.model_id,
            compute_capability=req.gpu.compute_capability,
        ),
        constraints=ProfileConstraints(disallow=req.constraints.disallow, require=req.constraints.require),
        base_candidates=candidates,
        defaults=ProfileDefaults(python=req.defaults.python, user=req.defaults.user, workdir=req.defaults.workdir),
        intent=IntentSpec(outcome=req.intent.outcome, summary=req.intent.summary),
        requirements=RequirementsSpec(
            needs=req.requirements.needs,
            optimize_for=req.requirements.optimize_for,
            constraints=req.requirements.constraints,
        ),
        derived_capabilities=req.derived_capabilities,
        selected_features=req.selected_features,
        rejected_candidates=[RejectedCandidateSpec(name=c.name, reason=c.reason) for c in req.rejected_candidates],
        fix_suggestions=req.fix_suggestions,
        decision_trace=req.decision_trace,
        host_facts=HostDiscoveryFacts(
            driver_version=req.host_facts.driver_version,
            runtime_version=req.host_facts.runtime_version,
            cpu_model=req.host_facts.cpu_model,
            cpu_cores_logical=req.host_facts.cpu_cores_logical,
            cpu_cores_physical=req.host_facts.cpu_cores_physical,
            memory_gb_total=req.host_facts.memory_gb_total,
            disk_gb_total=req.host_facts.disk_gb_total,
            detected_at=req.host_facts.detected_at,
            confidence=req.host_facts.confidence,
        ),
        capability_ranges=[CapabilityRange(name=r.name, min=r.min, max=r.max, values=r.values) for r in req.capability_ranges],
        labels=req.labels,
        tags=req.tags,
        advanced_override=req.advanced_override,
    )


def _to_validation_error(exc: Exception) -> AppValidationError:
    if isinstance(exc, ValidationErrors):
        return AppValidationError(exc.errors)
    if isinstance(exc, PydanticValidationError):
        return AppValidationError(pydantic_to_detail(exc))
    if isinstance(exc, SchemaValidationError):
        return AppValidationError(schema_to_detail(exc))
    raise exc


def prepare_stack(req: StackCreateRequest) -> tuple[StackRecipeSpec, dict]:
    try:
        req = normalize_stack_request(req)
        try:
            load_profile(req.target_profile_id)
        except Exception as exc:  # noqa: BLE001 - normalized into validation payload
            raise AppValidationError(
                [{"field": "target_profile_id", "message": f"Profile not found: {req.target_profile_id}"}]
            ) from exc
        run_stack_security_validation(req)
        recipe = build_stack_recipe(req)
        return recipe, serialize_for_yaml(recipe)
    except (ValidationErrors, PydanticValidationError, SchemaValidationError) as exc:
        raise _to_validation_error(exc) from exc


def prepare_layer(req: LayerCreateRequest) -> tuple[LayerSpec, dict]:
    try:
        run_block_security_validation(req)
        layer = build_layer(req)
        return layer, serialize_for_yaml(layer)
    except (ValidationErrors, PydanticValidationError, SchemaValidationError) as exc:
        raise _to_validation_error(exc) from exc


def prepare_profile(req: ProfileCreateRequest) -> tuple[Profile, dict]:
    try:
        req = normalize_profile_request(req)
        run_profile_security_validation(req)
        profile = build_profile(req)
        validate_profile(profile)
        return profile, serialize_for_yaml(profile)
    except (ValidationErrors, PydanticValidationError, SchemaValidationError) as exc:
        raise _to_validation_error(exc) from exc


def _assert_id_available(spec_id: str, spec_dir: Path, loader: Callable[[str], Any]) -> None:
    try:
        validate_id_available_file(spec_id, spec_dir)
        validate_id_available_loader(spec_id, loader)
    except ConflictError as exc:
        raise AppConflictError(exc.message) from exc


def create_stack(req: StackCreateRequest) -> Path:
    _, payload = prepare_stack(req)
    target_dir = get_stacks_dir()
    _assert_id_available(req.id, target_dir, load_stack)
    target = target_dir / f"{req.id}.yaml"
    atomic_write_yaml(payload, target)
    return target


def create_profile(req: ProfileCreateRequest) -> Path:
    _, payload = prepare_profile(req)
    target_dir = get_profiles_dir()
    _assert_id_available(req.id, target_dir, load_profile)
    target = target_dir / f"{req.id}.yaml"
    atomic_write_yaml(payload, target)
    unmark_profile_deleted(req.id)
    return target


def create_layer(req: LayerCreateRequest) -> Path:
    _, payload = prepare_layer(req)
    target_dir = get_layers_dir()
    _assert_id_available(req.id, target_dir, load_layer)
    target = target_dir / f"{req.id}.yaml"
    atomic_write_yaml(payload, target)
    return target


def update_stack(stack_id: str, req: StackCreateRequest) -> Path:
    if req.id != stack_id:
        raise AppValidationError([{"field": "id", "message": "Stack id is immutable for update; use duplicate/create for rename."}])
    _, payload = prepare_stack(req)
    target = get_stacks_dir() / f"{stack_id}.yaml"
    if not target.exists():
        raise AppNotFoundError(f"Stack not found: {stack_id}")
    atomic_write_yaml(payload, target)
    return target


def update_profile(profile_id: str, req: ProfileCreateRequest) -> Path:
    if req.id != profile_id:
        raise AppValidationError([{"field": "id", "message": "Profile id is immutable for update; use duplicate/create for rename."}])
    _, payload = prepare_profile(req)
    target = get_profiles_dir() / f"{profile_id}.yaml"
    if not target.exists():
        raise AppNotFoundError(f"Profile not found: {profile_id}")
    atomic_write_yaml(payload, target)
    unmark_profile_deleted(profile_id)
    return target


def update_layer(layer_id: str, req: LayerCreateRequest) -> Path:
    if req.id != layer_id:
        raise AppValidationError([{"field": "id", "message": "Layer id is immutable for update; use create for rename."}])
    _, payload = prepare_layer(req)
    target = get_layers_dir() / f"{layer_id}.yaml"
    if not target.exists():
        raise AppNotFoundError(f"Layer not found: {layer_id}")
    atomic_write_yaml(payload, target)
    return target


@dataclass
class DryRunResult:
    valid: bool
    errors: ValidationDetail
    yaml: str


def dry_run_stack(req: StackCreateRequest) -> DryRunResult:
    try:
        _, payload = prepare_stack(req)
    except AppValidationError as exc:
        return DryRunResult(valid=False, errors=exc.errors, yaml="")
    return DryRunResult(valid=True, errors=[], yaml=yaml.safe_dump(payload, sort_keys=True, default_flow_style=False))


def dry_run_profile(req: ProfileCreateRequest) -> DryRunResult:
    try:
        _, payload = prepare_profile(req)
    except AppValidationError as exc:
        return DryRunResult(valid=False, errors=exc.errors, yaml="")
    return DryRunResult(valid=True, errors=[], yaml=yaml.safe_dump(payload, sort_keys=True, default_flow_style=False))


def dry_run_layer(req: LayerCreateRequest) -> DryRunResult:
    try:
        _, payload = prepare_layer(req)
    except AppValidationError as exc:
        return DryRunResult(valid=False, errors=exc.errors, yaml="")
    return DryRunResult(valid=True, errors=[], yaml=yaml.safe_dump(payload, sort_keys=True, default_flow_style=False))


def create_block(req: LayerCreateRequest) -> Path:
    warnings.warn(
        _block_alias_warning("create_block", "create_layer"),
        DeprecationWarning,
        stacklevel=2,
    )
    return create_layer(req)


def update_block(block_id: str, req: LayerCreateRequest) -> Path:
    warnings.warn(
        _block_alias_warning("update_block", "update_layer"),
        DeprecationWarning,
        stacklevel=2,
    )
    return update_layer(block_id, req)


def dry_run_block(req: LayerCreateRequest) -> DryRunResult:
    warnings.warn(
        _block_alias_warning("dry_run_block", "dry_run_layer"),
        DeprecationWarning,
        stacklevel=2,
    )
    return dry_run_layer(req)


def prepare_block(req: LayerCreateRequest) -> tuple[LayerSpec, dict[str, Any]]:
    warnings.warn(
        _block_alias_warning("prepare_block", "prepare_layer"),
        DeprecationWarning,
        stacklevel=2,
    )
    return prepare_layer(req)


def build_block(req: LayerCreateRequest) -> LayerSpec:
    warnings.warn(
        _block_alias_warning("build_block", "build_layer"),
        DeprecationWarning,
        stacklevel=2,
    )
    return build_layer(req)


@dataclass
class ComposeResult:
    valid: bool
    errors: ValidationDetail
    yaml: str
    resolved_spec: dict[str, Any] | None
    dependency_conflicts: list[dict[str, str]]
    tuple_conflicts: list[dict[str, str]]
    runtime_conflicts: list[dict[str, str]]


def compose_stack_preview(req: StackCreateRequest) -> ComposeResult:
    dependency_conflicts: list[dict[str, str]] = []
    tuple_conflicts: list[dict[str, str]] = []
    runtime_conflicts: list[dict[str, str]] = []
    try:
        load_profile(req.target_profile_id)
        run_stack_security_validation(req)
        recipe = build_stack_recipe(req)
        layers = [load_layer(layer_id) for layer_id in recipe.layers]
        dependency_conflicts = analyze_recipe_dependency_conflicts(recipe, layers)
        tuple_conflicts = analyze_recipe_tuple_conflicts(recipe, layers)
        runtime_conflicts = analyze_recipe_runtime_conflicts(recipe, layers)
        resolved = compose_stack(recipe, layers)
        resolved_dict = serialize_for_yaml(resolved)
        return ComposeResult(
            valid=True,
            errors=[],
            yaml=yaml.safe_dump(resolved_dict, sort_keys=True, default_flow_style=False),
            resolved_spec=resolved_dict,
            dependency_conflicts=dependency_conflicts,
            tuple_conflicts=tuple_conflicts,
            runtime_conflicts=runtime_conflicts,
        )
    except ValidationErrors as exc:
        errors = exc.errors
    except PydanticValidationError as exc:
        errors = pydantic_to_detail(exc)
    except SchemaValidationError as exc:
        errors = schema_to_detail(exc)
    except ValueError as exc:
        errors = [{"field": "compose", "message": str(exc)}]
    except LayerNotFoundError as exc:
        errors = [{"field": "compose", "message": str(exc)}]
    except ProfileNotFoundError as exc:
        errors = [{"field": "target_profile_id", "message": str(exc)}]
    except Exception as exc:  # noqa: BLE001 - unknown internal failure
        raise AppInternalError(f"Compose preview failed: {exc}") from exc
    return ComposeResult(
        valid=False,
        errors=errors,
        yaml="",
        resolved_spec=None,
        dependency_conflicts=dependency_conflicts,
        tuple_conflicts=tuple_conflicts,
        runtime_conflicts=runtime_conflicts,
    )


_STACK_SAFE_OVERRIDES = frozenset({"display_name", "env", "ports"})
_PROFILE_SAFE_OVERRIDES = frozenset({"display_name"})


def duplicate_stack(stack_id: str, new_id: str, overrides: dict[str, Any]) -> tuple[str, str, Path]:
    try:
        source = load_stack(stack_id)
    except Exception as exc:  # noqa: BLE001 - current API exposes only not found here
        raise AppNotFoundError(f"Source stack not found: {stack_id}") from exc

    data = serialize_for_yaml(source)
    data["id"] = new_id
    unsafe_keys = set(overrides.keys()) - _STACK_SAFE_OVERRIDES
    if unsafe_keys:
        raise AppValidationError(
            [{"field": key, "message": f"Override not allowed for duplicate: {key}"} for key in sorted(unsafe_keys)]
        )
    if "display_name" in overrides:
        data["display_name"] = overrides["display_name"]
    if "env" in overrides and isinstance(overrides["env"], dict):
        data["env"] = [f"{k}={v}" for k, v in overrides["env"].items()]
    if "ports" in overrides and isinstance(overrides["ports"], list):
        data["ports"] = overrides["ports"]

    errors = validate_spec_id(new_id)
    if errors:
        raise AppValidationError(errors)

    stacks_dir = get_stacks_dir()
    _assert_id_available(new_id, stacks_dir, load_stack)
    target = stacks_dir / f"{new_id}.yaml"
    atomic_write_yaml(data, target)
    return new_id, data.get("display_name", source.display_name), target


def duplicate_profile(profile_id: str, new_id: str, overrides: dict[str, Any]) -> tuple[str, str, Path]:
    try:
        source = load_profile(profile_id)
    except Exception as exc:  # noqa: BLE001 - current API exposes only not found here
        raise AppNotFoundError(f"Source profile not found: {profile_id}") from exc

    data = serialize_for_yaml(source)
    data["id"] = new_id
    unsafe_keys = set(overrides.keys()) - _PROFILE_SAFE_OVERRIDES
    if unsafe_keys:
        raise AppValidationError(
            [{"field": key, "message": f"Override not allowed for duplicate: {key}"} for key in sorted(unsafe_keys)]
        )
    if "display_name" in overrides:
        data["display_name"] = overrides["display_name"]

    errors = validate_spec_id(new_id)
    if errors:
        raise AppValidationError(errors)

    profiles_dir = get_profiles_dir()
    _assert_id_available(new_id, profiles_dir, load_profile)
    target = profiles_dir / f"{new_id}.yaml"
    atomic_write_yaml(data, target)
    unmark_profile_deleted(new_id)
    return new_id, data.get("display_name", source.display_name), target
