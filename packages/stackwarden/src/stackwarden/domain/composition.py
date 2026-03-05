"""Composable stack assembly from recipe + reusable blocks."""

from __future__ import annotations

from dataclasses import dataclass

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from stackwarden.domain.enums import BuildStrategy
from stackwarden.domain.models import (
    ApiType,
    BlockSpec,
    ServeType,
    CopyItem,
    NpmDep,
    PipDep,
    StackComponents,
    StackEntrypoint,
    StackFiles,
    StackRecipeSpec,
    StackSpec,
    TaskType,
    VariantDef,
)


@dataclass
class _PipOrigin:
    dep: PipDep
    source: str


@dataclass
class _NpmOrigin:
    dep: NpmDep
    source: str


def _env_key(entry: str) -> str:
    return entry.split("=", 1)[0]


def _parse_specifier(spec: str) -> SpecifierSet:
    try:
        return SpecifierSet(spec)
    except InvalidSpecifier as exc:
        raise ValueError(f"Invalid pip version specifier {spec!r}") from exc


def _pinned_versions(spec: str) -> set[str]:
    parsed = _parse_specifier(spec)
    values: set[str] = set()
    for item in parsed:
        if item.operator in {"==", "==="}:
            values.add(item.version)
    return values


def _pip_constraints_compatible(existing: str, incoming: str) -> bool:
    if not existing or not incoming:
        return True

    existing_set = _parse_specifier(existing)
    incoming_set = _parse_specifier(incoming)

    existing_pins = _pinned_versions(existing)
    incoming_pins = _pinned_versions(incoming)

    if existing_pins and incoming_pins:
        return bool(existing_pins.intersection(incoming_pins))

    if existing_pins:
        for pinned in existing_pins:
            try:
                if incoming_set.contains(Version(pinned), prereleases=True):
                    return True
            except InvalidVersion:
                continue
        return False

    if incoming_pins:
        for pinned in incoming_pins:
            try:
                if existing_set.contains(Version(pinned), prereleases=True):
                    return True
            except InvalidVersion:
                continue
        return False

    # Non-pinned ranges are assumed compatible in v1.
    return True


def _merge_pip(
    accum: dict[str, _PipOrigin],
    incoming: list[PipDep],
    source: str,
) -> None:
    for dep in incoming:
        prev = accum.get(dep.name)
        if prev is None:
            accum[dep.name] = _PipOrigin(dep=dep, source=source)
            continue

        if prev.dep.version == dep.version:
            continue

        if not _pip_constraints_compatible(prev.dep.version, dep.version):
            raise ValueError(
                "Incompatible pip constraints for package "
                f"{dep.name!r}: {prev.dep.version!r} from {prev.source} "
                f"vs {dep.version!r} from {source}"
            )

        # Preserve deterministic precedence: incoming wins.
        accum[dep.name] = _PipOrigin(dep=dep, source=source)


def _merge_npm(
    accum: dict[tuple[str, str, str], _NpmOrigin],
    incoming: list[NpmDep],
    source: str,
) -> None:
    for dep in incoming:
        key = (dep.name, dep.package_manager, dep.install_scope)
        prev = accum.get(key)
        if prev is None:
            accum[key] = _NpmOrigin(dep=dep, source=source)
            continue
        if prev.dep.version_mode == dep.version_mode and prev.dep.version == dep.version:
            continue
        if (
            prev.dep.version_mode == "custom"
            and dep.version_mode == "custom"
            and prev.dep.version != dep.version
        ):
            raise ValueError(
                "Incompatible npm constraints for package "
                f"{dep.name!r}: {prev.dep.version!r} from {prev.source} "
                f"vs {dep.version!r} from {source}"
            )
        accum[key] = _NpmOrigin(dep=dep, source=source)


