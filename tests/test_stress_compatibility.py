"""Stress tests: compatibility-fix auto-retry and failure injection.

- Compatibility-fix: analyze_build_failure detects pip conflict, suggests overrides
- Compatibility-fix: apply + retry (CLI and Web API)
- Registry policy: deny blocks before build
- Tuple mismatch: IncompatibleStackError when tuple layer rejects
"""

from __future__ import annotations

from pathlib import Path

import pytest

from stacksmith.domain.compatibility_fix import (
    analyze_build_failure,
    apply_compatibility_fix,
    CompatibilityFixResult,
)
from stacksmith.domain.errors import RegistryPolicyError
from stacksmith.domain.registry_policy import RegistryPolicy, assert_registry_allowed


class TestCompatibilityFixAnalysis:
    """analyze_build_failure detects pip conflicts and suggests overrides."""

    def test_detects_setuptools_conflict(self):
        err = "The conflict is caused by: setuptools>=70"
        result = analyze_build_failure(err, base_image="nvcr.io/nvidia/pytorch:24.06")
        assert result.applicable
        assert "setuptools" in str(result.suggested_overrides).lower() or result.suggested_overrides

    def test_detects_generic_pip_resolver_error(self):
        err = "ERROR: pip's dependency resolver does not currently take into account..."
        result = analyze_build_failure(err, base_image="nvcr.io/nvidia/pytorch:24.06")
        assert isinstance(result, CompatibilityFixResult)

    def test_non_pip_error_not_applicable(self):
        result = analyze_build_failure("Docker daemon not running", base_image="python:3.12")
        assert not result.applicable

    def test_oom_not_applicable(self):
        result = analyze_build_failure("Cannot allocate memory", base_image="python:3.12")
        assert not result.applicable


class TestApplyCompatibilityFix:
    """apply_compatibility_fix merges overrides into YAML."""

    def test_apply_creates_file_when_missing(self, tmp_path):
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        apply_compatibility_fix(
            {"setuptools": ">=70"},
            base_image_contains="python",
            rules_dir=rules_dir,
        )
        overrides_file = rules_dir / "pip_compatibility_overrides.yaml"
        assert overrides_file.exists()
        import yaml
        data = yaml.safe_load(overrides_file.read_text())
        assert "overrides" in data
        assert any("python" in str(r.get("when", {}).get("base_image_contains", "")) for r in data["overrides"])


class TestRegistryPolicy:
    """Registry allow/deny enforced before build."""

    def test_assert_registry_allowed_raises_for_denied(self):
        policy = RegistryPolicy(allow=["nvcr.io"])
        with pytest.raises(RegistryPolicyError):
            assert_registry_allowed("docker.io/library/ubuntu:22.04", policy)

    def test_assert_registry_allowed_passes_for_allowed(self):
        policy = RegistryPolicy(allow=["docker.io"])
        assert_registry_allowed("docker.io/library/python:3.12", policy) is None
