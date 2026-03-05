"""Registry trust policy tests — allow/deny enforcement."""

from __future__ import annotations

import pytest

from stacksmith.domain.errors import RegistryPolicyError
from stacksmith.domain.registry_policy import RegistryPolicy, check_registry, _extract_registry
from stacksmith.domain.registry_policy import assert_registry_allowed


class TestExtractRegistry:
    def test_nvcr(self):
        assert _extract_registry("nvcr.io/nvidia/pytorch:24.06") == "nvcr.io"

    def test_ghcr(self):
        assert _extract_registry("ghcr.io/org/image:latest") == "ghcr.io"

    def test_docker_hub_short(self):
        assert _extract_registry("ubuntu:22.04") == "docker.io"

    def test_docker_hub_library(self):
        assert _extract_registry("library/python:3.10") == "docker.io"


class TestCheckRegistry:
    def test_empty_policy_allows_all(self):
        ok, reason = check_registry("anything:latest", RegistryPolicy())
        assert ok
        assert reason == ""

    def test_allow_list_permits(self):
        policy = RegistryPolicy(allow=["nvcr.io", "ghcr.io"])
        ok, _ = check_registry("nvcr.io/nvidia/pytorch:24.06", policy)
        assert ok

    def test_allow_list_denies_unlisted(self):
        policy = RegistryPolicy(allow=["nvcr.io"])
        ok, reason = check_registry("ghcr.io/org/image:latest", policy)
        assert not ok
        assert "not in the allow list" in reason

    def test_deny_list_blocks(self):
        policy = RegistryPolicy(deny=["docker.io/library/randomuser"])
        ok, reason = check_registry(
            "docker.io/library/randomuser/bad:latest", policy
        )
        assert not ok
        assert "denied" in reason

    def test_deny_list_allows_others(self):
        policy = RegistryPolicy(deny=["docker.io"])
        ok, _ = check_registry("nvcr.io/nvidia/pytorch:24.06", policy)
        assert ok

    def test_combined_allow_deny(self):
        policy = RegistryPolicy(allow=["nvcr.io"], deny=["docker.io"])
        ok, _ = check_registry("nvcr.io/nvidia/pytorch:24.06", policy)
        assert ok
        ok2, _ = check_registry("docker.io/library/ubuntu:22.04", policy)
        assert not ok2


class TestAssertRegistryAllowed:
    def test_allows_permitted_image(self):
        assert_registry_allowed(
            "nvcr.io/nvidia/pytorch:24.06",
            RegistryPolicy(allow=["nvcr.io"]),
        )

    def test_raises_for_denied_image(self):
        with pytest.raises(RegistryPolicyError):
            assert_registry_allowed(
                "docker.io/library/ubuntu:22.04",
                RegistryPolicy(allow=["nvcr.io"]),
            )
