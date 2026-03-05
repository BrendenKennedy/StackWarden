"""Security-focused allowlist validation for Create endpoints.

Each validator collects errors into a list of ``{field, message}`` dicts.
The route handler aggregates all errors and returns 422.
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Iterable

from stacksmith.contracts import ALLOWED_BUILD_STRATEGIES, SPEC_ID_PATTERN
from stacksmith.domain.errors import BlockNotFoundError, ProfileNotFoundError, StackNotFoundError

_SPEC_ID_RE = re.compile(SPEC_ID_PATTERN)
_APT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9+.\-]{0,63}$")
_NPM_NAME_RE = re.compile(r"^(@[a-z0-9._-]+/)?[a-z0-9._-]+$")
_ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]{0,63}$")
_COPY_PATH_RE = re.compile(r"^[A-Za-z0-9._\-/]+$")
_VARIANT_NAME_RE = re.compile(r"^[a-z][a-z0-9_\-]{0,63}$")
_IMAGE_REF_RE = re.compile(r"^[a-z0-9]+([._/\-][a-z0-9]+)*$")

_PIP_BANNED_PREFIXES = ("--index-url", "--extra-index-url", "-f", "--find-links", "--trusted-host")
_VARIANT_RESERVED_NAMES = frozenset({"profile", "stack", "fingerprint", "id", "tag", "base"})

_ALLOWED_BUILD_STRATEGIES = frozenset(ALLOWED_BUILD_STRATEGIES)

_MAX_ENV_VALUE_LEN = 4096
_MAX_TOKEN_LEN = 4096
_WHEELHOUSE_MODES = frozenset({"index", "wheelhouse_prefer", "wheelhouse_only"})
_NPM_INSTALL_MODES = frozenset({"spec", "lock_prefer", "lock_only"})
_APT_INSTALL_MODES = frozenset({"repo", "pin_prefer", "pin_only"})
_LOCKFILE_NAMES = frozenset({"package-lock.json", "pnpm-lock.yaml", "yarn.lock"})


class ValidationErrors(Exception):
    """Raised when one or more validation rules fail."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s)")


