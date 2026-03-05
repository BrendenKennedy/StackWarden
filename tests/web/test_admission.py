"""Tests for stackwarden.web.jobs.admission."""

from __future__ import annotations

import pytest

from stackwarden.domain.models import GpuSpec, HostDiscoveryFacts, Profile
from stackwarden.web.jobs.admission import AdmissionDecision, decide_admission


def _profile_with_memory(memory_gb: float | None) -> Profile:
    return Profile.model_validate(dict(
        id="test-profile",
        display_name="Test",
        arch="amd64",
        gpu=GpuSpec(vendor="nvidia", family="ampere"),
        host_facts=HostDiscoveryFacts(memory_gb_total=memory_gb),
    ))


class TestDecideAdmission:
    def test_allowed_when_budget_sufficient(self):
        profile = _profile_with_memory(32.0)
        result = decide_admission(profile, requested_memory_gb=4.0, reserved_memory_gb=0.0, active_builds=0)
        assert result.allowed is True
        assert result.memory_budget_gb == 30.0

    def test_rejected_when_over_budget(self):
        profile = _profile_with_memory(8.0)
        result = decide_admission(profile, requested_memory_gb=4.0, reserved_memory_gb=4.0, active_builds=1)
        assert result.allowed is False
        assert "Insufficient" in result.detail

    def test_fallback_allows_under_concurrency_limit(self):
        profile = _profile_with_memory(None)
        result = decide_admission(profile, requested_memory_gb=2.0, reserved_memory_gb=0.0, active_builds=2)
        assert result.allowed is True
        assert result.memory_budget_gb is None

    def test_fallback_rejects_at_concurrency_limit(self):
        profile = _profile_with_memory(None)
        result = decide_admission(profile, requested_memory_gb=2.0, reserved_memory_gb=0.0, active_builds=4)
        assert result.allowed is False
        assert "Too many concurrent builds" in result.detail

    def test_minimum_budget_floor(self):
        profile = _profile_with_memory(3.0)
        result = decide_admission(profile, requested_memory_gb=1.0, reserved_memory_gb=0.0, active_builds=0)
        assert result.allowed is True
        assert result.memory_budget_gb == 2.0
