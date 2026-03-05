"""Compatibility rule catalog loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from stackwarden.config import rules_dir


class RulePredicate(BaseModel):
    arch: str | None = None
    os_family: str | None = None
    gpu_vendor: str | None = None
    gpu_family: str | None = None
    compute_capability_min: float | None = None
    compute_capability_max: float | None = None


class RuleRequirement(BaseModel):
    driver_min: float | None = None
    cuda_min: float | None = None
    cuda_max: float | None = None
    container_runtime: str | None = None


class RuleOutcome(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    fix_hint: str | None = None


class CompatibilityRule(BaseModel):
    id: str
    version: int = 1
    enabled: bool = True
    strict_hard: bool = False
    when: RulePredicate = Field(default_factory=RulePredicate)
    requires: RuleRequirement = Field(default_factory=RuleRequirement)
    outcome: RuleOutcome
    deprecated: bool = False


class CompatibilityRuleCatalog(BaseModel):
    schema_version: int = 1
    rules: list[CompatibilityRule] = Field(default_factory=list)


def _default_rules_path() -> Path:
    return rules_dir() / "compatibility_rules.yaml"


def load_rule_catalog(path: Path | None = None) -> CompatibilityRuleCatalog:
    target = path or _default_rules_path()
    if not target.exists():
        return CompatibilityRuleCatalog()
    with open(target, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return CompatibilityRuleCatalog.model_validate(raw)


def catalog_as_dict(path: Path | None = None) -> dict[str, Any]:
    """Utility for diagnostics and docs generation."""
    catalog = load_rule_catalog(path)
    return catalog.model_dump(mode="json")