class ConflictError(Exception):
    """Raised when a spec ID already exists (409)."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _err(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


# ---------------------------------------------------------------------------
# Individual validators — return error lists
# ---------------------------------------------------------------------------

def validate_spec_id(spec_id: str, field: str = "id") -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if ".." in spec_id:
        errors.append(_err(field, "Path traversal not allowed in id"))
    elif not _SPEC_ID_RE.match(spec_id):
        errors.append(_err(
            field,
            "id must be 3–64 chars, start with a lowercase letter, "
            "and contain only lowercase letters, digits, hyphens, and underscores",
        ))
    return errors


def validate_id_available_file(spec_id: str, spec_dir: Path) -> list[dict[str, str]]:
    """Check that no file ``<id>.yaml`` already exists in *spec_dir*."""
    target = spec_dir / f"{spec_id}.yaml"
    if target.exists():
        raise ConflictError(f"Spec with id '{spec_id}' already exists at {target}")
    return []


def validate_id_available_loader(
    spec_id: str,
    loader: callable,
) -> list[dict[str, str]]:
    """Try to load *spec_id* via *loader*; if it succeeds the id is taken."""
    try:
        loader(spec_id)
    except (ProfileNotFoundError, StackNotFoundError, BlockNotFoundError):
        return []
    raise ConflictError(f"Spec with id '{spec_id}' already exists (loadable)")


def validate_pip_deps(deps: list) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for i, dep in enumerate(deps):
        name = dep.name if hasattr(dep, "name") else dep.get("name", "")
        version = dep.version if hasattr(dep, "version") else dep.get("version", "")
        version_mode = (
            dep.version_mode if hasattr(dep, "version_mode")
            else dep.get("version_mode", "latest")
        )

        if name.startswith("-"):
            errors.append(_err(f"pip[{i}].name", f"Pip option flags not allowed: {name!r}"))
            continue

        for banned in _PIP_BANNED_PREFIXES:
            if banned in name:
                errors.append(_err(f"pip[{i}].name", f"Pip option '{banned}' not allowed in package name"))

        if version_mode == "custom" and not version:
            errors.append(_err(f"pip[{i}].version", "Custom mode requires a version constraint"))
        if version_mode == "latest" and version:
            errors.append(_err(f"pip[{i}].version", "Latest mode must not include a version constraint"))
        if version_mode not in {"latest", "custom"}:
            errors.append(_err(f"pip[{i}].version_mode", f"Unsupported version_mode: {version_mode!r}"))
        if version and version_mode == "custom":
            try:
                from packaging.requirements import Requirement
                Requirement(f"{name}{version}")
            except Exception as exc:
                errors.append(_err(f"pip[{i}].version", f"Invalid version specifier: {exc}"))

    return errors


def validate_apt_packages(pkgs: list[str]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for i, pkg in enumerate(pkgs):
        if not _APT_NAME_RE.match(pkg):
            errors.append(_err(
                f"apt[{i}]",
                f"Invalid apt package name: {pkg!r}. "
                "Must contain only lowercase letters, digits, '.', '+', '-'.",
            ))
        for bad in (" ", ";", "&", "|", "`"):
            if bad in pkg:
                errors.append(_err(f"apt[{i}]", f"Forbidden character {bad!r} in apt package name"))
                break
    return errors


def validate_apt_constraints(
    pkgs: list[str],
    constraints: dict[str, str],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    allowed = set(pkgs)
    for name, constraint in constraints.items():
        if name not in allowed:
            errors.append(_err(f"apt_constraints.{name}", "Constraint references unknown apt package"))
            continue
        if not constraint.strip():
            errors.append(_err(f"apt_constraints.{name}", "Constraint cannot be empty"))
            continue
        if any(ch in constraint for ch in ("\n", "\r", ";", "&", "|", "`")):
            errors.append(_err(f"apt_constraints.{name}", "Constraint contains forbidden characters"))
    return errors


def validate_npm_deps(deps: list) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for i, dep in enumerate(deps):
        name = dep.name if hasattr(dep, "name") else dep.get("name", "")
        version = dep.version if hasattr(dep, "version") else dep.get("version", "")
        version_mode = (
            dep.version_mode if hasattr(dep, "version_mode")
            else dep.get("version_mode", "latest")
        )
        manager = (
            dep.package_manager if hasattr(dep, "package_manager")
            else dep.get("package_manager", "npm")
        )
        scope = (
            dep.install_scope if hasattr(dep, "install_scope")
            else dep.get("install_scope", "prod")
        )

        if not _NPM_NAME_RE.match(name):
            errors.append(_err(f"npm[{i}].name", f"Invalid npm package name: {name!r}"))
        if name.startswith("-") or any(flag in name for flag in ("--", ";", "&", "|", "`")):
            errors.append(_err(f"npm[{i}].name", "Package name must not contain command flags/shell control"))
        if manager not in {"npm", "pnpm", "yarn"}:
            errors.append(_err(f"npm[{i}].package_manager", f"Unsupported package manager: {manager!r}"))
        if scope not in {"prod", "dev"}:
            errors.append(_err(f"npm[{i}].install_scope", f"Unsupported install scope: {scope!r}"))
        if version_mode == "custom" and not version:
            errors.append(_err(f"npm[{i}].version", "Custom mode requires a version constraint"))
        if version_mode == "latest" and version:
            errors.append(_err(f"npm[{i}].version", "Latest mode must not include a version constraint"))
        if version_mode not in {"latest", "custom"}:
            errors.append(_err(f"npm[{i}].version_mode", f"Unsupported version_mode: {version_mode!r}"))
        if version and any(ch in version for ch in ("\n", "\r", ";", "&", "|", "`")):
            errors.append(_err(f"npm[{i}].version", "Version constraint contains forbidden characters"))
    return errors


def _has_lockfile_copy(copy_items: list) -> bool:
    for item in copy_items:
        src = item.src if hasattr(item, "src") else item.get("src", "")
        normalized = src.replace("\\", "/").rstrip("/")
        leaf = normalized.rsplit("/", 1)[-1]
        if leaf in _LOCKFILE_NAMES:
            return True
    return False


def validate_npm_install_mode(mode: str, copy_items: list) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    normalized = str(mode or "spec").strip()
    if normalized not in _NPM_INSTALL_MODES:
        errors.append(_err("npm_install_mode", f"Unsupported npm install mode: {normalized!r}"))
        return errors
    if normalized == "lock_only" and not _has_lockfile_copy(copy_items):
        errors.append(
            _err(
                "copy_items",
                "npm_install_mode='lock_only' requires copying one lockfile: "
                "package-lock.json, pnpm-lock.yaml, or yarn.lock",
            )
        )
    return errors


def validate_apt_install_mode(
    mode: str,
    pkgs: list[str],
    constraints: dict[str, str],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    normalized = str(mode or "repo").strip()
    if normalized not in _APT_INSTALL_MODES:
        errors.append(_err("apt_install_mode", f"Unsupported apt install mode: {normalized!r}"))
        return errors
    if normalized == "pin_only":
        missing = [pkg for pkg in pkgs if pkg not in constraints]
        if missing:
            errors.append(
                _err(
                    "apt_constraints",
                    "apt_install_mode='pin_only' requires constraints for all apt packages; "
                    f"missing: {', '.join(sorted(missing))}",
                )
            )
    return errors


def validate_pip_wheelhouse(
    pip_install_mode: str,
    pip_wheelhouse_path: str,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    mode = str(pip_install_mode or "index").strip()
    path = str(pip_wheelhouse_path or "").strip()

    if mode not in _WHEELHOUSE_MODES:
        errors.append(_err("pip_install_mode", f"Unsupported pip install mode: {mode!r}"))
        return errors

    if mode == "index":
        if path:
            errors.append(_err("pip_wheelhouse_path", "pip_wheelhouse_path must be empty when pip_install_mode='index'"))
        return errors

    if not path:
        errors.append(_err("pip_wheelhouse_path", "pip_wheelhouse_path is required for wheelhouse install modes"))
        return errors
    if path.startswith("/"):
        errors.append(_err("pip_wheelhouse_path", "Absolute wheelhouse paths are not allowed"))
    if ".." in path.split("/"):
        errors.append(_err("pip_wheelhouse_path", "Path traversal (..) not allowed in pip_wheelhouse_path"))
    if any(ch in path for ch in ("\n", "\r", ";", "&", "|", "`")):
        errors.append(_err("pip_wheelhouse_path", "pip_wheelhouse_path contains forbidden characters"))
    if not _COPY_PATH_RE.match(path):
        errors.append(_err("pip_wheelhouse_path", "pip_wheelhouse_path contains disallowed characters"))
    return errors


def validate_env_entries(env: dict[str, str]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for key, value in env.items():
        if not _ENV_KEY_RE.match(key):
            errors.append(_err(
                f"env.{key}",
                "Env key must match ^[A-Z_][A-Z0-9_]{0,63}$",
            ))
        for bad_char in ("\n", "\r"):
            if bad_char in value:
                errors.append(_err(f"env.{key}", "Env values must not contain newline characters"))
                break
        if len(value) > _MAX_ENV_VALUE_LEN:
            errors.append(_err(f"env.{key}", f"Env value exceeds {_MAX_ENV_VALUE_LEN} char limit"))
    return errors


def validate_copy_paths(items: list) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for i, item in enumerate(items):
        src = item.src if hasattr(item, "src") else item.get("src", "")
        dst = item.dst if hasattr(item, "dst") else item.get("dst", "")

        if src.startswith("/"):
            errors.append(_err(f"copy_items[{i}].src", "Absolute source path not allowed"))
        if ".." in src.split("/"):
            errors.append(_err(f"copy_items[{i}].src", "Path traversal (..) not allowed in src"))
        if not _COPY_PATH_RE.match(src) and src:
            errors.append(_err(f"copy_items[{i}].src", f"src contains disallowed characters: {src!r}"))

        for bad_char in ("\n", "\r"):
            if bad_char in dst:
                errors.append(_err(f"copy_items[{i}].dst", "dst must not contain newline characters"))
                break
    return errors


def validate_entrypoint_cmd(cmd: list[str]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not cmd:
        errors.append(_err("entrypoint_cmd", "Entrypoint cmd must have at least one element"))
        return errors
    for i, token in enumerate(cmd):
        for bad_char in ("\n", "\r"):
            if bad_char in token:
                errors.append(_err(f"entrypoint_cmd[{i}]", "Token must not contain newline characters"))
                break
        if len(token) > _MAX_TOKEN_LEN:
            errors.append(_err(f"entrypoint_cmd[{i}]", f"Token exceeds {_MAX_TOKEN_LEN} char limit"))
    return errors


def validate_variant_names(names: Iterable[str]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for name in names:
        if not _VARIANT_NAME_RE.match(name):
            errors.append(_err(
                f"variants.{name}",
                "Variant name must start with a lowercase letter and contain "
                "only lowercase letters, digits, hyphens, and underscores (max 64 chars)",
            ))
        if name in _VARIANT_RESERVED_NAMES:
            errors.append(_err(f"variants.{name}", f"'{name}' is a reserved name and cannot be used as a variant key"))
    return errors


def validate_enum_field(value: str, enum_cls: type[Enum], field_name: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    normalised = value.lower()
    valid_values = [e.value for e in enum_cls]
    if normalised not in valid_values:
        errors.append(_err(field_name, f"Must be one of: {', '.join(valid_values)}; got {value!r}"))
    return errors


def validate_build_strategy_restricted(value: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if value.lower() not in _ALLOWED_BUILD_STRATEGIES:
        errors.append(_err(
            "build_strategy",
            f"Create only supports: {', '.join(sorted(_ALLOWED_BUILD_STRATEGIES))}; got {value!r}",
        ))
    return errors


def validate_build_strategy_optional(value: str | None, field_name: str = "build_strategy") -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if value is None or value == "":
        return errors
    if value.lower() not in _ALLOWED_BUILD_STRATEGIES:
        errors.append(_err(
            field_name,
            f"Create only supports: {', '.join(sorted(_ALLOWED_BUILD_STRATEGIES))}; got {value!r}",
        ))
    return errors


def validate_ports(ports: list[int]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for i, port in enumerate(ports):
        if not (1 <= port <= 65535):
            errors.append(_err(f"ports[{i}]", f"Port must be between 1 and 65535; got {port}"))
    return errors


# ---------------------------------------------------------------------------
# Aggregate runner
# ---------------------------------------------------------------------------

def run_stack_security_validation(req) -> None:
    """Run all security validators on a StackCreateRequest. Raises ValidationErrors."""
    errors: list[dict[str, str]] = []
    errors.extend(validate_spec_id(req.id))
    errors.extend(validate_build_strategy_optional(req.build_strategy))
    if req.kind != "stack_recipe":
        errors.append(_err("kind", "Must be 'stack_recipe'"))
    if not req.blocks:
        errors.append(_err("blocks", "Recipe stack requires at least one block id"))
    seen: set[str] = set()
    for i, block_id in enumerate(req.blocks):
        if not block_id or not isinstance(block_id, str):
            errors.append(_err(f"blocks[{i}]", "Block id must be a non-empty string"))
            continue
        if block_id in seen:
            errors.append(_err(f"blocks[{i}]", f"Duplicate block id: {block_id}"))
        seen.add(block_id)
        errors.extend(validate_spec_id(block_id))
    errors.extend(validate_copy_paths(req.copy_items))
    errors.extend(validate_variant_names(req.variants.keys()))

    if errors:
        raise ValidationErrors(errors)


def run_profile_security_validation(req) -> None:
    """Run all security validators on a ProfileCreateRequest. Raises ValidationErrors."""
    from stacksmith.domain.enums import Arch, ContainerRuntime

    errors: list[dict[str, str]] = []
    errors.extend(validate_spec_id(req.id))
    errors.extend(validate_enum_field(req.arch, Arch, "arch"))
    errors.extend(validate_enum_field(req.container_runtime, ContainerRuntime, "container_runtime"))
    if str(req.os).lower() != "linux":
        errors.append(_err("os", "Only linux is supported for profile os"))
    is_v2 = getattr(req, "schema_version", 1) >= 2
    if not is_v2 and not req.base_candidates:
        errors.append(_err("base_candidates", "At least one base candidate is required"))

    for i, bc in enumerate(req.base_candidates):
        if not _IMAGE_REF_RE.match(bc.name):
            errors.append(_err(
                f"base_candidates[{i}].name",
                "Base candidate name must be a valid lowercase image reference "
                "(e.g. nvcr.io/nvidia/pytorch)",
            ))
        if not bc.tags:
            errors.append(_err(f"base_candidates[{i}].tags", "Each base candidate must have at least one tag"))

    if errors:
        raise ValidationErrors(errors)


def run_block_security_validation(req) -> None:
    """Run all security validators on a BlockCreateRequest. Raises ValidationErrors."""
    errors: list[dict[str, str]] = []
    errors.extend(validate_spec_id(req.id))
    errors.extend(validate_build_strategy_optional(req.build_strategy))
    errors.extend(validate_pip_deps(req.pip))
    errors.extend(validate_pip_wheelhouse(req.pip_install_mode, req.pip_wheelhouse_path))
    errors.extend(validate_npm_deps(req.npm))
    errors.extend(validate_npm_install_mode(req.npm_install_mode, req.copy_items))
    errors.extend(validate_apt_packages(req.apt))
    errors.extend(validate_apt_constraints(req.apt, req.apt_constraints))
    errors.extend(validate_apt_install_mode(req.apt_install_mode, req.apt, req.apt_constraints))
    errors.extend(validate_env_entries(req.env))
    errors.extend(validate_copy_paths(req.copy_items))
    if req.entrypoint_cmd:
        errors.extend(validate_entrypoint_cmd(req.entrypoint_cmd))
    errors.extend(validate_variant_names(req.variants.keys()))
    errors.extend(validate_ports(req.ports))
    for idx, name in enumerate(req.incompatible_with):
        errors.extend(validate_spec_id(name, field=f"incompatible_with[{idx}]"))

    if errors:
        raise ValidationErrors(errors)