def analyze_recipe_dependency_conflicts(
    recipe: StackRecipeSpec,
    blocks: list[BlockSpec],
) -> list[dict[str, str]]:
    """Return soft/hard dependency conflicts for a recipe composition preview."""
    by_id = {b.id: b for b in blocks}
    ordered_blocks: list[BlockSpec] = []
    for block_id in recipe.blocks:
        block = by_id.get(block_id)
        if block is None:
            continue
        ordered_blocks.append(block)

    pip_seen: dict[str, tuple[str, str]] = {}
    npm_seen: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    wheelhouse_seen: tuple[str, str, str] | None = None
    conflicts: list[dict[str, str]] = []

    def _push_pip(dep: PipDep, source: str) -> None:
        key = dep.name
        prev = pip_seen.get(key)
        if prev is None:
            pip_seen[key] = (dep.version, source)
            return
        prev_version, prev_source = prev
        if prev_version == dep.version:
            return
        compatible = _pip_constraints_compatible(prev_version, dep.version)
        severity = "warning" if compatible else "error"
        conflicts.append({
            "type": "pip",
            "name": dep.name,
            "severity": severity,
            "existing": prev_version or "latest",
            "incoming": dep.version or "latest",
            "existing_source": prev_source,
            "incoming_source": source,
            "message": (
                "Compatible dependency overlap; explicit selection recommended."
                if compatible
                else "Conflicting constraints detected; choose one version."
            ),
        })
        pip_seen[key] = (dep.version, source)

    def _push_npm(dep: NpmDep, source: str) -> None:
        key = (dep.name, dep.package_manager, dep.install_scope)
        prev = npm_seen.get(key)
        incoming_version = dep.version if dep.version_mode == "custom" else ""
        if prev is None:
            npm_seen[key] = (incoming_version, dep.version_mode, source)
            return
        prev_version, prev_mode, prev_source = prev
        if prev_version == incoming_version and prev_mode == dep.version_mode:
            return
        hard_conflict = prev_mode == "custom" and dep.version_mode == "custom" and prev_version != incoming_version
        conflicts.append({
            "type": "npm",
            "name": dep.name,
            "severity": "error" if hard_conflict else "warning",
            "existing": prev_version or "latest",
            "incoming": incoming_version or "latest",
            "existing_source": prev_source,
            "incoming_source": source,
            "message": (
                "Conflicting npm constraints detected; choose one version."
                if hard_conflict
                else "Overlapping npm intent; explicit selection recommended."
            ),
        })
        npm_seen[key] = (incoming_version, dep.version_mode, source)

    def _push_wheelhouse(mode: str, path: str, source: str) -> None:
        nonlocal wheelhouse_seen
        normalized_mode = mode or "index"
        normalized_path = (path or "").strip()
        if wheelhouse_seen is None:
            wheelhouse_seen = (normalized_mode, normalized_path, source)
            return
        prev_mode, prev_path, prev_source = wheelhouse_seen
        if prev_mode == normalized_mode and prev_path == normalized_path:
            return
        hard_conflict = (
            prev_mode == "wheelhouse_only"
            and normalized_mode == "wheelhouse_only"
            and prev_path != normalized_path
        )
        conflicts.append({
            "type": "pip_wheelhouse",
            "name": "pip_install_mode",
            "severity": "error" if hard_conflict else "warning",
            "existing": f"{prev_mode}:{prev_path or '-'}",
            "incoming": f"{normalized_mode}:{normalized_path or '-'}",
            "existing_source": prev_source,
            "incoming_source": source,
            "message": (
                "Conflicting wheelhouse-only sources detected; choose one path."
                if hard_conflict
                else "Wheelhouse policy overlap detected; recipe/source precedence will apply."
            ),
        })
        wheelhouse_seen = (normalized_mode, normalized_path, source)

    for block in ordered_blocks:
        source = f"block:{block.id}"
        _push_wheelhouse(
            block.components.pip_install_mode,
            block.components.pip_wheelhouse_path,
            source,
        )
        for dep in block.components.pip:
            _push_pip(dep, source)
        for dep in block.components.npm:
            _push_npm(dep, source)

    recipe_source = f"recipe:{recipe.id}"
    _push_wheelhouse(
        recipe.components.pip_install_mode,
        recipe.components.pip_wheelhouse_path,
        recipe_source,
    )
    for dep in recipe.components.pip:
        _push_pip(dep, recipe_source)
    for dep in recipe.components.npm:
        _push_npm(dep, recipe_source)

    return conflicts


def analyze_recipe_tuple_conflicts(
    recipe: StackRecipeSpec,
    blocks: list[BlockSpec],
) -> list[dict[str, str]]:
    """Detect conflicting tuple-like requires keys across recipe blocks."""
    by_id = {b.id: b for b in blocks}
    ordered_blocks = [by_id[block_id] for block_id in recipe.blocks if block_id in by_id]
    watched = (
        "arch",
        "os_family_id",
        "os_version_id",
        "container_runtime",
        "gpu_vendor_id",
        "gpu_family_id",
    )
    seen: dict[str, tuple[str, str]] = {}
    conflicts: list[dict[str, str]] = []
    for block in ordered_blocks:
        reqs = block.requires or {}
        source = f"block:{block.id}"
        for key in watched:
            value = str(reqs.get(key, "")).strip()
            if not value:
                continue
            prev = seen.get(key)
            if prev is None:
                seen[key] = (value, source)
                continue
            prev_value, prev_source = prev
            if prev_value == value:
                continue
            conflicts.append(
                {
                    "type": "tuple",
                    "name": key,
                    "severity": "error",
                    "existing": prev_value,
                    "incoming": value,
                    "existing_source": prev_source,
                    "incoming_source": source,
                    "message": f"Conflicting tuple requirement for '{key}'.",
                }
            )
            seen[key] = (value, source)
    return conflicts


