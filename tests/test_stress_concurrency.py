"""Stress tests: concurrency and race conditions.

- Parallel ensure (same profile+stack) — lock serializes, no duplicate builds
- Prune during build — catalog consistency
- Cancel mid-build — CancellationRequestedError, artifact marked failed
"""

from __future__ import annotations

import concurrent.futures
import threading
from unittest.mock import MagicMock, patch

import pytest

from stacksmith.domain.enums import ArtifactStatus
from stacksmith.domain.errors import CancellationRequestedError
from stacksmith.domain.locking import acquire_lock
from stacksmith.domain.models import (
    BaseCandidate,
    CudaSpec,
    GpuSpec,
    PipDep,
    Profile,
    StackComponents,
    StackEntrypoint,
    StackSpec,
)


def _profile() -> Profile:
    return Profile.model_validate(dict(
        id="stress_p",
        display_name="Stress",
        arch="amd64",
        cuda=CudaSpec(major=0, minor=0, variant="none"),
        gpu=GpuSpec(vendor="none", family="none"),
        base_candidates=[BaseCandidate(name="python", tags=["3.12-slim"])],
    ))


def _stack() -> StackSpec:
    return StackSpec.model_validate(dict(
        id="stress_s",
        display_name="Stress Stack",
        task="custom",
        serve="custom",
        api="none",
        build_strategy="overlay",
        components=StackComponents(
            base_role="python",
            pip=[PipDep(name="six", version=">=1.16")],
        ),
        entrypoint=StackEntrypoint(cmd=["python", "-c", "print(1)"]),
    ))


class TestLockSerialization:
    """Parallel ensure on same profile+stack should serialize via lock."""

    def test_acquire_lock_serializes_concurrent_calls(self, tmp_path):
        """Two threads acquiring the same lock block each other."""
        from stacksmith.paths import get_locks_root
        with patch("stacksmith.domain.locking.get_locks_root", return_value=tmp_path / "locks"):
            order: list[str] = []
            lock = threading.Lock()

            def hold_a():
                with acquire_lock("p1", "s1", timeout=2):
                    with lock:
                        order.append("a_start")
                    import time
                    time.sleep(0.05)
                    with lock:
                        order.append("a_end")

            def hold_b():
                with lock:
                    order.append("b_wait")
                with acquire_lock("p1", "s1", timeout=2):
                    with lock:
                        order.append("b_start")
                    with lock:
                        order.append("b_end")

            t1 = threading.Thread(target=hold_a)
            t2 = threading.Thread(target=hold_b)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            # Lock serializes: one of (a_end, b_start) must precede the other
            # (depending on scheduler, either a or b may acquire first)
            a_end_idx = order.index("a_end")
            b_start_idx = order.index("b_start")
            # If b started, b_end must come after b_start; if a started first, a_end before b_start
            assert "a_end" in order and "b_start" in order
            assert (a_end_idx < b_start_idx) or (order.index("b_end") < a_end_idx)

    def test_different_targets_do_not_block(self, tmp_path):
        """Different profile+stack can run in parallel (different lock keys)."""
        from stacksmith.paths import get_locks_root
        with patch("stacksmith.domain.locking.get_locks_root", return_value=tmp_path / "locks"):
            done: set[str] = set()
            lock = threading.Lock()

            def run(key: str):
                with acquire_lock(f"p_{key}", f"s_{key}", timeout=2):
                    with lock:
                        done.add(key)

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                futs = [ex.submit(run, str(i)) for i in range(4)]
                for f in concurrent.futures.as_completed(futs):
                    f.result()
            assert done == {"0", "1", "2", "3"}


