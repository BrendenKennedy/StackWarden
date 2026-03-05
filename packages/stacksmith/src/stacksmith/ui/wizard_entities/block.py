"""Guided block create wizard."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from rich.console import Console

from stacksmith.application.create_flows import create_block, dry_run_block
from stacksmith.contracts import ALLOWED_BUILD_STRATEGIES, SPEC_ID_PATTERN
from stacksmith.domain.block_catalog import BlockPreset, load_block_catalog
from stacksmith.web.schemas import BlockCreateRequest

from stacksmith.ui.create_wizard_engine import CreateWizardResult, WizardPrompts


PresetProfile = Literal["base", "cpu", "gpu", "dev", "prod"]


def _profile_overlay(profile: PresetProfile) -> dict[str, str]:
    if profile == "cpu":
        return {"OMP_NUM_THREADS": "8", "MKL_NUM_THREADS": "8"}
    if profile == "gpu":
        return {"NVIDIA_VISIBLE_DEVICES": "all", "CUDA_MODULE_LOADING": "LAZY"}
    if profile == "dev":
        return {"PYTHONUNBUFFERED": "1", "LOG_LEVEL": "debug"}
    if profile == "prod":
        return {"PYTHONUNBUFFERED": "1", "LOG_LEVEL": "info", "UVICORN_WORKERS": "2"}
    return {"STACKSMITH_PROFILE": "balanced"}


def _parse_requirements_text(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-") or line.startswith(("http://", "https://", "git+")):
            continue
        match = re.match(r"^([A-Za-z0-9._-]+(?:\[[\w,\-]+\])?)(.*)$", line)
        if not match:
            continue
        name = (match.group(1) or "").strip()
        version = (match.group(2) or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "version": version,
                "version_mode": "custom" if version else "latest",
            }
        )
    return out


def _parse_package_json_text(text: str) -> list[dict[str, str]]:
    data = json.loads(text)
    out: list[dict[str, str]] = []
    for scope, key in (("prod", "dependencies"), ("dev", "devDependencies")):
        entries = data.get(key) or {}
        if not isinstance(entries, dict):
            continue
        for name, version in entries.items():
            dep_name = str(name).strip()
            dep_version = str(version or "").strip()
            if not dep_name:
                continue
            out.append(
                {
                    "name": dep_name,
                    "version": dep_version,
                    "version_mode": "custom" if dep_version else "latest",
                    "package_manager": "npm",
                    "install_scope": scope,
                }
            )
    return out


def _parse_apt_text(text: str) -> tuple[list[str], dict[str, str]]:
    apt: list[str] = []
    constraints: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.match(r"^([a-z0-9][a-z0-9.+-]*)(.*)$", line)
        if not match:
            continue
        name = str(match.group(1))
        rest = str(match.group(2) or "").strip()
        apt.append(name)
        if rest:
            constraints[name] = rest
    return apt, constraints


def _pick_preset(prompts: WizardPrompts, preset_id: str | None = None) -> BlockPreset:
    catalog = load_block_catalog()
    presets = sorted(catalog.presets, key=lambda p: (p.category, p.id))
    if not presets:
        raise ValueError("Block preset catalog is empty.")
    by_id = {p.id: p for p in presets}
    if preset_id:
        chosen = by_id.get(preset_id)
        if not chosen:
            raise ValueError(f"Unknown preset id: {preset_id}")
        return chosen
    categories = sorted({p.category for p in presets})
    category = prompts.choose("Preset category", categories, default=categories[0])
    choices = [p.id for p in presets if p.category == category]
    selected = prompts.choose("Preset", choices, default=choices[0])
    return by_id[selected]


def run_block_create_wizard(
    *,
    block_id: str | None = None,
    display_name: str | None = None,
    preset_id: str | None = None,
    profile_mode: PresetProfile = "base",
    build_strategy: str | None = None,
    requirements_file: str | None = None,
    package_json_file: str | None = None,
    apt_file: str | None = None,
    non_interactive: bool = False,
    dry_run: bool = False,
    yes: bool = False,
    output: str | None = None,
    console: Console | None = None,
) -> CreateWizardResult:
    prompts = WizardPrompts(console=console, non_interactive=non_interactive)
    preset = _pick_preset(prompts, preset_id=preset_id)

    chosen_profile_mode = profile_mode
    if not non_interactive and not profile_mode:
        chosen_profile_mode = prompts.choose("Runtime mode", ["base", "cpu", "gpu", "dev", "prod"], default="base")  # type: ignore[assignment]

    env = {**preset.env, **_profile_overlay(chosen_profile_mode)}
    pip = [
        {
            "name": dep.name,
            "version": dep.version or "",
            "version_mode": "custom" if dep.version else "latest",
        }
        for dep in preset.pip
    ]
    npm: list[dict[str, str]] = []
    apt = list(preset.apt)
    apt_constraints: dict[str, str] = {}

    if requirements_file:
        text = Path(requirements_file).read_text(encoding="utf-8")
        pip.extend(_parse_requirements_text(text))
    if package_json_file:
        text = Path(package_json_file).read_text(encoding="utf-8")
        npm.extend(_parse_package_json_text(text))
    if apt_file:
        text = Path(apt_file).read_text(encoding="utf-8")
        apt_extra, apt_cons_extra = _parse_apt_text(text)
        apt.extend(apt_extra)
        apt_constraints.update(apt_cons_extra)

    resolved_id = block_id or prompts.text("Block ID", default=preset.id)
    if not re.fullmatch(SPEC_ID_PATTERN, resolved_id):
        raise ValueError("Block id must match pattern: ^[a-z][a-z0-9_\\-]{2,63}$")
    resolved_name = display_name or prompts.text("Display name", default=preset.display_name)

    strategy_value = build_strategy
    if strategy_value is None and not non_interactive:
        strategy_choice = prompts.choose(
            "Build strategy",
            ["default", *ALLOWED_BUILD_STRATEGIES],
            default="default",
        )
        strategy_value = None if strategy_choice == "default" else strategy_choice
    elif strategy_value == "":
        strategy_value = None

    payload: dict[str, Any] = {
        "schema_version": 2,
        "id": resolved_id,
        "display_name": resolved_name,
        "tags": list(dict.fromkeys(preset.tags)),
        "build_strategy": strategy_value,
        "base_role": None,
        "pip": pip,
        "pip_install_mode": "index",
        "pip_wheelhouse_path": "",
        "npm": npm,
        "npm_install_mode": "spec",
        "apt": list(dict.fromkeys(apt)),
        "apt_constraints": apt_constraints,
        "apt_install_mode": "repo",
        "env": env,
        "ports": list(dict.fromkeys(preset.ports)),
        "entrypoint_cmd": list(preset.entrypoint_cmd),
        "copy_items": [],
        "variants": {},
        "requires": dict(preset.requires),
        "conflicts": [],
        "incompatible_with": [],
        "provides": dict(preset.provides),
    }
    req = BlockCreateRequest.model_validate(payload)
    dry = dry_run_block(req)
    result = CreateWizardResult(
        entity="block",
        id=req.id,
        valid=dry.valid,
        yaml=dry.yaml,
        errors=dry.errors,
        metadata={"preset": preset.id, "profile_mode": chosen_profile_mode},
    )
    prompts.print_yaml_preview(dry.yaml)
    prompts.maybe_write_output(output, dry.yaml)
    if not dry.valid or dry_run:
        return result
    if not (yes or non_interactive) and not prompts.confirm("Create block now?", default=True):
        return result
    target = create_block(req)
    result.created = True
    result.path = str(target)
    return result