def analyze_recipe_runtime_conflicts(
    recipe: StackRecipeSpec,
    blocks: list[BlockSpec],
) -> list[dict[str, str]]:
    """Detect runtime merge overrides for env/entrypoint/base_role."""
    by_id = {b.id: b for b in blocks}
    ordered_blocks = [by_id[block_id] for block_id in recipe.blocks if block_id in by_id]
    conflicts: list[dict[str, str]] = []
    env_seen: dict[str, tuple[str, str]] = {}
    entrypoint_seen: tuple[str, str] | None = None
    base_role_seen: tuple[str, str] | None = None

    def _push_env(entry: str, source: str) -> None:
        key = _env_key(entry)
        prev = env_seen.get(key)
        if prev is None:
            env_seen[key] = (entry, source)
            return
        prev_value, prev_source = prev
        if prev_value == entry:
            return
        conflicts.append({
            "type": "env",
            "name": key,
            "severity": "warning",
            "existing": prev_value,
            "incoming": entry,
            "existing_source": prev_source,
            "incoming_source": source,
            "message": "Env key overridden by later block precedence.",
        })
        env_seen[key] = (entry, source)

    def _push_entrypoint(cmd: StackEntrypoint | None, source: str) -> None:
        nonlocal entrypoint_seen
        if cmd is None:
            return
        incoming = " ".join(cmd.cmd)
        if entrypoint_seen is None:
            entrypoint_seen = (incoming, source)
            return
        prev_value, prev_source = entrypoint_seen
        if prev_value == incoming:
            return
        conflicts.append({
            "type": "entrypoint",
            "name": "entrypoint.cmd",
            "severity": "warning",
            "existing": prev_value,
            "incoming": incoming,
            "existing_source": prev_source,
            "incoming_source": source,
            "message": "Entrypoint overridden by later block precedence.",
        })
        entrypoint_seen = (incoming, source)

    def _push_base_role(base_role: str | None, source: str) -> None:
        nonlocal base_role_seen
        if not base_role:
            return
        if base_role_seen is None:
            base_role_seen = (base_role, source)
            return
        prev_value, prev_source = base_role_seen
        if prev_value == base_role:
            return
        conflicts.append({
            "type": "base_role",
            "name": "components.base_role",
            "severity": "warning",
            "existing": prev_value,
            "incoming": base_role,
            "existing_source": prev_source,
            "incoming_source": source,
            "message": "Base role overridden by later block precedence.",
        })
        base_role_seen = (base_role, source)

    for block in ordered_blocks:
        source = f"block:{block.id}"
        for env in block.env:
            _push_env(env, source)
        _push_entrypoint(block.entrypoint, source)
        _push_base_role(block.components.base_role, source)

    recipe_source = f"recipe:{recipe.id}"
    for env in recipe.env:
        _push_env(env, recipe_source)
    _push_entrypoint(recipe.entrypoint, recipe_source)
    _push_base_role(recipe.components.base_role, recipe_source)

    return conflicts


