"""Stress tests: resource and environment failures.

- OOM: build fails, artifact marked FAILED, no crash
- Disk full: graceful handling (mock)
- Network failure: remote catalog sync fails, ensure continues with local data
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from stackwarden.domain.enums import ArtifactStatus
from stackwarden.domain.errors import BuildError


class TestOOMHandling:
    """OOM during build: artifact marked FAILED, no unhandled exception."""

    def test_build_error_sets_artifact_failed(self):
        """When builder raises, artifact is updated to FAILED."""
        from stackwarden.builders.plan_executor import _do_execute
        from stackwarden.catalog.store import CatalogStore
        from stackwarden.domain.models import Plan, PlanArtifact, PlanDecision

        plan = Plan(
            plan_id="x",
            profile_id="p1",
            stack_id="s1",
            decision=PlanDecision(base_image="base:latest", base_digest=None, builder="overlay"),
            steps=[],
            artifact=PlanArtifact(
                tag="local/stackwarden:test",
                fingerprint="fp1",
                labels={"stackwarden.variants": "{}", "stackwarden.schema_version": "1"},
            ),
        )
        profile = MagicMock()
        profile.id = "p1"
        stack = MagicMock()
        stack.id = "s1"
        catalog = MagicMock()
        catalog.mark_stale = MagicMock()
        catalog.get_artifact_by_fingerprint = MagicMock(return_value=None)
        catalog.insert_artifact = MagicMock()
        catalog.update_artifact = MagicMock()

        docker = MagicMock()
        builder = MagicMock()
        builder.execute.side_effect = MemoryError("Cannot allocate memory")

        with patch("stackwarden.builders.plan_executor.BUILDER_REGISTRY", {"overlay": builder}):
            with pytest.raises(BuildError):
                _do_execute(plan, profile, stack, docker, catalog, rebuild=True)

        # update_artifact should have been called with FAILED status
        calls = catalog.update_artifact.call_args_list
        failed_calls = [c for c in calls if c[0][0].status == ArtifactStatus.FAILED]
        assert len(failed_calls) >= 1


class TestNetworkFailure:
    """Remote catalog sync failure: ensure continues with local data."""

    def test_ensure_continues_when_remote_sync_fails(self):
        """ensure_internal continues when sync_remote_catalog raises."""
        from stackwarden.domain.ensure import ensure_internal
        from types import SimpleNamespace

        cfg = MagicMock()
        cfg.remote_catalog_enabled = True
        cfg.remote_catalog_auto_pull = True
        cfg.catalog_path = "/tmp/stackwarden_stress.db"
        cfg.registry = MagicMock()
        cfg.registry.allow = ["docker.io"]
        cfg.registry.deny = []

        def sync_fail(_):
            raise RuntimeError("network down")

        with patch("stackwarden.config.AppConfig.load", return_value=cfg), \
             patch("stackwarden.domain.remote_catalog.sync_remote_catalog", side_effect=sync_fail), \
             patch("stackwarden.config.load_profile") as lp, \
             patch("stackwarden.config.load_stack") as ls, \
             patch("stackwarden.config.load_block", return_value=None), \
             patch("stackwarden.resolvers.resolver.resolve") as mock_resolve, \
             patch("stackwarden.domain.registry_policy.assert_registry_allowed"), \
             patch("stackwarden.domain.ensure.DockerClient") as mock_docker_cls, \
             patch("stackwarden.domain.ensure.CatalogStore") as mock_cat_cls, \
             patch("stackwarden.builders.plan_executor.execute_plan") as mock_exec:

            from stackwarden.domain.models import (
                BaseCandidate,
                CudaSpec,
                GpuSpec,
                Profile,
                StackComponents,
                StackEntrypoint,
                StackSpec,
            )
            p = Profile.model_validate(dict(
                id="p1", display_name="P1", arch="amd64",
                cuda=CudaSpec(major=0, minor=0, variant="none"),
                gpu=GpuSpec(vendor="none", family="none"),
                base_candidates=[BaseCandidate(name="python", tags=["3.12-slim"])],
            ))
            s = StackSpec.model_validate(dict(
                id="s1", display_name="S1", task="custom", serve="custom", api="none",
                build_strategy="overlay",
                components=StackComponents(base_role="python"),
                entrypoint=StackEntrypoint(cmd=["python", "-V"]),
            ))
            lp.return_value = p
            ls.return_value = s

            plan = SimpleNamespace(
                decision=SimpleNamespace(base_image="docker.io/library/python:3.12-slim"),
            )
            mock_resolve.return_value = plan

            mock_docker = MagicMock()
            mock_docker.get_image_digest.return_value = "sha256:abc"
            mock_docker_cls.return_value = mock_docker

            rec = SimpleNamespace(tag="ok:tag", status=MagicMock(value="built"))
            mock_exec.return_value = rec

            catalog = MagicMock()
            catalog.upsert_profile = MagicMock()
            catalog.upsert_stack = MagicMock()
            mock_cat_cls.return_value = catalog

            record, _ = ensure_internal("p1", "s1")
            assert record.tag == "ok:tag"
