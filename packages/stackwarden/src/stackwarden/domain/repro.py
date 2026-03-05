"""Repro — generate a synthetic StackSpec with pinned dependencies from a manifest.

The synthetic stack uses a modified ID so its fingerprint is guaranteed to be
distinct from the original artifact, preventing tag collisions.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from stackwarden.domain.manifest import ResolvedManifest
from stackwarden.domain.models import NpmDep, PipDep, StackSpec


def repro_stack_from_manifest(
    manifest: ResolvedManifest,
    original_stack: StackSpec,
) -> StackSpec:
    """Create a temporary synthetic StackSpec with exact pinned versions.

    * pip deps come from ``pip_freeze`` (not the original version ranges).
    * apt packages come from ``apt_packages`` (exact ``name=version``).
    * The stack ``id`` is modified to ensure a distinct fingerprint.
    * Variant overrides from the manifest are preserved.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    repro_id = f"{original_stack.id}-repro-{ts}-{uuid.uuid4().hex[:8]}"

    pinned_pip = _parse_pip_freeze(manifest.pip_freeze)

    pinned_apt, pinned_apt_constraints = _parse_apt_packages(manifest.apt_packages)
    pinned_npm = _parse_npm_packages(manifest.npm_packages)

    data = original_stack.model_dump()
    data["id"] = repro_id
    data["display_name"] = f"{original_stack.display_name} (repro)"
    data["components"]["pip"] = [p.model_dump() for p in pinned_pip]
    data["components"]["pip_install_mode"] = manifest.pip_install_mode or "index"
    data["components"]["pip_wheelhouse_path"] = manifest.pip_wheelhouse_path or ""
    data["components"]["npm"] = [n.model_dump() for n in pinned_npm]
    data["components"]["npm_install_mode"] = manifest.npm_install_mode or "spec"
    data["components"]["apt"] = pinned_apt
    data["components"]["apt_constraints"] = pinned_apt_constraints
    data["components"]["apt_install_mode"] = "pin_only" if pinned_apt else (manifest.apt_install_mode or "repo")
    data["policy_overrides"] = {
        **(data.get("policy_overrides") or {}),
        "tuple_id": manifest.tuple_id or "",
        "tuple_status": manifest.tuple_status or "",
        "tuple_mode": manifest.tuple_mode or "",
    }

    return StackSpec.model_validate(data)


def _parse_pip_freeze(lines: list[str]) -> list[PipDep]:
    """Parse ``pip freeze`` output into ``PipDep`` objects."""
    deps: list[PipDep] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = re.match(r"^([A-Za-z0-9._-]+)==(.+)$", line)
        if match:
            deps.append(PipDep(name=match.group(1), version=f"=={match.group(2)}"))
        else:
            deps.append(PipDep(name=line))
    return deps


def _parse_npm_packages(lines: list[str]) -> list[NpmDep]:
    deps: list[NpmDep] = []
    for line in lines:
        token = line.strip()
        if not token or token.startswith("#"):
            continue
        name, version = token.rsplit("@", 1) if "@" in token[1:] else (token, "")
        deps.append(
            NpmDep(
                name=name,
                version=version,
                version_mode="custom" if version else "latest",
                package_manager="npm",
                install_scope="prod",
            )
        )
    return deps


def _parse_apt_packages(lines: list[str]) -> tuple[list[str], dict[str, str]]:
    apt_names: list[str] = []
    apt_constraints: dict[str, str] = {}
    for line in lines:
        token = line.strip()
        if not token or token.startswith("#"):
            continue
        if "=" in token:
            name, version = token.split("=", 1)
            pkg = name.strip()
            if not pkg:
                continue
            apt_names.append(pkg)
            if version.strip():
                apt_constraints[pkg] = f"={version.strip()}"
        else:
            apt_names.append(token)
    return apt_names, apt_constraints
