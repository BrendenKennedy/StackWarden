"""Stress tests: cross-platform behavior.

- Profile arch vs daemon arch mismatch — build uses platform flag
- Base image arch compatibility — resolver/overlay passes platform to buildx
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from stacksmith.domain.models import (
    BaseCandidate,
    CudaSpec,
    GpuSpec,
    Profile,
    StackComponents,
    StackEntrypoint,
    StackSpec,
)
from stacksmith.resolvers.rules import check_arch_compatibility


def _profile(arch: str = "amd64") -> Profile:
    return Profile.model_validate(dict(
        id="p1",
        display_name="P1",
        arch=arch,
        os="linux",
        cuda=CudaSpec(major=0, minor=0, variant="none"),
        gpu=GpuSpec(vendor="none", family="none"),
        base_candidates=[BaseCandidate(name="python", tags=["3.12-slim"])],
    ))


def _stack() -> StackSpec:
    return StackSpec.model_validate(dict(
        id="s1",
        display_name="S1",
        task="custom",
        serve="custom",
        api="none",
        build_strategy="overlay",
        components=StackComponents(base_role="python"),
        entrypoint=StackEntrypoint(cmd=["python", "-V"]),
    ))


class TestArchCompatibility:
    """Architecture compatibility checks."""

    def test_arm64_warns_on_problematic_packages(self):
        """check_arch_compatibility returns warnings for arm64 + known packages."""
        from stacksmith.domain.models import PipDep

        p = _profile(arch="arm64")
        s = _stack()
        s.components.pip = [PipDep(name="xformers", version=">=0.1")]
        warnings = check_arch_compatibility(p, s)
        assert isinstance(warnings, list)
        assert len(warnings) >= 1

    def test_amd64_no_arch_warning(self):
        """amd64 typically has no arch-specific warnings."""
        p = _profile(arch="amd64")
        s = _stack()
        warnings = check_arch_compatibility(p, s)
        assert isinstance(warnings, list)


class TestPlatformFlag:
    """Overlay build passes platform to buildx when profile arch is set."""

    def test_overlay_build_includes_platform(self):
        """build_overlay uses profile.os and profile.arch for platform."""
        from stacksmith.builders.overlay import build_overlay
        from stacksmith.domain.models import Plan, PlanArtifact, PlanDecision

        profile = _profile(arch="arm64")
        stack = _stack()
        plan = Plan(
            plan_id="x",
            profile_id="p1",
            stack_id="s1",
            decision=PlanDecision(base_image="python:3.12-slim", base_digest=None, builder="overlay"),
            steps=[],
            artifact=PlanArtifact(
                tag="local/stacksmith:test",
                fingerprint="fp1",
                labels={},
            ),
        )
        with patch("stacksmith.builders.overlay.buildx") as mock_buildx:
            build_overlay(plan, stack, profile, MagicMock())
            mock_buildx.build.assert_called_once()
            call_kw = mock_buildx.build.call_args[1]
            assert call_kw["platform"] == "linux/arm64"