def compose_stack(recipe: StackRecipeSpec, blocks: list[BlockSpec]) -> StackSpec:
    """Compose a concrete StackSpec from a stack recipe and ordered blocks."""
    seen: set[str] = set()
    for block_id in recipe.blocks:
        if block_id in seen:
            raise ValueError(f"Duplicate block reference in recipe: {block_id}")
        seen.add(block_id)

    by_id = {b.id: b for b in blocks}
    ordered_blocks: list[BlockSpec] = []
    for block_id in recipe.blocks:
        block = by_id.get(block_id)
        if block is None:
            raise ValueError(f"Unknown block reference in recipe: {block_id}")
        ordered_blocks.append(block)

    base_role: str | None = None
    build_strategy = recipe.build_strategy
    entrypoint: StackEntrypoint | None = None
    pip_install_mode = "index"
    pip_wheelhouse_path = ""
    npm_install_mode = "spec"
    apt_install_mode = "repo"

    pip_accum: dict[str, _PipOrigin] = {}
    npm_accum: dict[tuple[str, str, str], _NpmOrigin] = {}
    apt_accum: dict[str, str] = {}
    apt_constraints_accum: dict[str, str] = {}
    env_accum: dict[str, str] = {}
    ports_accum: dict[int, int] = {}
    copy_accum: dict[tuple[str, str], CopyItem] = {}
    variants: dict[str, VariantDef] = {}

    def _consume_block(spec: BlockSpec, source: str) -> None:
        nonlocal base_role, build_strategy, entrypoint, pip_install_mode, pip_wheelhouse_path
        nonlocal npm_install_mode, apt_install_mode
        if spec.components.base_role:
            base_role = spec.components.base_role
        if spec.build_strategy is not None:
            build_strategy = spec.build_strategy
        if spec.entrypoint is not None:
            entrypoint = spec.entrypoint
        pip_install_mode = spec.components.pip_install_mode
        pip_wheelhouse_path = spec.components.pip_wheelhouse_path
        npm_install_mode = spec.components.npm_install_mode
        apt_install_mode = spec.components.apt_install_mode
        _merge_pip(pip_accum, spec.components.pip, source)
        _merge_npm(npm_accum, spec.components.npm, source)
        for pkg in spec.components.apt:
            apt_accum[pkg] = pkg
        for pkg_name, constraint in spec.components.apt_constraints.items():
            apt_constraints_accum[pkg_name] = constraint
        for item in spec.files.copy_items:
            copy_accum[(item.src, item.dst)] = item
        for env in spec.env:
            env_accum[_env_key(env)] = env
        for port in spec.ports:
            ports_accum[port] = port
        for key, val in spec.variants.items():
            variants[key] = val

    for block in ordered_blocks:
        _consume_block(block, f"block:{block.id}")

    # Apply recipe-level overrides last.
    if recipe.components.base_role:
        base_role = recipe.components.base_role
    if recipe.entrypoint is not None:
        entrypoint = recipe.entrypoint
    if recipe.build_strategy is not None:
        build_strategy = recipe.build_strategy
    pip_install_mode = recipe.components.pip_install_mode
    pip_wheelhouse_path = recipe.components.pip_wheelhouse_path
    npm_install_mode = recipe.components.npm_install_mode
    apt_install_mode = recipe.components.apt_install_mode
    _merge_pip(pip_accum, recipe.components.pip, f"recipe:{recipe.id}")
    _merge_npm(npm_accum, recipe.components.npm, f"recipe:{recipe.id}")
    for pkg in recipe.components.apt:
        apt_accum[pkg] = pkg
    for pkg_name, constraint in recipe.components.apt_constraints.items():
        apt_constraints_accum[pkg_name] = constraint
    for item in recipe.files.copy_items:
        copy_accum[(item.src, item.dst)] = item
    for env in recipe.env:
        env_accum[_env_key(env)] = env
    for port in recipe.ports:
        ports_accum[port] = port
    variants.update(recipe.variants)

    if not base_role:
        base_role = "python"
    if build_strategy is None:
        build_strategy = BuildStrategy.OVERLAY
    if entrypoint is None:
        # Deterministic safe default when no selected block declares a runtime command.
        entrypoint = StackEntrypoint(cmd=["python", "-c", "import time; time.sleep(3600)"])

    return StackSpec(
        kind="stack",
        schema_version=recipe.schema_version,
        id=recipe.id,
        display_name=recipe.display_name,
        task=TaskType.CUSTOM,
        serve=ServeType.CUSTOM,
        api=ApiType.CUSTOM,
        build_strategy=build_strategy,
        components=StackComponents(
            base_role=base_role,
            pip=[pip_accum[name].dep for name in sorted(pip_accum.keys())],
            pip_install_mode=pip_install_mode,
            pip_wheelhouse_path=pip_wheelhouse_path,
            npm=[npm_accum[name].dep for name in sorted(npm_accum.keys())],
            npm_install_mode=npm_install_mode,
            apt=sorted(apt_accum.keys()),
            apt_constraints={k: apt_constraints_accum[k] for k in sorted(apt_constraints_accum.keys())},
            apt_install_mode=apt_install_mode,
        ),
        env=[env_accum[k] for k in sorted(env_accum.keys())],
        ports=sorted(ports_accum.keys()),
        entrypoint=entrypoint,
        files=StackFiles(copy_items=[copy_accum[k] for k in sorted(copy_accum.keys())]),
        variants=variants,
        blocks=list(recipe.blocks),
    )

