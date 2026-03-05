"""Pip compatibility overrides for base-image-specific package version resolution.

When building overlay images, certain base images (e.g. NGC PyTorch) pin
dependencies that conflict with upstream package requirements. This module
loads override rules and applies them during requirements rendering so
builds "just work" without users debugging pip conflicts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from stacksmith.domain.models import PipDep


def _base_name(package_name: str) -> str:
    """Return the base package name without extras (e.g. 'vllm' from 'vllm[all]')."""
    return package_name.split("[")[0].strip().lower()


def load_pip_overrides(rules_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load pip compatibility override rules from the rules directory."""
    if rules_dir is None:
        from stacksmith.config import _rules_dir
        rules_dir = _rules_dir()
    path = rules_dir / "pip_compatibility_overrides.yaml"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("overrides", [])


def get_pip_install_options(base_image: str, overrides: list[dict[str, Any]] | None = None) -> str:
    """Return extra pip install options (e.g. --no-binary) for packages that must
    be built from source on certain platforms (e.g. opencc on aarch64).
    """
    if overrides is None:
        overrides = load_pip_overrides()
    base_image_lower = base_image.lower()
    options: list[str] = []
    for rule in overrides:
        when = rule.get("when") or {}
        contains = (when.get("base_image_contains") or "").strip()
        if not contains or contains.lower() not in base_image_lower:
            continue
        opts = rule.get("pip_install_options")
        if opts:
            options.append(str(opts).strip())
        no_binary = rule.get("no_binary")
        if no_binary:
            pkgs = no_binary if isinstance(no_binary, list) else [no_binary]
            options.append("--no-binary=" + ",".join(p.strip() for p in pkgs if p.strip()))
    return " ".join(options)


def apply_overrides(
    pip_deps: list[PipDep],
    base_image: str,
    overrides: list[dict[str, Any]] | None = None,
) -> list[PipDep]:
    """Apply compatibility overrides to pip deps based on base image.

    Returns a new list of PipDep with versions overridden where rules match.
    """
    if overrides is None:
        overrides = load_pip_overrides()

    base_image_lower = base_image.lower()
    result: list[PipDep] = []

    for dep in pip_deps:
        dep_base = _base_name(dep.name)
        overridden_version: str | None = None

        for rule in overrides:
            when = rule.get("when") or {}
            contains = (when.get("base_image_contains") or "").strip()
            if not contains:
                continue
            if contains.lower() not in base_image_lower:
                continue

            packages = rule.get("packages") or {}
            for pkg_key, version in packages.items():
                if _base_name(pkg_key) == dep_base:
                    overridden_version = str(version).strip()
                    break
            if overridden_version is not None:
                break

        if overridden_version is not None:
            result.append(PipDep(name=dep.name, version=overridden_version))
        else:
            result.append(dep)

    return result
