"""Shared create/update/dry-run orchestration for profile/stack/block specs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml
from pydantic import ValidationError as PydanticValidationError

from stacksmith.web.schemas import BlockCreateRequest, ProfileCreateRequest, StackCreateRequest

from stacksmith.config import (
    get_blocks_dir,
    get_profiles_dir,
    get_stacks_dir,
    load_block,
    load_profile,
    load_stack,
)
from stacksmith.domain.composition import (
    analyze_recipe_dependency_conflicts,
    analyze_recipe_runtime_conflicts,
    analyze_recipe_tuple_conflicts,
    compose_stack,
)
from stacksmith.domain.enums import Arch, BuildStrategy, ContainerRuntime
from stacksmith.domain.errors import SchemaValidationError
from stacksmith.domain.errors import BlockNotFoundError
from stacksmith.domain.models import (
    BaseCandidate,
    BlockSpec,
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
from stacksmith.resolvers.validators import validate_profile
from stacksmith.application.spec_validation import (
    ConflictError,
    ValidationErrors,
    run_block_security_validation,
    run_profile_security_validation,
    run_stack_security_validation,
    validate_id_available_file,
    validate_id_available_loader,
    validate_spec_id,
)
from stacksmith.application.serialization import atomic_write_yaml, serialize_for_yaml

from .errors import AppConflictError, AppInternalError, AppNotFoundError, AppValidationError

ValidationDetail = list[dict[str, str]]


def pydantic_to_detail(exc: PydanticValidationError) -> ValidationDetail:
    details = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err.get("loc", []))
        details.append({"field": field, "message": err.get("msg", str(err))})
    return details


def schema_to_detail(exc: SchemaValidationError) -> ValidationDetail:
    return [{"field": exc.field, "message": str(exc)}]


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
    return req.model_copy(update={"derived_capabilities": derived, "decision_trace": trace})


def normalize_profile_request(req: ProfileCreateRequest) -> ProfileCreateRequest:
    trace = list(req.decision_trace or [])
    if req.derived_capabilities:
        trace.append("Ignored user-supplied derived_capabilities; recomputed from requirements.needs.")
    derived = _dedupe_preserve(list(req.requirements.needs or []))
    if derived:
        trace.append("Computed derived_capabilities from requirements.needs.")
    return req.model_copy(update={"derived_capabilities": derived, "decision_trace": trace})


def build_stack_recipe(req: StackCreateRequest) -> StackRecipeSpec:
    copy_items = [CopyItem(src=c.src, dst=c.dst) for c in req.copy_items]
    variants = {k: VariantDef(type=v.type, options=v.options, default=v.default) for k, v in req.variants.items()}
    return StackRecipeSpec(
        kind="stack_recipe",
        schema_version=req.schema_version if hasattr(req, "schema_version") else 1,
        id=req.id,
        display_name=req.display_name,
        blocks=req.blocks,
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


def build_block(req: BlockCreateRequest) -> BlockSpec:
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
    return BlockSpec(
        kind="block",
        schema_version=req.schema_version,
        id=req.id,
        display_name=req.display_name,
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
        run_stack_security_validation(req)
        recipe = build_stack_recipe(req)
        return recipe, serialize_for_yaml(recipe)
    except (ValidationErrors, PydanticValidationError, SchemaValidationError) as exc:
        raise _to_validation_error(exc) from exc


def prepare_block(req: BlockCreateRequest) -> tuple[BlockSpec, dict]:
    try:
        run_block_security_validation(req)
        block = build_block(req)
        return block, serialize_for_yaml(block)
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
    return target


def create_block(req: BlockCreateRequest) -> Path:
    _, payload = prepare_block(req)
    target_dir = get_blocks_dir()
    _assert_id_available(req.id, target_dir, load_block)
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
    return target


def update_block(block_id: str, req: BlockCreateRequest) -> Path:
    if req.id != block_id:
        raise AppValidationError([{"field": "id", "message": "Block id is immutable for update; use create for rename."}])
    _, payload = prepare_block(req)
    target = get_blocks_dir() / f"{block_id}.yaml"
    if not target.exists():
        raise AppNotFoundError(f"Block not found: {block_id}")
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


def dry_run_block(req: BlockCreateRequest) -> DryRunResult:
    try:
        _, payload = prepare_block(req)
    except AppValidationError as exc:
        return DryRunResult(valid=False, errors=exc.errors, yaml="")
    return DryRunResult(valid=True, errors=[], yaml=yaml.safe_dump(payload, sort_keys=True, default_flow_style=False))


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
        run_stack_security_validation(req)
        recipe = build_stack_recipe(req)
        blocks = [load_block(block_id) for block_id in recipe.blocks]
        dependency_conflicts = analyze_recipe_dependency_conflicts(recipe, blocks)
        tuple_conflicts = analyze_recipe_tuple_conflicts(recipe, blocks)
        runtime_conflicts = analyze_recipe_runtime_conflicts(recipe, blocks)
        resolved = compose_stack(recipe, blocks)
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
    except BlockNotFoundError as exc:
        errors = [{"field": "compose", "message": str(exc)}]
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
    return new_id, data.get("display_name", source.display_name), target