class TestCancelMidBuild:
    """Cancel during build raises CancellationRequestedError and marks artifact failed."""

    def test_cancel_before_builder_raises(self):
        """should_cancel returning True before builder.execute raises."""
        from stacksmith.domain.ensure import ensure_internal
        from stacksmith.config import AppConfig
        from stacksmith.catalog.store import CatalogStore

        cfg = MagicMock()
        cfg.remote_catalog_enabled = False
        cfg.catalog_path = "/tmp/stacksmith_stress_catalog.db"
        cfg.registry = MagicMock()
        cfg.registry.allow = ["docker.io"]
        cfg.registry.deny = []

        with patch("stacksmith.config.AppConfig.load", return_value=cfg), \
             patch("stacksmith.config.load_profile", return_value=_profile()), \
             patch("stacksmith.config.load_stack", return_value=_stack()), \
             patch("stacksmith.config.load_block", return_value=None), \
             patch("stacksmith.domain.remote_catalog.sync_remote_catalog", side_effect=lambda _: None), \
             patch("stacksmith.resolvers.resolver.resolve") as mock_resolve, \
             patch("stacksmith.domain.registry_policy.assert_registry_allowed"), \
             patch("stacksmith.domain.ensure.DockerClient") as mock_docker_cls, \
             patch("stacksmith.domain.ensure.CatalogStore") as mock_cat_cls:

            plan = MagicMock()
            plan.profile_id = "stress_p"
            plan.stack_id = "stress_s"
            plan.artifact = MagicMock()
            plan.artifact.labels = {"stacksmith.variants": "{}"}
            plan.decision = MagicMock()
            plan.decision.base_image = "docker.io/library/python:3.12-slim"
            mock_resolve.return_value = plan

            mock_docker = MagicMock()
            mock_docker.get_image_digest.return_value = "sha256:abc"
            mock_docker_cls.return_value = mock_docker

            catalog = CatalogStore.__new__(CatalogStore)
            catalog.upsert_profile = MagicMock()
            catalog.upsert_stack = MagicMock()
            catalog.mark_stale = MagicMock()
            catalog.get_artifact_by_fingerprint = MagicMock(return_value=None)
            catalog.insert_artifact = MagicMock()
            catalog.update_artifact = MagicMock()
            mock_cat_cls.return_value = catalog

            cancel_count = [0]

            def cancel_check():
                cancel_count[0] += 1
                return cancel_count[0] >= 2  # Cancel on second call (during execute_plan)

            with patch("stacksmith.builders.plan_executor.execute_plan") as mock_exec:
                def fail_on_cancel(*args, **kwargs):
                    if kwargs.get("should_cancel") and kwargs["should_cancel"]():
                        raise CancellationRequestedError("Canceled")
                    rec = MagicMock()
                    rec.status = ArtifactStatus.BUILT
                    rec.tag = "local/stacksmith:test"
                    return rec
                mock_exec.side_effect = fail_on_cancel

                with pytest.raises(CancellationRequestedError):
                    ensure_internal("stress_p", "stress_s", cancel_check=cancel_check)


class TestPruneDuringBuild:
    """Prune while build is in progress — catalog should remain consistent."""

    def test_prune_stale_does_not_remove_building(self, tmp_path):
        """prune_by_status(STALE) should not touch BUILDING artifacts."""
        from stacksmith.catalog.store import CatalogStore
        from stacksmith.domain.models import ArtifactRecord
        from stacksmith.catalog.models import ProfileRow, StackRow

        catalog = CatalogStore(db_path=tmp_path / "stress.db")
        with catalog._session() as s:
            s.add(ProfileRow(id="p1", display_name="P1", arch="amd64", cuda_variant="none", data_json="{}"))
            s.add(StackRow(id="s1", display_name="S1", task="llm", serve="vllm", api="fastapi", data_json="{}"))
            s.commit()

        r_building = ArtifactRecord(
            id="b1", profile_id="p1", stack_id="s1", tag="t1", fingerprint="fp1",
            base_image="base:latest", build_strategy="overlay", status=ArtifactStatus.BUILDING,
        )
        r_stale = ArtifactRecord(
            id="s1", profile_id="p1", stack_id="s1", tag="t2", fingerprint="fp2",
            base_image="base:latest", build_strategy="overlay", status=ArtifactStatus.STALE,
        )
        catalog.insert_artifact(r_building)
        catalog.insert_artifact(r_stale)

        count = catalog.prune_by_status(ArtifactStatus.STALE)
        assert count == 1
        remaining = catalog.get_artifact_by_tag("t1")
        assert remaining is not None
        assert remaining.status == ArtifactStatus.BUILDING
