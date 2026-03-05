"""Compatibility rules catalog and strict-mode behavior."""

from __future__ import annotations

import yaml

from stackwarden.domain.models import CudaSpec, GpuSpec, Profile, StackComponents, StackEntrypoint, StackSpec
from stackwarden.resolvers.compatibility import evaluate_compatibility
from stackwarden.resolvers.rule_catalog import load_rule_catalog


def _profile(runtime: str = "runc") -> Profile:
    return Profile.model_validate(
        {
            "schema_version": 2,
            "id": "p1",
            "display_name": "P1",
            "arch": "amd64",
            "os": "linux",
            "container_runtime": runtime,
            "cuda": CudaSpec(major=12, minor=4, variant="cuda12.4").model_dump(mode="json"),
            "gpu": GpuSpec(vendor="nvidia", family="ampere").model_dump(mode="json"),
            "capabilities": ["cuda"],
            "base_candidates": [{"name": "python", "tags": ["3.12-slim"]}],
            "host_facts": {"driver_version": "550.0", "confidence": {"driver_version": "detected"}},
        }
    )


def _stack() -> StackSpec:
    return StackSpec.model_validate(
        {
            "schema_version": 2,
            "kind": "stack",
            "id": "s1",
            "display_name": "S1",
            "task": "custom",
            "serve": "python_api",
            "api": "none",
            "build_strategy": "overlay",
            "components": StackComponents(base_role="python").model_dump(mode="json"),
            "entrypoint": StackEntrypoint(cmd=["python", "-V"]).model_dump(mode="json"),
        }
    )


def test_rule_catalog_schema_loads(tmp_path, monkeypatch):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "compatibility_rules.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "rules": [
                    {
                        "id": "runtime-hard",
                        "version": 1,
                        "strict_hard": True,
                        "when": {"gpu_vendor": "nvidia"},
                        "requires": {"container_runtime": "nvidia"},
                        "outcome": {"code": "RUNTIME_MISMATCH", "severity": "error", "message": "runtime"},
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    catalog = load_rule_catalog()
    assert catalog.schema_version == 1
    assert catalog.rules[0].id == "runtime-hard"


def test_strict_hard_rule_respects_strict_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STACKWARDEN_TUPLE_LAYER_MODE", "off")
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "compatibility_rules.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "rules": [
                    {
                        "id": "runtime-hard",
                        "version": 2,
                        "strict_hard": True,
                        "when": {"gpu_vendor": "nvidia"},
                        "requires": {"container_runtime": "nvidia"},
                        "outcome": {
                            "code": "RUNTIME_MISMATCH",
                            "severity": "error",
                            "message": "NVIDIA workloads require nvidia runtime",
                            "fix_hint": "switch runtime",
                        },
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    p = _profile(runtime="runc")
    s = _stack()

    non_strict = evaluate_compatibility(p, s, strict_mode=False)
    assert non_strict.compatible is True
    assert any(i.code == "RUNTIME_MISMATCH" for i in non_strict.warnings)
    assert non_strict.warnings[0].rule_id == "runtime-hard"
    assert non_strict.warnings[0].rule_version == 2

    strict = evaluate_compatibility(p, s, strict_mode=True)
    assert strict.compatible is False
    assert any(i.code == "RUNTIME_MISMATCH" for i in strict.errors)
